"""Luồng phiếu cơ hội: phiếu không có điểm → điểm tính riêng cho từng thành viên qua so khớp hybrid."""

from sqlalchemy import func, select

from app.db import new_session
from app.models import Opportunity, SearchRequestMatch, UserOpportunity
from app.services import embedding as emb
from app.services.matching import price_for
from tests.conftest import register
from tests.test_member import CARTON_NOTE, ask, make_opp, member, member_client, pay_membership, view  # noqa: F401

CASHEW_NOTE = "Chào bán hạt điều rang muối xuất khẩu, cần tìm nhà nhập khẩu thực phẩm ở châu Âu."


def other_member(client, n: int):
    tax = f"010000000{n}"
    register(client, tax_code=tax)
    return member_client(f"lienhe{tax}@minhan.vn")


def test_gia_dong_bien_voi_diem():
    prices = [price_for(29_000, s) for s in range(0, 101, 5)]
    assert prices == sorted(prices)  # điểm tăng → giá không giảm
    assert price_for(29_000, 50) == 29_000 and price_for(29_000, 0) < 29_000 < price_for(29_000, 100)
    assert price_for(0, 80) == 0


def test_embedding_ngu_nghia_va_bo_dau():
    a = emb.embed_hash("Cần 200.000 hộp carton 5 lớp mỗi tháng cho nhà máy")
    b = emb.embed_hash("Tìm nhà cung cấp thùng giấy bao bì")
    c = emb.embed_hash("Chào bán hạt điều rang muối sang châu Âu")
    assert emb.cosine(a, b) > 0.15 > emb.cosine(a, c)  # carton ≈ thùng giấy ≈ bao bì dù không trùng từ
    assert emb.fold("Đồng Nai – Bắc Ninh") == "dong nai bac ninh"


def test_phieu_co_hoi_khong_mang_diem(admin):
    oid = make_opp(admin)
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    assert o["score"] == 0 and o["match_count"] == 0
    with new_session() as db:
        assert db.get(Opportunity, oid).embedding  # có embedding sẵn để so khớp


def test_chi_xem_co_hoi_phu_hop_va_diem_rieng_tung_user(admin, member, client):
    oid = make_opp(admin)
    # chưa gửi phiếu tìm cơ hội → chưa thấy gì
    assert member.get("/api/member/opportunities").json()["total"] == 0
    assert member.get(f"/api/member/opportunities/{oid}").status_code == 404

    strong = ask(member)
    assert strong["match_count"] == 1
    mine = view(member, oid)
    assert mine["score"] >= 60 and mine["reasons"] and mine["price"] == price_for(1_250_000, mine["score"])

    # user B: yêu cầu hoàn toàn khác → không thấy cơ hội, không mua/lưu được
    b = other_member(client, 2)
    assert ask(b, CASHEW_NOTE, industries=["Nông sản & thuỷ sản"], regions=["Quốc tế"])["match_count"] == 0
    assert b.get("/api/member/opportunities").json()["total"] == 0
    assert b.get(f"/api/member/opportunities/{oid}").status_code == 404
    assert b.post(f"/api/member/saved/{oid}").status_code == 404
    pay_membership(b)
    assert b.post(f"/api/member/opportunities/{oid}/purchase").status_code == 404

    # user C: khớp yếu (chỉ mô tả, ngành/khu vực khác) → có thấy nhưng điểm & giá thấp hơn user A
    c = other_member(client, 3)
    weak = ask(c, "Cần thùng carton, hộp giấy bao bì cho kho hàng", industries=["Logistics & vận tải"], regions=["Toàn quốc"])
    assert weak["match_count"] == 1
    theirs = view(c, oid)
    assert theirs["score"] < mine["score"] and theirs["price"] < mine["price"]
    assert view(member, oid)["score"] == mine["score"]  # điểm của A không bị ảnh hưởng


