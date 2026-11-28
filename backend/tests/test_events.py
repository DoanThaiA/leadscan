"""Sự kiện: admin tạo trang sự kiện, khách đăng ký → QR thanh toán → nộp ảnh chuyển khoản, OCR đối soát."""

import base64

import httpx
import pytest
import respx

from app import db as dbmod
from app.config import get_settings
from app.models_events import EventRegistration
from app.services import storage

EVENTS = "/api/admin/events"
REGS = "/api/admin/event-registrations"
OCR_URL = "https://api.ocr.space/parse/image"

PDF = b"%PDF-1.4\n% profile\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def event(**over) -> dict:
    d = {
        "title": "Business Matching CLB CEO1989 × Coolmate",
        "status": "published",
        "subtitle": "Từ nội lực đến tăng trưởng",
        "summary": "Giao lưu, chia sẻ và kết nối hợp tác.",
        "host": "CLB CEO1989",
        "partner": "Coolmate",
        "starts_at": "2026-12-02T14:00:00",
        "ends_at": "2026-12-02T20:30:00",
        "venue": "Văn phòng Coolmate",
        "address": "Tòa nhà BMM, Km2 Phùng Hưng, Hà Đông, Hà Nội",
        "deadline": "2026-12-01",
        "intro": "## Tinh thần\n- Chia sẻ thật",
        "agenda": "- 14:30 đón khách",
        "matching": "## Coolmate cần\n- Xưởng may",
        "fee_member": 500000,
        "fee_guest": 600000,
        "bank_bin": "970418",
        "bank_name": "BIDV",
        "account_no": "12010001234567",
        "account_name": "CLB CEO1989",
        "contact_name": "Mr Phúc",
        "contact_phone": "0909802998",
    }
    d.update(over)
    return d


def registration(**over) -> dict:
    d = {
        "full_name": "Trần Thị Bình",
        "phone": "0912 345 678",
        "email": "Binh@Gmail.com",
        "company": "Công ty TNHH Minh An",
        "position": "Giám đốc",
        "attendee_type": "member",
        "needs": "Cung cấp vải dệt kim cho Coolmate, muốn mua đồng phục.",
        "website_url": "",
        "elapsed_ms": 8000,
    }
    d.update(over)
    return d


def b64(data: bytes, name: str) -> dict:
    return {"name": name, "data": base64.b64encode(data).decode()}


@pytest.fixture
def r2():
    st = storage.MemoryStorage()
    storage.set_backend(st)
    yield st
    storage.set_backend(None)


@pytest.fixture
def ocr_key(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "ocr-test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def ocr_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"IsErroredOnProcessing": False, "ParsedResults": [{"ParsedText": text}]})


def make_event(admin, **over) -> dict:
    r = admin.post(EVENTS, json=event(**over))
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ trang sự kiện


def test_admin_tao_su_kien_va_trang_cong_khai(admin, client):
    e = make_event(admin)
    assert e["slug"] == "business-matching-clb-ceo1989-coolmate"

    pub = client.get(f"/api/events/{e['slug']}")
    assert pub.status_code == 200
    d = pub.json()
    assert d["is_open"] is True and d["fee_guest"] == 600000 and d["payment_ready"] is True
    assert "bank_bin" not in d and "notify_email" not in d  # không lộ cấu hình thu tiền

    lst = client.get("/api/events").json()["items"]
    assert [x["slug"] for x in lst] == [e["slug"]]


def test_ban_nhap_khong_hien_tren_trang_cong_khai(admin, client):
    e = make_event(admin, status="draft")
    assert client.get("/api/events").json()["items"] == []
    assert client.get(f"/api/events/{e['slug']}").status_code == 404


def test_het_han_dang_ky_thi_khong_nhan_dang_ky(admin, client):
    e = make_event(admin, deadline="2020-01-01")
    assert client.get(f"/api/events/{e['slug']}").json()["is_open"] is False
    r = client.post(f"/api/events/{e['slug']}/register", json=registration())
    assert r.status_code == 410


# ------------------------------------------------------------------ đăng ký + QR


def test_dang_ky_tra_ve_ma_va_qr_vietqr(admin, client):
    e = make_event(admin)
    r = client.post(f"/api/events/{e['slug']}/register", json=registration())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] and d["status"] == "new" and d["amount"] == 500000
    assert d["code"].startswith("SK") and d["payment"]["transfer_content"] == d["code"]
    qr = d["payment"]["qr_payload"]
    assert qr.startswith("000201") and "12010001234567" in qr and "500000" in qr and d["code"] in qr

    # khách mời ngoài CLB đóng mức phí khác
    g = client.post(f"/api/events/{e['slug']}/register", json=registration(attendee_type="guest", email="k@x.vn")).json()
    assert g["amount"] == 600000


