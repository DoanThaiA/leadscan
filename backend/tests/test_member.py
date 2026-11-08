import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.db import new_session
from app.models import Company, InvoiceRequest, MemberUser, PaymentOrder, WalletTransaction
from app.services.vietqr import build_payload, crc16_ccitt
from tests.conftest import MEMBER_PW, register, valid_form

# ------------------------------------------------------------------ tiện ích


def member_client(email="a@minhan.vn", password=MEMBER_PW) -> TestClient:
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/member/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def member(client):
    register(client)
    return member_client()


def pay_membership(m: TestClient) -> str:
    r = m.post("/api/member/orders", json={"kind": "membership"})
    assert r.status_code == 201, r.text
    code = r.json()["order"]["code"]
    assert m.post(f"/api/member/orders/{code}/simulate-paid").status_code == 200
    return code


def make_opp(admin, **over) -> int:
    body = {
        "title": "Cần 200.000 hộp carton 5 lớp/tháng",
        "summary": "Nhà máy điện tử tại Bắc Ninh tìm NCC carton",
        "industry": "Bao bì & in ấn",
        "province": "Bắc Ninh",
        "region": "Miền Bắc",
        "source_type": "App đăng mua",
        "score": 92,
        "price": 1_250_000,
        "max_buyers": 2,
        "buyer_name": "Công ty Điện tử ABC",
        "detail": "Cần giao từ tháng 12, thanh toán 30 ngày",
        "status": "published",
        "contacts": [{"full_name": "Trần Mua Hàng", "title": "Trưởng phòng mua hàng", "phone": "0912345678"}],
    }
    body.update(over)
    r = admin.post("/api/admin/opportunities", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def balance(company_id=None) -> int:
    with new_session() as db:
        c = db.get(Company, company_id) if company_id else db.scalar(select(Company))
        ledger = db.scalar(select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(WalletTransaction.company_id == c.id))
        assert c.points_balance == ledger  # số dư luôn khớp sổ cái
        return c.points_balance


# ------------------------------------------------------------------ VietQR


def test_crc16_va_payload_vietqr():
    assert crc16_ccitt("123456789") == "29B1"  # giá trị chuẩn CRC-16/CCITT-FALSE
    p = build_payload("970436", "0011001234567", 10_000_000, "LSPABCDEFGH")
    assert p.startswith("000201010212") and "0010A000000727" in p and "QRIBFTTA" in p
    assert "540810000000" in p and "0811LSPABCDEFGH" in p
    assert p[-4:] == crc16_ccitt(p[:-4])


# ------------------------------------------------------------------ đăng ký & đăng nhập


def test_dang_ky_tao_tai_khoan_dang_nhap(client):
    r = client.post("/api/registrations", json=valid_form(password="ngan", password_confirm="ngan"))
    assert r.status_code == 422 and "password" in r.json()["fields"]
    r = client.post("/api/registrations", json=valid_form(password_confirm="khac-hoan-toan"))
    assert r.status_code == 422 and "password_confirm" in r.json()["fields"]

    register(client)
    dup = client.post("/api/registrations", json=valid_form(tax_code="0109999999", email="a@minhan.vn"))
    assert dup.status_code == 409 and "email" in dup.json()["fields"]

    m = member_client()
    me = m.get("/api/member/auth/me").json()
    assert me["email"] == "a@minhan.vn" and me["company"]["points_balance"] == 0 and me["company"]["membership_active"] is False
    assert client.post("/api/member/auth/login", json={"email": "a@minhan.vn", "password": "sai-mat-khau"}).status_code == 401
    assert TestClient(m.app).get("/api/member/auth/me").status_code == 401


def test_quen_mat_khau(client, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.notify.send_password_reset", lambda cfg, email, name, token: sent.update(email=email, token=token) or True)
    register(client)
    other = client.post("/api/member/auth/forgot", json={"email": "khong-co@x.vn"})
    r = client.post("/api/member/auth/forgot", json={"email": "A@minhan.vn"})
    assert r.json()["message"] == other.json()["message"]  # không lộ email nào có tài khoản
    assert sent["email"] == "a@minhan.vn"
    assert client.post("/api/member/auth/reset", json={"token": "sai", "password": "mat-khau-moi-1"}).status_code == 400
    assert client.post("/api/member/auth/reset", json={"token": sent["token"], "password": "mat-khau-moi-1"}).status_code == 204
    assert client.post("/api/member/auth/reset", json={"token": sent["token"], "password": "mat-khau-moi-2"}).status_code == 400  # dùng 1 lần
    member_client(password="mat-khau-moi-1")


# ------------------------------------------------------------------ thanh toán


def test_phi_thanh_vien_cong_10_trieu_diem(member):
    assert member.post("/api/member/orders", json={"kind": "topup", "amount": 5_000_000}).status_code == 400  # chưa là thành viên
    r = member.post("/api/member/orders", json={"kind": "membership"}).json()
    assert r["order"]["amount"] == 10_000_000 and r["order"]["points"] == 10_000_000
    assert r["payment"]["transfer_content"] == r["order"]["code"] and r["payment"]["qr_payload"].startswith("0002010102")
    code = r["order"]["code"]
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 200
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 409  # không cộng 2 lần

    me = member.get("/api/member/auth/me").json()["company"]
    assert me["points_balance"] == 10_000_000 and me["membership_active"] and me["status"] == "active"
    assert balance() == 10_000_000
    wallet = member.get("/api/member/wallet").json()
    assert wallet["transactions"]["items"][0]["kind"] == "membership"
    assert wallet["orders"][0]["status"] == "paid"


def test_nap_them_diem_va_gioi_han(member):
    pay_membership(member)
    assert member.post("/api/member/orders", json={"kind": "topup", "amount": 500_000}).status_code == 400
    r = member.post("/api/member/orders", json={"kind": "topup", "amount": 5_000_000})
    assert r.status_code == 201
    code = r.json()["order"]["code"]
    member.post(f"/api/member/orders/{code}/simulate-paid")
    assert balance() == 15_000_000


def test_huy_don(member):
    code = member.post("/api/member/orders", json={"kind": "membership"}).json()["order"]["code"]
    assert member.post(f"/api/member/orders/{code}/cancel").status_code == 200
    assert member.get(f"/api/member/orders/{code}").json()["order"]["status"] == "cancelled"
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 409


def test_gia_lap_bi_tat_khi_dung_infocms(member, monkeypatch):
    monkeypatch.setenv("LEADSCAN_PAYMENT_PROVIDER", "infocms")
    get_settings.cache_clear()
    code = member.post("/api/member/orders", json={"kind": "membership"}).json()["order"]["code"]
    assert member.post(f"/api/member/orders/{code}/simulate-paid").status_code == 404


def _signed(body: dict, secret="bi-mat-webhook"):
    raw = json.dumps(body).encode()
    return raw, {"Content-Type": "application/json", "X-Signature": hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()}


def test_webhook_infocms(member, client, monkeypatch):
    monkeypatch.setenv("LEADSCAN_PAYMENT_PROVIDER", "infocms")
    monkeypatch.setenv("LEADSCAN_INFOCMS_WEBHOOK_SECRET", "bi-mat-webhook")
    get_settings.cache_clear()
    code = member.post("/api/member/orders", json={"kind": "membership"}).json()["order"]["code"]
    url = "/api/payments/infocms/webhook"

    raw, h = _signed({"transactionId": "FT001", "amount": 10_000_000, "content": f"CT {code} thanh toan"})
    assert client.post(url, content=raw, headers={**h, "X-Signature": "sai"}).status_code == 401

    # thiếu tiền → không cộng điểm, ghi chú lại để admin xử lý
    raw2, h2 = _signed({"transactionId": "FT000", "amount": 9_000_000, "content": code})
    assert client.post(url, content=raw2, headers=h2).json()["ok"]
    assert member.get(f"/api/member/orders/{code}").json()["order"]["status"] == "pending"

    # nội dung bị ngân hàng đổi chữ thường / chèn dấu cách vẫn nhận ra mã đơn
    raw, h = _signed({"data": {"transactionId": "FT001", "amount": 10_000_000, "description": f"chuyen tien {code.lower()}"}})
    assert client.post(url, content=raw, headers=h).json() == {"ok": True}
    assert client.post(url, content=raw, headers=h).json()["duplicate"] is True  # gửi lại không cộng 2 lần
    assert balance() == 10_000_000
    with new_session() as db:
        o = db.scalar(select(PaymentOrder).where(PaymentOrder.code == code))
        assert o.status == "paid" and o.provider_txn_id == "FT001"


# ------------------------------------------------------------------ kho cơ hội & mua phiếu


def test_kho_co_hoi_an_thong_tin_truoc_khi_mua(admin, member):
    oid = make_opp(admin)
    make_opp(admin, title="Bản nháp chưa bán", status="draft")
    items = member.get("/api/member/opportunities").json()["items"]
    assert [i["id"] for i in items] == [oid]
    item = items[0]
    assert item["contact_count"] == 1 and "contacts" not in item and "buyer_name" not in item and "detail" not in item
    d = member.get(f"/api/member/opportunities/{oid}").json()
    assert d["purchase"] is None and "contacts" not in d["opportunity"]


def test_mua_phieu(admin, member, client):
    oid = make_opp(admin, max_buyers=2)
    assert member.post(f"/api/member/opportunities/{oid}/purchase").status_code == 402  # chưa đóng phí thành viên
    pay_membership(member)

    r = member.post(f"/api/member/opportunities/{oid}/purchase")
    assert r.status_code == 200 and r.json()["points_balance"] == 8_750_000
    assert balance() == 8_750_000
    assert member.post(f"/api/member/opportunities/{oid}/purchase").status_code == 409  # không mua 2 lần

    d = member.get(f"/api/member/opportunities/{oid}").json()
    assert d["opportunity"]["buyer_name"] == "Công ty Điện tử ABC"
    assert d["opportunity"]["contacts"][0]["phone"] == "0912345678"
    assert member.get("/api/member/purchases").json()["total"] == 1
    assert member.get("/api/member/opportunities", params={"only": "purchased"}).json()["items"][0]["purchased"] is True

    # khách thứ 2 mua lượt cuối, khách thứ 3 hết lượt
    register(client, tax_code="0100000002")
    m2 = member_client("lienhe0100000002@minhan.vn")
    pay_membership(m2)
    assert m2.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    register(client, tax_code="0100000003")
    m3 = member_client("lienhe0100000003@minhan.vn")
    pay_membership(m3)
    assert m3.post(f"/api/member/opportunities/{oid}/purchase").status_code == 409
    assert m3.get("/api/member/opportunities", params={"only": "available"}).json()["total"] == 0


def test_khong_du_diem(admin, member):
    oid = make_opp(admin, price=20_000_000)
    pay_membership(member)
    r = member.post(f"/api/member/opportunities/{oid}/purchase")
    assert r.status_code == 402 and "Số dư không đủ" in r.json()["detail"]
    assert balance() == 10_000_000


def test_loc_va_sap_xep(admin, member):
    make_opp(admin, title="A rẻ", price=29_000, score=70, region="Miền Nam", industry="Logistics & vận tải")
    make_opp(admin, title="B đắt", price=5_000_000, score=95)
    get = lambda **p: [i["title"] for i in member.get("/api/member/opportunities", params=p).json()["items"]]  # noqa: E731
    assert get(sort="price_asc") == ["A rẻ", "B đắt"]
    assert get(sort="score") == ["B đắt", "A rẻ"]
    assert get(region="Miền Nam") == ["A rẻ"]
    assert get(min_score=90) == ["B đắt"]
    assert get(q="đắt") == ["B đắt"]
    facets = member.get("/api/member/opportunities").json()["facets"]
    assert "Logistics & vận tải" in facets["industries"]


def test_yeu_cau_enrich(admin, member):
    oid = make_opp(admin)
    pay_membership(member)
    member.post(f"/api/member/opportunities/{oid}/purchase")
    pid = member.get("/api/member/purchases").json()["items"][0]["id"]
    assert member.post(f"/api/member/purchases/{pid}/enrich", json={"note": "Cần thêm số giám đốc nhà máy"}).status_code == 201
    assert member.post(f"/api/member/purchases/{pid}/enrich", json={"note": "Lần 2"}).status_code == 409
    reqs = admin.get("/api/admin/enrich-requests", params={"status": "open"}).json()["items"]
    assert len(reqs) == 1 and reqs[0]["company"]["name"]
    assert admin.patch(f"/api/admin/enrich-requests/{reqs[0]['id']}", json={"status": "done", "reply": "Đã bổ sung đầu mối 2"}).status_code == 200
    d = member.get(f"/api/member/opportunities/{oid}").json()
    assert d["purchase"]["enrich_requests"][0]["reply"] == "Đã bổ sung đầu mối 2"


# ------------------------------------------------------------------ hoá đơn


def test_yeu_cau_xuat_hoa_don_gui_email_ke_toan(member, monkeypatch):
    sent = []
    monkeypatch.setattr("app.services.notify.send_mail", lambda cfg, subject, body, to=None: sent.append((to, subject, body)) or True)
    code = member.post("/api/member/orders", json={"kind": "membership"}).json()["order"]["code"]
    inv = {"company_name": "Công ty TNHH Bao Bì Minh An", "tax_code": "0101234567", "address": "KCN Quế Võ, Bắc Ninh", "receive_email": "ketoan@minhan.vn"}
    assert member.post(f"/api/member/orders/{code}/invoice", json=inv).status_code == 400  # chưa thanh toán
    member.post(f"/api/member/orders/{code}/simulate-paid")
    bad = member.post(f"/api/member/orders/{code}/invoice", json={**inv, "tax_code": "12", "receive_email": "sai"})
    assert bad.status_code == 422 and {"tax_code", "receive_email"} <= set(bad.json()["fields"])
    assert member.post(f"/api/member/orders/{code}/invoice", json=inv).status_code == 201
    assert member.post(f"/api/member/orders/{code}/invoice", json=inv).status_code == 409

    to, subject, body = sent[-1]
    assert to == "vylyy9999@gmail.com" and code in subject
    assert "0101234567" in body and "ketoan@minhan.vn" in body and "10.000.000đ" in body
    with new_session() as db:
        assert db.scalar(select(InvoiceRequest)).email_sent_at is not None
    assert member.get("/api/member/wallet").json()["orders"][0]["invoice"]["status"] == "pending"


# ------------------------------------------------------------------ admin


def test_admin_xac_nhan_tay_va_dieu_chinh_diem(admin, member, client, staff):
    code = member.post("/api/member/orders", json={"kind": "membership"}).json()["order"]["code"]
    orders = admin.get("/api/admin/orders", params={"status": "pending"}).json()["items"]
    oid = orders[0]["id"]
    assert orders[0]["code"] == code
    assert staff.post(f"/api/admin/orders/{oid}/confirm", json={"note": "Đã đối soát"}).status_code == 403  # chỉ admin
    r = admin.post(f"/api/admin/orders/{oid}/confirm", json={"note": "Đã đối soát sao kê VCB"})
    assert r.status_code == 200 and r.json()["status"] == "paid" and r.json()["confirmed_by"] == "Quản Trị"
    assert balance() == 10_000_000

    with new_session() as db:
        cid = db.scalar(select(Company.id))
    assert admin.post(f"/api/admin/companies/{cid}/wallet/adjust", json={"amount": -20_000_000, "note": "Thử trừ quá"}).status_code == 400
    assert admin.post(f"/api/admin/companies/{cid}/wallet/adjust", json={"amount": 500_000, "note": "Tặng khuyến mãi"}).status_code == 200
    acc = admin.get(f"/api/admin/companies/{cid}/account").json()
    assert acc["points_balance"] == 10_500_000 and acc["transactions"][0]["actor"]["full_name"] == "Quản Trị"
    assert acc["members"][0]["email"] == "a@minhan.vn"


def test_admin_hoa_don(admin, member):
    code = pay_membership(member)
    member.post(f"/api/member/orders/{code}/invoice", json={"company_name": "Minh An", "tax_code": "0101234567", "address": "Bắc Ninh", "receive_email": "kt@minhan.vn"})
    inv = admin.get("/api/admin/invoices", params={"status": "pending"}).json()["items"][0]
    assert inv["order"]["code"] == code
    assert admin.patch(f"/api/admin/invoices/{inv['id']}", json={"status": "issued"}).status_code == 400  # thiếu số HĐ
    r = admin.patch(f"/api/admin/invoices/{inv['id']}", json={"status": "issued", "invoice_number": "0000123"})
    assert r.json()["status"] == "issued" and r.json()["issued_at"]
    assert member.get("/api/member/wallet").json()["orders"][0]["invoice"]["invoice_number"] == "0000123"


def test_admin_quan_ly_co_hoi(admin, member):
    oid = make_opp(admin, status="draft")
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    assert o["code"].startswith("CH-") and o["published_at"] is None and o["contacts"][0]["full_name"] == "Trần Mua Hàng"
    body = {**{k: o[k] for k in ("title", "summary", "industry", "province", "region", "source_type", "price", "max_buyers", "buyer_name", "detail")}, "status": "published", "contacts": []}
    r = admin.put(f"/api/admin/opportunities/{oid}", json=body)
    assert r.json()["status"] == "published" and r.json()["published_at"] and r.json()["contacts"] == []
    assert admin.get("/api/admin/opportunities").json()["counts"] == {"published": 1}

    pay_membership(member)
    member.post(f"/api/member/opportunities/{oid}/purchase")
    assert admin.delete(f"/api/admin/opportunities/{oid}").status_code == 400  # đã có người mua
    assert admin.put(f"/api/admin/opportunities/{oid}", json={**body, "max_buyers": 0}).status_code == 422
    detail = admin.get(f"/api/admin/opportunities/{oid}").json()
    assert detail["purchases"][0]["company"]["name"] == "Công ty TNHH Bao Bì Minh An"
    stats = admin.get("/api/admin/commerce-stats").json()
    assert stats["revenue_30d"] == 10_000_000 and stats["tickets_sold_30d"] == 1


def test_admin_tao_va_khoa_tai_khoan_thanh_vien(admin, client):
    cid = register(client)
    r = admin.post(f"/api/admin/companies/{cid}/members", json={"email": "sep@minhan.vn", "full_name": "Sếp", "password": "mat-khau-123"})
    assert r.status_code == 201
    m = member_client("sep@minhan.vn", "mat-khau-123")
    assert admin.patch(f"/api/admin/members/{r.json()['id']}", json={"is_active": False}).status_code == 200
    assert m.get("/api/member/auth/me").status_code == 401
    # khách hàng bị tạm khoá thì không đăng nhập cổng thành viên được
    admin.patch(f"/api/admin/companies/{cid}", json={"status": "suspended"})
    assert TestClient(m.app).post("/api/member/auth/login", json={"email": "a@minhan.vn", "password": MEMBER_PW}).status_code == 403
    with new_session() as db:
        assert db.scalar(select(func.count()).select_from(MemberUser)) == 2


def test_them_vao_kho_cua_toi(admin, member):
    a = make_opp(admin)
    draft = make_opp(admin, status="draft")
    assert member.post(f"/api/member/saved/{a}").status_code == 201
    assert member.post(f"/api/member/saved/{a}").status_code == 201  # lưu lại không nhân đôi
    assert member.post(f"/api/member/saved/{draft}").status_code == 404
    saved = member.get("/api/member/saved").json()
    assert saved["total"] == 1 and saved["items"][0]["saved"] is True and saved["items"][0]["saved_at"]
    assert "buyer_name" not in saved["items"][0]  # chưa mua → vẫn ẩn thông tin
    assert member.get(f"/api/member/opportunities/{a}").json()["opportunity"]["saved"] is True
    assert member.get("/api/member/dashboard").json()["saved_count"] == 1
    assert member.delete(f"/api/member/saved/{a}").status_code == 204
    assert member.get("/api/member/saved").json()["total"] == 0


def test_gui_yeu_cau_tim_co_hoi_bao_admin(member, admin, monkeypatch):
    from sqlalchemy import select

    from app.db import new_session
    from app.models import Activity, SearchRequest
    from app.services import notify

    sent = []
    monkeypatch.setattr(notify, "send_mail", lambda cfg, subject, body, to=None: sent.append((subject, body)) or True)

    m = member.get("/api/member/match").json()
    assert "Quốc tế" in m["options"]["regions"] and "Bao bì & in ấn" in m["criteria"]["industries"]  # ngành lúc đăng ký

    assert member.post("/api/member/search-requests", json={"note": "ngắn"}).status_code == 422
    body = {
        "industries": ["Bao bì & in ấn"], "regions": ["Quốc tế", "Hà Nội"], "sizes": ["200+ nhân sự", "bừa"],
        "sources": ["Dự án & gói thầu"], "min_score": 70,
        "note": "Cần tìm nhà nhập khẩu bao PP dệt tại châu Phi, đơn hàng từ 1 container/tháng.",
    }
    r = member.post("/api/member/search-requests", json=body)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "open" and out["criteria"]["sizes"] == ["200+ nhân sự"]

    # email báo admin có tiêu chí + mô tả
    (subject, mail) = sent[-1]
    assert f"#{out['id']}" in subject and "Quốc tế, Hà Nội" in mail and "châu Phi" in mail and "≥ 70" in mail
    with new_session() as db:
        req = db.get(SearchRequest, out["id"])
        assert req.email_sent_at is not None
        assert db.scalar(select(Activity).where(Activity.content.like("%gửi yêu cầu tìm cơ hội%")))
    # tiêu chí được nhớ để điền sẵn lần sau
    assert member.get("/api/member/match").json()["criteria"]["regions"] == ["Quốc tế", "Hà Nội"]
    assert member.get("/api/member/search-requests").json()["items"][0]["id"] == out["id"]

    # admin xem, trả lời
    items = admin.get("/api/admin/search-requests?status=open").json()["items"]
    assert items[0]["id"] == out["id"] and items[0]["member"]["email"] and items[0]["email_sent_at"]
    r = admin.patch(f"/api/admin/search-requests/{out['id']}", json={"status": "done", "reply": "Đã thêm 3 cơ hội vào kho."})
    assert r.status_code == 200 and r.json()["resolved_at"]
    mine = member.get("/api/member/search-requests").json()["items"][0]
    assert mine["status"] == "done" and mine["reply"] == "Đã thêm 3 cơ hội vào kho."
    assert admin.get("/api/admin/commerce-stats").json()["open_search"] == 0
    assert admin.post(f"/api/admin/search-requests/{out['id']}/resend-email").status_code == 200


def test_gioi_han_so_yeu_cau_tim_co_hoi_moi_ngay(member):
    for i in range(10):
        assert member.post("/api/member/search-requests", json={"note": f"Yêu cầu số {i} để thử giới hạn"}).status_code == 201
    assert member.post("/api/member/search-requests", json={"note": "Yêu cầu thứ mười một"}).status_code == 429

