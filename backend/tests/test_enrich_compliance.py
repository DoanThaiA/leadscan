"""Làm giàu dữ liệu MST — giai đoạn 5: lọc nâng cao, xuất có kiểm soát, theo dõi + cảnh báo, lịch tái thu thập, tuân thủ, mã hoá."""

import time
from datetime import timedelta

import pytest
from sqlalchemy import func, insert, select, text

from app import db as dbmod
from app.db import utcnow
from app.enrich import scheduler, sources
from app.enrich.apply import Origin, add_contact, apply_facts
from app.enrich.connectors.base import Facts, PersonFact, SignalFact
from tests.test_enrich import b64, import_csv, login_as
from tests.test_enrich_ops import xlsx
from tests.test_enrich_people import _company_domain, add_people, person_id

X, Y, Z = "0101234567", "0309876543", "0401234567"


@pytest.fixture
def base(admin):
    """3 doanh nghiệp: X, Y trong lô cho phép bán hàng B2B; Z trong lô chỉ cho nghiên cứu thị trường."""
    import_csv(admin, ["MST,Tên", f"{X},Công ty CP Đại Việt", f"{Y},Công ty TNHH Sao Mai"], purposes=["ban_hang_b2b"])
    import_csv(admin, ["MST,Tên", f"{Z},Công ty Hưng Thịnh"], purposes=["nghien_cuu_thi_truong"])
    dk = xlsx([
        ["Mã số doanh nghiệp", "Tên doanh nghiệp", "Địa chỉ trụ sở chính", "Tình trạng hoạt động", "Ngành nghề kinh doanh chính", "Vốn điều lệ"],
        [X, "CÔNG TY CP ĐẠI VIỆT", "1 Láng Hạ, Hà Nội", "Đang hoạt động", "Sản xuất bao bì", "50.000.000.000"],
        [Y, "CÔNG TY TNHH SAO MAI", "KCN Sóng Thần, Bình Dương", "Tạm ngừng kinh doanh", "Thương mại", "2.000.000.000"],
        [Z, "CÔNG TY HƯNG THỊNH", "12 Lê Lợi, Đà Nẵng", "Đang hoạt động", "Xây dựng", ""],
    ])
    assert admin.post("/api/admin/enrich/imports", json={"kind": "dkkd_mua", "file_name": "dk.xlsx", "file_b64": b64(dk), "source_url": "HĐ 1/2026"}).status_code == 201
    add_people(X, [("Nguyễn Văn An", "Tổng Giám đốc"), ("Lê Thị Hoa", "Kế toán trưởng")])
    return admin


