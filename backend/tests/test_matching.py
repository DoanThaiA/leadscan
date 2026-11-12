"""Luồng phiếu cơ hội: phiếu không có điểm → điểm tính riêng cho từng thành viên qua so khớp hybrid."""

from sqlalchemy import func, select

from app.db import new_session
from app.models import Opportunity, SearchRequestMatch, UserOpportunity
from app.services import embedding as emb
from app.services.matching import parse_value_vnd, price_for
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
    # không bao giờ thấp hơn giá cơ bản / mức tối thiểu 29.000 (lỗi cũ: điểm < 50 ra 28.000)
    assert price_for(29_000, 0) == price_for(29_000, 50) == 29_000 and price_for(10_000, 30) == 29_000
    # điểm cao phải đắt hơn rõ rệt (lỗi cũ: 60 điểm 32k, 86 điểm 39k)
    assert price_for(29_000, 86) >= 1.8 * price_for(29_000, 60)
    # gấp hơn (hạn chót gần), đủ thông tin hơn, đơn hàng lớn hơn → giá cao hơn
    assert price_for(29_000, 82, urgency=90) > price_for(29_000, 82, urgency=50)
    assert price_for(29_000, 82, info=1.0) > price_for(29_000, 82, info=0.2)
    assert price_for(29_000, 82, value_vnd=5_000_000_000) > price_for(29_000, 82)
    assert price_for(0, 80) == 0


def test_doc_gia_tri_uoc_tinh():
    assert parse_value_vnd("2–3 tỷ") == 3_000_000_000
    assert parse_value_vnd("500 triệu") == 500_000_000
    assert parse_value_vnd("khoảng 1.200.000.000đ") == 1_200_000_000
    assert parse_value_vnd("1,5 tỷ") == 1_500_000_000
    assert parse_value_vnd("120.000 USD") == 3_000_000_000
    assert parse_value_vnd("") == 0


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
    assert mine["score"] >= 60 and mine["reasons"] and mine["price"] >= price_for(1_250_000, mine["score"]) >= 1_250_000

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


def test_tim_kiem_lien_tuc_bao_co_hoi_moi(admin, member, client, monkeypatch):
    """Phiếu tìm "Tìm kiếm liên tục": cơ hội mới mở bán khớp phiếu → thông báo trong cổng + email gộp, mỗi cặp 1 lần."""
    from app.services import notify

    sent = []
    monkeypatch.setattr(notify, "send_mail", lambda cfg, subject, body, to=None: sent.append((subject, body, to)) or True)

    r = ask(member)  # chưa có cơ hội nào
    assert r["status"] == "open"
    assert member.get("/api/member/notifications").json() == {"unread": 0, "items": []}

    oid = make_opp(admin)  # cơ hội mới mở bán khớp phiếu đã có
    n = member.get("/api/member/notifications").json()
    assert n["unread"] == 1 and n["items"][0]["opportunity"]["id"] == oid and n["items"][0]["request"]["id"] == r["id"]
    assert n["items"][0]["score"] > 0 and not n["items"][0]["read"]
    mails = [m for m in sent if "cơ hội mới phù hợp" in m[0]]
    assert len(mails) == 1 and mails[0][2] == "a@minhan.vn"
    assert "Cần 200.000 hộp carton" in mails[0][1] and f"phu-hop?yeu-cau={r['id']}" in mails[0][1]
    assert member.get("/api/member/search-requests").json()["items"][0]["new_count"] == 1

    # sửa giá → vẫn khớp nhưng không báo lặp, không gửi thêm email
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    body = {k: o[k] for k in ("title", "summary", "industry", "province", "region", "source_type", "max_buyers", "buyer_name", "detail", "status")}
    admin.put(f"/api/admin/opportunities/{oid}", json={**body, "price": 1_300_000, "contacts": []})
    assert member.get("/api/member/notifications").json()["unread"] == 1
    assert len([m for m in sent if "cơ hội mới phù hợp" in m[0]]) == 1

    # mở phiếu → cơ hội gắn nhãn "Mới" (tải lại vẫn còn), rồi đánh dấu đã xem
    for _ in range(2):
        items = member.get(f"/api/member/search-requests/{r['id']}/opportunities").json()["items"]
        assert items[0]["id"] == oid and items[0]["is_new"] is True
    assert member.post(f"/api/member/search-requests/{r['id']}/seen").status_code == 204
    assert member.get(f"/api/member/search-requests/{r['id']}/opportunities").json()["items"][0]["is_new"] is False
    assert member.get("/api/member/notifications").json()["unread"] == 0
    assert member.get("/api/member/search-requests").json()["items"][0]["new_count"] == 0

    # phiếu tìm mới gửi: kết quả có ngay, không tạo thông báo (khách đang xem kết quả rồi)
    ask(member, "Tìm khách mua thùng carton tại Bắc Ninh")
    assert member.get("/api/member/notifications").json()["unread"] == 0

    # doanh nghiệp khác không thấy thông báo của mình; không đánh dấu được thông báo của người khác
    nid = member.get("/api/member/notifications").json()["items"][0]["id"]
    b = other_member(client, 7)
    assert b.get("/api/member/notifications").json()["items"] == []
    assert b.post(f"/api/member/notifications/{nid}/read").status_code == 404
    assert b.post(f"/api/member/search-requests/{r['id']}/seen").status_code == 404

    # phiếu bị từ chối thì dừng tìm: cơ hội mới không báo nữa
    for x in member.get("/api/member/search-requests").json()["items"]:
        admin.patch(f"/api/admin/search-requests/{x['id']}", json={"status": "rejected", "reply": "Dừng"})
    make_opp(admin, title="Cần 50.000 hộp carton 3 lớp cho nhà máy Bắc Ninh")
    assert member.get("/api/member/notifications").json()["unread"] == 0


