"""Làm giàu dữ liệu MST — giai đoạn 4: website doanh nghiệp, khớp người, gộp / tách, đồ thị quan hệ, suy luận email."""

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app import db as dbmod
from app.enrich import emails, runner, sources
from app.enrich.apply import Origin, add_contact, apply_facts
from app.enrich.connectors.base import Facts, PersonFact
from app.enrich.connectors.website import CompanyWebsite
from tests.test_enrich import b64, import_csv, login_as
from tests.test_enrich_ops import drain, xlsx

X, Y = "0101234567", "0309876543"


def add_people(mst: str, people: list[tuple[str, str]], source: str = "bien_tap", url: str = "https://nguon.vn/x") -> None:
    with dbmod.new_session() as db:
        src = sources.ensure(db, source)
        apply_facts(db, mst, Facts(people=[PersonFact(n, t) for n, t in people]), Origin(source=src, source_url=url, content_hash=url, method="thu_cong"))
        db.commit()


def person_id(name: str, mst: str | None = None) -> int:
    from app.models_enrich import EnrichPerson, PersonRole

    with dbmod.new_session() as db:
        stmt = select(EnrichPerson.id).where(EnrichPerson.ho_ten == name, EnrichPerson.merged_into_id.is_(None))
        if mst:
            stmt = stmt.join(PersonRole, PersonRole.person_id == EnrichPerson.id).where(PersonRole.company_mst == mst)
        return db.scalar(stmt)


@pytest.fixture
def two(admin):
    import_csv(admin, ["MST,Tên", f"{X},CTCP Đại Việt", f"{Y},CTCP Sao Mai"])
    return admin


# ------------------------------------------------------------------ khớp người (B06)


def test_same_company_same_name_is_one_person_other_company_is_candidate(two):
    add_people(X, [("Nguyễn Văn An", "Tổng Giám đốc")])
    add_people(X, [("Nguyễn Văn An", "Thành viên HĐQT")], url="https://nguon.vn/y")
    add_people(Y, [("Nguyễn Văn An", "Giám đốc")], url="https://nguon.vn/z")
    from app.models_enrich import EnrichPerson, MergeCandidate

    with dbmod.new_session() as db:
        assert db.scalar(select(func.count()).select_from(EnrichPerson)) == 2  # X: một người hai vai trò; Y: hồ sơ riêng
        cands = db.scalars(select(MergeCandidate)).all()
        assert len(cands) == 1 and cands[0].score < 0.85 and cands[0].status == "pending"
    px = two.get(f"/api/admin/enrich/persons/{person_id('Nguyễn Văn An', X)}").json()
    assert {r["chuc_danh"] for r in px["roles"]} == {"Tổng Giám đốc", "Thành viên HĐQT"}
    assert px["candidates"][0]["reasons"][0] == "Cùng họ tên chuẩn hoá"


def test_personal_mst_import_links_and_auto_merges_only_on_mst(two):
    add_people(Y, [("Nguyễn Văn An", "Giám đốc")])  # chưa có MST cá nhân
    f = xlsx([["MST cá nhân", "Họ và tên", "MST doanh nghiệp", "Chức danh"], ["8000000001", "NGUYỄN VĂN AN", X, "Tổng Giám đốc"], ["123", "Lê B", X, ""], ["8000000002", "Trần C", "0999999999", ""]])
    body = {"file_name": "mst-cn.xlsx", "file_b64": b64(f), "source_note": "Hồ sơ khách hàng đã ký hợp đồng", "confirmed": False}
    r = two.post("/api/admin/enrich/persons/import-mst", json=body)
    assert r.status_code == 422 and "không mua từ bên thứ ba" in r.json()["detail"]  # T03
    rep = two.post("/api/admin/enrich/persons/import-mst", json={**body, "confirmed": True}).json()
    assert rep["rows"] == 3 and rep["created"] == 1 and len(rep["skipped"]) == 2
    a = person_id("Nguyễn Văn An", X)
    assert a != person_id("Nguyễn Văn An", Y)  # khác DN, chưa có bằng chứng MST → không tự gộp

    # cùng MST cá nhân xuất hiện ở DN Y → hồ sơ cùng tên ở Y được gộp tự động
    f2 = xlsx([["Mã số thuế cá nhân", "Họ tên", "MST công ty"], ["8000000001", "Nguyễn Văn An", Y]])
    rep = two.post("/api/admin/enrich/persons/import-mst", json={**body, "file_b64": b64(f2), "confirmed": True}).json()
    assert rep["auto_merged"] == 1 and rep["by_mst"] == 1
    prof = two.get(f"/api/admin/enrich/persons/{a}").json()
    assert {r["company_mst"] for r in prof["roles"]} == {X, Y} and prof["mst_ca_nhan"] == "8000000001"
    assert prof["ops"][0]["op"] == "merge"
    sales = login_as("kinh_doanh", "sales4@leadscan.vn")
    assert "mst_ca_nhan" not in sales.get(f"/api/admin/enrich/persons/{a}").json()  # T04 / C02
    assert sales.post("/api/admin/enrich/persons/import-mst", json={**body, "confirmed": True}).status_code == 403


