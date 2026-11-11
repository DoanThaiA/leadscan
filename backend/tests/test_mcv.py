"""Cổng thanh toán MCV: ký request, webhook (chữ ký, timestamp, chống trùng, test_mode, số tiền), tra trạng thái.

MCV được giả lập bằng app.mcv_fake.FakeMcv gắn vào httpx (không gọi mạng).
"""

import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.db import new_session
from app.mcv_fake import FakeMcv
from app.models import Company, McvPayment, PaymentOrder, WalletTransaction
from app.services import mcv, mcv_payments
from app.services.mcv import McvClient, sign
from tests.conftest import MEMBER_PW, register

KEY, SECRET = "mcvpk_test_abc123", "mcvsk_bimat_456"
FEE = 10_000_000  # conftest cố định phí thành viên 10tr khi test
HOOK = "/api/mcv/webhook"


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("LEADSCAN_PAYMENT_PROVIDER", "mcv")
    monkeypatch.setenv("MCV_API_KEY", KEY)
    monkeypatch.setenv("MCV_SECRET", SECRET)
    monkeypatch.setenv("MCV_BASE_URL", "https://api.mcv.test")
    monkeypatch.setenv("LEADSCAN_MCV_ALLOW_TEST_MODE", "true")  # mặc định: môi trường chạy thử
    monkeypatch.setenv("LEADSCAN_MCV_RETURN_URL", "https://leadscan.net/thanh-vien/nap-tien/ket-qua")
    get_settings.cache_clear()
    f = FakeMcv(KEY, SECRET, base_url="https://pay.mcv.test")
    monkeypatch.setattr(mcv, "TRANSPORT", httpx.MockTransport(f.handle))
    return f


@pytest.fixture
def member(client, fake):
    register(client)
    from app.main import app

    c = TestClient(app)
    assert c.post("/api/member/auth/login", json={"email": "a@minhan.vn", "password": MEMBER_PW}).status_code == 200
    return c


def live_env(monkeypatch):
    """Môi trường thật: không nhận test_mode."""
    monkeypatch.setenv("LEADSCAN_MCV_ALLOW_TEST_MODE", "false")
    get_settings.cache_clear()


def new_order(m: TestClient) -> tuple[str, dict]:
    r = m.post("/api/member/orders", json={"kind": "membership"})
    assert r.status_code == 201, r.text
    return r.json()["order"]["code"], r.json()["payment"]


def balance() -> int:
    with new_session() as db:
        return db.scalar(select(Company.points_balance))


def order_status(code: str) -> str:
    with new_session() as db:
        return db.scalar(select(PaymentOrder.status).where(PaymentOrder.code == code))


def wallet_rows() -> int:
    with new_session() as db:
        return db.scalar(select(func.count()).select_from(WalletTransaction))


def deliver(client: TestClient, hook: tuple[dict, bytes]):
    headers, raw = hook
    return client.post(HOOK, content=raw, headers=headers)


# ------------------------------------------------------------------ ký request


def test_chu_ky_request_dung_cong_thuc():
    # HMAC-SHA256(key=Secret, message=timestamp + "." + raw_body), hex chữ thường
    raw = b'{"order_id":"LSP1","amount":10000}'
    expected = hmac.new(SECRET.encode(), b"1700000000." + raw, hashlib.sha256).hexdigest()
    assert sign(SECRET, 1700000000, raw) == expected == expected.lower()
    assert sign(SECRET, "1700000000", b"") == hmac.new(SECRET.encode(), b"1700000000.", hashlib.sha256).hexdigest()  # GET: body rỗng


