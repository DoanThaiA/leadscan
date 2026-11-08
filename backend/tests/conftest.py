import os

os.environ.setdefault("LEADSCAN_SCRYPT_N", "1024")  # băm mật khẩu nhanh khi test

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.config import get_settings

ADMIN_PW = "matkhau-admin-123"
STAFF_PW = "matkhau-staff-123"
MEMBER_PW = "matkhau-khach-123"


def _clear_caches():
    get_settings.cache_clear()
    dbmod.get_engine.cache_clear()
    dbmod._session_factory.cache_clear()


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    # Mặc định SQLite; đặt LEADSCAN_TEST_DATABASE_URL (PostgreSQL) để chạy test trên đúng loại DB của production
    pg = os.environ.get("LEADSCAN_TEST_DATABASE_URL")
    monkeypatch.setenv("LEADSCAN_DATABASE_URL", pg or f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("LEADSCAN_NOTIFY_EMAIL", "")
    monkeypatch.setenv("LEADSCAN_CLIENT_IP_HEADER", "")
    monkeypatch.setenv("LEADSCAN_COOKIE_SECURE", "false")  # TestClient chạy http
    monkeypatch.setenv("LEADSCAN_CELERY_EAGER", "true")
    monkeypatch.setenv("LEADSCAN_PAYMENT_PROVIDER", "mock")
    monkeypatch.setenv("LEADSCAN_PAYMENT_BANK_BIN", "970436")
    monkeypatch.setenv("LEADSCAN_PAYMENT_ACCOUNT_NO", "0011001234567")
    monkeypatch.setenv("LEADSCAN_PAYMENT_ACCOUNT_NAME", "CONG TY LEADSCAN")
    monkeypatch.setenv("LEADSCAN_SMTP_HOST", "")
    monkeypatch.setenv("LEADSCAN_RESEND_API_KEY", "")  # test không bao giờ gửi mail thật
    _clear_caches()
    from app import models, worker  # noqa: F401

    worker.celery_app.conf.task_always_eager = True  # task chạy ngay trong test, không cần Redis
    if pg:
        dbmod.Base.metadata.drop_all(dbmod.get_engine())
    dbmod.Base.metadata.create_all(dbmod.get_engine())
    yield
    if pg:
        dbmod.Base.metadata.drop_all(dbmod.get_engine())
    dbmod.get_engine().dispose()
    _clear_caches()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _make_user(email, name, role, pw):
    from app.models import AdminUser
    from app.security import hash_password

    with dbmod.new_session() as db:
        u = AdminUser(email=email, full_name=name, role=role, password_hash=hash_password(pw))
        db.add(u)
        db.commit()
        return u.id


@pytest.fixture
def admin_id():
    return _make_user("admin@leadscan.vn", "Quản Trị", "admin", ADMIN_PW)


@pytest.fixture
def staff_id():
    return _make_user("staff@leadscan.vn", "Nhân Viên", "staff", STAFF_PW)


@pytest.fixture
def admin(client, admin_id):
    """TestClient đã đăng nhập bằng tài khoản admin."""
    r = client.post("/api/admin/auth/login", json={"email": "admin@leadscan.vn", "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def staff(staff_id):
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/admin/auth/login", json={"email": "staff@leadscan.vn", "password": STAFF_PW})
    assert r.status_code == 200, r.text
    return c


def valid_form(**over) -> dict:
    form = {
        "company_name": "Công ty TNHH Bao Bì Minh An",
        "tax_code": "0101234567",
        "industries": ["Bao bì & in ấn", "Nhựa & cao su"],
        "company_size": "50–199 nhân sự",
        "province": "Bắc Ninh",
        "address": "KCN Quế Võ",
        "website": "minhan.vn",
        "contact_name": "Nguyễn Văn A",
        "position": "Giám đốc kinh doanh",
        "email": "A@MinhAn.vn",
        "phone": "0901 234 567",
        "agree": True,
        "website_url": "",
        "elapsed_ms": 15000,
        "password": MEMBER_PW,
        "password_confirm": MEMBER_PW,
    }
    form.update(over)
    if "tax_code" in over and "email" not in over:  # mỗi email chỉ 1 tài khoản → sinh email theo MST
        form["email"] = f"lienhe{''.join(ch for ch in over['tax_code'] if ch.isdigit())}@minhan.vn"
    return form


def register(client, **over) -> int:
    """Gửi form đăng ký, trả về id khách hàng vừa tạo."""
    from sqlalchemy import select

    from app.models import Company

    r = client.post("/api/registrations", json=valid_form(**over))
    assert r.status_code == 200, r.text
    with dbmod.new_session() as db:
        return db.scalar(select(Company.id).where(Company.code == r.json()["code"]))
