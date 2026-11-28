"""Cổng sự kiện c89.leadscan.net / epc.leadscan.net: mỗi cổng đăng & quản lý sự kiện riêng, admin LeadScan xem tổng hợp.

Trang của request lấy từ header X-LeadScan-Site (Nginx đặt ở production). Quyền dữ liệu theo tài khoản (AdminUser.site).
"""

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.models import AdminUser
from app.security import hash_password

from tests.conftest import ADMIN_PW
from tests.test_events import EVENTS, REGS, event, registration

PW = "matkhau-cong-123"
C89 = {"X-LeadScan-Site": "c89"}
EPC = {"X-LeadScan-Site": "epc"}


def _user(email: str, site: str | None, role: str = "admin") -> None:
    with dbmod.new_session() as db:
        db.add(AdminUser(email=email, full_name=email, role=role, site=site, password_hash=hash_password(PW)))
        db.commit()


def _login(email: str, headers: dict | None = None, pw: str = PW) -> TestClient:
    from app.main import app

    c = TestClient(app, headers=headers or {})
    r = c.post("/api/admin/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def c89_admin():
    _user("c89@ceo1989.vn", "c89")
    return _login("c89@ceo1989.vn", C89)


@pytest.fixture
def epc_admin():
    _user("epc@epc.vn", "epc")
    return _login("epc@epc.vn", EPC)


# ------------------------------------------------------------------ đăng nhập


def test_tai_khoan_cong_chi_dang_nhap_o_cong_cua_minh(client):
    _user("c89@ceo1989.vn", "c89")
    login = {"email": "c89@ceo1989.vn", "password": PW}
    r = client.post("/api/admin/auth/login", json=login)  # leadscan.net/admin
    assert r.status_code == 403 and "c89.leadscan.net/admin" in r.json()["detail"]
    assert client.post("/api/admin/auth/login", json=login, headers=EPC).status_code == 403
    assert client.post("/api/admin/auth/login", json=login, headers=C89).status_code == 200


def test_quan_tri_leadscan_vao_duoc_cong_nhan_vien_thuong_khong(admin_id, staff_id, client):
    assert client.post("/api/admin/auth/login", json={"email": "admin@leadscan.vn", "password": ADMIN_PW}, headers=C89).status_code == 200
    r = client.post("/api/admin/auth/login", json={"email": "staff@leadscan.vn", "password": "matkhau-staff-123"}, headers=C89)
    assert r.status_code == 403


# ------------------------------------------------------------------ phân quyền API


def test_tai_khoan_cong_bi_chan_moi_api_ngoai_su_kien(c89_admin):
    for path in ("/api/admin/companies", "/api/admin/users", "/api/admin/stats", "/api/admin/jobs", "/api/admin/enrich/companies"):
        assert c89_admin.get(path).status_code == 403, path
    assert c89_admin.get("/api/admin/auth/me").json()["site"] == "c89"
    assert c89_admin.get("/api/admin/meta").status_code == 200
    assert c89_admin.get(EVENTS).status_code == 200
    assert c89_admin.get("/api/admin/auth/me").json()["enrich_access"] is None


def test_meta_chi_hien_nhan_vien_cung_trang(admin, c89_admin):
    names = {s["full_name"] for s in admin.get("/api/admin/meta").json()["staff"]}
    assert "Quản Trị" in names and "c89@ceo1989.vn" not in names
    assert {s["full_name"] for s in c89_admin.get("/api/admin/meta").json()["staff"]} == {"c89@ceo1989.vn"}


# ------------------------------------------------------------------ mỗi cổng quản lý riêng


def test_cong_dang_su_kien_vao_cong_minh_khong_doi_duoc(c89_admin):
    e = c89_admin.post(EVENTS, json=event(site="epc")).json()
    assert e["site"] == "c89"  # gửi site khác cũng bị ép về cổng của tài khoản
    e2 = c89_admin.put(f"{EVENTS}/{e['id']}", json=event(site="leadscan")).json()
    assert e2["site"] == "c89"


def test_moi_cong_chi_thay_su_kien_cua_minh(admin, c89_admin, epc_admin):
    a = c89_admin.post(EVENTS, json=event(title="Sự kiện C89")).json()
    b = epc_admin.post(EVENTS, json=event(title="Sự kiện EPC")).json()
    lead = admin.post(EVENTS, json=event(title="Sự kiện LeadScan")).json()
    assert lead["site"] == "leadscan"

    assert [x["title"] for x in c89_admin.get(EVENTS).json()["items"]] == ["Sự kiện C89"]
    assert [x["title"] for x in epc_admin.get(EVENTS).json()["items"]] == ["Sự kiện EPC"]
    # sự kiện cổng khác: như không tồn tại
    assert c89_admin.get(f"{EVENTS}/{b['id']}").status_code == 404
    assert c89_admin.put(f"{EVENTS}/{b['id']}", json=event()).status_code == 404
    assert c89_admin.delete(f"{EVENTS}/{lead['id']}").status_code == 404

    # admin LeadScan: tổng hợp mọi trang, lọc được theo trang
    rows = admin.get(EVENTS).json()["items"]
    assert {(x["title"], x["site"]) for x in rows} == {("Sự kiện C89", "c89"), ("Sự kiện EPC", "epc"), ("Sự kiện LeadScan", "leadscan")}
    assert [x["title"] for x in admin.get(EVENTS + "?site=epc").json()["items"]] == ["Sự kiện EPC"]
    assert admin.get(f"{EVENTS}/{a['id']}").json()["site"] == "c89"
    assert admin.get(EVENTS + "/meta").json()["scope"] is None
    assert c89_admin.get(EVENTS + "/meta").json()["scope"] == "c89"


def test_dang_ky_tren_cong_va_tong_hop_ve_leadscan(admin, c89_admin, client):
    e = c89_admin.post(EVENTS, json=event()).json()
    # trang công khai: chỉ cổng c89 thấy sự kiện của c89
    assert client.get("/api/events", headers=C89).json()["items"][0]["slug"] == e["slug"]
    assert client.get("/api/events").json()["items"] == []
    assert client.get(f"/api/events/{e['slug']}").status_code == 404
    assert client.get(f"/api/events/{e['slug']}", headers=EPC).status_code == 404
    assert client.post(f"/api/events/{e['slug']}/register", json=registration()).status_code == 404

    r = client.post(f"/api/events/{e['slug']}/register", json=registration(), headers=C89)
    assert r.status_code == 200, r.text

    c89_regs = c89_admin.get(REGS).json()
    assert c89_regs["total"] == 1 and c89_regs["items"][0]["site"] == "c89"
    all_regs = admin.get(REGS).json()
    assert all_regs["total"] == 1 and all_regs["items"][0]["site"] == "c89"
    assert admin.get(REGS + "?site=epc").json()["total"] == 0


def test_cong_khac_khong_xem_duoc_dang_ky(c89_admin, epc_admin, client):
    e = c89_admin.post(EVENTS, json=event()).json()
    client.post(f"/api/events/{e['slug']}/register", json=registration(), headers=C89)
    rid = c89_admin.get(REGS).json()["items"][0]["id"]
    assert epc_admin.get(REGS).json()["total"] == 0
    for method, path in (("get", f"{REGS}/{rid}"), ("patch", f"{REGS}/{rid}"), ("get", f"{REGS}/{rid}/profile"), ("delete", f"{REGS}/{rid}")):
        kw = {"json": {"note": "x"}} if method == "patch" else {}
        assert getattr(epc_admin, method)(path, **kw).status_code == 404, path


def test_quan_tri_leadscan_o_cong_chi_thay_cong_do(admin_id, c89_admin):
    c89_admin.post(EVENTS, json=event(title="C89"))
    lead_at_c89 = _login("admin@leadscan.vn", C89, ADMIN_PW)
    assert [x["title"] for x in lead_at_c89.get(EVENTS).json()["items"]] == ["C89"]
    e = lead_at_c89.post(EVENTS, json=event(title="Đăng hộ C89")).json()
    assert e["site"] == "c89"


def test_admin_leadscan_chuyen_su_kien_sang_cong(admin, client):
    e = admin.post(EVENTS, json=event()).json()
    client.post(f"/api/events/{e['slug']}/register", json=registration())
    moved = admin.put(f"{EVENTS}/{e['id']}", json=event(site="c89")).json()
    assert moved["site"] == "c89"
    assert admin.get(REGS).json()["items"][0]["site"] == "c89"  # đăng ký đi theo sự kiện
    assert client.get(f"/api/events/{e['slug']}", headers=C89).status_code == 200


# ------------------------------------------------------------------ quản lý tài khoản cổng


def test_admin_leadscan_tao_tai_khoan_cong(admin):
    r = admin.post("/api/admin/users", json={"email": "ban@epc.vn", "full_name": "Ban EPC", "role": "staff", "site": "epc", "password": PW})
    assert r.status_code == 201 and r.json()["site"] == "epc"
    assert admin.post("/api/admin/users", json={"email": "x@x.vn", "full_name": "X", "site": "abc", "password": PW}).status_code == 422
    uid = r.json()["id"]
    assert admin.patch(f"/api/admin/users/{uid}", json={"site": ""}).json()["site"] is None


def test_nhan_vien_cong_khong_xoa_duoc(c89_admin):
    _user("nv@ceo1989.vn", "c89", role="staff")
    nv = _login("nv@ceo1989.vn", C89)
    e = c89_admin.post(EVENTS, json=event()).json()
    assert nv.delete(f"{EVENTS}/{e['id']}").status_code == 403
    assert c89_admin.delete(f"{EVENTS}/{e['id']}").status_code == 204


# ------------------------------------------------------------------ check-in bằng QR theo cổng


def test_check_in_chi_trong_cong_cua_minh(c89_admin, epc_admin, client):
    e = c89_admin.post(EVENTS, json=event()).json()
    code = client.post(f"/api/events/{e['slug']}/register", json=registration(), headers=C89).json()["code"]
    got = c89_admin.get(f"{REGS}/by-code/{code}")
    assert got.status_code == 200
    rid = got.json()["id"]
    assert epc_admin.get(f"{REGS}/by-code/{code}").status_code == 404
    assert epc_admin.post(f"{REGS}/{rid}/check-in").status_code == 404
    assert c89_admin.post(f"{REGS}/{rid}/check-in").json()["checked_in"] is True


def test_anh_qr_tren_cong_tro_ve_trang_quan_tri_cua_cong(client):
    import io

    from PIL import Image

    from app.services.events import checkin_qr_png

    on_c89 = client.get("/api/events/checkin-qr/SK7KQ4MX.png", headers=C89)
    assert on_c89.status_code == 200
    assert on_c89.content == checkin_qr_png("SK7KQ4MX", "c89") != checkin_qr_png("SK7KQ4MX")
    assert Image.open(io.BytesIO(on_c89.content)).format == "PNG"
