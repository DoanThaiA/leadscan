"""Kho doanh nghiệp (knowledge_companies): API quản trị + script quét PROFIT500."""

import httpx
import respx

from app import db as dbmod
from app.models import KnowledgeCompany
from app.services import profit500

URL = "/api/admin/knowledge-companies"


def body(**over) -> dict:
    d = {"name": "Công ty CP Thử Nghiệm", "tax_code": "0101234567", "industry": "Bao bì", "province": "Hà Nội"}
    d.update(over)
    return d


# ------------------------------------------------------------------ API


def test_can_dang_nhap(client):
    assert client.get(URL).status_code == 401


def test_them_sua_xoa(admin):
    r = admin.post(URL, json=body(founded_year=2005, website="https://thu.vn"))
    assert r.status_code == 201, r.text
    k = r.json()
    assert k["source"] == "manual" and k["ai_status"] == "pending" and k["founded_year"] == 2005

    lst = admin.get(URL, params={"q": "thử"}).json()
    assert lst["total"] == 1 and lst["counts"] == {"pending": 1}

    r = admin.put(f"{URL}/{k['id']}", json=body(name="Công ty CP Đã Sửa", ai_status="done", note="ghi chú"))
    assert r.status_code == 200 and r.json()["name"] == "Công ty CP Đã Sửa" and r.json()["ai_status"] == "done"
    assert admin.get(URL, params={"ai_status": "pending"}).json()["total"] == 0

    assert admin.delete(f"{URL}/{k['id']}").status_code == 204
    assert admin.get(f"{URL}/{k['id']}").status_code == 404


def test_mst_khong_trung_va_hop_le(admin):
    assert admin.post(URL, json=body()).status_code == 201
    dup = admin.post(URL, json=body(name="Công ty khác", tax_code="0101-234-567"))
    assert dup.status_code == 409
    assert admin.post(URL, json=body(name="Sai MST", tax_code="123")).json()["fields"]["tax_code"]
    # Không có MST thì thêm nhiều bản ghi vẫn được
    assert admin.post(URL, json=body(name="Chưa có MST 1", tax_code="")).status_code == 201
    assert admin.post(URL, json=body(name="Chưa có MST 2", tax_code=None)).status_code == 201


def test_nhan_vien_khong_duoc_xoa(admin, staff):
    k = staff.post(URL, json=body()).json()
    assert staff.delete(f"{URL}/{k['id']}").status_code == 403
    assert admin.delete(f"{URL}/{k['id']}").status_code == 204


# ------------------------------------------------------------------ đọc HTML


LIST_HTML = """
<div class="data-item rank-item">
  <div class="stt">52</div>
  <div><img src="https://cms.vietnamreport.net//source/LogoBusiness/greenfeed.png"></div>
  <div class="name">
    <div class="mb-2"><a href="/Thong-tin-doanh-nghiep/CONG-TY-CP-GREENFEED-VIET-NAM-Chart--261-2026.html" class="title">
      C&#212;NG TY CP GREENFEED VIỆT NAM </a></div>
    <div class="row">
      <div class="col-md-4"><span class="text-uppercase">CEO</span>: <a href="#profile">Đỗ Cao Bằng</a></div>
      <div class="col-md-4"><span class="text-uppercase">MST</span>: 1100598642</div>
      <div class="col-md-4"><span class="text-uppercase">Ngành nghề</span>: <a href="#">Sản xuất thức ăn chăn nuôi</a></div>
    </div>
  </div>
</div>
"""

# email "info@greenfeed.vn" được Cloudflare mã hoá với khoá 0x2a
CF = "2a" + bytes(b ^ 0x2A for b in b"info@greenfeed.vn").hex()

PROFILE_HTML = f"""
<h4 class="title">C&#212;NG TY CP GREENFEED VIỆT NAM</h4>
<div id="GeneralIntroduction">
  <div class="info-row"><div class="info-label">Tên tiếng Anh:</div><div class="info-value">GREENFEED VIETNAM CORPORATION</div></div>
  <div class="info-row"><div class="info-label">Xếp hạng PROFIT500:</div><div class="info-value"> 52(B1/2026) </div></div>
  <div class="info-row"><div class="info-label">Mã số thuế:</div><div class="info-value">1100598642</div></div>
  <div class="info-row"><div class="info-label">Mã chứng khoán:</div><div class="info-value">Chưa ni&#234;m yết</div></div>
  <div class="info-row"><div class="info-label">Trụ sở chính:</div><div class="info-value">Xã Nhựt Chánh - Huyện Bến Lức - Tỉnh Long An</div></div>
  <div class="info-row"><div class="info-label">Tel:</div><div class="info-value">0272-3632881</div></div>
  <div class="info-row"><div class="info-label">Email:</div><div class="info-value"><a class="__cf_email__" data-cfemail="{CF}">[email protected]</a></div></div>
  <div class="info-row"><div class="info-label">Website:</div><div class="info-value"><a href="http://www.greenfeed.com.vn">http://www.greenfeed.com.vn</a></div></div>
  <div class="info-row"><div class="info-label">Năm thành lập:</div><div class="info-value">2003</div></div>
  <div class="info-row"><div class="info-label">Vốn điều lệ:</div><div class="info-value">1.000 tỷ</div></div>
  <div class="dn-gioi-thieu"><h2 class="intro-title"><span>Giới thiệu</span></h2>
    <p><p>Th&agrave;nh lập năm 2003, GREENFEED l&agrave; tập đo&agrave;n.</p><p>Đoạn hai.</p></p></div>
</div>
"""