def test_dang_ky_thieu_nhu_cau_bao_loi_tung_o(admin, client):
    e = make_event(admin)
    r = client.post(f"/api/events/{e['slug']}/register", json=registration(needs="ngắn", phone="123"))
    assert r.status_code == 422
    fields = r.json()["fields"]
    assert "needs" in fields and "phone" in fields


def test_mien_phi_thi_xac_nhan_luon(admin, client):
    e = make_event(admin, fee_member=0, fee_guest=0)
    d = client.post(f"/api/events/{e['slug']}/register", json=registration()).json()
    assert d["status"] == "paid" and d["payment"]["qr_payload"] == ""


def test_dinh_kem_profile_pdf_luu_len_r2(admin, client, r2):
    e = make_event(admin)
    d = client.post(
        f"/api/events/{e['slug']}/register",
        json=registration(profile_file=b64(PDF, "Profile Minh An.pdf")),
    ).json()
    assert d["has_profile"] is True
    with dbmod.new_session() as db:
        reg = db.query(EventRegistration).one()
    assert reg.profile_key.startswith("SUKIEN/profile/") and reg.profile_mime == "application/pdf"
    assert r2.objects[reg.profile_key][0] == PDF

    # admin tải được profile (link ký sẵn)
    assert admin.get(f"{REGS}/{reg.id}/profile", follow_redirects=False).status_code == 302


def test_profile_khong_phai_pdf_bi_tu_choi(admin, client, r2):
    e = make_event(admin)
    r = client.post(f"/api/events/{e['slug']}/register", json=registration(profile_file=b64(PNG, "anh.pdf")))
    assert r.status_code == 422 and "profile_file" in r.json()["fields"]


def test_honeypot_va_gui_qua_nhanh(admin, client):
    e = make_event(admin)
    assert client.post(f"/api/events/{e['slug']}/register", json=registration(website_url="bot")).json() == {"ok": True, "code": ""}
    r = client.post(f"/api/events/{e['slug']}/register", json=registration(elapsed_ms=100))
    assert r.status_code == 429
    with dbmod.new_session() as db:
        assert db.query(EventRegistration).count() == 0


# ------------------------------------------------------------------ ảnh chuyển khoản + OCR


def _register(client, slug) -> dict:
    return client.post(f"/api/events/{slug}/register", json=registration()).json()


@respx.mock
def test_ocr_khop_ma_va_so_tien_thi_tu_xac_nhan(admin, client, r2, ocr_key):
    e = make_event(admin)
    d = _register(client, e["slug"])
    route = respx.post(OCR_URL).mock(return_value=ocr_reply(f"Chuyen tien thanh cong\n500.000 VND\nNoi dung: {d['code']}"))

    r = client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "bien lai.png")})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "paid" and out["ocr_status"] == "matched" and out["paid_at"]
    assert route.called
    with dbmod.new_session() as db:
        reg = db.query(EventRegistration).one()
    assert reg.proof_key.startswith("SUKIEN/thanh-toan/") and reg.ocr_amount == 500000
    assert reg.ocr_checks == {"code": True, "amount": True, "account": False}


@respx.mock
def test_ocr_sai_so_tien_thi_cho_doi_soat(admin, client, r2, ocr_key):
    e = make_event(admin)
    d = _register(client, e["slug"])
    respx.post(OCR_URL).mock(return_value=ocr_reply(f"100.000 VND {d['code']}"))
    out = client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")}).json()
    assert out["status"] == "review" and out["ocr_status"] == "mismatch" and "500.000" in out["ocr_message"]


@respx.mock
def test_ocr_khong_doc_duoc_chu(admin, client, r2, ocr_key):
    e = make_event(admin)
    d = _register(client, e["slug"])
    respx.post(OCR_URL).mock(return_value=ocr_reply("   "))
    out = client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")}).json()
    assert out["status"] == "review" and out["ocr_status"] == "unreadable"


