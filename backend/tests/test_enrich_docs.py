"""Làm giàu dữ liệu MST — giai đoạn 3: doanh nghiệp niêm yết, tài liệu công bố thông tin, bóc tách HĐQT / Ban điều hành."""

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app import db as dbmod
from app.enrich import governance, llm, runner, sources
from tests.test_enrich import b64, import_csv, login_as
from tests.test_enrich_ops import drain, xlsx

# ------------------------------------------------------------------ tài liệu mẫu

REPORT_HTML = """<html><body>
<h2>BÁO CÁO TÌNH HÌNH QUẢN TRỊ CÔNG TY 6 tháng đầu năm 2026</h2>
<p>I. Hoạt động của Đại hội đồng cổ đông</p><p>Nghị quyết số 01/2026 thông qua giao dịch với người có liên quan</p>
<p>II. Hội đồng quản trị</p>
<table><tr><th>STT</th><th>Thành viên HĐQT</th><th>Chức vụ</th><th>Ngày bắt đầu/không còn là thành viên HĐQT</th></tr>
<tr><td>1</td><td>Ông NGUYỄN VĂN AN</td><td>Chủ tịch HĐQT</td><td>Bổ nhiệm ngày 25/04/2023</td></tr>
<tr><td>2</td><td>Bà Trần Thị Bình</td><td>Thành viên HĐQT độc lập</td><td>Bổ nhiệm ngày 25/04/2023</td></tr>
<tr><td>3</td><td>Ông Lê Văn Cường</td><td>Thành viên HĐQT</td><td>Miễn nhiệm ngày 30/06/2026</td></tr></table>
<p>IV. Ban điều hành</p>
<table><tr><th>STT</th><th>Thành viên Ban điều hành</th><th>Ngày tháng năm sinh</th><th>Trình độ chuyên môn</th><th>Ngày bổ nhiệm/miễn nhiệm</th></tr>
<tr><td>1</td><td>Ông Phạm Minh Đức - Tổng Giám đốc</td><td>12/03/1975</td><td>Thạc sĩ</td><td>Bổ nhiệm ngày 01/01/2024</td></tr>
<tr><td>2</td><td>Bà Hoàng Thu Hà<br>Phó Tổng Giám đốc</td><td>01/02/1980</td><td>Cử nhân</td><td>01/07/2025</td></tr></table>
<p>VII. Danh sách về người có liên quan của công ty đại chúng</p>
<table><tr><th>Tên tổ chức/cá nhân</th><th>Số CCCD</th><th>Địa chỉ</th><th>Mối quan hệ</th></tr><tr><td>Nguyễn Thị Vợ</td><td>001234567890</td><td>Hà Nội</td><td>Vợ ông An</td></tr></table>
<p>Ông Nguyễn Văn Bí Mật - Thành viên HĐQT</p>
</body></html>"""

BOARD_ONLY_HTML = """<html><body><p>II. Hội đồng quản trị</p>
<table><tr><th>STT</th><th>Thành viên HĐQT</th><th>Chức vụ</th></tr>
<tr><td>1</td><td>Ông Nguyễn Văn An</td><td>Chủ tịch HĐQT</td></tr></table></body></html>"""


def pdf_bytes(lines: list[str]) -> bytes:
    """PDF 1 trang tối giản (font Helvetica — chữ không dấu) để thử nhánh đọc PDF."""
    esc = [ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for ln in lines]
    stream = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(f"({ln}) Tj T*" for ln in esc) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


# ------------------------------------------------------------------ bóc tách (B01, T09)


def test_tables_tier_reads_board_and_exec_and_cuts_insider_section():
    doc = governance.load(REPORT_HTML.encode(), "text/html")
    ex = governance.extract(doc)
    assert ex.method == "cau_truc" and ex.complete
    people = {p.ho_ten: p for p in ex.people}
    assert set(people) == {"Nguyễn Văn An", "Trần Thị Bình", "Lê Văn Cường", "Phạm Minh Đức", "Hoàng Thu Hà"}
    assert people["Nguyễn Văn An"].code == "chu_tich_hdqt" and people["Nguyễn Văn An"].tu_ngay == "2023-04-25"
    assert people["Lê Văn Cường"].den_ngay == "2026-06-30"
    # ngày sinh không bao giờ bị đọc nhầm thành ngày bổ nhiệm
    assert people["Phạm Minh Đức"].tu_ngay == "2024-01-01" and people["Phạm Minh Đức"].code == "tong_giam_doc"
    assert people["Hoàng Thu Hà"].code == "pho_tong_giam_doc"
    # mục người có liên quan bị cắt: không người, không CCCD, kể cả trong văn bản gửi mô hình
    assert "Danh sách về người có liên quan" in ex.cut_at
    text = governance.text_for_model(doc)
    assert "001234567890" not in text and "Vợ" not in text and "Bí Mật" not in text
    assert "1975" not in str(ex.to_dict())


