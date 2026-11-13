"""Đối tác LeadScan — Mốc 1: đăng ký, mã OTP xác thực email, đăng nhập riêng, quên mật khẩu, quản trị đối tác."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import new_session, utcnow
from app.models import PartnerEvent, PartnerOtp, PartnerSession, PartnerUser
from tests.conftest import MEMBER_PW, register

PARTNER_PW = "matkhau-doitac-123"


def signup_form(**over) -> dict:
    form = {
        "full_name": "Trần Thị Bình",
        "phone": "+84 912 345 678",
        "email": "Binh@Gmail.com",
        "password": PARTNER_PW,
        "kind": "personal",
        "industries": ["Bao bì & in ấn", "Không có trong danh mục"],
        "regions": ["Bắc Ninh"],
        "agree": True,
        "website_url": "",
        "elapsed_ms": 9000,
    }
    form.update(over)
    return form


def new_client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def otp_mail(monkeypatch):
    """Bắt mã OTP thay vì gửi email: danh sách (email, mã) theo thứ tự gửi."""
    from app.services import otp

    sent: list[tuple[str, str]] = []

    def fake(cfg, email, code, name=""):
        sent.append((email, code))
        return "test"

    monkeypatch.setattr(otp, "deliver", fake)
    return sent


@pytest.fixture
def partner(otp_mail) -> TestClient:
    c = new_client()
    r = c.post("/api/partner/auth/register", json=signup_form())
    assert r.status_code == 201, r.text
    return c


def _rewind_otp(minutes: int = 2):
    """Lùi thời điểm gửi mã để qua thời gian chờ gửi lại / hết hạn."""
    with new_session() as db:
        for o in db.scalars(select(PartnerOtp)):
            o.created_at -= timedelta(minutes=minutes)
            o.expires_at -= timedelta(minutes=minutes)
        db.commit()


# ------------------------------------------------------------------ đăng ký


def test_register_creates_unverified_partner_logged_in_and_sends_otp(otp_mail):
    c = new_client()
    r = c.post("/api/partner/auth/register", json=signup_form())
    assert r.status_code == 201, r.text
    j = r.json()
    me = j["me"]
    assert me["email"] == "binh@gmail.com"
    assert me["phone"] == "0912345678"  # +84 → 0, bỏ khoảng trắng
    assert me["email_verified"] is False
    assert me["code"].startswith("DT-") and len(me["code"]) == 9
    assert me["industries"] == ["Bao bì & in ấn"]  # ngoài danh mục bị bỏ
    assert me["tier"] == "new"
    assert j["otp"]["sent"] is True and j["otp"]["email"] == "bi•h@gmail.com"
    assert otp_mail == [("binh@gmail.com", otp_mail[0][1])] and len(otp_mail[0][1]) == 6

    # đăng nhập luôn sau khi đăng ký
    assert c.get("/api/partner/auth/me").json()["email"] == "binh@gmail.com"
    with new_session() as db:
        p = db.scalar(select(PartnerUser))
        assert p.terms_version and p.terms_accepted_at
        assert db.scalar(select(PartnerEvent.kind).where(PartnerEvent.partner_id == p.id)) == "created"
        otp = db.scalar(select(PartnerOtp))
        assert otp_mail[0][1] not in otp.code_hash  # chỉ lưu hash


def test_register_validation(otp_mail):
    c = new_client()
    r = c.post("/api/partner/auth/register", json=signup_form(full_name="", phone="123", email="x", password="short", kind="", agree=False))
    assert r.status_code == 422
    assert set(r.json()["fields"]) == {"full_name", "phone", "email", "password", "kind", "agree"}

    r = c.post("/api/partner/auth/register", json=signup_form(kind="org"))
    assert r.status_code == 422 and set(r.json()["fields"]) == {"org_name", "org_tax_code"}

    r = c.post("/api/partner/auth/register", json=signup_form(kind="org", org_name="Hiệp hội Bao bì", org_tax_code="0101234567"))
    assert r.status_code == 201
    assert r.json()["me"]["kind_label"] == "Tổ chức" and r.json()["me"]["org_tax_code"] == "0101234567"
    assert otp_mail  # vẫn gửi OTP


def test_register_rejects_bots(otp_mail):
    c = new_client()
    assert c.post("/api/partner/auth/register", json=signup_form(website_url="http://spam")).status_code == 400
    assert c.post("/api/partner/auth/register", json=signup_form(elapsed_ms=500)).status_code == 429
    assert c.post("/api/partner/auth/register", content=b"[1,2]", headers={"content-type": "application/json"}).status_code in (400, 422)
    with new_session() as db:
        assert db.scalar(select(PartnerUser.id)) is None
    assert otp_mail == []


def test_register_duplicate_email_or_phone(partner):
    c = new_client()
    r = c.post("/api/partner/auth/register", json=signup_form(phone="0987654321"))
    assert r.status_code == 409 and "email" in r.json()["fields"]
    r = c.post("/api/partner/auth/register", json=signup_form(email="khac@gmail.com", phone="0912 345 678"))
    assert r.status_code == 409 and "phone" in r.json()["fields"]


def test_member_email_becomes_partner_with_same_password(client, otp_mail):
    """Cùng email = cùng 1 tài khoản: đăng ký đối tác bằng email thành viên phải nhập đúng mật khẩu đang dùng."""
    register(client)  # thành viên a@minhan.vn / MEMBER_PW
    r = new_client().post("/api/partner/auth/register", json=signup_form(email="a@minhan.vn", password="mat-khau-khac-1"))
    assert r.status_code == 409 and "password" in r.json()["fields"]
    r = new_client().post("/api/partner/auth/register", json=signup_form(email="A@MinhAn.vn", password=MEMBER_PW))
    assert r.status_code == 201, r.text
    with new_session() as db:
        from app.models import MemberUser

        assert db.scalar(select(PartnerUser.password_hash)) == db.scalar(select(MemberUser.password_hash))


# ------------------------------------------------------------------ OTP


def test_otp_verify_flow(partner, otp_mail):
    code = otp_mail[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    r = partner.post("/api/partner/auth/otp/verify", json={"code": wrong})
    assert r.status_code == 400 and "Còn 4 lần" in r.json()["detail"]

    r = partner.post("/api/partner/auth/otp/verify", json={"code": code})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    assert partner.get("/api/partner/auth/me").json()["email_verified"] is True
    # đã xác thực → không gửi mã nữa
    assert partner.post("/api/partner/auth/otp/send").status_code == 409
    with new_session() as db:
        assert db.scalar(select(PartnerEvent).where(PartnerEvent.kind == "email_verified")) is not None


def test_otp_resend_cooldown_and_latest_code_wins(partner, otp_mail):
    r = partner.post("/api/partner/auth/otp/send")
    assert r.status_code == 429 and "giây" in r.json()["detail"]
    assert partner.get("/api/partner/auth/me").json()["otp_resend_after"] > 0

    _rewind_otp(2)
    r = partner.post("/api/partner/auth/otp/send")
    assert r.status_code == 200, r.text
    old, new = otp_mail[0][1], otp_mail[1][1]
    if old != new:  # mã cũ không còn dùng được
        assert partner.post("/api/partner/auth/otp/verify", json={"code": old}).status_code == 400
    assert partner.post("/api/partner/auth/otp/verify", json={"code": new}).status_code == 200


def test_otp_expired_and_too_many_attempts(partner, otp_mail):
    code = otp_mail[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert partner.post("/api/partner/auth/otp/verify", json={"code": wrong}).status_code == 400
    r = partner.post("/api/partner/auth/otp/verify", json={"code": code})
    assert r.status_code == 400 and "quá nhiều lần" in r.json()["detail"]

    _rewind_otp(20)  # mã qua email hiệu lực 15 phút
    assert partner.post("/api/partner/auth/otp/send").status_code == 200
    _rewind_otp(20)  # mã mới cũng hết hạn
    r = partner.post("/api/partner/auth/otp/verify", json={"code": otp_mail[-1][1]})
    assert r.status_code == 400 and "hết hạn" in r.json()["detail"]


def test_otp_hourly_limit(partner, otp_mail):
    for _ in range(4):
        _rewind_otp(2)  # vẫn trong 1 giờ
        assert partner.post("/api/partner/auth/otp/send").status_code == 200
    _rewind_otp(2)
    r = partner.post("/api/partner/auth/otp/send")
    assert r.status_code == 429 and "1 giờ" in r.json()["detail"]
    assert len(otp_mail) == 5


def test_verified_partner_dependency(partner, otp_mail):
    from fastapi import HTTPException

    from app.partner_auth import verified_partner

    with new_session() as db:
        p = db.scalar(select(PartnerUser))
        with pytest.raises(HTTPException) as e:
            verified_partner(p)
        assert e.value.status_code == 403
        p.email_verified_at = utcnow()
        assert verified_partner(p) is p


# ------------------------------------------------------------------ đăng nhập & tách cổng


def test_login_logout(partner):
    c = new_client()
    assert c.post("/api/partner/auth/login", json={"email": "binh@gmail.com", "password": "sai-mat-khau"}).status_code == 401
    r = c.post("/api/partner/auth/login", json={"email": " BINH@gmail.com ", "password": PARTNER_PW})
    assert r.status_code == 200 and r.json()["code"].startswith("DT-")
    assert c.cookies.get("ls_partner")
    assert c.post("/api/partner/auth/logout").status_code == 204
    assert c.get("/api/partner/auth/me").status_code == 401


def test_one_account_logs_into_both_portals(client, otp_mail):
    """1 tài khoản cho cả 2 cổng: đăng nhập ở cổng nào cũng mở phiên của cả 2, mỗi cổng giao diện / API riêng."""
    register(client)  # thành viên a@minhan.vn / MEMBER_PW
    # chỉ có hồ sơ thành viên: đăng nhập ở cổng đối tác vẫn được, trang đăng nhập cho chọn vào cổng thành viên
    c = new_client()
    r = c.post("/api/partner/auth/login", json={"email": "a@minhan.vn", "password": MEMBER_PW})
    assert r.status_code == 200 and r.json()["portals"] == {"member": True, "partner": False}
    assert r.json()["redirect"] == "/thanh-vien"
    assert c.get("/api/member/auth/me").status_code == 200
    assert c.get("/api/partner/auth/me").status_code == 401
    assert new_client().post("/api/partner/auth/login", json={"email": "a@minhan.vn", "password": "sai-mat-khau"}).status_code == 401

    p = new_client()
    assert p.post("/api/partner/auth/register", json=signup_form(email="a@minhan.vn", password=MEMBER_PW)).status_code == 201

    # có cả 2 hồ sơ: đăng nhập cổng thành viên → vào được cả cổng đối tác, và ngược lại
    m = new_client()
    r = m.post("/api/member/auth/login", json={"email": "a@minhan.vn", "password": MEMBER_PW})
    assert r.status_code == 200 and r.json()["company"] and r.json()["portals"] == {"member": True, "partner": True}
    assert m.get("/api/partner/auth/me").status_code == 200
    assert m.get("/api/partner/auth/me").json()["portals"] == {"member": True, "partner": True}
    q = new_client()
    r = q.post("/api/partner/auth/login", json={"email": "a@minhan.vn", "password": MEMBER_PW})
    assert r.status_code == 200 and r.json()["code"].startswith("DT-")
    assert q.get("/api/member/wallet").status_code == 200
    assert "Path=/api;" in r.headers["set-cookie"] and "HttpOnly" in r.headers["set-cookie"]

    # đăng xuất 1 cổng = đăng xuất cả 2
    assert q.post("/api/member/auth/logout").status_code == 204
    assert q.get("/api/partner/auth/me").status_code == 401
    assert q.get("/api/member/auth/me").status_code == 401


def test_partner_only_account_on_member_login(partner):
    c = new_client()
    r = c.post("/api/member/auth/login", json={"email": "binh@gmail.com", "password": PARTNER_PW})
    assert r.status_code == 200 and r.json()["portals"] == {"member": False, "partner": True}
    assert r.json()["redirect"] == "/doi-tac/xac-thuc"  # chưa xác thực email
    assert c.get("/api/partner/auth/me").status_code == 200
    assert c.get("/api/member/auth/me").status_code == 401


def test_password_change_and_reset_apply_to_both_portals(client, otp_mail, monkeypatch):
    from app.services import notify

    register(client)
    assert new_client().post("/api/partner/auth/register", json=signup_form(email="a@minhan.vn", password=MEMBER_PW)).status_code == 201
    m = new_client()
    m.post("/api/member/auth/login", json={"email": "a@minhan.vn", "password": MEMBER_PW})
    assert m.post("/api/member/auth/password", json={"current_password": MEMBER_PW, "new_password": "moi-12345678"}).status_code == 204
    r = new_client().post("/api/partner/auth/login", json={"email": "a@minhan.vn", "password": "moi-12345678"})
    assert r.status_code == 200 and r.json()["code"].startswith("DT-")

    tokens: list[str] = []
    monkeypatch.setattr(notify, "send_partner_password_reset", lambda cfg, email, name, token: tokens.append(token) or True)
    new_client().post("/api/partner/auth/forgot", json={"email": "a@minhan.vn"})
    assert new_client().post("/api/partner/auth/reset", json={"token": tokens[0], "password": "lan-ba-12345678"}).status_code == 204
    assert m.get("/api/member/auth/me").status_code == 401  # đặt lại mật khẩu → đăng xuất mọi phiên cả 2 cổng
    assert new_client().post("/api/member/auth/login", json={"email": "a@minhan.vn", "password": "lan-ba-12345678"}).json()["company"]


def test_partner_email_registers_as_member_with_same_password(client, partner):
    from tests.conftest import valid_form

    r = client.post("/api/registrations", json=valid_form(email="binh@gmail.com"))
    assert r.status_code == 409 and "password" in r.json()["fields"]
    r = client.post("/api/registrations", json=valid_form(email="binh@gmail.com", password=PARTNER_PW, password_confirm=PARTNER_PW))
    assert r.status_code == 200, r.text
    r = new_client().post("/api/member/auth/login", json={"email": "binh@gmail.com", "password": PARTNER_PW})
    assert r.status_code == 200 and r.json()["portals"] == {"member": True, "partner": True}


def test_change_password(partner):
    assert partner.post("/api/partner/auth/password", json={"current_password": "sai", "new_password": "moi-12345678"}).status_code == 400
    assert partner.post("/api/partner/auth/password", json={"current_password": PARTNER_PW, "new_password": "moi-12345678"}).status_code == 204
    c = new_client()
    assert c.post("/api/partner/auth/login", json={"email": "binh@gmail.com", "password": "moi-12345678"}).status_code == 200


def test_forgot_and_reset_password(partner, monkeypatch):
    from app.services import notify

    tokens: list[str] = []
    monkeypatch.setattr(notify, "send_partner_password_reset", lambda cfg, email, name, token: tokens.append(token) or True)

    c = new_client()
    r1 = c.post("/api/partner/auth/forgot", json={"email": "khong-co@gmail.com"})
    r2 = c.post("/api/partner/auth/forgot", json={"email": "binh@gmail.com"})
    assert r1.json()["message"] == r2.json()["message"]  # không lộ email nào có tài khoản
    assert len(tokens) == 1

    assert c.post("/api/partner/auth/reset", json={"token": "sai", "password": "moi-12345678"}).status_code == 400
    assert c.post("/api/partner/auth/reset", json={"token": tokens[0], "password": "moi-12345678"}).status_code == 204
    assert c.post("/api/partner/auth/reset", json={"token": tokens[0], "password": "lan-hai-123456"}).status_code == 400  # dùng 1 lần
    # phiên cũ bị đăng xuất
    assert partner.get("/api/partner/auth/me").status_code == 401
    assert c.post("/api/partner/auth/login", json={"email": "binh@gmail.com", "password": "moi-12345678"}).status_code == 200


def test_options():
    j = new_client().get("/api/partner/options").json()
    assert "Bao bì & in ấn" in j["industries"] and "Bắc Ninh" in j["regions"] and j["kinds"]["org"] == "Tổ chức"


# ------------------------------------------------------------------ quản trị


def _pid() -> int:
    with new_session() as db:
        return db.scalar(select(PartnerUser.id))


def test_admin_list_and_manual_email_verify(partner, staff):
    r = staff.get("/api/admin/partners?verified=no")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 1 and j["counts"] == {"all": 1, "unverified": 1}
    assert j["items"][0]["email_verified"] is False and j["items"][0]["status"] == "active"
    assert staff.get("/api/admin/partners?q=0912345").json()["total"] == 1
    assert staff.get("/api/admin/partners?q=khong-ai").json()["total"] == 0

    pid = _pid()
    r = staff.post(f"/api/admin/partners/{pid}/verify-email", json={"note": "Đã gọi xác nhận"})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    assert "Đã gọi xác nhận" in r.json()["events"][0]["content"] and r.json()["events"][0]["actor"] == "Nhân Viên"
    assert staff.post(f"/api/admin/partners/{pid}/verify-email", json={}).status_code == 409
    assert partner.get("/api/partner/auth/me").json()["email_verified"] is True
    assert staff.get("/api/admin/partners?verified=no").json()["total"] == 0


def test_admin_partner_api_requires_admin_login(partner, otp_mail):
    assert new_client().get("/api/admin/partners").status_code == 401
    assert partner.get("/api/admin/partners").status_code == 401  # cookie đối tác không mở được trang quản trị


def test_lock_and_tier_admin_only(partner, staff, admin):
    pid = _pid()
    assert staff.patch(f"/api/admin/partners/{pid}", json={"status": "locked", "reason": "Gian lận"}).status_code == 403
    assert staff.patch(f"/api/admin/partners/{pid}", json={"tier": "silver"}).status_code == 403
    r = staff.patch(f"/api/admin/partners/{pid}", json={"note": "Môi giới KCN Quế Võ"})
    assert r.status_code == 200 and r.json()["note"] == "Môi giới KCN Quế Võ"

    assert admin.patch(f"/api/admin/partners/{pid}", json={"status": "locked"}).status_code == 422  # thiếu lý do
    r = admin.patch(f"/api/admin/partners/{pid}", json={"status": "locked", "reason": "Nghi tài khoản ảo"})
    assert r.status_code == 200 and r.json()["status"] == "locked"
    # khoá → mất phiên, không đăng nhập lại được
    assert partner.get("/api/partner/auth/me").status_code == 401
    with new_session() as db:
        assert db.scalar(select(PartnerSession.id)) is None
    r = new_client().post("/api/partner/auth/login", json={"email": "binh@gmail.com", "password": PARTNER_PW})
    assert r.status_code == 403

    r = admin.patch(f"/api/admin/partners/{pid}", json={"status": "active", "tier": "silver", "reason": "Đạt điều kiện Bạc"})
    assert r.status_code == 200 and r.json()["tier"] == "silver" and r.json()["tier_label"] == "Bạc"
    kinds = [e["kind"] for e in r.json()["events"]]
    assert kinds[:3] == ["tier", "status", "status"] and "note" in kinds and kinds[-1] == "created"
    assert new_client().post("/api/partner/auth/login", json={"email": "binh@gmail.com", "password": PARTNER_PW}).status_code == 200


def test_otp_email_is_sent_via_mail_or_logged(monkeypatch, caplog):
    """Không monkeypatch deliver: chưa cấu hình mail → ghi log; có mail → gửi email chứa mã."""
    from app.config import get_settings
    from app.services import notify, otp

    cfg = get_settings()
    with caplog.at_level("WARNING"):
        assert otp.deliver(cfg, "a@b.vn", "123456", "An") == "log"
    assert "123456" in caplog.text

    sent = []
    monkeypatch.setattr(notify, "mail_provider", lambda c: "smtp")
    monkeypatch.setattr(notify, "send_mail", lambda c, subject, body, to=None, **kw: sent.append((to, subject, body)) or True)
    assert otp.deliver(cfg, "a@b.vn", "654321", "An") == "email"
    assert sent and sent[0][0] == "a@b.vn" and "654321" in sent[0][2] and "/xac-thuc" in sent[0][2]


def test_changing_email_invalidates_code(partner, otp_mail):
    with new_session() as db:
        p = db.scalar(select(PartnerUser))
        p.email = "khac@gmail.com"
        db.commit()
    assert partner.post("/api/partner/auth/otp/verify", json={"code": otp_mail[-1][1]}).status_code == 400