def test_chua_cau_hinh_ocr_thi_cho_doi_soat_thu_cong(admin, client, r2):
    e = make_event(admin)
    d = _register(client, e["slug"])
    out = client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")}).json()
    assert out["status"] == "review" and out["ocr_status"] == "off"


def test_anh_sai_dinh_dang_bi_tu_choi(admin, client, r2):
    e = make_event(admin)
    d = _register(client, e["slug"])
    r = client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PDF, "a.png")})
    assert r.status_code == 422 and "image" in r.json()["fields"]


@respx.mock
def test_da_thanh_toan_thi_khong_nhan_them_anh(admin, client, r2, ocr_key):
    e = make_event(admin)
    d = _register(client, e["slug"])
    respx.post(OCR_URL).mock(return_value=ocr_reply(f"500000 {d['code']}"))
    client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")})
    again = client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "b.png")})
    assert again.status_code == 409


def test_tra_cuu_dang_ky_theo_ma(admin, client):
    e = make_event(admin)
    d = _register(client, e["slug"])
    out = client.get(f"/api/events/registrations/{d['code'].lower()}").json()
    assert out["code"] == d["code"] and out["payment"]["amount"] == 500000
    # ai đoán trúng mã cũng không lấy được email / SĐT đầy đủ
    assert out["email"] == "b***@gmail.com" and "phone" not in out and "needs" not in out
    assert client.get("/api/events/registrations/SKZZZZZZ").status_code == 404


# ------------------------------------------------------------------ quản trị đăng ký


def test_admin_xem_loc_va_xac_nhan_thu_cong(admin, client, r2):
    e = make_event(admin)
    d = _register(client, e["slug"])
    client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")})

    lst = admin.get(REGS).json()
    assert lst["total"] == 1 and lst["counts"]["review"] == 1
    item = lst["items"][0]
    assert item["needs"].startswith("Cung cấp vải") and item["company"] == "Công ty TNHH Minh An"
    assert item["event_slug"] == e["slug"] and item["proof_filename"] == "a.png"

    rid = item["id"]
    assert admin.get(f"{REGS}/{rid}/proof", follow_redirects=False).status_code == 302
    upd = admin.patch(f"{REGS}/{rid}", json={"status": "paid", "note": "Đã đối chiếu sao kê"}).json()
    assert upd["status"] == "paid" and upd["paid_at"] and upd["note"] == "Đã đối chiếu sao kê"
    assert admin.get(REGS).json()["revenue"] == 500000


@respx.mock
def test_admin_doc_lai_anh_bang_ocr(admin, client, r2, ocr_key):
    e = make_event(admin)
    d = _register(client, e["slug"])
    respx.post(OCR_URL).mock(return_value=ocr_reply("mo qua"))
    client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")})
    rid = admin.get(REGS).json()["items"][0]["id"]

    respx.post(OCR_URL).mock(return_value=ocr_reply(f"500,000d  {d['code']}"))
    out = admin.post(f"{REGS}/{rid}/recheck").json()
    assert out["status"] == "paid" and out["ocr_status"] == "matched"


def test_xoa_dang_ky_xoa_luon_tep_tren_r2(admin, client, r2):
    e = make_event(admin)
    client.post(f"/api/events/{e['slug']}/register", json=registration(profile_file=b64(PDF, "p.pdf")))
    rid = admin.get(REGS).json()["items"][0]["id"]
    assert admin.delete(f"{REGS}/{rid}").status_code == 204
    assert r2.objects == {}


def test_danh_sach_su_kien_cua_admin_dem_dang_ky(admin, client):
    e = make_event(admin)
    _register(client, e["slug"])
    row = admin.get(EVENTS).json()["items"][0]
    assert row["registrations"] == 1 and row["paid"] == 0 and row["fee_member"] == 500000


def test_khach_khong_vao_duoc_api_quan_tri(client):
    assert client.get(REGS).status_code == 401
    assert client.get(EVENTS).status_code == 401


# ------------------------------------------------------------------ email cho khách: không trùng, admin xác nhận cũng báo

RESEND = "https://api.resend.com/emails"
BTC = "btc@ceo1989.vn"