def test_doc_het_thong_bao(admin, member):
    ask(member)
    make_opp(admin)
    make_opp(admin, title="Cần thùng carton 7 lớp cho kho Bắc Ninh")
    assert member.get("/api/member/notifications").json()["unread"] == 2
    assert member.post("/api/member/notifications/read-all").status_code == 204
    n = member.get("/api/member/notifications").json()
    assert n["unread"] == 0 and len(n["items"]) == 2 and all(i["read"] for i in n["items"])


# ------------------------------------------------------------------ lỗi từ đợt test: túi giữ nhiệt / TP.HCM

THERMAL_NOTE = (
    "Tôi muốn tìm bên mua túi giữ nhiệt theo thiết kế riêng (OEM/ODM), đơn hàng từ 5.000 chiếc trở lên, "
    "kích thước khoảng 60 × 90 cm, tải trọng 5kg, giao hàng tại TP. Hồ Chí Minh hoặc khu vực miền Nam."
)


def _bag_opp(admin, title: str, province: str = "TP. Hồ Chí Minh", region: str = "Miền Nam", **over) -> int:
    return make_opp(admin, title=title, summary=title, province=province, region=region, buyer_name="Công ty X", detail="", **over)


def test_cung_nganh_khac_san_pham_khong_duoc_diem_cao(admin, member):
    """Ngành "Bao bì & in ấn" rộng: túi PP dệt / RPET / túi trồng cây không phải túi giữ nhiệt."""
    right = _bag_opp(admin, "Cần đặt 5.000 túi giữ nhiệt in logo theo thiết kế riêng")
    synonym = _bag_opp(admin, "Chuỗi giao đồ ăn cần 8.000 túi giữ lạnh shipper")
    near = _bag_opp(admin, "Cần thùng giữ nhiệt đựng hải sản 3.000 chiếc")
    wrong = [_bag_opp(admin, t) for t in ("Cần 10.000 túi PP dệt đựng gạo", "Mua túi RPET in logo cho siêu thị", "Đặt túi trồng cây vải 20.000 chiếc",
                                          "Cần đơn vị thiết kế, giao hàng riêng cho khu vực miền Nam")]  # chỉ trùng từ chung chung
    r = ask(member, THERMAL_NOTE, industries=["Bao bì & in ấn"], regions=["Quốc tế"])
    assert r["understood"]["products"] == ["Túi giữ nhiệt"] and "TP. Hồ Chí Minh" in r["understood"]["places"]
    assert r["understood"]["warning"]  # chọn "Quốc tế" nhưng mô tả ghi TP.HCM → cảnh báo
    items = {i["id"]: i for i in member.get(f"/api/member/search-requests/{r['id']}/opportunities").json()["items"]}
    assert right in items and synonym in items and near in items
    assert not set(wrong) & set(items)  # sai sản phẩm → không vào kết quả
    assert items[right]["score"] > items[near]["score"]  # đúng sản phẩm > sản phẩm tương đương
    assert any(x.startswith("Đúng sản phẩm") for x in items[synonym]["reasons"])


