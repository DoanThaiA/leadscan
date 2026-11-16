"""Làm giàu dữ liệu MST — giai đoạn 2: nguồn chính thức, hàng đợi có checkpoint, giới hạn tốc độ, hàng đợi thủ công."""

import io
import re
from datetime import timedelta

import httpx
import pytest
import respx
from openpyxl import Workbook
from sqlalchemy import func, select

from app import db as dbmod
from app.enrich import runner, sources
from app.enrich.connectors import registry
from app.enrich.connectors.base import CompanyFact, Connector, Facts, NeedsHuman
from app.enrich.normalize import company_type, normalize_phone, normalize_status, parse_money, province_of
from app.enrich.titles import normalize_title
from tests.test_enrich import b64, import_csv, login_as

# ------------------------------------------------------------------ chuẩn hoá (B02, B03)


@pytest.mark.parametrize(
    "addr,prov",
    [
        ("Số 1 Láng Hạ, Đống Đa, Thành phố Hà Nội, Việt Nam", "Hà Nội"),
        ("KCN VSIP, Thuận An, Tỉnh Bình Dương", "Hồ Chí Minh"),  # tên cũ → tỉnh sau sáp nhập 2025
        ("12 Lê Lợi, TP Quy Nhơn, Bình Định", "Gia Lai"),
        ("Phường Phú Hội, Thừa Thiên Huế", "Huế"),
        ("Lô A KCN Tân Tạo TP.HCM", "Hồ Chí Minh"),
        ("không rõ", None),
    ],
)
def test_province(addr, prov):
    assert province_of(addr) == prov


def test_value_normalizers():
    assert company_type("CÔNG TY TNHH MTV ABC") == "Công ty TNHH một thành viên"
    assert company_type("Công ty Cổ phần Sữa Việt Nam") == "Công ty cổ phần"
    assert company_type("Chi nhánh Công ty X tại Hà Nội") == "Chi nhánh"
    assert normalize_status("NNT đang hoạt động (đã được cấp GCN ĐKT)") == "Đang hoạt động"
    assert normalize_status("NNT ngừng hoạt động và đã đóng MST") == "Ngừng hoạt động, đã đóng MST"
    assert normalize_phone("024 3826 1234") == "+842438261234"
    assert normalize_phone("+84 912.345.678") == "+84912345678"
    assert normalize_phone("123") is None
    assert parse_money("1.500.000.000") == 1_500_000_000
    assert parse_money("2,5 tỷ đồng") == 2_500_000_000
    assert normalize_title("Tổng Giám đốc") == ("tong_giam_doc", True)
    assert normalize_title("Phó Chủ tịch HĐQT") == ("pho_chu_tich_hdqt", True)
    assert normalize_title("Kế toán trưởng") == ("ke_toan_truong", False)
    assert normalize_title("Giám đốc Tài chính") == ("giam_doc_khoi", True)


# ------------------------------------------------------------------ dữ liệu mua ĐKKD (A03)


def xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


DKKD_FILE = [
    ["DỮ LIỆU DOANH NGHIỆP — CỔNG THÔNG TIN QUỐC GIA VỀ ĐĂNG KÝ DOANH NGHIỆP"],
    [],
    ["Mã số doanh nghiệp", "Tên doanh nghiệp", "Địa chỉ trụ sở chính", "Tình trạng hoạt động", "Ngành nghề kinh doanh chính", "Ngày thành lập", "Vốn điều lệ", "Người đại diện theo pháp luật", "Số CCCD người đại diện"],
    ["0101234567", "CÔNG TY CỔ PHẦN ĐẠI VIỆT", "Số 1 Láng Hạ, Đống Đa, Hà Nội", "Đang hoạt động", "Sản xuất bao bì", "05/03/2010", "15.000.000.000", "Nguyễn Văn An", "001080001234"],
    ["0309876543", "CÔNG TY TNHH SAO MAI", "KCN Sóng Thần, Dĩ An, Tỉnh Bình Dương", "Tạm ngừng kinh doanh có thời hạn", "Thương mại", "2015-07-01", "2 tỷ", "Trần Thị Bình", "079090009999"],
    ["0999999999", "CÔNG TY NGOÀI DANH SÁCH", "Hà Nội", "Đang hoạt động", "", "", "", "Lê C", "1"],
]