@pytest.fixture
def mail(monkeypatch):
    monkeypatch.setenv("LEADSCAN_RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("LEADSCAN_EVENT_EMAIL", BTC)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mails(route) -> list[tuple[str, str]]:
    import json

    return [(b["to"][0], b["subject"]) for b in (json.loads(c.request.content) for c in route.calls)]


def _guest(route) -> list[str]:
    return [s for to, s in _mails(route) if to != BTC]


def _reg(db_id=None) -> EventRegistration:
    from sqlalchemy import select

    with dbmod.new_session() as db:
        return db.scalar(select(EventRegistration))


@respx.mock
def test_dang_ky_gui_khach_va_ban_to_chuc_moi_ben_1_email(admin, client, mail):
    route = respx.post(RESEND).respond(200, json={"id": "e1"})
    e = make_event(admin)
    d = _register(client, e["slug"])
    mails = _mails(route)
    assert len(mails) == 2 and {to for to, _ in mails} == {BTC, "binh@gmail.com"}
    assert any("Đã nhận đăng ký" in s and d["code"] in s for s in _guest(route))
    r = _reg()
    assert r.receipt_sent_at and r.email_sent_at and r.confirm_sent_at is None


def test_hop_thu_btc_loi_thi_thu_lai_khong_gui_trung_khach(admin, client, mail):
    from app.worker import deliver_event_registration

    e = make_event(admin)
    with respx.mock() as m:
        route = m.post(RESEND).mock(side_effect=lambda req: httpx.Response(500 if BTC in req.content.decode() else 200, json={"id": "x"}))
        _register(client, e["slug"])
        r = _reg()
        assert r.receipt_sent_at and r.email_sent_at is None
        assert deliver_event_registration(r.id) is False  # lần thử lại: BTC vẫn lỗi
        assert len(_guest(route)) == 1  # khách chỉ nhận 1 email

        route.mock(return_value=httpx.Response(200, json={"id": "ok"}))
        assert deliver_event_registration(r.id) is True
        assert len(_guest(route)) == 1 and _reg().email_sent_at


def test_email_khach_loi_thi_lan_sau_gui_lai(admin, client, mail):
    from app.worker import deliver_event_registration

    e = make_event(admin)
    with respx.mock() as m:
        route = m.post(RESEND).mock(side_effect=lambda req: httpx.Response(200 if BTC in req.content.decode() else 500, json={"id": "x"}))
        _register(client, e["slug"])
        r = _reg()
        assert r.email_sent_at and r.receipt_sent_at is None
        route.mock(return_value=httpx.Response(200, json={"id": "ok"}))
        assert deliver_event_registration(r.id) is True
        assert [to for to, _ in _mails(route)].count(BTC) == 1  # BTC không bị báo lại
        assert _reg().receipt_sent_at


@respx.mock
def test_nut_gui_lai_chi_gui_ban_to_chuc(admin, client, mail):
    route = respx.post(RESEND).respond(200, json={"id": "e1"})
    e = make_event(admin)
    _register(client, e["slug"])
    rid = admin.get(REGS).json()["items"][0]["id"]
    assert admin.post(f"{REGS}/{rid}/resend").status_code == 200
    assert len(_guest(route)) == 1 and [to for to, _ in _mails(route)].count(BTC) == 2


@respx.mock
def test_admin_xac_nhan_thu_cong_thi_bao_khach_mot_lan(admin, client, mail):
    route = respx.post(RESEND).respond(200, json={"id": "e1"})
    e = make_event(admin)
    _register(client, e["slug"])
    rid = admin.get(REGS).json()["items"][0]["id"]
    before = len(route.calls)
    assert admin.patch(f"{REGS}/{rid}", json={"status": "paid"}).json()["confirm_sent_at"]
    new = _mails(route)[before:]
    assert new == [("binh@gmail.com", new[0][1])]  # chỉ khách, không báo lại ban tổ chức
    # đổi qua lại trạng thái không gửi thêm
    admin.patch(f"{REGS}/{rid}", json={"status": "review"})
    admin.patch(f"{REGS}/{rid}", json={"status": "paid"})
    admin.patch(f"{REGS}/{rid}", json={"note": "ok"})
    assert len(route.calls) == before + 1


@respx.mock
def test_admin_doc_lai_ocr_khop_thi_bao_khach(admin, client, r2, ocr_key, mail):
    route = respx.post(RESEND).respond(200, json={"id": "e1"})
    e = make_event(admin)
    d = _register(client, e["slug"])
    respx.post(OCR_URL).mock(return_value=ocr_reply("mo qua"))
    client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")})
    rid = admin.get(REGS).json()["items"][0]["id"]
    before = len(route.calls)
    assert before == 2  # OCR không khớp → chưa gửi gì thêm

    respx.post(OCR_URL).mock(return_value=ocr_reply(f"500,000d  {d['code']}"))
    assert admin.post(f"{REGS}/{rid}/recheck").json()["status"] == "paid"
    assert [to for to, _ in _mails(route)[before:]] == ["binh@gmail.com"]


@respx.mock
def test_ocr_tu_xac_nhan_bao_ca_hai_ben(admin, client, r2, ocr_key, mail):
    route = respx.post(RESEND).respond(200, json={"id": "e1"})
    e = make_event(admin)
    d = _register(client, e["slug"])
    respx.post(OCR_URL).mock(return_value=ocr_reply(f"500,000d  {d['code']}"))
    client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(PNG, "a.png")})
    assert sorted(to for to, _ in _mails(route)[2:]) == sorted([BTC, "binh@gmail.com"])
    assert _reg().confirm_sent_at


