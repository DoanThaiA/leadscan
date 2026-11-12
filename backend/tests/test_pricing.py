"""Công thức giá phiếu cơ hội chỉnh được trên trang quản trị (/api/admin/pricing)."""

from app.services import pricing
from app.services.matching import price_for


def test_defaults_match_previous_formula():
    """Mặc định giữ đúng công thức cũ (giá hiện tại không đổi khi chưa ai chỉnh)."""
    assert price_for(29_000, 70) == 44_000
    assert price_for(29_000, 86) == 64_000
    assert price_for(29_000, 86, urgency=90, info=0.8, value_vnd=3_000_000_000) == 155_000
    assert price_for(29_000, 100, urgency=100, info=1.0, value_vnd=25_000_000_000) == 329_000
    assert price_for(10_000, 30) == 29_000 and price_for(0, 90) == 0


def test_admin_updates_formula_with_history(admin):
    r = admin.get("/api/admin/pricing")
    assert r.status_code == 200 and r.json()["values"]["min_price"] == 29_000 and len(r.json()["fields"]) == len(pricing.SETTINGS)

    # lý do bắt buộc; ngưỡng giá trị phải tăng dần; ngoài khoảng → 422
    assert admin.put("/api/admin/pricing", json={"values": {"min_price": 35000}, "reason": ""}).status_code == 422
    r = admin.put("/api/admin/pricing", json={"values": {"value_t2": 50_000_000}, "reason": "thử"})
    assert r.status_code == 422 and "tăng dần" in r.json()["detail"]
    assert admin.put("/api/admin/pricing", json={"values": {"score_max_mult": 50}, "reason": "thử"}).status_code == 422

    r = admin.put("/api/admin/pricing", json={"values": {"min_price": 35000, "score_max_mult": 4, "round_to": 5000}, "reason": "Tăng giá Q1"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["values"]["min_price"] == 35000 and j["values"]["score_max_mult"] == 4.0
    assert {lg["key"] for lg in j["logs"]} == {"min_price", "score_max_mult", "round_to"} and j["logs"][0]["reason"] == "Tăng giá Q1"
    # áp dụng ngay (đã xoá bộ nhớ tạm khi lưu)
    assert price_for(10_000, 0) == 35_000
    assert price_for(29_000, 100) == 140_000  # 35.000 × 4, làm tròn 5.000
    # lưu lại cùng giá trị → không ghi thêm lịch sử
    assert len(admin.put("/api/admin/pricing", json={"values": {"min_price": 35000}, "reason": "lặp"}).json()["logs"]) == 3


def test_staff_can_view_and_preview_but_not_save(admin, client, staff_id):
    from tests.conftest import STAFF_PW

    staff = client.__class__(client.app)
    assert staff.post("/api/admin/auth/login", json={"email": "staff@leadscan.vn", "password": STAFF_PW}).status_code == 200
    assert staff.get("/api/admin/pricing").status_code == 200
    assert staff.put("/api/admin/pricing", json={"values": {"min_price": 1}, "reason": "abc"}).status_code == 403
    r = staff.post("/api/admin/pricing/preview", json={"values": {"urg_3": 2}, "scenarios": [{"score": 50, "days_left": 2}]})
    assert r.status_code == 200
    it = r.json()["items"][0]
    assert it["current"]["urgency"] == 1.4 and it["current"]["price"] == 41_000
    assert it["draft"]["urgency"] == 2.0 and it["draft"]["price"] == 58_000
    assert price_for(29_000, 50, urgency=100) == 41_000  # xem thử không lưu


def test_preview_with_real_opportunity(admin):
    r = admin.post("/api/admin/opportunities", json={"title": "Cần 5.000 túi giữ nhiệt", "industry": "Bao bì & in ấn", "price": 50_000,
                                                      "estimated_value": "2 tỷ", "status": "draft"})
    assert r.status_code in (200, 201), r.text
    code = r.json()["code"]
    it = admin.post("/api/admin/pricing/preview", json={"scenarios": [{"score": 80, "opp_code": code.lower()}]}).json()["items"][0]
    assert it["opportunity"]["code"] == code and it["opportunity"]["value_vnd"] == 2_000_000_000
    assert it["current"]["base"] == 50_000 and it["current"]["value"] == 1.3
    assert admin.post("/api/admin/pricing/preview", json={"scenarios": [{"score": 80, "opp_code": "CH-999999"}]}).status_code == 404
