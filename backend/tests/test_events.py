"""Sự kiện: admin tạo trang sự kiện, khách đăng ký → QR thanh toán → nộp ảnh chuyển khoản, OCR đối soát."""

import base64
import io

import httpx
import pytest
import respx
from PIL import Image

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


# ------------------------------------------------------------------ tệp lớn (tới 20 MB)


def test_profile_gan_20mb_van_nhan(admin, client, r2):
    e = make_event(admin)
    big = PDF + b"0" * (19 * 1024 * 1024)
    r = client.post(f"/api/events/{e['slug']}/register", json=registration(profile_file=b64(big, "to.pdf")))
    assert r.status_code == 200, r.text
    assert client.get(f"/api/events/{e['slug']}").json()["profile_max_mb"] == 20


def test_profile_qua_20mb_bao_loi_ro(admin, client, r2):
    e = make_event(admin)
    big = PDF + b"0" * (20 * 1024 * 1024)
    r = client.post(f"/api/events/{e['slug']}/register", json=registration(profile_file=b64(big, "to.pdf")))
    assert r.status_code in (413, 422) and "20 MB" in r.json()["fields"]["profile_file"]


@respx.mock
def test_anh_lon_duoc_thu_nho_truoc_khi_ocr(admin, client, r2, ocr_key):
    buf = io.BytesIO()
    Image.effect_noise((1600, 2400), 90).convert("RGB").save(buf, "PNG")
    original = buf.getvalue()
    assert len(original) > 1024 * 1024

    e = make_event(admin)
    d = _register(client, e["slug"])
    route = respx.post(OCR_URL).mock(return_value=ocr_reply(f"500.000 {d['code']}"))
    out = client.post(f"/api/events/registrations/{d['code']}/proof", json={"image": b64(original, "to.png")}).json()
    assert out["status"] == "paid"
    assert len(route.calls[0].request.content) < 1100 * 1024  # bản gửi OCR đã nhỏ lại
    with dbmod.new_session() as db:
        reg = db.query(EventRegistration).one()
    assert r2.objects[reg.proof_key][0] == original  # ảnh lưu trên R2 giữ nguyên