# ------------------------------------------------------------------ gộp / tách / hoàn tác (B07)


def test_manual_merge_and_undo(two):
    add_people(X, [("Trần Thị Bình", "Kế toán trưởng")])
    add_people(Y, [("Trần Thị Bình", "Giám đốc")], url="https://nguon.vn/2")
    a, b = person_id("Trần Thị Bình", X), person_id("Trần Thị Bình", Y)
    cand = two.get("/api/admin/enrich/merge-candidates").json()[0]
    editor = login_as("bien_tap", "editor4@leadscan.vn")
    r = editor.post(f"/api/admin/enrich/merge-candidates/{cand['id']}", json={"action": "merge", "keep": "a"})
    assert r.status_code == 200 and r.json()["status"] == "merged"
    keep, drop = sorted((a, b))
    assert two.get(f"/api/admin/enrich/persons/{drop}").json() == {"id": drop, "merged_into_id": keep}
    assert len(two.get(f"/api/admin/enrich/persons/{keep}").json()["roles"]) == 2
    assert two.get("/api/admin/enrich/persons?q=tran thi binh").json()["total"] == 1

    op = two.get(f"/api/admin/enrich/persons/{keep}").json()["ops"][0]
    assert editor.post(f"/api/admin/enrich/entity-ops/{op['id']}/undo").status_code == 200
    assert len(two.get(f"/api/admin/enrich/persons/{keep}").json()["roles"]) == 1
    assert len(two.get(f"/api/admin/enrich/persons/{drop}").json()["roles"]) == 1
    assert two.get("/api/admin/enrich/merge-candidates").json()[0]["id"] == cand["id"]  # cặp quay về chờ quyết
    assert editor.post(f"/api/admin/enrich/entity-ops/{op['id']}/undo").status_code == 409  # không hoàn tác hai lần

    # khác MST cá nhân → không gộp được
    from app.models_enrich import EnrichPerson

    with dbmod.new_session() as db:
        db.get(EnrichPerson, a).mst_ca_nhan = "8000000011"
        db.get(EnrichPerson, b).mst_ca_nhan = "8000000012"
        db.commit()
    r = two.post("/api/admin/enrich/persons/merge", json={"keep_id": a, "drop_id": b})
    assert r.status_code == 422 and "MST cá nhân khác nhau" in r.json()["detail"]
    assert two.post(f"/api/admin/enrich/merge-candidates/{cand['id']}", json={"action": "reject"}).json()["status"] == "rejected"
    auditor = login_as("tham_dinh", "audit4@leadscan.vn")
    assert auditor.post("/api/admin/enrich/persons/merge", json={"keep_id": a, "drop_id": b}).status_code == 403


