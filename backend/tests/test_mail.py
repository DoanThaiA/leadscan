import json

import httpx
import respx

from app.config import get_settings
from app.services.notify import mail_provider, send_mail


def _cfg(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(f"LEADSCAN_{k.upper()}", v)
    get_settings.cache_clear()
    return get_settings()


def test_chua_cau_hinh_thi_khong_gui(monkeypatch):
    cfg = _cfg(monkeypatch, resend_api_key="", smtp_host="")
    assert mail_provider(cfg) is None
    assert send_mail(cfg, "x", "y", to="a@b.vn") is False


def test_gui_qua_resend(monkeypatch):
    cfg = _cfg(monkeypatch, resend_api_key="re_test_key", notify_from="no-reply@mcv.network", mail_from_name="MCV Network")
    assert mail_provider(cfg) == "resend"
    with respx.mock(assert_all_called=True) as m:
        route = m.post("https://api.resend.com/emails").respond(200, json={"id": "email_123"})
        assert send_mail(cfg, "[LeadScan] Thử", "Nội dung tiếng Việt", to="vylyy9999@gmail.com") is True
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer re_test_key"
    body = json.loads(req.content)
    html = body.pop("html")  # mọi email đều kèm bản HTML giao diện LeadScan (services/mail_layout.py)
    assert body == {"from": "MCV Network <no-reply@mcv.network>", "to": ["vylyy9999@gmail.com"], "subject": "[LeadScan] Thử", "text": "Nội dung tiếng Việt"}
    assert html.startswith("<!doctype html>") and "Nội dung tiếng Việt" in html and "leadscan-logo-reverse-1200.png" in html


def test_resend_loi_tra_false_khong_nem_loi(monkeypatch):
    cfg = _cfg(monkeypatch, resend_api_key="re_test_key")
    with respx.mock() as m:
        m.post("https://api.resend.com/emails").respond(403, json={"message": "domain not verified"})
        assert send_mail(cfg, "s", "b", to="a@b.vn") is False
        m.post("https://api.resend.com/emails").mock(side_effect=httpx.ConnectTimeout("timeout"))
        assert send_mail(cfg, "s", "b", to="a@b.vn") is False


def test_hoa_don_gui_qua_resend_va_ghi_nhan_da_gui(client, monkeypatch):
    """Luồng thật (tắt IAM): thanh toán → worker tự gửi thông tin hoá đơn qua Resend tới kế toán → email_sent_at được ghi."""
    from sqlalchemy import select

    from app.db import new_session
    from app.models import InvoiceRequest
    from tests.conftest import register
    from tests.test_member import member_client, pay_membership

    _cfg(monkeypatch, resend_api_key="re_test_key")
    register(client)
    m = member_client()
    with respx.mock(assert_all_called=True) as rm:
        route = rm.post("https://api.resend.com/emails").respond(200, json={"id": "email_456"})
        code = pay_membership(m)
    sent = _sent(route)["vylyy9999@gmail.com"]
    assert code in sent["subject"] and "0101234567" in sent["text"] and "Tiền thuế GTGT" in sent["text"]
    with new_session() as db:
        assert db.scalar(select(InvoiceRequest)).email_sent_at is not None


def _env_mail(monkeypatch, **extra):
    env = {
        "resend_api_key": "re_test_key",
        "notify_email": "quantri@gmail.com",
        "notify_from": "no-reply@leadscan.net",
        "mail_from_name": "LeadScan",
        "admin_url": "https://leadscan.net/admin",
        "member_url": "https://leadscan.net/thanh-vien",
    }
    return _cfg(monkeypatch, **{**env, **extra})


def _sent(route, since: int = 0) -> dict:
    """{người nhận: body JSON} của các email gửi qua Resend (từ lần gọi thứ `since`)."""
    out = {}
    for call in list(route.calls)[since:]:
        b = json.loads(call.request.content)
        out[b["to"][0]] = b
    return out


def test_dang_ky_moi_bao_quan_tri_va_chao_mung_khach(client, monkeypatch):
    """Luồng thật: khách gửi form → worker gửi 2 email: báo quản trị + chào mừng khách."""
    from tests.conftest import valid_form

    _env_mail(monkeypatch)
    with respx.mock(assert_all_called=True) as m:
        route = m.post("https://api.resend.com/emails").respond(200, json={"id": "email_1"})
        r = client.post("/api/registrations", json=valid_form())
        assert r.status_code == 200, r.text
    code = r.json()["code"]
    sent = _sent(route)
    assert set(sent) == {"quantri@gmail.com", "a@minhan.vn"}

    admin = sent["quantri@gmail.com"]
    assert admin["from"] == "LeadScan <no-reply@leadscan.net>"
    assert admin["subject"].startswith("[LeadScan] Đăng ký mới: Công ty TNHH Bao Bì Minh An")
    assert "MST: 0101234567" in admin["text"]
    assert "Nguyễn Văn A - 0901234567 - a@minhan.vn" in admin["text"]
    assert "https://leadscan.net/admin/khach-hang/" in admin["text"]

    welcome = sent["a@minhan.vn"]
    assert welcome["subject"] == "[LeadScan] Chào mừng Công ty TNHH Bao Bì Minh An — đăng ký thành công"
    assert "Chào Nguyễn Văn A" in welcome["text"] and code in welcome["text"]
    assert "https://leadscan.net/thanh-vien/dang-nhap" in welcome["text"]
    assert "10.000.000đ/năm" in welcome["text"] and "10.000.000 điểm" in welcome["text"]
    assert "matkhau" not in welcome["text"].lower().replace(" ", "")  # không bao giờ gửi mật khẩu qua email


def test_dang_ky_khong_co_email_quan_tri_van_chao_mung_khach(client, monkeypatch):
    from tests.conftest import valid_form

    _env_mail(monkeypatch, notify_email="")
    with respx.mock(assert_all_called=False) as m:
        route = m.post("https://api.resend.com/emails").respond(200, json={"id": "x"})
        assert client.post("/api/registrations", json=valid_form()).status_code == 200
    assert set(_sent(route)) == {"a@minhan.vn"}


def test_thanh_toan_gui_email_thanh_vien_va_bao_quan_tri(client, monkeypatch):
    """Đơn phí thành viên được ghi nhận → email "Kích hoạt thành viên" cho khách + báo quản trị."""
    from tests.conftest import MEMBER_PW, set_contact_email, valid_form

    _env_mail(monkeypatch)
    with respx.mock(assert_all_called=False) as m:
        route = m.post("https://api.resend.com/emails").respond(200, json={"id": "x"})
        assert client.post("/api/registrations", json=valid_form()).status_code == 200
        set_contact_email("ketoan@minhan.vn")  # người liên hệ khác email đăng nhập (a@minhan.vn)
        client.post("/api/member/auth/login", json={"email": "a@minhan.vn", "password": MEMBER_PW})
        code = client.post("/api/member/orders", json={"kind": "membership"}).json()["order"]["code"]
        before = route.call_count
        assert client.post(f"/api/member/orders/{code}/simulate-paid").status_code == 200
        sent = _sent(route, before)
        # gửi người liên hệ (không gửi email đăng nhập) + kế toán nhận thông tin xuất hoá đơn (tắt IAM)
        assert set(sent) == {"quantri@gmail.com", "ketoan@minhan.vn", "vylyy9999@gmail.com"}
        assert code in sent["vylyy9999@gmail.com"]["subject"]

        member = sent["ketoan@minhan.vn"]
        assert member["subject"] == "[LeadScan] Kích hoạt thành viên thành công"
        assert code in member["text"] and "10.000.000đ" in member["text"]
        assert "Số dư hiện tại    : 10.000.000 điểm" in member["text"]
        assert "Thành viên đến" in member["text"]
        assert f"https://leadscan.net/thanh-vien/nap-tien/{code}" in member["text"]

        admin = sent["quantri@gmail.com"]
        assert admin["subject"].startswith("[LeadScan] Đã nhận thanh toán phí thành viên: Công ty TNHH Bao Bì Minh An")
        assert "(tự động)" in admin["text"] and "/admin/khach-hang/" in admin["text"]

        # Gọi lại không cộng điểm lần 2 → không gửi email lần 2
        before = route.call_count
        assert client.post(f"/api/member/orders/{code}/simulate-paid").status_code == 409
        assert route.call_count == before


def test_khach_chua_co_lien_he_co_email_thi_khong_gui_email_dang_nhap(client, monkeypatch):
    """Email tự động gửi khách đi tới người liên hệ; doanh nghiệp không có người liên hệ nào có email → không gửi."""
    from sqlalchemy import select

    from app.db import new_session
    from app.models import Company
    from app.services import notify
    from tests.conftest import register, set_contact_email

    cid = register(client)
    with new_session() as db:
        assert notify.company_contact(db, cid) == ("a@minhan.vn", "Nguyễn Văn A")
    set_contact_email("")
    with new_session() as db:
        assert notify.company_contact(db, cid) is None
        assert db.scalar(select(Company.id)) == cid