def test_request_gui_dung_chuoi_da_ky(member, fake):
    code, pay = new_order(member)
    req = fake.requests[-1]
    assert req.method == "POST" and req.url.path == "/v1/payments"
    raw, h = req.content, req.headers
    assert h["x-mcv-key"] == KEY and h["content-type"] == "application/json"
    assert abs(int(h["x-mcv-timestamp"]) - time.time()) < 5
    # chữ ký tính trên ĐÚNG chuỗi byte đã gửi (không encode lại), tiếng Việt giữ nguyên UTF-8
    assert h["x-mcv-signature"] == sign(SECRET, h["x-mcv-timestamp"], raw)
    body = json.loads(raw)
    assert body["order_id"] == code and body["amount"] == FEE and "Phí thành viên" in raw.decode("utf-8")
    assert body["return_url"] == "https://leadscan.net/thanh-vien/nap-tien/ket-qua"
    assert 5 <= body["expires_in_minutes"] <= 60

    # tra trạng thái: GET ký với body rỗng
    with new_session() as db:
        mp = db.scalar(select(McvPayment))
    data = McvClient(get_settings()).get_payment(mp.payment_code)
    g = fake.requests[-1]
    assert g.method == "GET" and g.content == b"" and g.headers["x-mcv-signature"] == sign(SECRET, g.headers["x-mcv-timestamp"], b"")
    assert data["payment_code"] == pay["payment_code"]


def test_tao_don_tra_ve_qr_mcv(member):
    code, pay = new_order(member)
    assert pay["provider"] == "mcv" and pay["payment_code"] and pay["mcv_status"] == "pending"
    assert pay["test_mode"] is True and pay["qr_payload"] is None  # khoá test: không có QR thật
    assert pay["checkout_url"].startswith("https://pay.mcv.test/checkout/")
    assert pay["account_name"] and pay["transfer_content"] and pay["expires_at"].endswith("Z")
    assert pay["can_simulate"] is True
    with new_session() as db:
        mp = db.scalar(select(McvPayment))
        assert mp.mcv_order_id == code and mp.order.code == code and mp.processed_at is None


def test_mcv_loi_van_giu_don_va_tao_lai_duoc(member, fake, monkeypatch):
    fake.api_key = "mcvpk_test_khac"  # MCV từ chối khoá → 401
    code, pay = new_order(member)
    assert pay["payment_code"] is None and "Chưa tạo được mã thanh toán" in pay["error"]
    assert order_status(code) == "pending"
    fake.api_key = KEY
    r = member.post(f"/api/member/orders/{code}/mcv")
    assert r.status_code == 200, r.text
    assert r.json()["payment"]["payment_code"]


# ------------------------------------------------------------------ webhook


def test_webhook_hop_le_cong_diem(member, client, fake):
    code, pay = new_order(member)
    fake.mark_paid(pay["payment_code"])
    r = deliver(client, fake.webhooks[-1])
    assert r.status_code == 200 and r.json()["result"] == "credited"
    assert order_status(code) == "paid" and balance() == FEE
    o = member.get(f"/api/member/orders/{code}").json()
    assert o["order"]["status"] == "paid" and o["me"]["company"]["membership_active"] is True


def test_webhook_sai_1_ky_tu_bi_401(member, client, fake):
    code, pay = new_order(member)
    fake.mark_paid(pay["payment_code"])
    headers, raw = fake.webhooks[-1]
    sig = headers["X-MCV-Signature"]
    bad_sig = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    assert client.post(HOOK, content=raw, headers={**headers, "X-MCV-Signature": bad_sig}).status_code == 401
    # sửa 1 byte trong body (vd tăng số tiền) mà giữ chữ ký cũ
    tampered = raw.replace(b'"status":"paid"', b'"status":"paie"')
    assert tampered != raw
    assert client.post(HOOK, content=tampered, headers=headers).status_code == 401
    # thiếu chữ ký
    assert client.post(HOOK, content=raw, headers={k: v for k, v in headers.items() if k != "X-MCV-Signature"}).status_code == 401
    assert order_status(code) == "pending" and balance() == 0


def test_webhook_timestamp_cu_bi_bo(member, client, fake):
    code, pay = new_order(member)
    fake.mark_paid(pay["payment_code"], send_webhook=False)
    old = fake.webhook_request(pay["payment_code"], timestamp=int(time.time()) - 301)  # ký đúng nhưng lệch > 5 phút
    assert deliver(client, old).status_code == 401
    future = fake.webhook_request(pay["payment_code"], timestamp=int(time.time()) + 301)
    assert deliver(client, future).status_code == 401
    assert order_status(code) == "pending" and balance() == 0
    # MCV gửi lại (ký timestamp mới) → nhận
    assert deliver(client, fake.webhook_request(pay["payment_code"])).json()["result"] == "credited"