def test_split_and_undo(two):
    add_people(X, [("Phạm Minh Đức", "Tổng Giám đốc")])
    pid = person_id("Phạm Minh Đức", X)
    # vai trò ở Y bị gắn nhầm vào cùng hồ sơ (vd gộp nhầm trước đây)
    with dbmod.new_session() as db:
        from app.models_enrich import PersonRole

        db.add(PersonRole(person_id=pid, company_mst=Y, chuc_danh="Giám đốc", chuc_danh_chuan="giam_doc", la_nguoi_quyet_dinh=True, source_code="bien_tap"))
        db.commit()
    roles = two.get(f"/api/admin/enrich/persons/{pid}").json()["roles"]
    y_role = next(r["id"] for r in roles if r["company_mst"] == Y)
    assert two.post(f"/api/admin/enrich/persons/{pid}/split", json={"role_ids": [r["id"] for r in roles]}).status_code == 422
    op = two.post(f"/api/admin/enrich/persons/{pid}/split", json={"role_ids": [y_role], "note": "Hai người trùng tên"}).json()
    new = op["other_person_id"]
    assert [r["company_mst"] for r in two.get(f"/api/admin/enrich/persons/{new}").json()["roles"]] == [Y]
    assert two.get(f"/api/admin/enrich/persons/{new}").json()["bang_chung"]  # họ tên của hồ sơ mới vẫn có bằng chứng
    assert two.post(f"/api/admin/enrich/entity-ops/{op['id']}/undo").status_code == 200
    assert len(two.get(f"/api/admin/enrich/persons/{pid}").json()["roles"]) == 2


# ------------------------------------------------------------------ đồ thị quan hệ + xuất bên liên quan (C02, C03)


def test_graph_and_related_export(two):
    add_people(X, [("Nguyễn Văn An", "Chủ tịch HĐQT"), ("Lê Thị Hoa", "Tổng Giám đốc")])
    a = person_id("Nguyễn Văn An", X)
    with dbmod.new_session() as db:
        from app.models_enrich import EnrichPerson, PersonRole

        db.add(PersonRole(person_id=a, company_mst=Y, chuc_danh="Thành viên HĐQT", chuc_danh_chuan="thanh_vien_hdqt", la_nguoi_quyet_dinh=True, source_code="bien_tap"))
        db.get(EnrichPerson, a).mst_ca_nhan = "8000000001"
        hoa = person_id("Lê Thị Hoa", X)
        add_contact(db, "person", str(hoa), "email", "hoa.le@daiviet.vn", "bien_tap", inferred=False)
        add_contact(db, "person", str(a), "email", "an.nguyen@daiviet.vn", "suy_luan_email", inferred=True, verify_status="mx_ok")
        db.commit()
    g = two.get(f"/api/admin/enrich/persons/{a}/graph").json()
    assert {n["type"] for n in g["nodes"]} == {"person", "company"} and len(g["nodes"]) == 4
    assert len(g["edges"]) == 3

    assert two.get(f"/api/admin/enrich/persons/{a}/related.csv").status_code == 422  # phải khai mục đích
    r = two.get(f"/api/admin/enrich/persons/{a}/related.csv?purpose=tham_dinh_kyc")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    assert "Lê Thị Hoa" in text and "hoa.le@daiviet.vn" in text and "8000000001" not in text  # T04
    assert "an.nguyen@daiviet.vn" not in text  # B11: email suy luận chỉ khi chọn
    assert "an.nguyen@daiviet.vn (suy luận)" in two.get(f"/api/admin/enrich/persons/{a}/related.csv?purpose=tham_dinh_kyc&include_inferred=true").content.decode("utf-8-sig")

    sales = login_as("kinh_doanh", "sales5@leadscan.vn")
    assert sales.get(f"/api/admin/enrich/persons/{a}/graph").status_code == 200
    assert sales.get(f"/api/admin/enrich/persons/{a}/related.csv?purpose=tham_dinh_kyc").status_code == 403
    assert sales.get("/api/admin/enrich/merge-candidates").status_code == 403
    analyst = login_as("phan_tich", "analyst5@leadscan.vn")
    assert analyst.get(f"/api/admin/enrich/persons/{a}").status_code == 403

    from app.models_enrich import AccessLog

    with dbmod.new_session() as db:
        actions = {(a_.action, a_.target.split("?")[0]) for a_ in db.scalars(select(AccessLog))}
    assert ("export", f"person:{a}/related") in actions and ("read", f"person:{a}/graph") in actions