def dkkd_body(**over):
    return {
        "kind": "dkkd_mua",
        "file_name": "dkkd-11-2026.xlsx",
        "file_b64": b64(xlsx(DKKD_FILE)),
        "source_url": "Hợp đồng cung cấp thông tin số 123/2026/HĐ-ĐKKD",
        "data_date": "2026-11-10",
        **over,
    }


@pytest.fixture
def two_msts(admin):
    import_csv(admin, ["MST,Tên", "0101234567,Cty Dai Viet (ten cu)", "0309876543,"])
    return admin


def test_dkkd_preview_skips_sensitive_and_unknown(two_msts):
    body = dkkd_body()
    body.pop("source_url"), body.pop("data_date")
    r = two_msts.post("/api/admin/enrich/imports/preview", json=body)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["matched"] == 2 and rep["not_in_system"] == 1 and rep["not_in_system_sample"] == ["0999999999"]
    assert rep["sensitive_columns"] == ["Số CCCD người đại diện"]
    assert rep["columns"]["nguoi_dai_dien"] == "Người đại diện theo pháp luật"
    assert "001080001234" not in str(rep["sample"])


def test_dkkd_import_fills_profile_people_and_beats_list_name(two_msts):
    admin = two_msts
    r = admin.post("/api/admin/enrich/imports", json=dkkd_body())
    assert r.status_code == 201, r.text
    rep = r.json()["report"]
    assert rep["people"] == 2 and rep["evidence"] > 10

    p = admin.get("/api/admin/enrich/companies/0101234567").json()
    f = {x["key"]: x for x in p["fields"]}
    assert f["ten"]["value"] == "CÔNG TY CỔ PHẦN ĐẠI VIỆT" and f["ten"]["source"]["code"] == "dkkd_mua"
    assert f["ten"]["conflict"] is True  # tên trong danh sách nhập lô vẫn giữ làm bằng chứng
    assert f["tinh"]["value"] == "Hà Nội" and f["trang_thai"]["value"] == "Đang hoạt động"
    assert f["nganh_nghe"]["value"] == ["Sản xuất bao bì"]
    assert f["ngay_thanh_lap"]["value"] == "2010-03-05" and f["von"]["value"] == 15_000_000_000
    assert f["ten"]["score"] == 95 and f["ten"]["stale"] is False
    assert p["loai_hinh"] == "Công ty cổ phần"

    p2 = admin.get("/api/admin/enrich/companies/0309876543").json()
    f2 = {x["key"]: x for x in p2["fields"]}
    assert f2["tinh"]["value"] == "Hồ Chí Minh" and f2["trang_thai"]["value"] == "Tạm ngừng kinh doanh"
    assert f2["von"]["value"] == 2_000_000_000

    people = admin.get("/api/admin/enrich/companies/0101234567/people").json()
    assert people[0]["ho_ten"] == "Nguyễn Văn An" and people[0]["chuc_danh_chuan"] == "dai_dien_phap_luat"
    assert people[0]["la_nguoi_quyet_dinh"] is True
    assert people[0]["bang_chung"][0]["source_url"].startswith("Hợp đồng")
    s = admin.get("/api/admin/enrich/stats").json()
    assert s["full_profile"] == 2 and s["with_decision_maker"] == 2

    # MST ngoài danh sách không được tạo hồ sơ (B05 + phạm vi mục 2)
    assert admin.get("/api/admin/enrich/companies/0999999999").status_code == 404

    # nhập lại cùng file → không sinh bằng chứng / người mới (B12)
    again = admin.post("/api/admin/enrich/imports", json=dkkd_body()).json()["report"]
    assert again["evidence"] == 0 and again["people"] == 0 and again["duplicates"] > 0

    from app.models_enrich import AccessLog

    with dbmod.new_session() as db:
        targets = list(db.scalars(select(AccessLog.target).where(AccessLog.action == "write")))
    assert "company:0101234567/people<-dkkd_mua" in targets


def test_import_requires_known_mst_and_header(two_msts):
    body = dkkd_body(file_b64=b64(xlsx([["Mã số doanh nghiệp", "Tên doanh nghiệp"], ["0888888888", "X"]])))
    r = two_msts.post("/api/admin/enrich/imports", json=body)
    assert r.status_code == 422 and "Không dòng nào khớp" in r.json()["detail"]
    body = dkkd_body(file_b64=b64(xlsx([["Cột A", "Cột B"], ["0101234567", "X"]])))
    assert "Không thấy dòng tiêu đề" in two_msts.post("/api/admin/enrich/imports", json=body).json()["detail"]