def search(client, definition, **kw):
    r = client.post("/api/admin/enrich/companies/search", json={"definition": definition, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ N05: mã hoá


def test_personal_mst_and_raw_pages_encrypted_at_rest(base):
    from app.enrich import raw_store
    from app.models_enrich import EnrichPerson

    pid = person_id("Nguyễn Văn An", X)
    with dbmod.new_session() as db:
        db.get(EnrichPerson, pid).mst_ca_nhan = "8000000001"
        db.commit()
    table = "enrich_persons" if dbmod.get_engine().dialect.name == "sqlite" else "kho_b.enrich_persons"
    with dbmod.get_engine().connect() as c:
        stored = c.execute(text(f"select mst_ca_nhan from {table} where id = {pid}")).scalar()
    assert stored.startswith("e1:") and "8000000001" not in stored
    with dbmod.new_session() as db:
        assert db.scalar(select(EnrichPerson.id).where(EnrichPerson.mst_ca_nhan == "8000000001")) == pid  # vẫn tìm được

    from app.services import storage

    storage.set_backend(storage.MemoryStorage())
    try:
        key = raw_store.put("x", "abc123", b"<p>CCCD 001234567890</p>", "text/html")
        packed = storage.backend().get_bytes(key)
        assert packed.startswith(b"LSE1") and b"001234567890" not in packed
        assert raw_store.get(key) == b"<p>CCCD 001234567890</p>"
    finally:
        storage.set_backend(None)


# ------------------------------------------------------------------ C04, C05, N03: lọc


def test_filter_and_or_regex_and_derived_fields(base):
    assert search(base, {"conditions": [{"field": "tinh", "cmp": "eq", "value": "Hà Nội"}]})["total"] == 1
    assert search(base, {"op": "or", "conditions": [{"field": "tinh", "cmp": "eq", "value": "Hà Nội"}, {"field": "tinh", "cmp": "eq", "value": "Đà Nẵng"}]})["total"] == 2
    assert search(base, {"conditions": [{"field": "ten", "cmp": "contains", "value": "dai viet"}]})["items"][0]["mst"] == X  # không dấu
    assert search(base, {"conditions": [{"field": "ten", "cmp": "regex", "value": "^CÔNG TY (CP|TNHH)"}]})["total"] == 2
    assert search(base, {"conditions": [{"field": "von", "cmp": "gte", "value": 10_000_000_000}]})["total"] == 1
    assert search(base, {"conditions": [{"field": "nganh_nghe", "cmp": "contains", "value": "bao bì"}]})["total"] == 1
    assert search(base, {"conditions": [{"field": "co_nguoi_quyet_dinh", "cmp": "is_true"}]})["items"][0]["mst"] == X
    assert search(base, {"conditions": [{"field": "muc_dich", "cmp": "eq", "value": "nghien_cuu_thi_truong"}]})["items"][0]["mst"] == Z
    nested = {"op": "and", "conditions": [{"field": "trang_thai", "cmp": "eq", "value": "Đang hoạt động"}, {"op": "or", "conditions": [{"field": "tinh", "cmp": "eq", "value": "Đà Nẵng"}, {"field": "von", "cmp": "empty"}]}]}
    assert [i["mst"] for i in search(base, nested)["items"]] == [Z]
    assert search(base, {"q": "sao mai"})["total"] == 1
    r = base.post("/api/admin/enrich/companies/search", json={"definition": {"conditions": [{"field": "ten", "cmp": "regex", "value": "(abc"}]}})
    assert r.status_code == 422 and "chính quy" in r.json()["detail"]
    assert base.post("/api/admin/enrich/companies/search", json={"definition": {"conditions": [{"field": "cccd", "cmp": "eq", "value": "1"}]}}).status_code == 422


def test_search_20k_under_2_seconds(admin):
    """N03: kết quả lọc trên 20.000 hồ sơ trả về dưới 2 giây."""
    from app.models_enrich import EnrichCompany

    now = utcnow()
    tinh = ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ"]
    with dbmod.new_session() as db:
        db.execute(insert(EnrichCompany), [
            {"mst": f"0{i:09d}", "ten": f"Công ty Số {i}", "ten_khong_dau": f"cong ty so {i}", "tinh": tinh[i % 5], "trang_thai": "Đang hoạt động" if i % 3 else "Tạm ngừng kinh doanh", "von": i * 1_000_000, "created_at": now, "updated_at": now}
            for i in range(1, 20001)
        ])
        db.commit()
    d = {"op": "or", "conditions": [{"op": "and", "conditions": [{"field": "tinh", "cmp": "eq", "value": "Đà Nẵng"}, {"field": "von", "cmp": "gte", "value": 5_000_000_000}]}, {"field": "ten", "cmp": "regex", "value": "Số 1[0-9]{3}$"}]}
    t0 = time.perf_counter()
    res = search(admin, d, page_size=50)
    elapsed = time.perf_counter() - t0
    assert res["total"] > 1000 and elapsed < 2.0, elapsed


def test_saved_and_shared_filters(base):
    d = {"conditions": [{"field": "tinh", "cmp": "eq", "value": "Hà Nội"}]}
    mine = base.post("/api/admin/enrich/filters", json={"name": "DN Hà Nội", "definition": d}).json()
    shared = base.post("/api/admin/enrich/filters", json={"name": "Chia sẻ nhóm", "shared": True, "definition": d}).json()
    assert base.post("/api/admin/enrich/filters", json={"name": "Sai", "definition": {"conditions": [{"field": "x", "cmp": "eq"}]}}).status_code == 422
    sales = login_as("kinh_doanh", "sales6@leadscan.vn")
    names = {f["name"] for f in sales.get("/api/admin/enrich/filters").json()}
    assert names == {"Chia sẻ nhóm"}
    assert sales.put(f"/api/admin/enrich/filters/{shared['id']}", json={"name": "Đổi", "definition": d}).status_code == 403
    assert search(sales, shared["definition"])["total"] == 1  # dùng lại được
    assert base.delete(f"/api/admin/enrich/filters/{mine['id']}").status_code == 204


# ------------------------------------------------------------------ C08, C09, T02, T04, T11, B11: xuất


def do_export(client, **body):
    return client.post("/api/admin/enrich/exports", json={"definition": {}, "columns": ["mst", "ten", "nguoi_quyet_dinh", "email_nguoi"], **body})


def test_export_rules(base):
    from app.models_enrich import EnrichPerson, ExportRecord, OptOut

    an = person_id("Nguyễn Văn An", X)
    with dbmod.new_session() as db:
        db.get(EnrichPerson, an).mst_ca_nhan = "8000000001"
        add_contact(db, "person", str(an), "email", "an.nguyen@daiviet.vn", "website", inferred=False)
        add_contact(db, "person", str(an), "email", "nguyenvanan@daiviet.vn", "suy_luan_email", inferred=True, verify_status="mx_ok")
        db.commit()
    add_people(Y, [("Trần Thị Bình", "Giám đốc")], url="https://nguon.vn/y")
    with dbmod.new_session() as db:
        db.add(OptOut(kind="person", value=str(person_id("Trần Thị Bình", Y)), reason="Từ chối"))
        db.commit()

    assert do_export(base, purpose="").status_code == 422  # T11: bắt buộc khai mục đích
    r = do_export(base, purpose="ban_hang_b2b")
    assert r.status_code == 200 and int(r.headers["x-export-blocked"]) == 1  # Z không cho phép bán hàng (T02)
    body = r.content.decode("utf-8-sig")
    lines = body.strip().splitlines()
    assert "Hạn sử dụng đến" in lines[0] and "Bán hàng" in lines[0]  # T11
    assert Z not in body and "8000000001" not in body  # T02, T04
    assert "Nguyễn Văn An — Tổng Giám đốc" in body and "an.nguyen@daiviet.vn" in body
    assert "nguyenvanan@daiviet.vn" not in body  # B11: suy luận chỉ khi chọn
    assert "Trần Thị Bình" not in body  # C10
    assert "Lê Thị Hoa" not in body  # kế toán trưởng không phải người ra quyết định
    assert "nguyenvanan@daiviet.vn (suy luận)" in do_export(base, purpose="ban_hang_b2b", include_inferred=True).content.decode("utf-8-sig")

    # chỉ còn Z trong bộ lọc → mọi dòng bị chặn → cả lần xuất bị chặn, vẫn ghi nhật ký
    r = do_export(base, purpose="ban_hang_b2b", definition={"conditions": [{"field": "mst", "cmp": "eq", "value": Z}]})
    assert r.status_code == 403 and "bị chặn" in r.json()["detail"]
    with dbmod.new_session() as db:
        recs = db.scalars(select(ExportRecord).order_by(ExportRecord.id)).all()
        assert [x.status for x in recs] == ["ok", "ok", "blocked"]
        assert recs[0].row_count == 2 and recs[0].blocked_count == 1 and recs[0].optout_count >= 1 and recs[0].includes_kho_b

    sales = login_as("kinh_doanh", "sales7@leadscan.vn")
    body = do_export(sales, purpose="ban_hang_b2b").content.decode("utf-8-sig")
    assert "Người ra quyết định" not in body and "Nguyễn Văn An" not in body  # cột kho B tự bị loại (C08)
    editor = login_as("bien_tap", "editor7@leadscan.vn")
    assert "Nguyễn Văn An" not in do_export(editor, purpose="ban_hang_b2b").content.decode("utf-8-sig")  # biên tập: không xuất kho B
    analyst = login_as("phan_tich", "analyst7@leadscan.vn")
    assert do_export(analyst, purpose="nghien_cuu_thi_truong").status_code == 403
    rep = analyst.get("/api/admin/enrich/reports/market").json()  # C11: số liệu tổng hợp, không dữ liệu cá nhân
    assert rep["total"] == 3 and {r["key"] for r in rep["by_tinh"]} == {"Hà Nội", "Hồ Chí Minh", "Đà Nẵng"}
    assert "Nguyễn" not in str(rep)
    assert analyst.get("/api/admin/enrich/reports/market.csv").status_code == 200
    logs = base.get("/api/admin/enrich/compliance/exports").json()
    assert [x["status"] for x in logs].count("blocked") == 1 and logs[-1]["columns"] == ["mst", "ten", "nguoi_quyet_dinh", "email_nguoi"]
    assert logs[0]["columns"] == ["mst", "ten"] and logs[0]["includes_kho_b"] is False  # biên tập xuất cuối cùng: cột kho B đã bị loại


# ------------------------------------------------------------------ C06: theo dõi + cảnh báo


def test_watchlist_alerts_and_digest(base, monkeypatch):
    wl = base.post("/api/admin/enrich/watchlists", json={"name": "Khách hàng lớn", "email_digest": True}).json()
    only_debt = base.post("/api/admin/enrich/watchlists", json={"name": "Chỉ nợ thuế", "kinds": ["no_thue"]}).json()
    assert base.post(f"/api/admin/enrich/watchlists/{wl['id']}/items", json={"definition": {"conditions": [{"field": "tinh", "cmp": "in", "value": "Hà Nội,Hồ Chí Minh"}]}}).json()["added"] == 2
    assert base.post(f"/api/admin/enrich/watchlists/{only_debt['id']}/items", json={"msts": [X, "0999999999"]}).json() == {"added": 1, "already": 0, "unknown": 1}
    scheduler_scan = lambda: scheduler.scan_alerts(dbmod.new_session())  # noqa: E731
    scheduler_scan()  # đặt con trỏ: dữ liệu nạp trước khi theo dõi không sinh cảnh báo
    assert base.get("/api/admin/enrich/alerts").json()["unread"] == 0

    # thay đổi mới: địa chỉ + tình trạng X đổi (nguồn tin cậy cao hơn), nợ thuế, bổ nhiệm, miễn nhiệm
    with dbmod.new_session() as db:
        src = sources.ensure(db, "dkkd_tra_cuu")
        src.trust = 0.99
        db.commit()
        apply_facts(db, X, Facts(company=[_cf("dia_chi", "99 Trần Duy Hưng, Hà Nội"), _cf("trang_thai", "Tạm ngừng kinh doanh")]), Origin(source=src, source_url="https://dkkd", content_hash="h2", method="nhap_tay"))
        nt = sources.ensure(db, "no_thue")
        apply_facts(db, X, Facts(signals=[SignalFact("no_thue", {"so_tien": 1_500_000_000, "co_quan": "Thuế Hà Nội"})]), Origin(source=nt, source_url="https://gdt", content_hash="h3", method="cau_truc"))
        bt = sources.ensure(db, "bien_tap")
        apply_facts(db, X, Facts(people=[PersonFact("Đỗ Văn Mới", "Phó Tổng Giám đốc"), PersonFact("Nguyễn Văn An", "Tổng Giám đốc", den_ngay=utcnow().date())]), Origin(source=bt, source_url="https://nguon.vn/x2", content_hash="h4", method="thu_cong"))
        db.commit()
    assert scheduler.scan_alerts(dbmod.new_session()) >= 5
    alerts = base.get("/api/admin/enrich/alerts").json()
    kinds = sorted(a["kind"] for a in alerts["items"] if a["watchlist_id"] == wl["id"])
    assert kinds == ["bo_nhiem", "dia_chi", "nguoi_dai_dien", "no_thue", "trang_thai"]
    assert [a["kind"] for a in alerts["items"] if a["watchlist_id"] == only_debt["id"]] == ["no_thue"]
    assert not any("Đỗ Văn Mới" in a["summary"] or "Nguyễn Văn An" in a["summary"] for a in alerts["items"])  # không tên người
    addr = next(a for a in alerts["items"] if a["kind"] == "dia_chi")
    assert "1 Láng Hạ" in addr["summary"] and "99 Trần Duy Hưng" in addr["summary"]

    sent = []
    monkeypatch.setattr("app.services.notify.send_mail", lambda cfg, subject, body, to=None, **kw: sent.append((to, subject, body)) or True)
    assert scheduler.send_digests(dbmod.new_session()) == 1 and sent[0][0] == "admin@leadscan.vn" and "nợ thuế" in sent[0][2]
    assert scheduler.send_digests(dbmod.new_session()) == 0  # không gửi lại
    assert base.post("/api/admin/enrich/alerts/read", json={"all": True}).json()["updated"] == len(alerts["items"])
    assert base.get("/api/admin/enrich/alerts?unread=true").json()["items"] == []
    other = login_as("kinh_doanh", "sales8@leadscan.vn")
    assert other.get(f"/api/admin/enrich/watchlists/{wl['id']}").status_code == 404  # danh sách riêng


def _cf(field, value):
    from app.enrich.connectors.base import CompanyFact

    return CompanyFact(field, value, "")


# ------------------------------------------------------------------ A12: lịch tái thu thập


def test_recrawl_schedule(base):
    db = dbmod.new_session()
    runs = scheduler.schedule_recrawl(db)
    by = {r["connector"]: r["jobs"] for r in runs}
    assert by == {"dkkd_tra_cuu": 3, "tracuu_nnt": 3}  # nguồn thủ công đang bật; website (tự động) đang tắt
    assert scheduler.schedule_recrawl(db) == []  # đang có việc mở → không tạo trùng
    from app.models_enrich import CrawlJob

    old = utcnow() - timedelta(days=40)
    for j in db.scalars(select(CrawlJob)).all():
        j.status, j.finished_at = "done", old
    db.commit()
    by = {r["connector"]: r["jobs"] for r in scheduler.schedule_recrawl(db)}
    assert by == {"dkkd_tra_cuu": 3, "tracuu_nnt": 3}  # cả hai chu kỳ 30 ngày đã quá
    reminders = {r["source"] for r in base.get("/api/admin/enrich/ops/schedule").json()["file_reminders"]}
    assert {"no_thue", "dau_thau", "ds_niem_yet"} <= reminders and "dkkd_mua" not in reminders  # vừa nhập ĐKKD
    db.close()


# ------------------------------------------------------------------ mục 10: tuân thủ


def test_optout_and_subject_requests(base):
    an = person_id("Nguyễn Văn An", X)
    with dbmod.new_session() as db:
        add_contact(db, "person", str(an), "email", "an.nguyen@daiviet.vn", "website", inferred=False)
        db.commit()
    r = base.post("/api/admin/enrich/compliance/optouts", json={"kind": "phone", "value": "0912 345 678", "reason": "Gọi điện yêu cầu"})
    assert r.status_code == 201 and r.json()["value"] == "+84912345678"
    assert base.post("/api/admin/enrich/compliance/optouts", json={"kind": "email", "value": "khong-phai-email"}).status_code == 422

    found = base.get("/api/admin/enrich/compliance/subjects?q=an.nguyen@daiviet.vn").json()
    assert [p["id"] for p in found] == [an]
    rep = base.get(f"/api/admin/enrich/compliance/subjects/{an}/report").json()  # T06
    assert rep["nguoi"]["ho_ten"] == "Nguyễn Văn An" and rep["vai_tro"][0]["chuc_danh"] == "Tổng Giám đốc"
    assert rep["lien_he"][0]["gia_tri"] == "an.nguyen@daiviet.vn" and rep["nguon_goc"] and rep["nguon_goc"][0]["co_so_phap_ly"]
    dl = base.get(f"/api/admin/enrich/compliance/subjects/{an}/report?download=true")
    assert dl.headers["content-disposition"].startswith("attachment")

    # T05 — ẩn vĩnh viễn: không còn trong hồ sơ doanh nghiệp
    hoa = person_id("Lê Thị Hoa", X)
    assert base.post(f"/api/admin/enrich/compliance/subjects/{hoa}/erase", json={"mode": "hide", "reason": "YC-001"}).json()["mode"] == "hide"
    names = [p["ho_ten"] for p in base.get(f"/api/admin/enrich/companies/{X}/people").json()]
    assert names == ["Nguyễn Văn An"]

    # T05 — xoá: dữ liệu mất, email vào danh sách từ chối, nguồn nói lại cũng không tạo lại hồ sơ
    r = base.post(f"/api/admin/enrich/compliance/subjects/{an}/erase", json={"mode": "delete", "reason": "YC-002"}).json()
    assert r["mode"] == "delete" and r["contacts"] == 1
    assert base.get(f"/api/admin/enrich/companies/{X}/people").json() == []
    assert any(o["value"] == "an.nguyen@daiviet.vn" for o in base.get("/api/admin/enrich/compliance/optouts").json()["items"])
    add_people(X, [("Nguyễn Văn An", "Tổng Giám đốc")], url="https://nguon.vn/lan-2")
    assert base.get(f"/api/admin/enrich/companies/{X}/people").json() == []
    from app.models_enrich import OptOut

    with dbmod.new_session() as db:
        stored = [v for (v,) in db.execute(select(OptOut.value).where(OptOut.kind == "ten_dn"))]
    assert stored and all("Nguyễn" not in v and "nguyen" not in v for v in stored)  # chỉ khoá băm

    sales = login_as("kinh_doanh", "sales9@leadscan.vn")
    editor = login_as("bien_tap", "editor9@leadscan.vn")
    for c in (sales, editor):
        assert c.get("/api/admin/enrich/compliance/subjects?q=nguyen").status_code == 403
    auditor = login_as("tham_dinh", "audit9@leadscan.vn")
    assert auditor.get("/api/admin/enrich/compliance/optouts").status_code == 200


def test_retention_dpia_and_logs(base):
    from app.models_enrich import EnrichPerson

    hoa = person_id("Lê Thị Hoa", X)
    with dbmod.new_session() as db:
        db.get(EnrichPerson, hoa).created_at = utcnow() - timedelta(days=800)
        db.commit()
    due = base.get("/api/admin/enrich/compliance/retention").json()
    assert [p["id"] for p in due["items"]] == [hoa] and due["months"] == 24  # T07
    base.get(f"/api/admin/enrich/persons/{hoa}")  # được dùng → không còn quá hạn
    assert base.get("/api/admin/enrich/compliance/retention").json()["items"] == []

    d = base.get("/api/admin/enrich/compliance/dpia").json()  # T10
    assert {s["ma"] for s in d["nguon"]} >= {"dkkd_mua", "bien_tap"} and d["thoi_han"]["du_lieu_ca_nhan_khong_dung_thang"] == 24
    assert d["loai_du_lieu"]["so_luong"]["nguoi"] == 2 and "CCCD / CMND" in d["loai_du_lieu"]["khong_thu_thap"]
    assert any(x["hanh_dong"] == "read" for x in d["truy_cap_12_thang"])
    logs = base.get("/api/admin/enrich/compliance/access-logs?action=read").json()
    assert logs and logs[0]["target"] == f"person:{hoa}"
    sales = login_as("kinh_doanh", "sales10@leadscan.vn")
    assert sales.get("/api/admin/enrich/compliance/dpia").status_code == 403


def test_raw_purge_keeps_evidence(base):
    from app.enrich import raw_store
    from app.models_enrich import CompanyEvidence, SourcePage
    from app.services import storage

    mem = storage.MemoryStorage()
    storage.set_backend(mem)
    try:
        with dbmod.new_session() as db:
            src = sources.ensure(db, "bien_tap")
            page, _ = raw_store.save_page(db, src.code, "https://x.vn/a", b"<p>old</p>", "text/html", mst=X)
            page.fetched_at = utcnow() - timedelta(days=400)
            db.add(CompanyEvidence(mst=X, field="website", value="https://x.vn", source_code=src.code, method="luat", source_page_id=page.id, source_url="https://x.vn/a"))
            db.commit()
            key, page_id = page.storage_key, page.id
        assert scheduler.purge_raw(dbmod.new_session()) == 1  # chỉ trang quá hạn (file ĐKKD vừa nhập vẫn giữ)
        assert mem.head(key) is None
        with dbmod.new_session() as db:
            assert db.get(SourcePage, page_id) is None and db.scalar(select(func.count()).select_from(SourcePage)) == 1
            ev = db.scalar(select(CompanyEvidence).where(CompanyEvidence.source_url == "https://x.vn/a"))
            assert ev is not None and ev.source_page_id is None
    finally:
        storage.set_backend(None)