def test_rules_tier_on_text_and_pdf():
    txt = (
        "II. Hội đồng quản trị\n1. Ông Nguyễn Văn An - Chủ tịch HĐQT\n2. Bà Trần Thị Bình – Thành viên HĐQT\n"
        "III. Ban điều hành\nÔng Phạm Minh Đức, Tổng Giám đốc, bổ nhiệm ngày 01/01/2024\n"
        "VIII. Giao dịch cổ phiếu của người nội bộ\nÔng Nguyễn Văn Bí Mật - Thành viên HĐQT\n"
    )
    ex = governance.extract(governance.load(txt.encode(), "text/plain"))
    assert ex.method == "luat" and ex.complete
    assert [p.ho_ten for p in ex.people] == ["Nguyễn Văn An", "Trần Thị Bình", "Phạm Minh Đức"]

    pdf = pdf_bytes([
        "BAO CAO TINH HINH QUAN TRI CONG TY",
        "II. Hoi dong quan tri",
        "1. Ong Nguyen Van An - Chu tich HDQT",
        "2. Ba Tran Thi Binh - Thanh vien HDQT",
        "IV. Ban dieu hanh",
        "Ong Pham Minh Duc - Tong Giam doc, bo nhiem ngay 01/01/2024",
        "VII. Danh sach ve nguoi co lien quan",
        "Ong Bi Mat - Thanh vien HDQT",
    ])
    doc = governance.load(pdf, "application/pdf")
    ex = governance.extract(doc)
    assert ex.complete and {p.ho_ten for p in ex.people} == {"Nguyen Van An", "Tran Thi Binh", "Pham Minh Duc"}
    assert ex.cut_at.startswith("VII.")


def test_scanned_pdf_goes_to_manual():
    ex = governance.extract(governance.load(pdf_bytes([]), "application/pdf"))
    assert not ex.people and any("dạng ảnh" in n for n in ex.notes)


# ------------------------------------------------------------------ luồng API


@pytest.fixture
def listed(admin):
    """Hai MST trong lô, nạp danh sách niêm yết gắn mã CK cho cả hai."""
    import_csv(admin, ["MST,Tên", "0101234567,CTCP Đại Việt", "0309876543,CTCP Sao Mai"])
    f = xlsx([["Mã CK", "Mã số thuế", "Tên công ty", "Sàn"], ["DVT", "0101234567", "CTCP Đại Việt", "HOSE"], ["SMC", "0309876543", "CTCP Sao Mai", "HNX"], ["ZZZ", "0999999999", "Ngoài DS", "UPCOM"]])
    r = admin.post("/api/admin/enrich/imports", json={"kind": "ds_niem_yet", "file_name": "niem-yet.xlsx", "file_b64": b64(f), "source_url": "https://www.hsx.vn/danh-sach"})
    assert r.status_code == 201, r.text
    return admin


def upload(client, html: str, ref="DVT", **over):
    body = {"ref": ref, "doc_type": "bao_cao_quan_tri", "period": "6T/2026", "source_url": "https://congty.vn/bctqt-6t-2026.html", "file_name": "bctqt.html", "file_b64": b64(html.encode()), **over}
    return client.post("/api/admin/enrich/documents/upload", json=body)


