"""Phân hệ làm giàu dữ liệu theo MST — giai đoạn 1: nhập lô, bằng chứng, hồ sơ, phân quyền kho A/B."""

import base64
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from app import db as dbmod
from app.enrich.normalize import bo_dau, parse_mst
from tests.conftest import _make_user

PW = "matkhau-enrich-123"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def csv_file(rows: list[str]) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8")


BATCH = {"name": "Lô khách hàng tháng 11", "list_source": "CRM nội bộ", "purposes": ["ban_hang_b2b", "tham_dinh_kyc"]}


def import_csv(client, rows: list[str], file_name="ds.csv", **over):
    body = {**BATCH, **over, "file_name": file_name, "file_b64": b64(csv_file(rows))}
    return client.post("/api/admin/enrich/batches", json=body)


def login_as(enrich_role: str | None, email: str, role: str = "staff") -> TestClient:
    from app.main import app
    from app.models import AdminUser

    uid = _make_user(email, f"User {enrich_role}", role, PW)
    with dbmod.new_session() as db:
        db.get(AdminUser, uid).enrich_role = enrich_role
        db.commit()
    c = TestClient(app)
    r = c.post("/api/admin/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return c


def seed_person(mst="0101234567", **over) -> int:
    """Người + vai trò + liên hệ + bằng chứng trong kho B (giai đoạn 1 chưa có connector sinh dữ liệu người)."""
    from app.enrich import sources
    from app.models_enrich import EnrichContact, EnrichPerson, PersonEvidence, PersonRole

    with dbmod.new_session() as db:
        src = sources.ensure(db, sources.EDITOR)
        p = EnrichPerson(
            ho_ten=over.get("ho_ten", "Nguyễn Văn An"),
            ho_ten_khong_dau=bo_dau(over.get("ho_ten", "Nguyễn Văn An")),
            mst_ca_nhan=over.get("mst_ca_nhan", "8000000001"),
            nam_sinh=1975,
        )
        db.add(p)
        db.flush()
        db.add(PersonRole(person_id=p.id, company_mst=mst, chuc_danh="Tổng Giám đốc", chuc_danh_chuan="ceo", la_nguoi_quyet_dinh=True, source_code=src.code))
        db.add(EnrichContact(owner_type="person", owner_id=str(p.id), kind="email", value=over.get("email", "an@congty.vn"), source_code=src.code))
        db.add(PersonEvidence(person_id=p.id, field="ho_ten", value=p.ho_ten, source_code=src.code, source_url="https://congty.vn/ban-lanh-dao", excerpt="TGĐ Nguyễn Văn An", method="thu_cong"))
        db.commit()
        return p.id


# ------------------------------------------------------------------ chuẩn hoá


@pytest.mark.parametrize(
    "raw,expected,padded",
    [
        ("0101234567", "0101234567", False),
        (" 0101 234 567 ", "0101234567", False),
        ("0101234567-001", "0101234567-001", False),
        ("0101234567001", "0101234567-001", False),
        (101234567, "0101234567", True),  # Excel làm rơi số 0 đầu
        (101234567.0, "0101234567", True),
        ("101234567", "0101234567", True),
        ("101234567001", "0101234567-001", True),
    ],
)
def test_parse_mst_valid(raw, expected, padded):
    r = parse_mst(raw)
    assert r.mst == expected and r.padded is padded


@pytest.mark.parametrize("raw", ["", None, "12345", "01012345678", "0101A34567", "0101234567-01", 1.5, True])
def test_parse_mst_invalid(raw):
    r = parse_mst(raw)
    assert r.mst is None and r.error


def test_bo_dau():
    assert bo_dau("  Công ty  TNHH Đại Việt ") == "cong ty tnhh dai viet"


# ------------------------------------------------------------------ nhập lô (A01, A02)


def test_preview_reports_valid_duplicate_invalid(admin):
    rows = ["MST,Tên doanh nghiệp", "0101234567,Công ty A", "0101234567,Công ty A lặp", "abc,Sai", "101234568,Rơi số 0", "", "0101234569-001,Chi nhánh"]
    r = admin.post("/api/admin/enrich/batches/preview", json={"file_name": "ds.csv", "file_b64": b64(csv_file(rows))})
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["total_rows"] == 5
    assert rep["valid"] == 3 and rep["duplicate_in_file"] == 1 and rep["invalid"] == 1 and rep["zero_padded"] == 1
    assert rep["invalid_rows"][0] == {"row": 4, "value": "abc", "reason": "Có ký tự không phải chữ số"}
    assert rep["duplicate_rows"][0] == {"row": 3, "mst": "0101234567", "first_row": 2}
    assert rep["has_name_column"] is True and rep["new"] == 3
    # xem trước không ghi gì
    assert admin.get("/api/admin/enrich/stats").json()["total"] == 0


def test_import_creates_companies_with_evidence_and_purposes(admin):
    r = import_csv(admin, ["MST;Tên doanh nghiệp", "0101234567;Công ty Cổ phần Đại Việt", "0309876543;"])
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["mst_count"] == 2 and b["new_count"] == 2 and b["purposes"] == ["ban_hang_b2b", "tham_dinh_kyc"]

    p = admin.get("/api/admin/enrich/companies/0101234567").json()
    shown = {f["key"]: f for f in p["fields"]}
    assert {k for k, f in shown.items() if f["source"]} == {"mst", "ten"}  # chỉ hai trường có nguồn
    assert shown["dia_chi"]["value"] is None and shown["dia_chi"]["evidence_count"] == 0  # vẫn hiển thị, để trống
    assert shown["ten"]["value"] == "Công ty Cổ phần Đại Việt"
    assert shown["ten"]["source"]["code"] == "nhap_lo" and shown["ten"]["source_url"] == "ds.csv#dong=2"
    assert shown["ten"]["fetched_at"]
    assert "Địa chỉ trụ sở" in p["missing_fields"]
    assert p["purposes"] == ["ban_hang_b2b", "tham_dinh_kyc"]
    assert p["batches"][0]["row_no"] == 2

    # dòng không có tên → chỉ có MST
    p2 = admin.get("/api/admin/enrich/companies/0309876543").json()
    assert [f["key"] for f in p2["fields"] if f["source"]] == ["mst"]

    ev = admin.get("/api/admin/enrich/companies/0101234567/evidence").json()
    assert {e["field"] for e in ev} == {"mst", "ten"}
    assert all(e["in_use"] and e["batch"]["id"] == b["id"] and e["excerpt"].startswith("Dòng 2:") for e in ev)

    # tìm không dấu + theo MST
    assert admin.get("/api/admin/enrich/companies?q=dai viet").json()["total"] == 1
    assert admin.get("/api/admin/enrich/companies?q=0309").json()["items"][0]["mst"] == "0309876543"
    assert admin.get(f"/api/admin/enrich/companies?batch_id={b['id']}").json()["total"] == 2


def test_reimport_keeps_old_value_as_evidence_and_logs_change(admin):
    import_csv(admin, ["MST,Tên", "0101234567,Công ty A"])
    r = import_csv(admin, ["MST,Tên", "0101234567,Công ty A Mới", "0201234567,Công ty B"], purposes=["nghien_cuu_thi_truong"])
    b2 = r.json()
    assert b2["mst_count"] == 2 and b2["new_count"] == 1 and b2["report"]["existing"] == 1

    p = admin.get("/api/admin/enrich/companies/0101234567").json()
    ten = next(f for f in p["fields"] if f["key"] == "ten")
    assert ten["value"] == "Công ty A Mới" and ten["conflict"] is True and ten["evidence_count"] == 2
    assert p["purposes"] == ["ban_hang_b2b", "tham_dinh_kyc", "nghien_cuu_thi_truong"]
    assert len(p["batches"]) == 2
    assert p["changes"][0]["old_value"] == "Công ty A" and p["changes"][0]["new_value"] == "Công ty A Mới"

    ev = admin.get("/api/admin/enrich/companies/0101234567/evidence").json()
    names = [(e["value"], e["in_use"]) for e in ev if e["field"] == "ten"]
    assert ("Công ty A", False) in names and ("Công ty A Mới", True) in names


def test_import_xlsx_restores_leading_zero(admin):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Mã số thuế", "Tên công ty"])
    ws.append([101234567, "Công ty Số"])  # Excel lưu dạng số → mất số 0
    ws.append(["0309876543", "Công ty Chữ"])
    buf = io.BytesIO()
    wb.save(buf)
    r = admin.post("/api/admin/enrich/batches", json={**BATCH, "file_name": "ds.xlsx", "file_b64": b64(buf.getvalue())})
    assert r.status_code == 201, r.text
    assert r.json()["report"]["zero_padded"] == 1
    assert admin.get("/api/admin/enrich/companies/0101234567").json()["ten"] == "Công ty Số"


def _xlsx(rows: list[list]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.create_sheet("Ghi chu").append(["Sheet phụ — không được nhập"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


EXTRA_FILE = [
    ["Ngành nghề", "Tên doanh nghiệp", "MST", "Địa chỉ trụ sở", "Điện thoại", "Phân nhóm sản phẩm", "Mã HS (4 số)", "Số dòng hàng", "Số CCCD"],
    ["Dệt may", "Công ty CP May Xuất khẩu A", "0101234567", "Số 1 Lê Lợi, Phường Bến Thành, TP Hồ Chí Minh", 974102195, "Quần áo và phụ kiện may mặc", "6104, 6204", 2, "001200000001"],
    ["Điện tử", "Công ty TNHH Linh kiện B", "0309876543001", "KCN Quế Võ, Tỉnh Bắc Ninh", "8.40948E+11 / 84988062325", "Linh kiện điện tử; Bo mạch", "8542", 1, ""],
]


def test_import_extra_columns_into_profile(admin):
    data = _xlsx(EXTRA_FILE)
    pre = admin.post("/api/admin/enrich/batches/preview", json={"file_name": "ds.xlsx", "file_b64": b64(data)}).json()
    cols = {c["header"]: (c["field"], c["filled"]) for c in pre["columns"]}
    assert cols == {
        "Ngành nghề": ("nhom_nganh", 2),
        "Địa chỉ trụ sở": ("dia_chi", 2),
        "Điện thoại": ("dien_thoai", 2),
        "Phân nhóm sản phẩm": ("nhom_san_pham", 2),
        "Mã HS (4 số)": ("ma_hs", 2),
    }
    assert pre["ignored_columns"] == ["Số dòng hàng"] and pre["sensitive_columns"] == ["Số CCCD"]
    assert pre["phones"]["ok"] == 2 and pre["phones"]["bad"] == 1
    assert pre["phones"]["bad_rows"][0]["unreadable"] == ["8.40948E+11"]

    r = admin.post("/api/admin/enrich/batches", json={**BATCH, "file_name": "ds.xlsx", "file_b64": b64(data)})
    assert r.status_code == 201, r.text
    p = admin.get("/api/admin/enrich/companies/0101234567").json()
    shown = {f["key"]: f["value"] for f in p["fields"]}
    assert shown["nhom_nganh"] == "Dệt may"
    assert shown["nhom_san_pham"] == ["Quần áo và phụ kiện may mặc"]
    assert shown["ma_hs"] == ["6104", "6204"]
    assert shown["tinh"] == "Hồ Chí Minh"  # tách tỉnh từ địa chỉ
    assert shown["nganh_nghe"] is None  # "Ngành nghề" trơn là nhóm ngành theo danh sách, không phải ngành ĐKKD
    assert p["contacts"] == [{"kind": "phone", "value": "+84974102195", "source_code": "nhap_lo", "source_name": "Danh sách MST nhập theo lô"}]

    p2 = admin.get("/api/admin/enrich/companies/0309876543-001").json()
    assert {f["key"]: f["value"] for f in p2["fields"]}["nhom_san_pham"] == ["Linh kiện điện tử", "Bo mạch"]
    assert [c["value"] for c in p2["contacts"]] == ["+84988062325"]

    # nhập lại cùng file: không thêm bằng chứng / liên hệ trùng
    n_ev = len(admin.get("/api/admin/enrich/companies/0101234567/evidence").json())
    admin.post("/api/admin/enrich/batches", json={**BATCH, "file_name": "ds.xlsx", "file_b64": b64(data)})
    assert len(admin.get("/api/admin/enrich/companies/0101234567/evidence").json()) == n_ev
    assert len(admin.get("/api/admin/enrich/companies/0101234567").json()["contacts"]) == 1

    # lọc theo mã HS / nhóm ngành
    flt = {"op": "and", "conditions": [{"field": "ma_hs", "cmp": "contains", "value": "6204"}]}
    res = admin.post("/api/admin/enrich/companies/search", json={"definition": flt}).json()
    assert [c["mst"] for c in res["items"]] == ["0101234567"]


def test_official_source_outranks_batch_value(admin):
    """Giá trị từ lô (tin cậy 0,5) bị dữ liệu ĐKKD (0,95) đè khi hiển thị nhưng vẫn giữ làm bằng chứng."""
    from app.enrich import sources
    from app.enrich.apply import Origin, apply_facts
    from app.enrich.connectors.base import CompanyFact, Facts

    import_csv(admin, ["MST,Tên,Địa chỉ", "0101234567,Công ty A,Số 1 phố Cũ, Hà Nội"])
    with dbmod.new_session() as db:
        src = sources.ensure(db, "dkkd_mua")
        apply_facts(db, "0101234567", Facts(company=[CompanyFact("dia_chi", "Số 9 phố Mới, Hà Nội", "")]), Origin(src, "dkkd.xlsx#dong=2", "h1", "cau_truc"))
        db.commit()
    shown = {f["key"]: f for f in admin.get("/api/admin/enrich/companies/0101234567").json()["fields"]}
    assert shown["dia_chi"]["value"] == "Số 9 phố Mới, Hà Nội" and shown["dia_chi"]["conflict"] is True


@pytest.mark.parametrize(
    "raw,ok,bad",
    [
        (974102195, ["+84974102195"], []),
        ("241.3821603", ["+842413821603"], []),
        ("066 3534086", ["+84663534086"], []),
        ("8.40948E+11 / 84988062325", ["+84988062325"], ["8.40948E+11"]),
        ("38940914", [], ["38940914"]),
        ("18006809", ["18006809"], []),
        ("", [], []),
    ],
)
def test_split_phones(raw, ok, bad):
    from app.enrich.importer import split_phones

    assert split_phones(raw) == (ok, bad)


def test_import_without_header_uses_first_column(admin):
    r = import_csv(admin, ["0101234567", "0309876543"])
    assert r.status_code == 201 and r.json()["mst_count"] == 2


@pytest.mark.parametrize(
    "file_name,rows,msg",
    [
        ("ds.xls", ["MST", "0101234567"], ".xls"),
        ("ds.pdf", ["MST"], "Chỉ nhận"),
        ("ds.csv", ["Tên,Địa chỉ", "A,B"], "Không thấy cột mã số thuế"),
        ("ds.csv", ["MST", "abc", "12"], "không có mã số thuế hợp lệ"),
    ],
)
def test_import_rejects_bad_files(admin, file_name, rows, msg):
    r = import_csv(admin, rows, file_name=file_name)
    assert r.status_code == 422 and msg in r.json()["detail"]
    assert admin.get("/api/admin/enrich/batches").json() == []


def test_batch_requires_purpose(admin):
    r = import_csv(admin, ["MST", "0101234567"], purposes=[])
    assert r.status_code == 422
    r = import_csv(admin, ["MST", "0101234567"], purposes=["ban_du_lieu"])
    assert r.status_code == 422


def test_field_without_evidence_is_displayed_without_source(admin):
    """Trường có giá trị nhưng chưa có bằng chứng vẫn hiển thị, chỉ không kèm nguồn."""
    import_csv(admin, ["MST", "0101234567"])
    from app.models_enrich import EnrichCompany

    with dbmod.new_session() as db:
        c = db.get(EnrichCompany, "0101234567")
        c.dia_chi = "Ghi thẳng không có nguồn"
        c.ngay_thanh_lap = date(2001, 1, 1)
        db.commit()
    p = admin.get("/api/admin/enrich/companies/0101234567").json()
    shown = {f["key"]: f for f in p["fields"]}
    assert shown["dia_chi"]["value"] == "Ghi thẳng không có nguồn" and shown["dia_chi"]["source"] is None
    assert shown["ngay_thanh_lap"]["value"] == "2001-01-01" and shown["ngay_thanh_lap"]["score"] is None
    assert shown["mst"]["source"] is not None
    assert "Địa chỉ trụ sở" not in p["missing_fields"]


def test_stats_coverage(admin):
    import_csv(admin, ["MST,Tên", "0101234567,A", "0309876543,"])
    s = admin.get("/api/admin/enrich/stats").json()
    assert s["total"] == 2 and s["by_field"]["ten"] == 1 and s["full_profile"] == 0 and s["batches"] == 1
    seed_person()
    assert admin.get("/api/admin/enrich/stats").json()["with_decision_maker"] == 1


# ------------------------------------------------------------------ phân quyền (N04, T01, T04)


def test_staff_without_enrich_role_has_no_access(staff):
    assert staff.get("/api/admin/enrich/meta").status_code == 403
    assert staff.get("/api/admin/enrich/companies").status_code == 403
    me = staff.get("/api/admin/auth/me").json()
    assert me["enrich_access"] is None


def test_admin_defaults_to_system_admin_role(admin):
    me = admin.get("/api/admin/auth/me").json()
    assert me["enrich_role"] is None and me["enrich_access"] == "quan_tri"
    assert "batch.import" in admin.get("/api/admin/enrich/meta").json()["caps"]


def test_admin_assigns_enrich_role(admin, staff_id):
    r = admin.patch(f"/api/admin/users/{staff_id}", json={"enrich_role": "kinh_doanh"})
    assert r.status_code == 200 and r.json()["enrich_access"] == "kinh_doanh"
    assert admin.patch(f"/api/admin/users/{staff_id}", json={"enrich_role": "sieu_nhan"}).status_code == 422
    r = admin.patch(f"/api/admin/users/{staff_id}", json={"enrich_role": ""})
    assert r.json()["enrich_access"] is None
    # PATCH không gửi enrich_role thì giữ nguyên
    admin.patch(f"/api/admin/users/{staff_id}", json={"enrich_role": "phan_tich"})
    assert admin.patch(f"/api/admin/users/{staff_id}", json={"full_name": "Đổi tên"}).json()["enrich_role"] == "phan_tich"
    assert "enrich_roles" in admin.get("/api/admin/meta").json()


def test_sales_role_sees_names_but_not_personal_tax_code(admin):
    import_csv(admin, ["MST", "0101234567"])
    seed_person()
    sales = login_as("kinh_doanh", "sales@leadscan.vn")

    people = sales.get("/api/admin/enrich/companies/0101234567/people")
    assert people.status_code == 200
    p = people.json()[0]
    assert p["ho_ten"] == "Nguyễn Văn An" and p["chuc_danh"] == "Tổng Giám đốc" and p["la_nguoi_quyet_dinh"] is True
    assert p["lien_he"][0]["value"] == "an@congty.vn"
    assert "mst_ca_nhan" not in p and "nam_sinh" not in p and "bang_chung" not in p

    # T01: truy vấn trực tiếp kho B bị từ chối
    assert sales.get("/api/admin/enrich/persons").status_code == 403
    # không được nhập lô
    assert import_csv(sales, ["MST", "0309876543"]).status_code == 403
    # kho A vẫn xem được, kèm nguồn gốc
    assert sales.get("/api/admin/enrich/companies/0101234567").status_code == 200
    assert sales.get("/api/admin/enrich/companies/0101234567/evidence").status_code == 200


def test_auditor_sees_full_person_with_evidence(admin):
    import_csv(admin, ["MST", "0101234567"])
    seed_person()
    auditor = login_as("tham_dinh", "audit@leadscan.vn")
    p = auditor.get("/api/admin/enrich/companies/0101234567/people").json()[0]
    assert p["mst_ca_nhan"] == "8000000001" and p["nam_sinh"] == 1975
    assert p["bang_chung"][0]["source_url"] == "https://congty.vn/ban-lanh-dao"
    r = auditor.get("/api/admin/enrich/persons?q=nguyen van")
    assert r.status_code == 200 and r.json()["items"][0]["mst_ca_nhan"] == "8000000001"
    assert auditor.get("/api/admin/enrich/persons?q=8000000001").json()["total"] == 1
    assert import_csv(auditor, ["MST", "0309876543"]).status_code == 403


def test_market_analyst_has_no_kho_b(admin):
    import_csv(admin, ["MST", "0101234567"])
    seed_person()
    analyst = login_as("phan_tich", "analyst@leadscan.vn")
    assert analyst.get("/api/admin/enrich/companies/0101234567").json()["can"]["people"] is False
    assert analyst.get("/api/admin/enrich/companies/0101234567/people").status_code == 403
    assert analyst.get("/api/admin/enrich/persons").status_code == 403
    assert analyst.get("/api/admin/enrich/stats").status_code == 200


# ------------------------------------------------------------------ nhật ký truy cập kho B (N06, T08), từ chối liên hệ (C10)


def test_kho_b_reads_are_logged_and_log_is_append_only(admin):
    import_csv(admin, ["MST", "0101234567"])
    seed_person()
    admin.get("/api/admin/enrich/companies/0101234567/people")
    admin.get("/api/admin/enrich/persons?q=an")
    from app.models_enrich import AccessLog

    with dbmod.new_session() as db:
        logs = db.scalars(select(AccessLog).order_by(AccessLog.id)).all()
        assert [(log.action, log.target, log.row_count) for log in logs] == [
            ("read", "company:0101234567/people", 1),
            ("list", "persons?q=an", 1),
        ]
        assert logs[0].user_id is not None
    table = "enrich_access_logs" if dbmod.get_engine().dialect.name == "sqlite" else "kho_b.enrich_access_logs"
    # 403 không ghi nhật ký đọc
    analyst = login_as("phan_tich", "analyst2@leadscan.vn")
    analyst.get("/api/admin/enrich/companies/0101234567/people")
    with dbmod.get_engine().connect() as conn:
        assert conn.execute(text(f"select count(*) from {table}")).scalar() == 2

    for stmt in (f"UPDATE {table} SET row_count = 0", f"DELETE FROM {table}"):
        with pytest.raises(Exception, match="chỉ được ghi thêm"):
            with dbmod.get_engine().begin() as conn:
                conn.execute(text(stmt))


def test_opted_out_person_and_contact_are_hidden(admin):
    import_csv(admin, ["MST", "0101234567"])
    pid = seed_person()
    seed_person(ho_ten="Trần Thị Bình", mst_ca_nhan="8000000002", email="binh@congty.vn")
    from app.models_enrich import OptOut

    with dbmod.new_session() as db:
        db.add(OptOut(kind="person", value=str(pid), reason="Chủ thể yêu cầu"))
        db.add(OptOut(kind="email", value="BINH@congty.vn", reason="Từ chối email"))
        db.commit()
    people = admin.get("/api/admin/enrich/companies/0101234567/people").json()
    assert [p["ho_ten"] for p in people] == ["Trần Thị Bình"]
    assert people[0]["lien_he"] == []
    assert admin.get("/api/admin/enrich/persons").json()["total"] == 1


# ------------------------------------------------------------------ T09: không có cột dữ liệu nhạy cảm trong kho B


def test_kho_b_schema_has_no_sensitive_columns():
    from app.models_enrich import KHO_B

    forbidden = ("cccd", "cmnd", "can_cuoc", "ho_chieu", "passport", "ho_khau", "thuong_tru", "dia_chi_nha", "ngan_hang", "so_tai_khoan", "bank", "suc_khoe", "benh", "gia_dinh", "vo_chong", "con_cai", "quan_he")
    tables = [t for t in dbmod.Base.metadata.tables.values() if t.schema == KHO_B]
    assert len(tables) >= 7
    cols = [f"{t.name}.{c.name}" for t in tables for c in t.columns]
    bad = [c for c in cols if any(w in c.lower() for w in forbidden)]
    assert bad == []
    # bảng thật trong CSDL cũng vậy
    insp = inspect(dbmod.get_engine())
    schema = None if dbmod.get_engine().dialect.name == "sqlite" else KHO_B
    for t in tables:
        assert all(not any(w in c["name"] for w in forbidden) for c in insp.get_columns(t.name, schema=schema))


@pytest.mark.parametrize(
    "header,field",
    [
        ("Tên tiếng Anh", "ten_tieng_anh"),
        ("Fax", "fax"),
        ("Năm thành lập", "nam_thanh_lap"),
        ("Giới thiệu", "mo_ta"),
        ("Ngành nghề kinh doanh chính", "nganh_nghe"),
        ("Ngành nghề", "nhom_nganh"),
        ("Tình trạng hoạt động", "trang_thai"),
        ("Địa chỉ email", "email"),
        ("Mã HS (4 số)", "ma_hs"),
        ("Số dòng hàng", None),
    ],
)
def test_extra_header_mapping(header, field):
    from app.enrich.importer import _extra_field

    assert _extra_field(bo_dau(header)) == field
