"""Webhook nhận đăng ký thành viên từ hệ thống ngoài: POST /api/registrations/webhook (khoá Bearer trong .env)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import new_session
from app.models import Activity, Company, MemberUser

URL = "/api/registrations/webhook"
SECRET = "khoa-webhook-thu-nghiem-0123456789"
AUTH = {"Authorization": f"Bearer {SECRET}"}


def new_client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def hook(monkeypatch):
    """Bật webhook + bắt email gửi khách (chào mừng / đặt mật khẩu)."""
    from app.services import notify

    monkeypatch.setenv("LEADSCAN_REGISTRATION_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    mails: dict[str, list] = {"setup": [], "welcome": []}
    monkeypatch.setattr(notify, "send_account_setup", lambda cfg, c, email, name, token: mails["setup"].append((email, token)) or True)
    monkeypatch.setattr(notify, "send_welcome", lambda cfg, c, email, name: mails["welcome"].append(email) or True)
    return mails


def lead(**over) -> dict:
    d = {
        "company_name": "Công ty TNHH Nội Thất Hoà Phát Đạt",
        "tax_code": "0312345678",
        "contact_name": "Lê Thị Hoa",
        "email": "Hoa@HoaPhatDat.vn",
        "phone": "0903 111 222",
        "source": "Facebook Ads",
    }
    d.update(over)
    return d


def test_disabled_without_secret(client):
    assert client.post(URL, json=lead(), headers=AUTH).status_code == 404


def test_auth_required_and_brute_force_blocked(client, hook):
    assert client.post(URL, json=lead()).status_code == 401
    assert client.post(URL, json=lead(), headers={"Authorization": "Bearer sai"}).status_code == 401
    for _ in range(19):
        client.post(URL, json=lead(), headers={"Authorization": "Bearer sai"})
    assert client.post(URL, json=lead(), headers=AUTH).status_code == 429  # IP đã dò khoá quá nhiều
    with new_session() as db:
        assert db.scalar(select(Company.id)) is None


def test_creates_member_and_sends_password_setup(client, hook):
    r = client.post(URL, json=lead(), headers=AUTH)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["ok"] and out["code"].startswith("LS-") and out["account"] == "created" and out["password_setup_email"] is True
    with new_session() as db:
        c = db.get(Company, out["company_id"])
        assert (c.name, c.tax_code, c.source, c.status) == ("Công ty TNHH Nội Thất Hoà Phát Đạt", "0312345678", "webhook:facebook-ads", "new")
        assert c.contacts[0].phone == "0903111222" and c.contacts[0].email == "hoa@hoaphatdat.vn"
        assert "qua webhook (nguồn: facebook-ads)" in db.scalar(select(Activity.content).where(Activity.company_id == c.id))
        assert db.scalar(select(MemberUser.email)) == "hoa@hoaphatdat.vn"

    # khách nhận email đặt mật khẩu (không phải email "mật khẩu bạn đã đặt") → đặt mật khẩu → đăng nhập được
    assert hook["welcome"] == [] and len(hook["setup"]) == 1 and hook["setup"][0][0] == "hoa@hoaphatdat.vn"
    token = hook["setup"][0][1]
    m = new_client()
    assert m.post("/api/member/auth/reset", json={"token": token, "password": "hoa-dat-mat-khau-1"}).status_code == 204
    assert m.post("/api/member/auth/login", json={"email": "hoa@hoaphatdat.vn", "password": "hoa-dat-mat-khau-1"}).status_code == 200


def test_with_password_and_idempotent_retry(client, hook):
    r = client.post(URL, json=lead(password="mat-khau-tu-crm-1", company_size="Rất lớn (không có trong danh mục)"), headers=AUTH)
    assert r.status_code == 201 and r.json()["password_setup_email"] is False
    assert hook["welcome"] == ["hoa@hoaphatdat.vn"] and hook["setup"] == []
    assert new_client().post("/api/member/auth/login", json={"email": "hoa@hoaphatdat.vn", "password": "mat-khau-tu-crm-1"}).status_code == 200

    # bên gửi retry cùng MST + email → trả lại đăng ký cũ, không tạo trùng, không gửi email lần 2
    again = client.post(URL, json=lead(password="mat-khau-tu-crm-1"), headers=AUTH)
    assert again.status_code == 200 and again.json()["duplicate"] is True and again.json()["code"] == r.json()["code"]
    assert hook["welcome"] == ["hoa@hoaphatdat.vn"]
    # cùng MST nhưng email khác → khách khác đã đăng ký MST này
    r = client.post(URL, json=lead(email="khac@hoaphatdat.vn"), headers=AUTH)
    assert r.status_code == 409 and "tax_code" in r.json()["fields"]
    # email đã có tài khoản thành viên của doanh nghiệp khác
    r = client.post(URL, json=lead(tax_code="0398765432"), headers=AUTH)
    assert r.status_code == 409 and "email" in r.json()["fields"]


def test_validation(client, hook):
    r = client.post(URL, json=lead(phone="123", email="khong-phai-email", tax_code="12", password="ngan"), headers=AUTH)
    assert r.status_code == 422
    assert {"phone", "email", "tax_code", "password"} <= set(r.json()["fields"])
    assert "industries" not in r.json()["fields"] and "agree" not in r.json()["fields"]  # webhook không bắt buộc
    assert client.post(URL, content=b"[1,2]", headers={**AUTH, "Content-Type": "application/json"}).status_code == 400


def test_partner_email_shares_account(client, hook, monkeypatch):
    from app.services import otp
    from tests.test_partner import PARTNER_PW, signup_form

    monkeypatch.setattr(otp, "deliver", lambda cfg, email, code, name="": "test")
    assert new_client().post("/api/partner/auth/register", json=signup_form(email="hoa@hoaphatdat.vn")).status_code == 201
    r = client.post(URL, json=lead(password="mat-khau-khac-123"), headers=AUTH)
    assert r.status_code == 409 and "password" in r.json()["fields"]

    r = client.post(URL, json=lead(), headers=AUTH)
    assert r.status_code == 201 and r.json()["account"] == "shared_with_partner" and r.json()["password_setup_email"] is False
    r = new_client().post("/api/member/auth/login", json={"email": "hoa@hoaphatdat.vn", "password": PARTNER_PW})
    assert r.status_code == 200 and r.json()["portals"] == {"member": True, "partner": True}