def test_tax_debt_and_procurement_signals(two_msts):
    admin = two_msts
    debt = xlsx([["STT", "Mã số thuế", "Tên người nộp thuế", "Tổng số tiền thuế nợ", "Cơ quan thuế quản lý"], [1, "0101234567", "CTCP Đại Việt", "1.234.567.000", "Thuế TP Hà Nội"]])
    r = admin.post("/api/admin/enrich/imports", json={"kind": "no_thue", "file_name": "no-thue.xlsx", "file_b64": b64(debt), "source_url": "https://hanoi.gdt.gov.vn/danh-sach-no-thue-10-2026", "data_date": "2026-10-31"})
    assert r.status_code == 201, r.text
    bid = xlsx([["Số TBMT", "Tên gói thầu", "Bên mời thầu", "Mã số thuế nhà thầu", "Tên nhà thầu trúng thầu", "Giá trúng thầu", "Ngày phê duyệt"], ["IB2600012345", "Cung cấp bao bì", "Bệnh viện X", "0101234567", "Đại Việt", "980.000.000", "12/11/2026"]])
    r = admin.post("/api/admin/enrich/imports", json={"kind": "dau_thau", "file_name": "kq.xlsx", "file_b64": b64(bid), "source_url": "https://muasamcong.mpi.gov.vn/ket-qua/IB2600012345"})
    assert r.status_code == 201, r.text
    sig = admin.get("/api/admin/enrich/companies/0101234567").json()["signals"]
    kinds = {s["kind"]: s for s in sig}
    assert kinds["no_thue"]["payload"]["so_tien"] == 1_234_567_000 and kinds["no_thue"]["day"] == "2026-10-31"
    assert kinds["trung_thau"]["payload"]["gia_trung_thau"] == 980_000_000 and kinds["trung_thau"]["day"] == "2026-11-12"
    # nhập lại → không trùng tín hiệu
    admin.post("/api/admin/enrich/imports", json={"kind": "dau_thau", "file_name": "kq.xlsx", "file_b64": b64(bid), "source_url": "https://muasamcong.mpi.gov.vn/ket-qua/IB2600012345"})
    assert len(admin.get("/api/admin/enrich/companies/0101234567").json()["signals"]) == 2
    assert len(admin.get("/api/admin/enrich/imports").json()["items"]) == 3


# ------------------------------------------------------------------ hàng đợi thủ công (A10)


def test_manual_queue_flow(two_msts):
    admin = two_msts
    batch_id = admin.get("/api/admin/enrich/batches").json()[0]["id"]
    r = admin.post("/api/admin/enrich/runs", json={"name": "Tra ĐKKD thủ công", "connectors": ["dkkd_tra_cuu"], "batch_id": batch_id})
    assert r.status_code == 201, r.text
    assert r.json()["totals"]["manual"] == 2
    # tạo lại vòng trùng → không sinh việc trùng cho MST đang có việc mở (A06)
    assert admin.post("/api/admin/enrich/runs", json={"name": "Lặp", "connectors": ["dkkd_tra_cuu"]}).json()["totals"]["total"] == 0

    t = admin.get("/api/admin/enrich/manual/next").json()["task"]
    assert t["mst"] == "0101234567" and t["lookup_url"].startswith("https://dangkykinhdoanh.gov.vn")
    assert {f["key"] for f in t["fields"]} >= {"ten", "dia_chi", "trang_thai", "nguoi_dai_dien"}

    # người khác không lấy được việc đang bị giữ
    editor = login_as("bien_tap", "editor@leadscan.vn")
    t2 = editor.get("/api/admin/enrich/manual/next").json()["task"]
    assert t2["mst"] == "0309876543"
    assert editor.post(f"/api/admin/enrich/manual/{t['job_id']}", json={"action": "save", "values": {"ten": "X"}}).status_code == 422

    assert admin.post(f"/api/admin/enrich/manual/{t['job_id']}", json={"action": "save", "values": {}}).status_code == 422
    r = admin.post(
        f"/api/admin/enrich/manual/{t['job_id']}",
        json={"action": "save", "values": {"ten": "Công ty CP Đại Việt", "dia_chi": "1 Láng Hạ, Hà Nội", "trang_thai": "Đang hoạt động", "nguoi_dai_dien": "Nguyễn Văn An", "khong_co": "bị bỏ"}},
    )
    assert r.status_code == 200 and r.json()["status"] == "done"
    f = {x["key"]: x for x in admin.get("/api/admin/enrich/companies/0101234567").json()["fields"]}
    assert f["ten"]["method"] == "nhap_tay" and f["ten"]["source"]["code"] == "dkkd_tra_cuu"
    assert f["tinh"]["value"] == "Hà Nội"

    assert editor.post(f"/api/admin/enrich/manual/{t2['job_id']}", json={"action": "skip"}).status_code == 200
    assert editor.get("/api/admin/enrich/manual/next").json()["task"] is None  # bỏ qua → 24 giờ sau mới hiện lại
    sales = login_as("kinh_doanh", "sales2@leadscan.vn")
    assert sales.get("/api/admin/enrich/manual/next").status_code == 403


