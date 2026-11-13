"""Hạng thành viên: Thường / Vàng (tổng nạp ≥ ngưỡng) — hạng Vàng được mua độc quyền phiếu với giá ×2."""

import pytest
from sqlalchemy import select

from app.db import new_session
from app.models import Opportunity, Purchase
from app.config import get_settings
from tests.test_matching import other_member
from tests.test_member import ask, balance, make_opp, member, pay_membership, view  # noqa: F401


@pytest.fixture(autouse=True)
def gold_15m(monkeypatch):
    # test đóng phí thành viên 10tr (conftest) → đặt ngưỡng Vàng 15tr để thấy được cả hạng Thường
    monkeypatch.setenv("LEADSCAN_GOLD_TOPUP_THRESHOLD", "15000000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def topup(m, amount: int) -> None:
    r = m.post("/api/member/orders", json={"kind": "topup", "amount": amount})
    assert r.status_code == 201, r.text
    assert m.post(f"/api/member/orders/{r.json()['order']['code']}/simulate-paid").status_code == 200


def tier(m) -> dict:
    return m.get("/api/member/auth/me").json()["company"]["tier"]


def test_len_hang_vang_theo_tong_nap(member):
    t = tier(member)
    assert t["key"] == "standard" and t["label"] == "Thường" and t["topup_total"] == 0 and t["to_gold"] == 15_000_000
    pay_membership(member)  # 10tr
    assert tier(member)["key"] == "standard" and tier(member)["to_gold"] == 5_000_000
    topup(member, 5_000_000)
    t = tier(member)
    assert t["key"] == "gold" and t["label"] == "Vàng" and t["topup_total"] == 15_000_000 and t["to_gold"] == 0 and t["can_exclusive"]


def test_mua_doc_quyen_chi_hang_vang_gia_gap_doi(admin, member, client):
    oid = make_opp(admin)  # 2 lượt mua
    ask(member)
    pay_membership(member)

    d = member.get(f"/api/member/opportunities/{oid}").json()
    assert d["exclusive"]["available"] is False and "hạng Vàng" in d["exclusive"]["reason"]
    assert member.post(f"/api/member/opportunities/{oid}/purchase", json={"exclusive": True}).status_code == 403

    topup(member, 5_000_000)
    d = member.get(f"/api/member/opportunities/{oid}").json()
    price = d["opportunity"]["price"]
    assert d["exclusive"] == {"available": True, "price": 2 * price, "reason": ""}

    before = balance()
    r = member.post(f"/api/member/opportunities/{oid}/purchase", json={"exclusive": True})
    assert r.status_code == 200, r.text
    assert before - balance() == 2 * price
    with new_session() as db:
        o = db.get(Opportunity, oid)
        assert o.sold_count == 1 and o.max_buyers == 1  # đóng các lượt còn lại
        assert db.scalar(select(Purchase)).exclusive is True
    assert member.get("/api/member/purchases").json()["items"][0]["exclusive"] is True
    assert view(member, oid)["sold_out"] is True

    # thành viên khác (cũng khớp cơ hội) không mua được nữa
    b = other_member(client, 2)
    ask(b)
    pay_membership(b)
    assert b.post(f"/api/member/opportunities/{oid}/purchase").status_code == 409

    # quản trị thấy lượt mua độc quyền + hạng của khách
    buyers = admin.get(f"/api/admin/opportunities/{oid}").json()["purchases"]
    assert buyers[0]["exclusive"] is True
    with new_session() as db:
        cid = db.scalar(select(Purchase.company_id))
    acc = admin.get(f"/api/admin/companies/{cid}/account").json()
    assert acc["tier"]["key"] == "gold" and acc["purchases"][0]["exclusive"] is True


def test_khong_mua_doc_quyen_khi_da_co_nguoi_mua_hoac_phieu_von_doc_quyen(admin, member, client):
    oid = make_opp(admin)
    one = make_opp(admin, title="Cần 50.000 hộp carton 3 lớp/tháng", max_buyers=1)
    ask(member)
    pay_membership(member)
    topup(member, 5_000_000)

    b = other_member(client, 2)
    ask(b)
    pay_membership(b)
    assert b.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200  # mua thường trước

    d = member.get(f"/api/member/opportunities/{oid}").json()
    assert d["exclusive"]["available"] is False and "đã có người mua" in d["exclusive"]["reason"]
    assert member.post(f"/api/member/opportunities/{oid}/purchase", json={"exclusive": True}).status_code == 409
    assert member.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200  # vẫn mua thường được (còn 1 lượt)

    d = member.get(f"/api/member/opportunities/{one}").json()
    assert d["exclusive"]["available"] is False and "vốn đã độc quyền" in d["exclusive"]["reason"]