@respx.mock
def test_mien_phi_khong_gui_them_email_xac_nhan(admin, client, mail):
    route = respx.post(RESEND).respond(200, json={"id": "e1"})
    e = make_event(admin, fee_member=0)
    _register(client, e["slug"])
    r = _reg()
    assert r.status == "paid" and r.confirm_sent_at and len(_guest(route)) == 1


# ------------------------------------------------------------------ mã QR check-in


@respx.mock
def test_email_xac_nhan_co_ma_qr_check_in(admin, client, mail):
    import json

    route = respx.post(RESEND).respond(200, json={"id": "e1"})
    e = make_event(admin)
    d = _register(client, e["slug"])
    sent = [json.loads(c.request.content) for c in route.calls]
    first = next(m for m in sent if m["to"] != [BTC])
    assert "checkin-qr" not in first["html"]  # chưa thanh toán → chưa có QR

    rid = admin.get(REGS).json()["items"][0]["id"]
    admin.patch(f"{REGS}/{rid}", json={"status": "paid"})
    mail_ = json.loads(route.calls[-1].request.content)
    assert mail_["to"] == ["binh@gmail.com"] and "Đã xác nhận tham dự" in mail_["subject"]
    qr = f"/api/events/checkin-qr/{d['code']}.png"
    assert qr in mail_["html"] and qr in mail_["text"]


def test_anh_qr_check_in_chua_link_trang_le_tan(client):
    import io

    from PIL import Image

    r = client.get("/api/events/checkin-qr/SK7KQ4MX.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(r.content)).size[0] > 150
    assert client.get("/api/events/checkin-qr/abc.png").status_code == 404
    from app.services.events import checkin_url

    assert checkin_url("SK7KQ4MX").endswith("/admin/su-kien/check-in?ma=SK7KQ4MX")


def test_le_tan_tra_ma_va_check_in(admin, client):
    e = make_event(admin)
    d = _register(client, e["slug"])
    got = admin.get(f"{REGS}/by-code/{d['code'].lower()}").json()
    assert got["code"] == d["code"] and got["checked_in"] is False
    assert admin.get(f"{REGS}/by-code/SK0000000").status_code == 404

    out = admin.post(f"{REGS}/{got['id']}/check-in").json()
    assert out["checked_in"] and out["checked_in_at"] and out["already"] is False
    again = admin.post(f"{REGS}/{got['id']}/check-in").json()
    assert again["already"] is True and again["checked_in_at"] == out["checked_in_at"]
    item = admin.get(REGS).json()["items"][0]
    assert item["checked_in"] and item["checked_in_at"]

    # bỏ check-in trong trang quản trị → xoá giờ đến
    assert admin.patch(f"{REGS}/{got['id']}", json={"checked_in": False}).json()["checked_in_at"] is None


def test_dang_ky_da_huy_khong_check_in_duoc(admin, client):
    e = make_event(admin)
    _register(client, e["slug"])
    rid = admin.get(REGS).json()["items"][0]["id"]
    admin.patch(f"{REGS}/{rid}", json={"status": "cancelled"})
    assert admin.post(f"{REGS}/{rid}/check-in").status_code == 409


def test_khach_khong_check_in_duoc(client):
    assert client.get(f"{REGS}/by-code/SK7KQ4MX").status_code == 401
    assert client.post(f"{REGS}/1/check-in").status_code == 401