def test_tat_ca_co_hoi_gop_tu_cac_phieu_khong_trung(admin, member):
    oid = make_opp(admin)
    weak = ask(member, "Cần thùng carton", industries=[], regions=[])
    strong = ask(member)
    assert weak["match_count"] == 1 and strong["match_count"] == 1

    lst = member.get("/api/member/opportunities").json()
    assert lst["total"] == 1  # cùng 1 cơ hội khớp 2 phiếu → chỉ 1 dòng
    with new_session() as db:
        assert db.scalar(select(func.count()).select_from(UserOpportunity)) == 1
        assert db.scalar(select(func.count()).select_from(SearchRequestMatch)) == 2
    s_weak = member.get(f"/api/member/search-requests/{weak['id']}/opportunities").json()
    s_strong = member.get(f"/api/member/search-requests/{strong['id']}/opportunities").json()
    assert [i["id"] for i in s_weak["items"]] == [oid] == [i["id"] for i in s_strong["items"]]
    assert s_strong["items"][0]["score"] >= s_weak["items"][0]["score"]
    assert lst["items"][0]["score"] == s_strong["items"][0]["score"]  # tổng hợp lấy điểm cao nhất
    reqs = member.get("/api/member/search-requests").json()["items"]
    assert {r["id"]: r["match_count"] for r in reqs} == {weak["id"]: 1, strong["id"]: 1}

    # kho tự có cơ hội, không trùng; khách bỏ khỏi kho thì gửi phiếu mới không tự thêm lại
    assert member.get("/api/member/saved").json()["total"] == 1
    member.delete(f"/api/member/saved/{oid}")
    ask(member, "Cần mua hộp carton ở Bắc Ninh")
    assert member.get("/api/member/saved").json()["total"] == 0
    assert member.get("/api/member/opportunities").json()["total"] == 1


def test_xem_phieu_cua_nguoi_khac_bi_chan(member, client):
    r = ask(member)
    b = other_member(client, 2)
    assert b.get(f"/api/member/search-requests/{r['id']}/opportunities").status_code == 404


def test_phieu_co_hoi_moi_tu_khop_phieu_tim_da_co(admin, member):
    ask(member)  # phiếu tìm có trước, chưa có cơ hội nào
    assert member.get("/api/member/opportunities").json()["total"] == 0
    oid = make_opp(admin, status="draft")
    assert member.get("/api/member/opportunities").json()["total"] == 0  # nháp chưa bán
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    body = {k: o[k] for k in ("title", "summary", "industry", "province", "region", "source_type", "price", "max_buyers", "buyer_name", "detail")}
    assert admin.put(f"/api/admin/opportunities/{oid}", json={**body, "status": "published", "contacts": []}).json()["match_count"] == 1
    assert member.get("/api/member/opportunities").json()["total"] == 1

    # sửa nội dung thành lĩnh vực khác → hết phù hợp, tự gỡ khỏi Tất cả cơ hội
    other = {**body, "title": "Bán hạt điều rang muối xuất khẩu châu Âu", "summary": "Nhà máy chế biến hạt điều", "industry": "Nông sản & thuỷ sản",
             "province": "Bình Phước", "region": "Miền Nam", "detail": "Hạt điều nhân trắng", "status": "published", "contacts": []}
    assert admin.put(f"/api/admin/opportunities/{oid}", json=other).json()["match_count"] == 0
    assert member.get("/api/member/opportunities").json()["total"] == 0


def test_phieu_tu_choi_va_so_khop_lai(admin, member):
    make_opp(admin)
    r = ask(member)
    assert admin.patch(f"/api/admin/search-requests/{r['id']}", json={"status": "rejected", "reply": "Không phù hợp"}).status_code == 200
    assert member.get("/api/member/opportunities").json()["total"] == 0
    assert admin.patch(f"/api/admin/search-requests/{r['id']}", json={"status": "open"}).json()["match_count"] == 1
    assert admin.post(f"/api/admin/search-requests/{r['id']}/rematch").json()["match_count"] == 1
    assert admin.get("/api/admin/search-requests").json()["items"][0]["match_count"] == 1


def test_min_score_cua_phieu_loc_bot_co_hoi(admin, member):
    make_opp(admin)
    r = ask(member, CARTON_NOTE, min_score=100)
    assert r["match_count"] == 0  # không cơ hội nào đạt 100 điểm
    assert member.get("/api/member/dashboard").json()["matched_count"] == 0
    ask(member)
    assert member.get("/api/member/dashboard").json()["matched_count"] == 1