def test_listed_upload_auto_applies_and_counts_coverage(listed):
    admin = listed
    lst = admin.get("/api/admin/enrich/listed").json()
    assert lst["total_listed"] == 2 and lst["full_board"] == 0
    assert {r["ma_ck"] for r in lst["items"]} == {"DVT", "SMC"}

    r = upload(admin, REPORT_HTML)
    assert r.status_code == 201 and r.json()["status"] == "parsed", r.text  # đủ HĐQT + BĐH bằng bảng → tự ghi

    people = admin.get("/api/admin/enrich/companies/0101234567/people").json()
    by = {p["ho_ten"]: p for p in people}
    assert by["Nguyễn Văn An"]["chuc_danh_chuan"] == "chu_tich_hdqt" and by["Nguyễn Văn An"]["tu_ngay"] == "2023-04-25"
    assert by["Lê Văn Cường"]["den_ngay"] == "2026-06-30"  # đã miễn nhiệm
    assert "Nguyễn Văn Bí Mật" not in by and "Nguyễn Thị Vợ" not in by
    assert by["Phạm Minh Đức"]["bang_chung"][0]["source_url"] == "https://congty.vn/bctqt-6t-2026.html"

    lst = admin.get("/api/admin/enrich/listed").json()
    row = next(x for x in lst["items"] if x["ma_ck"] == "DVT")
    assert row["full"] and row["board"] == 2 and row["exec"] == 2 and row["documents"] == 1
    s = admin.get("/api/admin/enrich/stats").json()
    assert s["listed"] == 2 and s["listed_full_board"] == 1

    # báo cáo kỳ sau có TGĐ mới → tín hiệu bổ nhiệm (C06); nạp lại báo cáo cũ không sinh gì
    newer = REPORT_HTML.replace("Ông Phạm Minh Đức - Tổng Giám đốc", "Ông Đỗ Quang Huy - Tổng Giám đốc").replace("01/01/2024", "01/10/2026")
    assert upload(admin, newer, source_url="https://congty.vn/bctqt-2026-q4.html").json()["status"] == "parsed"
    sig = admin.get("/api/admin/enrich/companies/0101234567").json()["signals"]
    assert [(s["kind"], s["payload"]["chuc_danh"]) for s in sig] == [("bo_nhiem", "Tổng Giám đốc")]
    assert "Đỗ Quang Huy" not in str(sig)  # tín hiệu ở kho A chỉ có chức danh, không có tên người


def test_incomplete_document_goes_to_review_and_editor_fixes(listed):
    admin = listed
    r = upload(admin, BOARD_ONLY_HTML, ref="0309876543")
    assert r.json()["status"] == "needs_review"
    doc_id = r.json()["id"]
    docs = admin.get("/api/admin/enrich/documents?status=needs_review").json()
    assert docs["items"][0]["people_count"] == 1 and docs["items"][0]["has_exec"] is False
    assert "Nguyễn Văn An" not in str(docs)  # danh sách không lộ tên

    sales = login_as("kinh_doanh", "sales3@leadscan.vn")
    assert sales.get(f"/api/admin/enrich/documents/{doc_id}").status_code == 403
    assert sales.get(f"/api/admin/enrich/documents/{doc_id}/file").status_code == 403
    auditor = login_as("tham_dinh", "audit3@leadscan.vn")
    d = auditor.get(f"/api/admin/enrich/documents/{doc_id}").json()
    assert d["extracted"]["people"][0]["ho_ten"] == "Nguyễn Văn An"
    f = auditor.get(f"/api/admin/enrich/documents/{doc_id}/file")
    assert f.status_code == 200 and "Hội đồng quản trị" in f.text
    assert auditor.post(f"/api/admin/enrich/documents/{doc_id}/review", json={"action": "reject"}).status_code == 403

    people = d["extracted"]["people"] + [{"ho_ten": "Ông Phan Văn Tú", "chuc_danh": "Tổng Giám đốc", "nhom": "bdh", "tu_ngay": "2025-01-01", "den_ngay": None}]
    assert admin.post(f"/api/admin/enrich/documents/{doc_id}/review", json={"action": "approve", "people": [{"ho_ten": "x1"}]}).status_code == 422
    r = admin.post(f"/api/admin/enrich/documents/{doc_id}/review", json={"action": "approve", "people": people})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    ppl = {p["ho_ten"]: p for p in admin.get("/api/admin/enrich/companies/0309876543/people").json()}
    assert ppl["Phan Văn Tú"]["chuc_danh_chuan"] == "tong_giam_doc"
    methods = {p["ho_ten"]: p["bang_chung"][0]["method"] for p in ppl.values()}
    assert methods == {"Nguyễn Văn An": "cau_truc", "Phan Văn Tú": "thu_cong"}  # phần biên tập viên thêm = quyết định biên tập
    assert admin.get("/api/admin/enrich/listed?only_missing=true").json()["count"] == 1

    from app.models_enrich import AccessLog

    with dbmod.new_session() as db:
        targets = [t for (t,) in db.execute(select(AccessLog.target))]
    assert f"document:{doc_id}" in targets and f"document:{doc_id}/file" in targets and f"document:{doc_id}/approve" in targets


def test_unknown_company_and_bad_type_rejected(listed):
    assert upload(listed, REPORT_HTML, ref="XYZ").status_code == 422
    assert upload(listed, REPORT_HTML, doc_type="khong_co").status_code == 422


@pytest.fixture
def fast_cbtt(listed, monkeypatch):
    from app.services import storage

    monkeypatch.setattr(sources, "MIN_INTERVAL_S", 0.0)
    storage.set_backend(storage.MemoryStorage())
    runner._robots.clear()
    with dbmod.new_session() as db:
        src = sources.ensure(db, "cbtt")
        src.config = {**src.config, "min_interval_s": 0}
        db.commit()
    yield listed
    storage.set_backend(None)
    runner._robots.clear()