def test_webhook_gui_2_lan_chi_cong_1_lan(member, client, fake, monkeypatch):
    code, pay = new_order(member)
    fake.mark_paid(pay["payment_code"])
    hook = fake.webhooks[-1]
    assert deliver(client, hook).json()["result"] == "credited"
    assert deliver(client, hook).json()["result"] == "duplicate"  # MCV gửi lại
    assert deliver(client, fake.webhook_request(pay["payment_code"])).json()["result"] == "duplicate"  # admin bấm gửi lại (event mới)
    # tra trạng thái (paid) sau webhook cũng không cộng lần nữa
    monkeypatch.setattr(mcv_payments, "POLL_SECONDS", 0)
    member.get(f"/api/member/orders/{code}")
    assert balance() == FEE and wallet_rows() == 1
    with new_session() as db:
        mp = db.scalar(select(McvPayment))
        assert mp.processed_at is not None and mp.result == "credited"


def test_moi_truong_that_tu_choi_test_mode(member, client, fake, monkeypatch):
    code, pay = new_order(member)
    live_env(monkeypatch)
    fake.mark_paid(pay["payment_code"])
    r = deliver(client, fake.webhooks[-1])
    assert r.status_code == 200 and r.json()["result"] == "ignored: test_mode"  # 200: không để MCV gửi lại mãi
    monkeypatch.setattr(mcv_payments, "POLL_SECONDS", 0)
    assert member.get(f"/api/member/orders/{code}").json()["payment"]["can_simulate"] is False  # tra trạng thái cũng không mở
    assert order_status(code) == "pending" and balance() == 0
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 404  # không có giả lập trên môi trường thật


def test_sai_so_tien_khong_mo_dich_vu(member, client, fake):
    code, pay = new_order(member)
    fake.payments[pay["payment_code"]]["amount"] = 10_000  # MCV báo số tiền khác giá đơn
    fake.mark_paid(pay["payment_code"])
    r = deliver(client, fake.webhooks[-1])
    assert r.status_code == 200 and r.json()["result"] == "ignored: amount_mismatch"
    assert order_status(code) == "pending" and balance() == 0
    with new_session() as db:
        mp = db.scalar(select(McvPayment))
        assert mp.result == "amount_mismatch" and mp.processed_at is not None
        assert "không khớp" in db.scalar(select(PaymentOrder.note))
    assert deliver(client, fake.webhook_request(pay["payment_code"])).json()["result"] == "duplicate"


def test_chuyen_thieu_tien_khong_co_webhook(member, fake, monkeypatch):
    code, pay = new_order(member)
    fake.mark_paid(pay["payment_code"], paid_amount=FEE - 1)
    assert fake.webhooks == []
    monkeypatch.setattr(mcv_payments, "POLL_SECONDS", 0)
    p = member.get(f"/api/member/orders/{code}").json()["payment"]
    assert p["mcv_status"] == "needs_attention" and order_status(code) == "pending" and balance() == 0


def test_webhook_su_kien_khac_va_don_khong_ton_tai(member, client, fake):
    code, pay = new_order(member)
    fake.mark_paid(pay["payment_code"], send_webhook=False)
    headers, raw = fake.webhook_request(pay["payment_code"])
    assert client.post(HOOK, content=raw, headers={**headers, "X-MCV-Event": "payment.refunded"}).json()["ignored"]
    body = json.loads(raw)
    body["data"]["order_id"] = "LSPKHONGCO1"
    raw2 = json.dumps(body).encode()
    ts = str(int(time.time()))
    h2 = {**headers, "X-MCV-Timestamp": ts, "X-MCV-Signature": sign(SECRET, ts, raw2)}
    assert client.post(HOOK, content=raw2, headers=h2).json()["result"] == "ignored: không có đơn"
    assert balance() == 0


# ------------------------------------------------------------------ tra trạng thái, hết hạn, giả lập


