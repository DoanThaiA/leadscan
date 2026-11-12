"""Đối tác LeadScan — Mốc 3: ví hoa hồng.

Kịch bản S0–S4 lấy đúng bảng 5.3 của brief (giá phiếu tính như doanh thu thuần → đặt thuế suất KCT để net = giá).
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import new_session, utcnow
from app.models import Company, Contact, PartnerCredit, PartnerSubmission, PartnerUser, Purchase
from app.services import catalog, partner_wallet
from tests.test_partner import new_client, sms  # noqa: F401
from tests.test_partner_submissions import published_body, sub_form, submit, verified_partner


@pytest.fixture(autouse=True)
def no_vat(monkeypatch):
    monkeypatch.setenv("LEADSCAN_IAM_VAT_RATE", "KCT")
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def partner(sms):  # noqa: F811
    return verified_partner()


_n = [0]


def company(**over) -> int:
    _n[0] += 1
    with new_session() as db:
        c = Company(code=f"LS-T-{_n[0]:04d}", name=f"Công ty Mua {_n[0]}", tax_code=f"09{_n[0]:08d}", tax_key=f"09{_n[0]:08d}",
                    industry="Bao bì & in ấn", company_size="10–49 nhân sự", province="Hà Nội", **over)
        db.add(c)
        db.commit()
        return c.id


def published_sub(partner, admin, *, large=False, **form) -> tuple[int, int]:
    """Cơ hội đối tác Đạt → phiếu → mở bán. Trả về (submission_id, opportunity_id)."""
    j = submit(partner, **form)
    r = admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "verified", "is_large": large})
    assert r.status_code == 200, r.text
    oid = admin.post(f"/api/admin/partner-submissions/{j['id']}/create-opportunity").json()["opportunity_id"]
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    r = admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=29000, region="Miền Bắc", max_buyers=1000))
    assert r.status_code == 200, r.text
    return j["id"], oid


def sell(oid: int, price: int, company_id: int | None = None, when=None) -> int:
    """Ghi 1 lượt mua (giá thành viên thực trả) và chạy bộ tính như catalog.buy."""
    with new_session() as db:
        p = Purchase(company_id=company_id or company(), opportunity_id=oid, price=price, created_at=when or utcnow())
        db.add(p)
        db.flush()
        partner_wallet.safe(partner_wallet.on_purchase, db, p)
        db.commit()
        return p.id


def refund(purchase_id: int):
    with new_session() as db:
        catalog.refund(db, db.get(Purchase, purchase_id), "Thông tin sai")
        db.commit()


def credited(sub_id: int) -> int:
    with new_session() as db:
        return sum(c.amount for c in db.scalars(select(PartnerCredit).where(PartnerCredit.submission_id == sub_id, PartnerCredit.state != "void")))


def summary(partner) -> dict:
    return partner.get("/api/partner/wallet").json()["summary"]


def set_settings(admin, **values):
    r = admin.put("/api/admin/partner-settings", json={"values": values, "reason": "kiểm thử"})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ ly cafe


def test_s0_cafe_pending_until_published(partner, admin):
    j = submit(partner)
    admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "verified"})
    s = summary(partner)
    assert s["pending"] == 30000 and s["available"] == 0 and s["cafe_used"] == 1 and s["cafe_left"] == 9
    oid = admin.post(f"/api/admin/partner-submissions/{j['id']}/create-opportunity").json()["opportunity_id"]
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=29000, region="Miền Bắc"))
    s = summary(partner)
    assert s["pending"] == 0 and s["available"] == 30000  # S0: đạt xác minh, chưa bán → 30.000đ


# ------------------------------------------------------------------ bảng 5.3 — PA2 (mặc định)


@pytest.mark.parametrize(
    "prices,large,expected",
    [
        ([29000], False, 30000),  # S1: 1 lượt phiếu cơ bản → vẫn 1 ly cafe
        ([29000] * 3, False, 30000),  # S2: 3 lượt (87.000đ) → 20% = 17.400 < ly cafe
        ([1_250_000] * 2, False, 500000),  # S3: 2 lượt enrich vòng 2 → 20% × 2,5tr
        ([50_000_000], True, 5_000_000),  # S4: cơ hội lớn 10%
    ],
)
def test_brief_scenarios_pa2(partner, admin, prices, large, expected):
    sid, oid = published_sub(partner, admin, large=large)
    for p in prices:
        sell(oid, p)
    assert credited(sid) == expected


@pytest.mark.parametrize(
    "prices,large,expected",
    [([29000], False, 35800), ([29000] * 3, False, 47400), ([1_250_000] * 2, False, 530000), ([50_000_000], True, 5_030_000)],
)
def test_brief_scenarios_pa1(partner, admin, prices, large, expected):
    set_settings(admin, reward_mode="sum")
    sid, oid = published_sub(partner, admin, large=large)
    for p in prices:
        sell(oid, p)
    assert credited(sid) == expected


def test_commission_hold_then_available(partner, admin):
    sid, oid = published_sub(partner, admin)
    sell(oid, 1_250_000)  # 20% = 250.000 → ghi thêm 220.000 (đã có 30.000 ly cafe)
    s = summary(partner)
    assert s["available"] == 30000 and s["pending"] == 220000
    with new_session() as db:
        c = db.scalar(select(PartnerCredit).where(PartnerCredit.kind == "commission", PartnerCredit.amount > 0))
        assert c.calc["rate"] == 20 and c.calc["target"] == 250000 and c.calc["credited_before"] == 30000
        assert (c.available_at - c.created_at).days == 7
        c.available_at = utcnow() - timedelta(minutes=1)
        db.commit()
    s = summary(partner)  # mở ví → giải phóng khoản hết hạn giữ
    assert s["available"] == 250000 and s["pending"] == 0


def test_vat_is_excluded_from_revenue(partner, admin, monkeypatch):
    monkeypatch.setenv("LEADSCAN_IAM_VAT_RATE", "10")
    from app.config import get_settings

    get_settings.cache_clear()
    sid, oid = published_sub(partner, admin)
    sell(oid, 1_100_000)  # trước thuế 1.000.000 → 20% = 200.000
    assert credited(sid) == 200000


def test_tier_and_custom_rate(partner, admin):
    pid = partner.get("/api/partner/auth/me").json()["id"]
    admin.patch(f"/api/admin/partners/{pid}", json={"tier": "silver", "reason": "đạt điều kiện"})
    sid, oid = published_sub(partner, admin)
    sell(oid, 1_000_000)
    assert credited(sid) == 250000  # Bạc 25%
    r = admin.patch(f"/api/admin/partners/{pid}", json={"custom_rate": 40})
    assert r.status_code == 422  # vượt trần 30%
    admin.patch(f"/api/admin/partners/{pid}", json={"custom_rate": 30, "reason": "hợp đồng chiến lược"})
    sid2, oid2 = published_sub(partner, admin, company_name="Công ty Khác", tax_code="0311111111")
    sell(oid2, 1_000_000)
    assert credited(sid2) == 300000


# ------------------------------------------------------------------ hạn mức, thời hạn, liên quan


def test_cafe_quota_per_month(partner, admin):
    pid = partner.get("/api/partner/auth/me").json()["id"]
    admin.patch(f"/api/admin/partners/{pid}", json={"custom_cafe_quota": 1})
    a = submit(partner)
    b = submit(partner, company_name="Công ty Hai", tax_code="0322222222")
    for x in (a, b):
        admin.post(f"/api/admin/partner-submissions/{x['id']}/decide", json={"decision": "verified"})
    assert credited(a["id"]) == 30000 and credited(b["id"]) == 0  # vượt hạn mức: không có ly cafe trả trước
    ev = partner.get(f"/api/partner/submissions/{b['id']}").json()["events"]
    assert any("hạn mức" in e["content"] for e in ev)
    # nhưng vẫn chia doanh thu khi bán (từ đồng đầu tiên)
    oid = admin.post(f"/api/admin/partner-submissions/{b['id']}/create-opportunity").json()["opportunity_id"]
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=29000, region="Miền Bắc"))
    sell(oid, 100_000)
    assert credited(b["id"]) == 20000


def test_share_window_12_months(partner, admin):
    sid, oid = published_sub(partner, admin)
    with new_session() as db:
        s = db.get(PartnerSubmission, sid)
        s.published_at = utcnow() - timedelta(days=370)
        db.commit()
    sell(oid, 5_000_000)
    assert credited(sid) == 30000
    d = partner.get(f"/api/partner/submissions/{sid}").json()
    assert d["share_expired"] is True and any("hạn chia sẻ" in e["content"] for e in d["events"]) is False  # nhật ký nội bộ, không lộ
    assert partner_wallet.add_months(utcnow().replace(month=1, day=31), 1).day in (28, 29)


def test_related_buyer_gets_no_commission(partner, admin):
    sid, oid = published_sub(partner, admin)
    cid = company()
    with new_session() as db:
        db.add(Contact(company_id=cid, full_name="Bình", phone="+84 912 345 678", email="x@y.vn", is_primary=True))
        db.commit()
    sell(oid, 2_000_000, company_id=cid)  # đối tác dùng SĐT 0912345678
    assert credited(sid) == 30000
    with new_session() as db:
        assert db.scalar(select(PartnerCredit).where(PartnerCredit.kind == "commission")) is None  # lượt này không vào lũy kế
    sell(oid, 1_000_000)  # lượt bình thường: 20% × 1tr (không cộng lượt liên quan)
    assert credited(sid) == 200000


# ------------------------------------------------------------------ hoàn phiếu, gian lận, điều chỉnh


def test_refund_claws_back_commission_but_keeps_cafe(partner, admin):
    sid, oid = published_sub(partner, admin)
    p1 = sell(oid, 1_250_000)
    p2 = sell(oid, 1_250_000)
    assert credited(sid) == 500000
    refund(p2)
    assert credited(sid) == 250000  # thu hồi đúng phần của lượt hoàn
    refund(p1)
    assert credited(sid) == 30000  # không thu hồi ly cafe bảo đảm
    with new_session() as db:
        kinds = [c.kind for c in db.scalars(select(PartnerCredit).where(PartnerCredit.submission_id == sid).order_by(PartnerCredit.id))]
        assert kinds.count("clawback") == 2
    s = summary(partner)
    assert s["available"] + s["pending"] == 30000 and s["available"] >= 0  # thu hồi trừ vào khoản đang giữ, không làm Khả dụng âm


def test_refund_of_uncounted_purchase_is_noop(partner, admin):
    sid, oid = published_sub(partner, admin)
    pid = sell(oid, 29000)
    refund(pid)
    assert credited(sid) == 30000


def test_fraud_claws_back_everything_and_locks(partner, admin, staff):
    sid, oid = published_sub(partner, admin)
    sell(oid, 1_000_000)
    assert credited(sid) == 200000
    url = f"/api/admin/partner-submissions/{sid}/fraud"
    assert staff.post(url, json={"reason": "Doanh nghiệp không tồn tại"}).status_code == 403
    r = admin.post(url, json={"reason": "Doanh nghiệp không tồn tại"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected" and r.json()["reject_reason"] == "fraud"
    assert credited(sid) == 0
    assert partner.get("/api/partner/auth/me").status_code == 401  # tài khoản bị khoá
    sell(oid, 1_000_000)  # phiếu còn bán cũng không ghi thêm
    assert credited(sid) == 0
    # chọn "Gian lận" qua quyết định thường bị chặn (phải dùng nút riêng để thu hồi)
    j = submit(verified_partner(email="c@gmail.com", phone="0977000111"), company_name="Công ty Ba", tax_code="0333333333")
    assert admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "rejected", "reason": "fraud"}).status_code == 422


def test_redecide_revokes_cafe(partner, admin):
    j = submit(partner)
    url = f"/api/admin/partner-submissions/{j['id']}/decide"
    admin.post(url, json={"decision": "verified"})
    assert credited(j["id"]) == 30000
    admin.post(url, json={"decision": "duplicate", "partner_note": "Đối tác khác gửi trước"})
    assert credited(j["id"]) == 0
    admin.post(url, json={"decision": "supplement"})
    assert credited(j["id"]) == 30000 and summary(partner)["available"] == 30000  # đóng góp bổ sung: Khả dụng ngay


def test_adjust_admin_only(partner, admin, staff):
    pid = partner.get("/api/partner/auth/me").json()["id"]
    assert staff.post(f"/api/admin/partners/{pid}/adjust", json={"amount": 50000, "reason": "Thưởng hợp đồng"}).status_code == 403
    r = admin.post(f"/api/admin/partners/{pid}/adjust", json={"amount": 50000, "reason": "Thưởng hợp đồng"})
    assert r.status_code == 200 and r.json()["wallet"]["available"] == 50000
    w = partner.get("/api/partner/wallet").json()
    assert w["items"][0]["kind_label"] == "Điều chỉnh" and "calc" not in w["items"][0] and "actor" not in w["items"][0]


# ------------------------------------------------------------------ cấu hình, tích hợp mua thật


def test_settings_validation_and_log(admin, staff):
    assert staff.put("/api/admin/partner-settings", json={"values": {"cafe_amount": 25000}, "reason": "chốt"}).status_code == 403
    assert admin.put("/api/admin/partner-settings", json={"values": {"rate_new": 90}, "reason": "sai"}).status_code == 422
    assert admin.put("/api/admin/partner-settings", json={"values": {"reward_mode": "x"}, "reason": "sai"}).status_code == 422
    r = admin.put("/api/admin/partner-settings", json={"values": {"cafe_amount": 25000}, "reason": "Chốt mục 12"})
    assert r.status_code == 200 and r.json()["values"]["cafe_amount"] == 25000
    assert r.json()["logs"][0] == {**r.json()["logs"][0], "key": "cafe_amount", "old": "30000", "new": "25000", "reason": "Chốt mục 12"}
    assert new_client().get("/api/partner/reward-config").json()["cafe"] == 25000


def test_real_member_purchase_and_refund_flow(partner, admin, client):
    """Mua qua catalog.buy thật (giá theo điểm riêng của thành viên) → hoa hồng; admin hoàn phiếu → thu hồi."""
    from tests.conftest import register
    from tests.test_member import ask, member_client, pay_membership

    sid, oid = published_sub(partner, admin)
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=2_000_000, region="Miền Bắc"))
    register(client)
    m = member_client()
    pay_membership(m)
    ask(m, "Cần cung cấp thùng carton 5 lớp cho nhà máy điện tử ở Bắc Ninh, line SMT mới")
    r = m.post(f"/api/member/opportunities/{oid}/purchase")
    assert r.status_code == 200, r.text
    with new_session() as db:
        pur = db.scalar(select(Purchase).where(Purchase.opportunity_id == oid))
        expected = max(30000, pur.price * 20 // 100)
    assert credited(sid) == expected
    d = partner.get(f"/api/partner/submissions/{sid}").json()
    assert d["sold_count"] == 1 and d["earned"] == expected
    r = admin.post(f"/api/admin/purchases/{pur.id}/refund", json={"note": "Thông tin sai"})
    assert r.status_code == 200, r.text
    assert credited(sid) == 30000
    assert partner.get(f"/api/partner/submissions/{sid}").json()["sold_count"] == 0


def test_dashboard_wallet(partner, admin):
    sid, oid = published_sub(partner, admin)
    sell(oid, 1_000_000)
    d = partner.get("/api/partner/dashboard").json()
    assert d["wallet"]["total"] == 200000 and d["wallet"]["month"] == 200000 and d["sold"] == 1
    assert d["recent"][0]["earned"] == 200000 and d["recent"][0]["sold_count"] == 1
