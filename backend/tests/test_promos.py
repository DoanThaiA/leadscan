"""Mã khuyến mãi: admin cấu hình, thành viên áp mã khi thanh toán, đơn 0đ kích hoạt luôn không cần thanh toán."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import new_session
from app.models import Company, PaymentOrder
from tests.test_member import member, member_client, pay_membership  # noqa: F401  (fixture member)

FEE = 10_000_000  # phí thành viên khi test (conftest)


def promo(admin, **over) -> dict:
    body = {"code": "giam20", "name": "Chào mừng", "discount_type": "percent", "discount_value": 20, "applies_to": "all"}
    body.update(over)
    r = admin.post("/api/admin/promos", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def company() -> Company:
    with new_session() as db:
        return db.scalar(select(Company))


def test_admin_crud_and_permissions(admin, staff):
    p = promo(admin, code=" chao mung-2027 ", max_discount=50_000)
    assert p["code"] == "CHAOMUNG-2027" and p["description"] == "Giảm 20% (tối đa 50.000đ)" and p["state"] == "active"
    assert admin.post("/api/admin/promos", json={"code": "CHAOMUNG-2027", "discount_type": "amount", "discount_value": 1}).status_code == 409
    assert admin.post("/api/admin/promos", json={"code": "X", "discount_type": "amount", "discount_value": 1}).status_code == 422
    assert admin.post("/api/admin/promos", json={"code": "PCT", "discount_type": "percent", "discount_value": 120}).status_code == 422
    assert staff.get("/api/admin/promos").status_code == 200
    assert staff.post("/api/admin/promos", json={"code": "NV01", "discount_type": "amount", "discount_value": 1}).status_code == 403

    r = admin.put(f"/api/admin/promos/{p['id']}", json={**p, "code": "MOI-2027", "is_active": False, "max_discount": None})
    assert r.status_code == 200 and r.json()["code"] == "MOI-2027" and r.json()["state"] == "off"
    assert admin.delete(f"/api/admin/promos/{p['id']}").status_code == 204
    assert admin.get("/api/admin/promos").json()["items"] == []


def test_discount_applies_and_points_stay_full(admin, member):  # noqa: F811
    promo(admin, code="GIAM20", discount_value=20, applies_to="membership")
    r = member.post("/api/member/promo/check", json={"code": "giam20", "kind": "membership"})
    assert r.status_code == 200 and r.json()["discount"] == 2_000_000 and r.json()["pay"] == 8_000_000

    r = member.post("/api/member/orders", json={"kind": "membership", "promo_code": "giam20"})
    assert r.status_code == 201, r.text
    o = r.json()["order"]
    assert (o["amount"], o["original_amount"], o["discount"], o["promo_code"], o["points"]) == (8_000_000, FEE, 2_000_000, "GIAM20", FEE)
    assert o["status"] == "pending" and r.json()["payment"]["amount"] == 8_000_000
    assert member.post(f"/api/member/orders/{o['code']}/simulate-paid").status_code == 200
    c = company()
    assert c.points_balance == FEE and c.topup_total == 8_000_000  # điểm theo giá gốc, tổng nạp theo tiền thật

    stats = admin.get("/api/admin/promos").json()["items"][0]
    assert stats["used"] == 1 and stats["paid_count"] == 1 and stats["discount_total"] == 2_000_000
    assert admin.get("/api/admin/orders?promo=giam20").json()["total"] == 1
    # đã dùng → không xoá, không đổi chữ mã được
    assert admin.delete(f"/api/admin/promos/{stats['id']}").status_code == 409
    assert admin.put(f"/api/admin/promos/{stats['id']}", json={**stats, "code": "KHAC"}).status_code == 409


def test_free_order_activates_without_payment(admin, member):  # noqa: F811
    promo(admin, code="FREE100", discount_value=100)
    r = member.post("/api/member/orders", json={"kind": "membership", "promo_code": "FREE100"})
    assert r.status_code == 201, r.text
    o = r.json()["order"]
    assert o["amount"] == 0 and o["status"] == "paid" and o["provider"] == "free" and o["paid_amount"] == 0
    assert r.json()["me"]["company"]["membership_active"] and r.json()["me"]["company"]["points_balance"] == FEE
    assert r.json()["payment"]["qr_payload"] is None
    assert member.get(f"/api/member/orders/{o['code']}").json()["order"]["status"] == "paid"


def test_fixed_amount_larger_than_order_is_free(admin, member):  # noqa: F811
    pay_membership(member)
    promo(admin, code="TANG5TR", discount_type="amount", discount_value=7_000_000, applies_to="topup")
    r = member.post("/api/member/orders", json={"kind": "topup", "amount": 5_000_000, "promo_code": "TANG5TR"})
    o = r.json()["order"]
    assert o["amount"] == 0 and o["discount"] == 5_000_000 and o["status"] == "paid"
    assert company().points_balance == FEE + 5_000_000


@pytest.mark.parametrize(
    "over,kind,msg",
    [
        ({"is_active": False}, "membership", "không tồn tại"),
        ({"applies_to": "topup"}, "membership", "chỉ áp dụng"),
        ({"min_amount": 20_000_000}, "membership", "đơn từ 20.000.000đ"),
        ({"ends_on": (date.today() - timedelta(days=2)).isoformat()}, "membership", "hết hạn"),
        ({"starts_on": (date.today() + timedelta(days=3)).isoformat()}, "membership", "áp dụng từ ngày"),
    ],
)
def test_invalid_promo(admin, member, over, kind, msg):  # noqa: F811
    promo(admin, code="LOI", **over)
    r = member.post("/api/member/promo/check", json={"code": "LOI", "kind": kind})
    assert r.status_code == 400 and msg in r.json()["detail"]
    r = member.post("/api/member/orders", json={"kind": kind, "promo_code": "LOI"})
    assert r.status_code == 400 and msg in r.json()["detail"]
    with new_session() as db:
        assert db.scalar(select(PaymentOrder.id)) is None  # mã lỗi → không tạo đơn
    assert member.post("/api/member/promo/check", json={"code": "KHONGCO", "kind": kind}).status_code == 400


def test_usage_limits_and_cancel_releases(admin, client, member):  # noqa: F811
    promo(admin, code="MOTLAN", discount_value=10, per_company_limit=1, max_uses=2)
    code = member.post("/api/member/orders", json={"kind": "membership", "promo_code": "MOTLAN"}).json()["order"]["code"]
    r = member.post("/api/member/orders", json={"kind": "membership", "promo_code": "MOTLAN"})
    assert r.status_code == 400 and "hết lượt" in r.json()["detail"]  # đơn đang chờ vẫn giữ lượt
    assert member.post(f"/api/member/orders/{code}/cancel").status_code == 200
    assert member.post("/api/member/orders", json={"kind": "membership", "promo_code": "MOTLAN"}).status_code == 201  # huỷ → trả lượt

    from tests.conftest import register

    register(client, tax_code="0109999999")
    other = member_client("lienhe0109999999@minhan.vn")
    assert other.post("/api/member/orders", json={"kind": "membership", "promo_code": "MOTLAN"}).status_code == 201
    register(client, tax_code="0108888888")
    third = member_client("lienhe0108888888@minhan.vn")
    r = third.post("/api/member/orders", json={"kind": "membership", "promo_code": "MOTLAN"})
    assert r.status_code == 400 and "hết lượt sử dụng" in r.json()["detail"]  # tổng 2 lượt
