"""Quét PROFIT500 thẳng vào phân hệ làm giàu theo MST (kho doanh nghiệp cũ đã xoá)."""

import httpx
import respx

from app import db as dbmod
from app.services import profit500

PURPOSES = ["ban_hang_b2b"]


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


def _mock_site(m, *, list_html=None, profile_html=None):
    m.get(f"{profit500.BASE_URL}/Charts/SearchBusiness").mock(
        return_value=httpx.Response(200, json={"Succeeded": True, "Result": {"TotalItems": 1, "PageSize": 50, "Data": list_html or LIST_HTML}})
    )
    return m.get(url__regex=r".*/Thong-tin-doanh-nghiep/.*").mock(return_value=httpx.Response(200, text=profile_html or PROFILE_HTML))


def _crawl(db, client, **kw):
    return profit500.crawl(db, year=2026, purposes=PURPOSES, client=client, progress=lambda _: None, **kw)


def test_quet_ghi_thang_vao_lam_giau(admin):
    client = profit500.Profit500Client(delay=0)
    with respx.mock(assert_all_called=False) as m:
        profile_route = _mock_site(m)
        with dbmod.new_session() as db:
            s1 = _crawl(db, client)
            assert (s1.created, s1.updated, s1.skipped, s1.no_mst, s1.errors) == (1, 0, 0, 0, [])
            assert s1.batch_id

            # đã có bằng chứng PROFIT500 → không tải lại trang hồ sơ, không tạo lô
            s2 = _crawl(db, client)
            assert (s2.created, s2.skipped, s2.batch_id) == (0, 1, None)
            assert profile_route.call_count == 1

    p = admin.get("/api/admin/enrich/companies/1100598642").json()
    shown = {f["key"]: f for f in p["fields"]}
    assert shown["ten"]["value"] == "CÔNG TY CP GREENFEED VIỆT NAM"
    assert shown["ten"]["source"]["code"] == "profit500" and shown["ten"]["source_url"].startswith("https://profit500.vn/")
    assert shown["ten_tieng_anh"]["value"] == "GREENFEED VIETNAM CORPORATION"
    assert shown["nam_thanh_lap"]["value"] == 2003
    assert shown["mo_ta"]["value"].startswith("Thành lập năm 2003")
    assert shown["nhom_nganh"]["value"] == "Sản xuất thức ăn chăn nuôi"
    assert shown["tinh"]["value"] == "Tây Ninh"  # Long An sáp nhập vào Tây Ninh (34 tỉnh/thành từ 1/7/2025)
    assert shown["domain"]["value"] == "greenfeed.com.vn"
    assert "ma_ck" not in shown  # "Chưa niêm yết"
    assert {(c["kind"], c["value"]) for c in p["contacts"]} == {("phone", "+842723632881"), ("email", "info@greenfeed.vn")}
    assert [s["kind"] for s in p["signals"]] == ["xep_hang"] and p["signals"][0]["payload"]["hang"] == 52
    assert p["purposes"] == PURPOSES and p["batches"][0]["name"].startswith("PROFIT500 – Top 500")
    ev = admin.get("/api/admin/enrich/companies/1100598642/evidence").json()
    assert all("Vietnam Report" in e["excerpt"] for e in ev)
    assert not any("Đỗ Cao Bằng" in (e["value"] + e["excerpt"]) for e in ev)  # không lưu tên CEO

    # quét lại có --update, nội dung không đổi → lô mới nhưng không sinh bằng chứng / tín hiệu trùng
    with respx.mock(assert_all_called=False) as m:
        _mock_site(m)
        with dbmod.new_session() as db:
            s3 = _crawl(db, profit500.Profit500Client(delay=0), update=True)
    assert s3.updated == 1 and s3.batch_id
    assert len(admin.get("/api/admin/enrich/companies/1100598642/evidence").json()) == len(ev)
    assert len(admin.get("/api/admin/enrich/companies/1100598642").json()["signals"]) == 1


def test_quet_bo_qua_doanh_nghiep_khong_co_mst(admin):
    client = profit500.Profit500Client(delay=0)
    with respx.mock(assert_all_called=False) as m:
        _mock_site(m, list_html=LIST_HTML.replace(": 1100598642", ": "), profile_html=PROFILE_HTML.replace("1100598642", ""))
        with dbmod.new_session() as db:
            s = _crawl(db, client)
    assert (s.no_mst, s.created, s.batch_id) == (1, 0, None)
    assert admin.get("/api/admin/enrich/stats").json()["total"] == 0


def test_loi_mot_doanh_nghiep_khong_dung_ca_luot():
    client = profit500.Profit500Client(delay=0, retries=1)
    with respx.mock(assert_all_called=False) as m:
        _mock_site(m).mock(return_value=httpx.Response(404))
        with dbmod.new_session() as db:
            s = _crawl(db, client)
            assert s.created == 0 and len(s.errors) == 1


# ------------------------------------------------------------------ kho doanh nghiệp cũ đã xoá


def test_kho_cu_khong_con_tren_giao_dien(admin):
    assert admin.get("/api/admin/knowledge-companies").status_code == 404