@respx.mock
def test_url_list_is_fetched_with_rate_limit_and_robots(fast_cbtt):
    admin = fast_cbtt
    respx.get("https://ir.daiviet.vn/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private/\n"))
    respx.get("https://ir.daiviet.vn/bctqt.html").mock(return_value=httpx.Response(200, html=REPORT_HTML))
    blocked = respx.get("https://ir.daiviet.vn/private/x.pdf").mock(return_value=httpx.Response(200, content=b"x"))
    respx.get("https://ir.saomai.vn/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://ir.saomai.vn/mat.pdf").mock(return_value=httpx.Response(404))
    text = "DVT, https://ir.daiviet.vn/bctqt.html, 6T/2026\nDVT, https://ir.daiviet.vn/private/x.pdf\nSMC; https://ir.saomai.vn/mat.pdf\nXYZ, https://a.vn/b\nDVT, khong-phai-url\n"
    r = admin.post("/api/admin/enrich/documents/urls", json={"text": text})
    assert r.status_code == 201
    rep = r.json()
    assert rep["created"] == 3 and len(rep["skipped"]) == 2
    drain()
    docs = {d["source_url"]: d for d in admin.get("/api/admin/enrich/documents").json()["items"]}
    assert docs["https://ir.daiviet.vn/bctqt.html"]["status"] == "parsed" and docs["https://ir.daiviet.vn/bctqt.html"]["period"] == "6T/2026"
    assert docs["https://ir.daiviet.vn/private/x.pdf"]["status"] == "failed" and "robots" in docs["https://ir.daiviet.vn/private/x.pdf"]["error"]
    assert docs["https://ir.saomai.vn/mat.pdf"]["status"] == "failed"
    assert not blocked.called
    # khai lại cùng đường dẫn → bỏ qua
    assert admin.post("/api/admin/enrich/documents/urls", json={"text": "DVT, https://ir.daiviet.vn/bctqt.html"}).json()["created"] == 0


def test_model_tier_is_off_by_default_and_cached_when_on(listed, monkeypatch):
    admin = listed
    plain = "Báo cáo quản trị\nHội đồng quản trị gồm ông Nguyễn Văn An làm chủ tịch và bà Trần Thị Bình.\nTổng giám đốc là ông Phạm Minh Đức.\n"
    calls = []

    def fake_call(text):
        calls.append(text)
        return ([
            {"ho_ten": "Nguyễn Văn An", "chuc_danh": "Chủ tịch HĐQT", "nhom": "hdqt", "tu_ngay": None, "den_ngay": None},
            {"ho_ten": "Phạm Minh Đức", "chuc_danh": "Tổng Giám đốc", "nhom": "bdh", "tu_ngay": "2024-01-01", "den_ngay": None},
        ], 1200, 150)

    monkeypatch.setattr(llm, "call_model", fake_call)
    r = upload(admin, plain, file_name="bc.txt", source_url="https://congty.vn/a.txt")
    assert r.json()["status"] == "needs_review" and calls == []  # tầng 3 tắt mặc định

    monkeypatch.setenv("LEADSCAN_ENRICH_LLM_ENABLED", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    r = upload(admin, plain, file_name="bc.txt", source_url="https://congty.vn/b.txt")
    doc_id = r.json()["id"]
    assert r.json()["status"] == "needs_review" and len(calls) == 1  # kết quả mô hình luôn qua duyệt
    d = admin.get(f"/api/admin/enrich/documents/{doc_id}").json()
    assert d["method"] == "mo_hinh" and {p["ho_ten"] for p in d["extracted"]["people"]} == {"Nguyễn Văn An", "Phạm Minh Đức"}
    # cùng nội dung → dùng bộ đệm, không gọi lại
    admin.post(f"/api/admin/enrich/documents/{doc_id}/reparse")
    assert len(calls) == 1
    from app.models_enrich import LlmCache

    with dbmod.new_session() as db:
        assert db.scalar(select(func.count()).select_from(LlmCache)) == 1

    # mô hình lỗi → ghi chú, tài liệu vẫn vào hàng chờ duyệt
    def boom(text):
        raise llm.LlmError("API lỗi 529")

    monkeypatch.setattr(llm, "call_model", boom)
    r = upload(admin, plain + "khác", file_name="bc2.txt", source_url="https://congty.vn/c.txt")
    d = admin.get(f"/api/admin/enrich/documents/{r.json()['id']}").json()
    assert d["status"] == "needs_review" and any("529" in n for n in d["extracted"]["notes"])
    get_settings.cache_clear()