# ------------------------------------------------------------------ connector tự động: khung chạy (A06, A08, A09, A13)


class FakeHttp(Connector):
    code = "nguon_thu"
    name = "Nguồn thử nghiệm"
    kind = "http"
    domain = "nguon.test"
    default_trust = 0.8
    legal_basis = "Nguồn giả lập cho kiểm thử."
    defaults = {"min_interval_s": 0.0, "timeout_s": 5, "max_retries": 0, "recrawl_days": 90}
    version = 1

    def urls(self, mst):
        return [f"https://nguon.test/dn/{mst}"]

    def parse(self, mst, url, content, content_type):
        html = content.decode()
        if "captcha" in html:
            raise NeedsHuman("Trang yêu cầu captcha")
        name = re.search(r"<h1>(.*?)</h1>", html).group(1)
        addr = re.search(r'<p class="addr">(.*?)</p>', html).group(1)
        facts = Facts(company=[CompanyFact("ten", name, f"<h1>{name}</h1>"), CompanyFact("dia_chi", addr, addr)])
        if self.version > 1:
            facts.company.append(CompanyFact("website", "daiviet.vn", "website"))
        return facts


def page(name, addr="Số 1, Hà Nội"):
    return httpx.Response(200, html=f'<html><h1>{name}</h1><p class="addr">{addr}</p></html>')


@pytest.fixture
def fake_http(two_msts, monkeypatch):
    from app.services import storage

    c = registry.register(FakeHttp())
    monkeypatch.setattr(sources, "MIN_INTERVAL_S", 0.0)
    storage.set_backend(storage.MemoryStorage())
    runner._robots.clear()
    with dbmod.new_session() as db:
        src = sources.ensure(db, c.code)
        src.enabled = True
        db.commit()
    yield two_msts  # client admin; connector: registry.get("nguon_thu")
    registry.unregister(c.code)
    storage.set_backend(None)
    runner._robots.clear()


def drain():
    from app.worker import enrich_dispatch_task

    for _ in range(50):
        if not enrich_dispatch_task():
            return


def start_run(client, **over):
    r = client.post("/api/admin/enrich/runs", json={"name": "Vòng thử", "connectors": ["nguon_thu"], **over})
    assert r.status_code == 201, r.text
    drain()
    return client.get(f"/api/admin/enrich/runs/{r.json()['id']}").json()


@respx.mock
def test_http_connector_end_to_end_and_reparse(fake_http):
    admin = fake_http
    respx.get("https://nguon.test/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n"))
    respx.get("https://nguon.test/dn/0101234567").mock(return_value=page("Công ty CP Đại Việt"))
    respx.get("https://nguon.test/dn/0309876543").mock(return_value=httpx.Response(404))
    run = start_run(admin)
    assert run["status"] == "done"
    t = run["totals"]
    assert t["done"] == 1 and t["not_found"] == 1 and t["remaining"] == 0

    f = {x["key"]: x for x in admin.get("/api/admin/enrich/companies/0101234567").json()["fields"]}
    assert f["ten"]["value"] == "Công ty CP Đại Việt" and f["ten"]["source"]["code"] == "nguon_thu" and f["ten"]["method"] == "luat"

    from app.models_enrich import CompanyEvidence, FetchLog, SourcePage

    with dbmod.new_session() as db:
        pg = db.scalar(select(SourcePage).where(SourcePage.source_code == "nguon_thu"))
        assert pg.mst == "0101234567" and pg.size > 0
        calls_before = db.scalar(select(func.count()).select_from(FetchLog))
    assert respx.calls.call_count == calls_before == 3  # robots + 2 trang

    # A09: đổi bộ bóc tách → bóc lại từ bản gốc đã lưu, không gọi mạng lần nào
    registry.get("nguon_thu").version = 2
    r = admin.post("/api/admin/enrich/sources/nguon_thu/reparse")
    assert r.status_code == 200 and r.json()["pages"] == 1 and r.json()["evidence"] == 2  # website + domain
    assert respx.calls.call_count == 3
    with dbmod.new_session() as db:
        assert db.scalar(select(func.count()).select_from(CompanyEvidence).where(CompanyEvidence.field == "domain")) == 1

    # vòng mới: MST đã xong được tải lại nhưng nội dung trùng → không sinh bằng chứng trùng (B12)
    respx.get("https://nguon.test/dn/0101234567").mock(return_value=page("Công ty CP Đại Việt"))
    start_run(admin)
    with dbmod.new_session() as db:
        assert db.scalar(select(func.count()).select_from(CompanyEvidence).where(CompanyEvidence.source_code == "nguon_thu", CompanyEvidence.field == "ten")) == 1