def test_uu_tien_dia_diem_ghi_trong_mo_ta(admin, member):
    """Khách để ô Khu vực = Quốc tế nhưng mô tả cần giao tại TP.HCM → cơ hội ở TP.HCM / miền Nam xếp trên cơ hội quốc tế."""
    hcm = _bag_opp(admin, "Cần 5.000 túi giữ nhiệt giao kho Thủ Đức", province="TP.HCM")
    binh_duong = _bag_opp(admin, "Cần 5.000 túi giữ nhiệt cho nhà máy", province="Bình Dương")
    intl = _bag_opp(admin, "Importer needs 5,000 túi giữ nhiệt (thermal bag) OEM", province="Nhật Bản", region="Quốc tế")
    r = ask(member, THERMAL_NOTE, industries=["Bao bì & in ấn"], regions=["Quốc tế"])
    items = {i["id"]: i["score"] for i in member.get(f"/api/member/search-requests/{r['id']}/opportunities").json()["items"]}
    assert items[hcm] > items[intl] and items[binh_duong] > items[intl]


def test_co_hoi_da_mua_bi_sua(admin, member):
    """Đã mua → cơ hội bị sửa không còn phù hợp: khách vẫn xem bản đã mua (điểm lúc mua), điểm hiện tại cập nhật, admin hoàn điểm."""
    from tests.test_member import balance, pay_membership

    oid = _bag_opp(admin, "Cần đặt 5.000 túi giữ nhiệt in logo theo thiết kế riêng")
    ask(member, THERMAL_NOTE)
    pay_membership(member)
    before = view(member, oid)
    assert member.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    paid = 10_000_000 - balance()

    body = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    body.update(title="Cần 10.000 túi PP dệt đựng gạo", summary="Bao PP dệt cho nhà máy gạo", buyer_name="Công ty Y")
    assert admin.put(f"/api/admin/opportunities/{oid}", json=body).status_code == 200

    p = member.get(f"/api/member/opportunities/{oid}").json()["purchase"]
    assert p["snapshot"]["title"] == "Cần đặt 5.000 túi giữ nhiệt in logo theo thiết kế riêng"
    assert p["snapshot"]["buyer_name"] == "Công ty X" and p["snapshot"]["score"] == before["score"]
    assert {"Tiêu đề", "Bên có nhu cầu"} <= set(p["changed_fields"])
    assert view(member, oid)["score"] < before["score"]  # điểm hiện tại được chấm lại, không giữ điểm cũ

    buyer = admin.get(f"/api/admin/opportunities/{oid}").json()["purchases"][0]
    assert buyer["score_at_purchase"] == before["score"] and buyer["score_now"] < before["score"] and buyer["changed_fields"]
    assert admin.post(f"/api/admin/purchases/{buyer['id']}/refund", json={"note": "Cơ hội đổi sản phẩm sau khi mua"}).status_code == 200
    assert balance() == 10_000_000 and member.get("/api/member/purchases").json()["items"][0]["refund_amount"] == paid
    assert admin.post(f"/api/admin/purchases/{buyer['id']}/refund", json={"note": "Hoàn lần hai"}).status_code == 409