def test_doc_danh_sach():
    [it] = profit500.parse_list_html(LIST_HTML)
    assert it["name"] == "CÔNG TY CP GREENFEED VIỆT NAM"
    assert (it["rank"], it["source_id"], it["rank_year"]) == (52, "261", 2026)
    assert it["ceo_name"] == "Đỗ Cao Bằng" and it["tax_code"] == "1100598642"
    assert it["industry"] == "Sản xuất thức ăn chăn nuôi"
    assert it["source_url"].startswith("https://profit500.vn/Thong-tin-doanh-nghiep/")


def test_doc_gioi_thieu_chung():
    p = profit500.parse_profile_html(PROFILE_HTML)
    assert p["name_en"] == "GREENFEED VIETNAM CORPORATION"
    assert p["rank_label"] == "52(B1/2026)" and p["rank"] == 52
    assert p["stock_code"] == ""  # "Chưa niêm yết"
    assert p["province"] == "Long An"
    assert p["email"] == "info@greenfeed.vn"
    assert p["website"] == "http://www.greenfeed.com.vn"
    assert p["founded_year"] == 2003
    assert p["extra"] == {"Vốn điều lệ": "1.000 tỷ"}
    assert p["description"] == "Thành lập năm 2003, GREENFEED là tập đoàn.\nĐoạn hai."


def test_tinh_tu_dia_chi():
    assert profit500.province_from_address("18 Láng Hạ - Phường Thành Công - TP. Hà Nội") == "Hà Nội"
    assert profit500.province_from_address("KCN Yên Bình, Phường Vạn Xuân, Tỉnh Thái Nguyên") == "Thái Nguyên"
    assert profit500.province_from_address("") == ""


# ------------------------------------------------------------------ quét (giả lập trang nguồn)


def _mock_site(m, *, total=1):
    m.get(f"{profit500.BASE_URL}/Charts/SearchBusiness").mock(
        return_value=httpx.Response(200, json={"Succeeded": True, "Result": {"TotalItems": total, "PageSize": 50, "Data": LIST_HTML}})
    )
    return m.get(url__regex=r".*/Thong-tin-doanh-nghiep/.*").mock(return_value=httpx.Response(200, text=PROFILE_HTML))


def test_quet_them_moi_roi_bo_qua_roi_cap_nhat():
    client = profit500.Profit500Client(delay=0)
    with respx.mock(assert_all_called=False) as m:
        profile_route = _mock_site(m)
        with dbmod.new_session() as db:
            s1 = profit500.crawl(db, year=2026, client=client, progress=lambda _: None)
            assert (s1.created, s1.updated, s1.skipped, s1.errors) == (1, 0, 0, [])

            k = db.query(KnowledgeCompany).one()
            assert k.source == "profit500" and k.source_id == "261" and k.tax_code == "1100598642"
            assert k.rank == 52 and k.rank_year == 2026 and k.ceo_name == "Đỗ Cao Bằng"
            assert k.rank_list.startswith("PROFIT500 – Top 500")
            assert k.crawled_at is not None

            # Admin đánh dấu đã quét + ghi chú → lần quét sau không được ghi đè
            k.ai_status, k.note, k.phone = "done", "đã gọi", "0909"
            db.commit()

            s2 = profit500.crawl(db, year=2026, client=client, progress=lambda _: None)
            assert (s2.created, s2.skipped) == (0, 1)
            assert profile_route.call_count == 1  # đã có → không tải lại trang hồ sơ

            s3 = profit500.crawl(db, year=2026, update=True, client=client, progress=lambda _: None)
            assert s3.updated == 1
            db.refresh(k)
            assert k.ai_status == "done" and k.note == "đã gọi"
            assert k.phone == "0272-3632881"  # trường lấy từ nguồn được làm mới
            assert db.query(KnowledgeCompany).count() == 1


def test_quet_khop_theo_mst_voi_ban_ghi_nhap_tay(admin):
    admin.post(URL, json=body(name="Greenfeed (nhập tay)", tax_code="1100598642"))
    client = profit500.Profit500Client(delay=0)
    with respx.mock(assert_all_called=False) as m:
        _mock_site(m)
        with dbmod.new_session() as db:
            s = profit500.crawl(db, year=2026, client=client, progress=lambda _: None)
            assert (s.created, s.skipped) == (0, 1)  # trùng MST → không tạo bản thứ hai
            assert db.query(KnowledgeCompany).count() == 1


def test_loi_mot_doanh_nghiep_khong_dung_ca_luot():
    client = profit500.Profit500Client(delay=0, retries=1)
    with respx.mock(assert_all_called=False) as m:
        _mock_site(m).mock(return_value=httpx.Response(404))
        with dbmod.new_session() as db:
            s = profit500.crawl(db, year=2026, client=client, progress=lambda _: None)
            assert s.created == 0 and len(s.errors) == 1