@respx.mock
def test_robots_disallow_and_captcha_go_to_right_queue(fake_http):
    respx.get("https://nguon.test/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow: /dn/0309876543\n"))
    respx.get("https://nguon.test/dn/0101234567").mock(return_value=httpx.Response(200, html="<p>Nhập captcha</p>"))
    blocked = respx.get("https://nguon.test/dn/0309876543").mock(return_value=page("X"))
    run = start_run(fake_http)
    assert run["totals"]["manual"] == 1 and run["totals"]["failed"] == 1
    assert not blocked.called
    assert any("robots.txt" in e["error"] for e in run["errors"])
    task = fake_http.get("/api/admin/enrich/manual/next?connector=nguon_thu").json()["task"]
    assert task["mst"] == "0101234567" and "captcha" in task["hint"]


@respx.mock
def test_rate_limit_per_domain_is_respected_and_logged(fake_http, monkeypatch):
    monkeypatch.setattr(sources, "MIN_INTERVAL_S", 0.25)
    respx.get("https://nguon.test/robots.txt").mock(return_value=httpx.Response(200, text=""))
    respx.get(url__regex=r"https://nguon.test/dn/.*").mock(return_value=page("A"))
    start_run(fake_http)
    d = fake_http.get("/api/admin/enrich/ops/domains").json()
    dom = next(x for x in d["domains"] if x["domain"] == "nguon.test")
    assert dom["requests"] == 3 and dom["min_gap_s"] >= 0.25