def test_poll_trang_thai_mo_dich_vu_khi_chua_co_webhook(member, fake, monkeypatch):
    code, pay = new_order(member)
    fake.mark_paid(pay["payment_code"], send_webhook=False)  # webhook chưa tới
    assert member.get(f"/api/member/orders/{code}").json()["order"]["status"] == "pending"  # vừa tra < 5 giây → chưa gọi lại
    monkeypatch.setattr(mcv_payments, "POLL_SECONDS", 0)
    r = member.get(f"/api/member/orders/{code}").json()
    assert r["order"]["status"] == "paid" and r["me"]["company"]["points_balance"] == FEE


def test_qr_het_han_tao_ma_moi_qr_cu_van_nhan(member, client, fake, monkeypatch):
    monkeypatch.setattr(mcv_payments, "POLL_SECONDS", 0)
    code, pay = new_order(member)
    old = pay["payment_code"]
    fake.expire(old)
    p = member.get(f"/api/member/orders/{code}").json()
    assert p["payment"]["mcv_status"] == "expired" and p["order"]["status"] == "pending"  # đơn không bị huỷ
    r = member.post(f"/api/member/orders/{code}/mcv")
    new = r.json()["payment"]["payment_code"]
    assert r.status_code == 200 and new != old
    # khách vẫn chuyển theo QR cũ → vẫn mở dịch vụ
    fake.mark_paid(old)
    assert deliver(client, fake.webhooks[-1]).json()["result"] == "credited"
    # rồi lại chuyển theo QR mới → không cộng thêm, ghi lại để đối soát/hoàn tiền
    fake.mark_paid(new)
    assert deliver(client, fake.webhooks[-1]).json()["result"] == "ignored: order_already_paid"
    assert balance() == FEE and wallet_rows() == 1
    with new_session() as db:
        assert db.scalar(select(func.count()).select_from(McvPayment).where(McvPayment.order_id.is_not(None))) == 2


def test_trang_ket_qua_tra_tu_server(member, fake):
    code, pay = new_order(member)
    pc = pay["payment_code"]
    # status=paid trên URL không có giá trị: server tra MCV → vẫn pending
    r = member.get(f"/api/member/orders/{code}", params={"payment_code": pc})
    assert r.json()["order"]["status"] == "pending"
    fake.mark_paid(pc, send_webhook=False)
    with new_session() as db:  # lần tra trước đã quá 5 giây
        db.query(McvPayment).update({McvPayment.checked_at: None})
        db.commit()
    r = member.get(f"/api/member/orders/{code}", params={"payment_code": pc})
    assert r.json()["order"]["status"] == "paid" and balance() == FEE
    assert member.get(f"/api/member/orders/{code}", params={"payment_code": "x y"}).status_code == 422


def test_ket_qua_payment_code_cua_don_khac_bi_bo_qua(member, fake):
    code1, pay1 = new_order(member)
    code2, _ = new_order(member)
    fake.mark_paid(pay1["payment_code"], send_webhook=False)
    r = member.get(f"/api/member/orders/{code2}", params={"payment_code": pay1["payment_code"]}).json()
    assert r["order"]["status"] == "pending" and r["payment"]["payment_code"] != pay1["payment_code"]
    assert order_status(code1) == "pending"


def test_gia_lap_da_tra_chi_o_moi_truong_thu(member, client, fake):
    code, pay = new_order(member)
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 200
    assert order_status(code) == "paid" and balance() == FEE  # ghi nhận qua tra trạng thái ngay
    assert deliver(client, fake.webhooks[-1]).json()["result"] == "duplicate"  # webhook tới sau không cộng lần 2
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 409


def test_gia_lap_bi_tat_khi_dung_khoa_that(member, fake, monkeypatch):
    monkeypatch.setenv("MCV_API_KEY", "mcvpk_live_abc")
    get_settings.cache_clear()
    fake.api_key = "mcvpk_live_abc"
    code, pay = new_order(member)
    assert pay["test_mode"] is False and pay["qr_payload"].startswith("000201")  # khoá thật có QR
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 404
