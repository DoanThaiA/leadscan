import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cli import main as cli_main
from app.db import new_session
from app.models import AdminSession, AdminUser, Company
from app.registration_form import normalize
from tests.conftest import ADMIN_PW, register, valid_form

# ------------------------------------------------------------------ đăng nhập


def test_chua_dang_nhap_bi_chan(client):
    assert client.get("/api/admin/companies").status_code == 401
    assert client.get("/api/admin/auth/me").status_code == 401


def test_dang_nhap_sai_va_dung(client, admin_id):
    bad = client.post("/api/admin/auth/login", json={"email": "admin@leadscan.vn", "password": "sai-mat-khau"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Email hoặc mật khẩu không đúng."
    nobody = client.post("/api/admin/auth/login", json={"email": "khong-co@x.vn", "password": ADMIN_PW})
    assert nobody.status_code == 401

    ok = client.post("/api/admin/auth/login", json={"email": " ADMIN@leadscan.vn ", "password": ADMIN_PW})
    assert ok.status_code == 200 and ok.json()["role"] == "admin"
    assert "httponly" in ok.headers["set-cookie"].lower()
    assert client.get("/api/admin/auth/me").json()["email"] == "admin@leadscan.vn"

    assert client.post("/api/admin/auth/logout").status_code == 204
    assert client.get("/api/admin/auth/me").status_code == 401


def test_khoa_sau_nhieu_lan_dang_nhap_sai(client, admin_id):
    for _ in range(10):
        client.post("/api/admin/auth/login", json={"email": "admin@leadscan.vn", "password": "sai-mat-khau"})
    r = client.post("/api/admin/auth/login", json={"email": "admin@leadscan.vn", "password": ADMIN_PW})
    assert r.status_code == 429


def test_doi_mat_khau(admin):
    r = admin.post("/api/admin/auth/password", json={"current_password": "sai", "new_password": "mat-khau-moi-123"})
    assert r.status_code == 400
    r = admin.post("/api/admin/auth/password", json={"current_password": ADMIN_PW, "new_password": "mat-khau-moi-123"})
    assert r.status_code == 204
    admin.post("/api/admin/auth/logout")
    assert admin.post("/api/admin/auth/login", json={"email": "admin@leadscan.vn", "password": "mat-khau-moi-123"}).status_code == 200


def test_thao_tac_ghi_tu_trang_khac_bi_chan(admin):
    cid = register(admin)
    r = admin.patch(f"/api/admin/companies/{cid}", json={"status": "active"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


# ------------------------------------------------------------------ khách hàng


def test_danh_sach_tim_kiem_loc_phan_trang(admin, staff_id):
    a = register(admin, company_name="Bao Bì Minh An", tax_code="0100000001")
    b = register(admin, company_name="Nhựa Hoàng Long", tax_code="0100000002", email="long@hl.vn", phone="0988777666")
    register(admin, company_name="Điện tử Sao Mai", tax_code="0100000003")
    admin.patch(f"/api/admin/companies/{b}", json={"status": "contacted", "assigned_to_id": staff_id})

    all_ = admin.get("/api/admin/companies").json()
    assert all_["total"] == 3 and [i["id"] for i in all_["items"]][-1] == a  # mới nhất trước
    assert all_["items"][0]["primary_contact"]["full_name"] == "Nguyễn Văn A"

    def ids(**params):
        return [i["id"] for i in admin.get("/api/admin/companies", params=params).json()["items"]]

    assert ids(q="hoàng long") == [b] or ids(q="Hoàng Long") == [b]
    assert ids(q="0100000001") == [a]
    assert ids(q="long@hl.vn") == [b]
    assert ids(q="0988 777") == [b]  # tìm theo SĐT người liên hệ
    assert ids(status="contacted") == [b]
    assert ids(assigned=str(staff_id)) == [b]
    assert len(ids(assigned="none")) == 2
    page2 = admin.get("/api/admin/companies", params={"page": 2, "page_size": 2}).json()
    assert page2["total"] == 3 and len(page2["items"]) == 1


def test_chi_tiet_va_cap_nhat_ghi_lich_su(admin, staff_id):
    cid = register(admin)
    r = admin.patch(
        f"/api/admin/companies/{cid}",
        json={"name": "Minh An Packaging", "status": "contacted", "assigned_to_id": staff_id},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Minh An Packaging" and d["status"] == "contacted" and d["assigned_to"]["full_name"] == "Nhân Viên"
    kinds = [a["kind"] for a in d["activities"]]
    assert kinds[:3] == ["assign", "status", "update"] and kinds[-1] == "created"
    assert d["activities"][1]["content"] == "Mới đăng ký → Đã liên hệ"
    assert d["activities"][0]["actor"]["full_name"] == "Quản Trị"
    assert d["created_at"].endswith("Z")

    r = admin.patch(f"/api/admin/companies/{cid}", json={"unassign": True})
    assert r.json()["assigned_to"] is None


def test_cap_nhat_sai_du_lieu_tra_loi_theo_truong(admin):
    cid = register(admin)
    r = admin.patch(f"/api/admin/companies/{cid}", json={"tax_code": "12", "status": "xyz", "company_size": "?"})
    assert r.status_code == 422
    assert set(r.json()["fields"]) == {"tax_code", "status", "company_size"}
    assert r.json()["fields"]["tax_code"] == "Mã số thuế gồm 10 hoặc 13 chữ số."


def test_doi_mst_trung_khach_khac(admin):
    register(admin, tax_code="0100000001")
    b = register(admin, tax_code="0100000002")
    r = admin.patch(f"/api/admin/companies/{b}", json={"tax_code": "0100000001"})
    assert r.status_code == 409


def test_khong_tim_thay(admin):
    assert admin.get("/api/admin/companies/999").status_code == 404


def test_nguoi_lien_he(admin):
    cid = register(admin)
    r = admin.post(f"/api/admin/companies/{cid}/contacts", json={"full_name": "Trần B", "phone": "0912 000 111", "is_primary": True})
    assert r.status_code == 201
    new_id = r.json()["id"]
    contacts = admin.get(f"/api/admin/companies/{cid}").json()["contacts"]
    assert [c["is_primary"] for c in contacts] == [True, False] and contacts[0]["id"] == new_id

    bad = admin.post(f"/api/admin/companies/{cid}/contacts", json={"full_name": "X", "email": "sai"})
    assert bad.status_code == 422 and "email" in bad.json()["fields"]

    first_id = contacts[1]["id"]
    assert admin.patch(f"/api/admin/contacts/{first_id}", json={"full_name": "Nguyễn Văn A2", "is_primary": True}).status_code == 200
    assert admin.delete(f"/api/admin/contacts/{first_id}").status_code == 204
    remaining = admin.get(f"/api/admin/companies/{cid}").json()["contacts"]
    assert len(remaining) == 1 and remaining[0]["is_primary"]  # người còn lại thành liên hệ chính
    assert admin.delete(f"/api/admin/contacts/{remaining[0]['id']}").status_code == 400


def test_chan_dung_va_ghi_chu(admin):
    cid = register(admin)
    r = admin.put(
        f"/api/admin/companies/{cid}/profile",
        json={"offering": "Màng PE", "target_regions": ["Miền Nam", "Sao Hoả"], "expected_tickets": "bừa"},
    )
    assert r.status_code == 200
    assert r.json()["target_regions"] == ["Miền Nam"] and r.json()["expected_tickets"] == ""
    assert admin.post(f"/api/admin/companies/{cid}/notes", json={"content": "Đã gọi, hẹn demo thứ 5"}).status_code == 201
    acts = admin.get(f"/api/admin/companies/{cid}").json()["activities"]
    assert acts[0]["kind"] == "note" and acts[0]["content"] == "Đã gọi, hẹn demo thứ 5"


def test_thong_ke(admin):
    a = register(admin, tax_code="0100000001")
    register(admin, tax_code="0100000002")
    admin.patch(f"/api/admin/companies/{a}", json={"status": "active"})
    s = admin.get("/api/admin/stats").json()
    assert s["total"] == 2 and s["by_status"]["active"] == 1 and s["by_status"]["new"] == 1
    assert s["new_today"] == 2 and s["new_7d"] == 2 and len(s["daily"]) == 30 and s["daily"][-1]["count"] == 2
    assert len(s["recent"]) == 2


def test_meta(admin):
    m = admin.get("/api/admin/meta").json()
    assert m["statuses"]["active"] == "Thành viên" and m["staff"][0]["full_name"] == "Quản Trị"


# ------------------------------------------------------------------ phân quyền & nhân viên


def test_nhan_vien_khong_quan_ly_duoc_tai_khoan_va_khong_xoa_khach(client, staff):
    cid = register(staff)
    assert staff.get("/api/admin/users").status_code == 403
    assert staff.delete(f"/api/admin/companies/{cid}").status_code == 403
    assert staff.patch(f"/api/admin/companies/{cid}", json={"status": "contacted"}).status_code == 200


def test_admin_quan_ly_nhan_vien(admin, admin_id):
    r = admin.post("/api/admin/users", json={"email": "Moi@LeadScan.vn", "full_name": "Người Mới", "password": "mat-khau-123456"})
    assert r.status_code == 201 and r.json()["email"] == "moi@leadscan.vn" and r.json()["role"] == "staff"
    uid = r.json()["id"]
    assert admin.post("/api/admin/users", json={"email": "moi@leadscan.vn", "full_name": "X", "password": "mat-khau-123456"}).status_code == 409
    assert admin.post("/api/admin/users", json={"email": "x@y.vn", "full_name": "X", "password": "ngan"}).status_code == 422

    # người mới đăng nhập được; bị khoá thì mất phiên ngay
    from app.main import app

    other = TestClient(app)
    assert other.post("/api/admin/auth/login", json={"email": "moi@leadscan.vn", "password": "mat-khau-123456"}).status_code == 200
    assert admin.patch(f"/api/admin/users/{uid}", json={"is_active": False}).json()["is_active"] is False
    assert other.get("/api/admin/auth/me").status_code == 401
    with new_session() as db:
        assert db.scalars(select(AdminSession).where(AdminSession.user_id == uid)).all() == []

    # không tự khoá / tự hạ quyền
    assert admin.patch(f"/api/admin/users/{admin_id}", json={"is_active": False}).status_code == 400
    assert admin.patch(f"/api/admin/users/{admin_id}", json={"role": "staff"}).status_code == 400
    assert len(admin.get("/api/admin/users").json()) == 2


def test_admin_xoa_khach_hang(admin):
    cid = register(admin)
    assert admin.delete(f"/api/admin/companies/{cid}").status_code == 204
    with new_session() as db:
        assert db.scalar(select(Company)) is None


# ------------------------------------------------------------------ lệnh CLI


def test_cli_create_admin(monkeypatch, capsys):
    monkeypatch.setenv("LEADSCAN_ADMIN_PASSWORD", "mat-khau-cli-123")
    assert cli_main(["create-admin", "--email", "Boss@LeadScan.vn", "--name", "Sếp"]) == 0
    assert cli_main(["create-admin", "--email", "boss@leadscan.vn"]) == 0  # chạy lại = đặt lại mật khẩu
    with new_session() as db:
        (u,) = db.scalars(select(AdminUser)).all()
    assert u.email == "boss@leadscan.vn" and u.role == "admin" and u.full_name == "Sếp"
    monkeypatch.setenv("LEADSCAN_ADMIN_PASSWORD", "ngan")
    assert cli_main(["create-admin", "--email", "a@b.vn"]) == 1


def test_cli_import_legacy(tmp_path):
    d, _ = normalize(valid_form())
    (tmp_path / "LS-20261107-70C3.json").write_text(
        json.dumps({"code": "LS-20261107-70C3", "status": "synced", "created_at": "2026-11-07T11:57:21+07:00", "ip": "1.2.3.4", "data": d}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert cli_main(["import-legacy", str(tmp_path)]) == 0
    assert cli_main(["import-legacy", str(tmp_path)]) == 0  # chạy lại không nhân đôi
    with new_session() as db:
        (c,) = db.scalars(select(Company)).unique().all()
        assert c.source == "landing-php" and c.contacts[0].email == "a@minhan.vn" and c.profile.offering
        assert c.created_at.hour == 4  # 11:57 giờ VN = 04:57 UTC