@respx.mock
def test_failing_source_retries_then_auto_pauses(fake_http):
    admin = fake_http
    for i in range(12):
        import_csv(admin, ["MST", f"05{i:08d}"], name=f"Lô {i}")
    respx.get("https://nguon.test/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(url__regex=r"https://nguon.test/dn/.*").mock(return_value=httpx.Response(503))
    start_run(admin)
    src = next(s for s in admin.get("/api/admin/enrich/sources").json() if s["code"] == "nguon_thu")
    assert src["enabled"] is False and "Tự tạm dừng" in src["paused_reason"]
    run = admin.get("/api/admin/enrich/runs").json()["runs"][0]
    # robots.txt (404 = được phép) + 9 trang lỗi = 10 request, 90% lỗi → dừng; phần còn lại chờ, không chạy tiếp
    assert run["totals"]["failed"] == 9 and run["totals"]["remaining"] == 5
    # bật lại → xoá lý do tạm dừng
    r = admin.patch("/api/admin/enrich/sources/nguon_thu", json={"enabled": True})
    assert r.status_code == 200 and r.json()["paused_reason"] == ""


@respx.mock
def test_retry_with_backoff_then_success(fake_http):
    with dbmod.new_session() as db:
        src = sources.ensure(db, "nguon_thu")
        src.config = {**src.config, "max_retries": 2}
        db.commit()
    respx.get("https://nguon.test/robots.txt").mock(return_value=httpx.Response(404))
    route = respx.get(url__regex=r"https://nguon.test/dn/.*")
    route.side_effect = [httpx.Response(500), httpx.Response(500), page("A"), page("B")]
    run = start_run(fake_http)
    assert run["totals"]["remaining"] == 2  # đang lùi dần, chưa tới giờ thử lại
    from app.models_enrich import CrawlJob

    with dbmod.new_session() as db:
        for j in db.scalars(select(CrawlJob)):
            j.next_attempt_at = j.next_attempt_at - timedelta(hours=1)
        db.commit()
    drain()
    run = fake_http.get(f"/api/admin/enrich/runs/{run['id']}").json()
    assert run["totals"]["done"] == 2 and run["status"] == "done"


def test_checkpoint_recovers_stale_jobs_and_stops_respect_pause(fake_http):
    admin = fake_http
    from app.models_enrich import CrawlJob

    r = admin.post("/api/admin/enrich/ops", json={})  # sai method → 405, để chắc endpoint là PUT
    assert r.status_code == 405
    assert admin.put("/api/admin/enrich/ops", json={"paused": True, "pause_reason": "Bảo trì"}).json()["running_now"] is False
    run = admin.post("/api/admin/enrich/runs", json={"name": "Vòng", "connectors": ["nguon_thu"]}).json()
    drain()
    assert admin.get(f"/api/admin/enrich/runs/{run['id']}").json()["totals"]["remaining"] == 2  # dừng khẩn cấp: không chạy

    # worker chết giữa chừng: việc "running" quá 30 phút → về pending (N02)
    with dbmod.new_session() as db:
        j = db.scalar(select(CrawlJob).limit(1))
        j.status, j.started_at = "running", j.created_at - timedelta(hours=1)
        db.commit()
        assert runner.recover_stale(db) == 1
        assert db.get(CrawlJob, j.id).status == "pending"

    # khung giờ chạy
    assert runner.in_window({"enabled": True, "start": 22, "end": 6}, _vn(23)) is True
    assert runner.in_window({"enabled": True, "start": 22, "end": 6}, _vn(12)) is False
    assert runner.in_window({"enabled": True, "start": 8, "end": 17}, _vn(9)) is True

    # tạm dừng / huỷ vòng
    assert admin.post(f"/api/admin/enrich/runs/{run['id']}/status", json={"status": "cancelled"}).json()["status"] == "cancelled"
    assert admin.post(f"/api/admin/enrich/runs/{run['id']}/status", json={"status": "running"}).status_code == 409


def _vn(hour):
    from datetime import datetime

    return datetime(2026, 11, 17, hour, 0, tzinfo=runner.VN)


# ------------------------------------------------------------------ cấu hình nguồn (A04, A08, T12) & quyền


def test_source_config_rules(two_msts):
    admin = two_msts
    srcs = {s["code"]: s for s in admin.get("/api/admin/enrich/sources").json()}
    assert srcs["dkkd_mua"]["trust"] == 0.95 and srcs["dkkd_mua"]["enabled"] is True
    assert srcs["dkkd_tra_cuu"]["kind"] == "manual"
    assert admin.patch("/api/admin/enrich/sources/dkkd_tra_cuu", json={"min_interval_s": 1}).status_code == 422  # A08: ≥ 2 giây
    r = admin.patch("/api/admin/enrich/sources/dkkd_tra_cuu", json={"min_interval_s": 5, "trust": 0.7})
    assert r.json()["min_interval_s"] == 5 and r.json()["trust"] == 0.7
    # T12: xoá cơ sở pháp lý → tắt; không bật lại được khi chưa khai
    r = admin.patch("/api/admin/enrich/sources/tracuu_nnt", json={"legal_basis": ""})
    assert r.json()["enabled"] is False
    r = admin.patch("/api/admin/enrich/sources/tracuu_nnt", json={"enabled": True})
    assert r.status_code == 422 and "cơ sở pháp lý" in r.json()["detail"]
    assert admin.post("/api/admin/enrich/runs", json={"name": "x", "connectors": ["tracuu_nnt"]}).status_code == 422
    assert admin.post("/api/admin/enrich/runs", json={"name": "x", "connectors": ["dkkd_mua"]}).status_code == 422  # nguồn file


def test_ops_permissions(two_msts):
    auditor = login_as("tham_dinh", "audit2@leadscan.vn")
    assert auditor.get("/api/admin/enrich/runs").status_code == 200
    assert auditor.post("/api/admin/enrich/runs", json={"name": "x", "connectors": ["dkkd_tra_cuu"]}).status_code == 403
    assert auditor.patch("/api/admin/enrich/sources/dkkd_mua", json={"trust": 0.1}).status_code == 403
    assert auditor.post("/api/admin/enrich/imports/preview", json={"kind": "no_thue", "file_name": "a.csv", "file_b64": b64(b"x")}).status_code == 403
    editor = login_as("bien_tap", "editor2@leadscan.vn")
    assert editor.put("/api/admin/enrich/ops", json={"paused": True}).status_code == 403
    assert editor.post("/api/admin/enrich/runs", json={"name": "x", "connectors": ["dkkd_tra_cuu"]}).status_code == 403
    assert editor.get("/api/admin/enrich/imports").status_code == 200