# ------------------------------------------------------------------ suy luận email (B10, B11)


def _company_domain(mst: str, domain: str) -> None:
    from app.enrich import merge
    from app.models_enrich import CompanyEvidence

    with dbmod.new_session() as db:
        db.add(CompanyEvidence(mst=mst, field="website", value=f"https://{domain}", source_code="bien_tap", method="thu_cong"))
        db.add(CompanyEvidence(mst=mst, field="domain", value=domain, source_code="bien_tap", method="thu_cong"))
        sources.ensure(db, "bien_tap")
        db.flush()
        merge.recompute_companies(db, [mst])
        db.commit()


def test_email_inference_needs_real_email_and_mx(two, monkeypatch):
    _company_domain(X, "daiviet.vn")
    add_people(X, [("Nguyễn Văn An", "Tổng Giám đốc"), ("Trần Thị Bình", "Phó Tổng Giám đốc"), ("Lê Văn Cường", "Kế toán trưởng"), ("Hoàng Thu Hà", "Giám đốc Tài chính")])
    mx = {"daiviet.vn": True}
    monkeypatch.setattr(emails, "has_mx", lambda d: mx.get(d))

    r = two.post("/api/admin/enrich/emails/infer", json={"mst": X}).json()
    assert r["created"] == 0 and "Chưa có email thật" in r["skipped"]  # B10: chưa có email thật cùng tên miền

    with dbmod.new_session() as db:
        add_contact(db, "person", str(person_id("Nguyễn Văn An", X)), "email", "an.nguyen@daiviet.vn", "website", inferred=False)
        from app.models_enrich import OptOut

        db.add(OptOut(kind="email", value="ha.hoang@daiviet.vn", reason="Từ chối"))
        db.commit()
    mx["daiviet.vn"] = False
    assert "MX" in two.post("/api/admin/enrich/emails/infer", json={"mst": X}).json()["skipped"]  # không MX → không lưu
    mx["daiviet.vn"] = True
    r = two.post("/api/admin/enrich/emails/infer", json={"mst": X}).json()
    assert r["pattern"] == "ten.ho" and r["created"] == 1  # chỉ Bình: Cường không phải người ra quyết định, Hà đã từ chối

    binh = two.get(f"/api/admin/enrich/persons/{person_id('Trần Thị Bình', X)}").json()
    c = binh["lien_he"][0]
    assert c == {"id": c["id"], "kind": "email", "value": "binh.tran@daiviet.vn", "is_inferred": True, "verify_status": "mx_ok", "source_code": "suy_luan_email"}
    ev = next(e for e in binh["bang_chung"] if e["field"] == "email")
    assert ev["is_inferred"] and ev["method"] == "suy_luan" and "ten.ho" in ev["excerpt"]
    assert two.post("/api/admin/enrich/emails/infer", json={"mst": X}).json()["created"] == 0  # chạy lại không trùng
    # mọi email suy luận đều có trạng thái xác minh (nghiệm thu GĐ4)
    from app.models_enrich import EnrichContact

    with dbmod.new_session() as db:
        assert db.scalar(select(func.count()).select_from(EnrichContact).where(EnrichContact.is_inferred.is_(True), EnrichContact.verify_status == "unverified")) == 0


# ------------------------------------------------------------------ connector website


HOME = """<html><head><script type="application/ld+json">{"@type":"Organization","telephone":"024 3826 1234","email":"info@daiviet.vn"}</script></head>
<body><a href="/gioi-thieu/ban-lanh-dao">Ban lãnh đạo</a> <a href="/lien-he">Liên hệ</a> <a href="/bi-mat/lanh-dao">Lãnh đạo nội bộ</a>
<a href="https://facebook.com/daiviet/about">FB</a> <a href="/tin-tuc/giam-doc-moi">Tin</a></body></html>"""
LEADERS = """<html><body><h2>Ban lãnh đạo</h2>
<div><h3>Ông Nguyễn Văn An</h3><p>Chủ tịch HĐQT</p></div>
<p>Tổng Giám đốc: Bà Trần Thị Bình</p><p>Email: binh.tran@daiviet.vn</p>
<p>Giám đốc Công ty Cổ phần Đại Việt cam kết chất lượng</p>
<p>Liên hệ kinh doanh: sales@daiviet.vn — hoặc canhan@gmail.com</p></body></html>"""


