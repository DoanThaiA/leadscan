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
    assert body == {"from": "MCV Network <no-reply@mcv.network>", "to": ["vylyy9999@gmail.com"], "subject": "[LeadScan] Thử", "text": "Nội dung tiếng Việt"}


def test_resend_loi_tra_false_khong_nem_loi(monkeypatch):
    cfg = _cfg(monkeypatch, resend_api_key="re_test_key")
    with respx.mock() as m:
        m.post("https://api.resend.com/emails").respond(403, json={"message": "domain not verified"})
        assert send_mail(cfg, "s", "b", to="a@b.vn") is False
        m.post("https://api.resend.com/emails").mock(side_effect=httpx.ConnectTimeout("timeout"))
        assert send_mail(cfg, "s", "b", to="a@b.vn") is False


def test_hoa_don_gui_qua_resend_va_ghi_nhan_da_gui(client, monkeypatch):
    """Luồng thật: thanh toán → gửi thông tin hoá đơn → worker gửi Resend tới kế toán → email_sent_at được ghi."""
    from sqlalchemy import select

    from app.db import new_session
    from app.models import InvoiceRequest
    from tests.conftest import register
    from tests.test_member import member_client, pay_membership

    _cfg(monkeypatch, resend_api_key="re_test_key")
    register(client)
    m = member_client()
    code = pay_membership(m)
    with respx.mock(assert_all_called=True) as rm:
        route = rm.post("https://api.resend.com/emails").respond(200, json={"id": "email_456"})
        r = m.post(f"/api/member/orders/{code}/invoice", json={"company_name": "Minh An", "tax_code": "0101234567", "address": "Bắc Ninh", "receive_email": "kt@minhan.vn"})
        assert r.status_code == 201
    sent = json.loads(route.calls.last.request.content)
    assert sent["to"] == ["vylyy9999@gmail.com"] and code in sent["subject"] and "0101234567" in sent["text"]
    with new_session() as db:
        assert db.scalar(select(InvoiceRequest)).email_sent_at is not None