def test_website_parser_rules():
    c = CompanyWebsite()
    f = c.parse(X, "https://www.daiviet.vn/", HOME.encode(), "text/html")
    assert f.follow == ["https://www.daiviet.vn/gioi-thieu/ban-lanh-dao", "https://www.daiviet.vn/lien-he", "https://www.daiviet.vn/bi-mat/lanh-dao"]
    assert ("email", "info@daiviet.vn") in f.contacts and ("phone", "+842438261234") in f.contacts
    f = c.parse(X, "https://www.daiviet.vn/gioi-thieu/ban-lanh-dao", LEADERS.encode(), "text/html")
    people = {p.ho_ten: (p.chuc_danh, p.email) for p in f.people}
    assert people == {"Nguyễn Văn An": ("Chủ tịch HĐQT", None), "Trần Thị Bình": ("Tổng Giám đốc", "binh.tran@daiviet.vn")}
    assert ("email", "sales@daiviet.vn") in f.contacts and not any("gmail" in v for _, v in f.contacts)


@respx.mock
def test_website_connector_end_to_end(two, monkeypatch):
    from app.services import storage

    _company_domain(X, "daiviet.vn")
    monkeypatch.setattr(sources, "MIN_INTERVAL_S", 0.0)
    storage.set_backend(storage.MemoryStorage())
    runner._robots.clear()
    with dbmod.new_session() as db:
        src = sources.ensure(db, "website")
        assert src.enabled is False  # connector tự động mặc định tắt
        src.enabled = True
        src.config = {**src.config, "min_interval_s": 0, "max_pages": 3}
        db.commit()
    respx.get("https://daiviet.vn/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow: /bi-mat/\n"))
    respx.get("https://daiviet.vn/").mock(return_value=httpx.Response(200, html=HOME.replace("www.", "")))
    respx.get("https://daiviet.vn/gioi-thieu/ban-lanh-dao").mock(return_value=httpx.Response(200, html=LEADERS))
    respx.get("https://daiviet.vn/lien-he").mock(return_value=httpx.Response(404))
    secret = respx.get("https://daiviet.vn/bi-mat/lanh-dao").mock(return_value=httpx.Response(200, html=LEADERS))
    fb = respx.get(url__regex=r"https://facebook\.com/.*").mock(return_value=httpx.Response(200))
    try:
        r = two.post("/api/admin/enrich/runs", json={"name": "Website", "connectors": ["website"]})
        assert r.status_code == 201, r.text
        drain()
        run = two.get(f"/api/admin/enrich/runs/{r.json()['id']}").json()
        assert run["totals"]["done"] == 1 and run["totals"]["not_found"] == 1  # Y chưa có website
        assert not secret.called and not fb.called  # robots.txt + chỉ đi trong cùng website
        people = {p["ho_ten"]: p for p in two.get(f"/api/admin/enrich/companies/{X}/people").json()}
        assert people["Trần Thị Bình"]["chuc_danh_chuan"] == "tong_giam_doc"
        assert people["Trần Thị Bình"]["lien_he"][0]["value"] == "binh.tran@daiviet.vn" and not people["Trần Thị Bình"]["lien_he"][0]["is_inferred"]
        assert people["Nguyễn Văn An"]["bang_chung"][0]["source_url"] == "https://daiviet.vn/gioi-thieu/ban-lanh-dao"
        from app.models_enrich import EnrichContact

        with dbmod.new_session() as db:
            company_contacts = set(db.scalars(select(EnrichContact.value).where(EnrichContact.owner_type == "company", EnrichContact.owner_id == X)))
        assert company_contacts == {"info@daiviet.vn", "+842438261234", "sales@daiviet.vn"}
        assert two.get("/api/admin/enrich/stats").json()["with_decision_maker"] == 1
    finally:
        storage.set_backend(None)
        runner._robots.clear()
