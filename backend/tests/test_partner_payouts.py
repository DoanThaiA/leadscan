"""Đối tác LeadScan — Mốc 4: hồ sơ thanh toán, lệnh rút, thuế TNCN, lô chi, file chi."""

from datetime import date

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.db import new_session
from app.models import PartnerEvent, PartnerPayoutProfile, PartnerUser, PartnerWithdrawal
from app.services import partner_payouts as pay
from tests.test_partner import new_client, signup_form, otp_mail  # noqa: F401
from tests.test_partner_submissions import verified_partner

PROFILE = {"legal_name": "Trần Thị Bình", "id_number": "001190012345", "tax_code": "", "bank_bin": "970436",
           "account_no": "0011004455667", "account_holder": "TRAN THI BINH"}


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("LEADSCAN_PARTNER_SECRET_KEY", Fernet.generate_key().decode())
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def partner(otp_mail):  # noqa: F811
    return verified_partner()


def pid(c) -> int:
    return c.get("/api/partner/auth/me").json()["id"]


def fund(admin, c, amount: int):
    r = admin.post(f"/api/admin/partners/{pid(c)}/adjust", json={"amount": amount, "reason": "nạp kiểm thử"})
    assert r.status_code == 200, r.text


def with_profile(c, **over):
    r = c.put("/api/partner/payout-profile", json={**PROFILE, **over})
    assert r.status_code == 200, r.text
    return r.json()["profile"]


def withdraw(c, amount: int) -> dict:
    r = c.post("/api/partner/withdrawals", json={"amount": amount})
    assert r.status_code == 201, r.text
    return r.json()


def summary(c) -> dict:
    return c.get("/api/partner/withdrawals").json()["summary"]


# ------------------------------------------------------------------ hồ sơ thanh toán


def test_profile_requires_secret_key(partner, monkeypatch):
    monkeypatch.setenv("LEADSCAN_PARTNER_SECRET_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    assert partner.put("/api/partner/payout-profile", json=PROFILE).status_code == 503
    assert "chưa được mở" in partner.get("/api/partner/withdrawals").json()["rules"]["reason"]


def test_profile_validation_and_encryption(partner):
    r = partner.put("/api/partner/payout-profile", json={**PROFILE, "id_number": "123", "account_no": "12", "account_holder": "NGUYEN VAN A"})
    assert r.status_code == 422 and set(r.json()["fields"]) == {"id_number", "account_no", "account_holder"}
    r = partner.put("/api/partner/payout-profile", json={**PROFILE, "account_holder": "NGUYEN VAN A"})
    assert "chính chủ" in r.json()["fields"]["account_holder"]

    prof = with_profile(partner)
    assert prof["account_masked"] == "••••5667" and prof["id_masked"].endswith("2345") and prof["bank_name"] == "Vietcombank"
    assert prof["name_match"] is True and "account_no" not in prof
    with new_session() as db:
        row = db.scalar(select(PartnerPayoutProfile))
        assert "0011004455667" not in row.account_enc and "001190012345" not in row.id_number_enc  # mã hoá khi lưu
        assert pay.decrypt(row.account_enc) == "0011004455667"


def test_org_partner_profile_uses_org_tax_code(otp_mail):  # noqa: F811
    c = verified_partner(kind="org", org_name="Hiệp hội Bao bì Việt Nam", org_tax_code="0101234567", email="hh@gmail.com", phone="0911222333")
    r = c.put("/api/partner/payout-profile", json={"bank_bin": "970418", "account_no": "12345678", "account_holder": "HIEP HOI BAO BI VIET NAM"})
    assert r.status_code == 200, r.text
    assert r.json()["profile"]["legal_name"] == "Hiệp hội Bao bì Việt Nam" and r.json()["profile"]["tax_code"] == "0101234567"


# ------------------------------------------------------------------ lệnh rút


def test_withdraw_rules(partner, admin):
    r = partner.post("/api/partner/withdrawals", json={"amount": 100000})
    assert r.status_code == 409 and "hồ sơ thanh toán" in r.json()["detail"]
    with_profile(partner)
    fund(admin, partner, 90000)
    assert "tối thiểu" in partner.get("/api/partner/withdrawals").json()["rules"]["reason"]
    fund(admin, partner, 210000)  # Khả dụng 300.000
    assert partner.post("/api/partner/withdrawals", json={"amount": 50000}).status_code == 422
    assert partner.post("/api/partner/withdrawals", json={"amount": 400000}).status_code == 422
    w = withdraw(partner, 250000)
    assert w["code"].startswith("RT-") and w["status_label"] == "Chờ duyệt" and w["tax_withheld"] == 0 and w["account_masked"] == "••••5667"
    s = summary(partner)
    assert s["available"] == 50000 and s["withdrawing"] == 250000 and s["paid"] == 0
    r = partner.post("/api/partner/withdrawals", json={"amount": 100000})
    assert r.status_code == 409 and "chờ xử lý" in r.json()["detail"]  # mỗi lúc 1 lệnh


def test_cancel_returns_money_and_monthly_limit(partner, admin):
    with_profile(partner)
    fund(admin, partner, 1_000_000)
    a = withdraw(partner, 200000)
    assert partner.post(f"/api/partner/withdrawals/{a['id']}/cancel").status_code == 200
    assert summary(partner)["available"] == 1_000_000
    # huỷ không tính vào giới hạn tháng; 2 lệnh (đã chi) / tháng
    for _ in range(2):
        w = withdraw(partner, 100000)
        admin.post(f"/api/admin/partner-withdrawals/{w['id']}/approve")
        with new_session() as db:  # coi như đã chi để mở lệnh tiếp
            db.get(PartnerWithdrawal, w["id"]).status = "paid"
            db.commit()
    rules = partner.get("/api/partner/withdrawals").json()["rules"]
    assert rules["can_request"] is False and "2 lệnh" in rules["reason"]
    # đối tác khác không huỷ được lệnh của mình
    other = verified_partner(email="o@gmail.com", phone="0933000444")
    assert other.post(f"/api/partner/withdrawals/{a['id']}/cancel").status_code == 404


def test_tax_withholding_threshold(partner, admin, otp_mail):  # noqa: F811
    with_profile(partner)
    fund(admin, partner, 20_000_000)
    w = withdraw(partner, 6_000_000)  # brief 6.3: rút 6tr → khấu trừ 600k, thực nhận 5,4tr
    assert w["tax_withheld"] == 600000 and w["net_amount"] == 5_400_000
    partner.post(f"/api/partner/withdrawals/{w['id']}/cancel")
    w = withdraw(partner, 4_900_000)  # dưới 5tr → không khấu trừ tại nguồn
    assert w["tax_withheld"] == 0 and w["net_amount"] == 4_900_000
    # tổ chức: không khấu trừ
    org = verified_partner(kind="org", org_name="Công ty TNHH Môi giới KCN", org_tax_code="0309999999", email="kcn@gmail.com", phone="0944555666")
    org.put("/api/partner/payout-profile", json={"bank_bin": "970407", "account_no": "99887766", "account_holder": "CONG TY TNHH MOI GIOI KCN"})
    fund(admin, org, 10_000_000)
    assert withdraw(org, 8_000_000)["tax_withheld"] == 0


# ------------------------------------------------------------------ duyệt, lô chi


def test_approve_reject_admin_only(partner, admin, staff, monkeypatch):
    from app.services import notify

    mails: list[str] = []
    monkeypatch.setattr(notify, "send_mail", lambda cfg, subject, body, to=None, **kw: mails.append(f"{subject}|{body}") or True)
    with_profile(partner)
    fund(admin, partner, 500000)
    w = withdraw(partner, 300000)
    assert staff.post(f"/api/admin/partner-withdrawals/{w['id']}/approve").status_code == 403
    lst = staff.get("/api/admin/partner-withdrawals").json()
    assert lst["items"][0]["code"] == w["code"] and lst["items"][0]["name_match"] is True and lst["items"][0]["legal_name"] == "Trần Thị Bình"
    r = admin.post(f"/api/admin/partner-withdrawals/{w['id']}/reject", json={"reason": "Sai thông tin"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert summary(partner)["available"] == 500000
    assert any("không được duyệt" in m for m in mails)
    w2 = withdraw(partner, 300000)
    assert admin.post(f"/api/admin/partner-withdrawals/{w2['id']}/approve").json()["status_label"] == "Đã duyệt — chờ chi"
    assert partner.post(f"/api/partner/withdrawals/{w2['id']}/cancel").status_code == 409  # đã duyệt: không tự huỷ


def test_batch_export_and_paid(partner, admin, staff, otp_mail, monkeypatch):  # noqa: F811
    from app.services import notify

    mails: list[str] = []
    monkeypatch.setattr(notify, "send_mail", lambda cfg, subject, body, to=None, **kw: mails.append(body) or True)
    assert admin.post("/api/admin/partner-payout-batches", json={}).status_code == 409  # chưa có lệnh duyệt

    with_profile(partner)
    fund(admin, partner, 7_000_000)
    w = withdraw(partner, 6_000_000)
    admin.post(f"/api/admin/partner-withdrawals/{w['id']}/approve")
    org = verified_partner(kind="org", org_name="Hội chợ Thương mại ABC", org_tax_code="0308888888", email="hc@gmail.com", phone="0955666777")
    org.put("/api/partner/payout-profile", json={"bank_bin": "970422", "account_no": "55556666", "account_holder": "HOI CHO THUONG MAI ABC"})
    fund(admin, org, 2_000_000)
    wo = withdraw(org, 2_000_000)
    admin.post(f"/api/admin/partner-withdrawals/{wo['id']}/approve")

    assert staff.post("/api/admin/partner-payout-batches", json={}).status_code == 403
    r = admin.post("/api/admin/partner-payout-batches", json={"pay_date": "2026-11-20"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["code"] == "LO-20261120" and b["count"] == 1  # tổ chức chưa có hoá đơn → chưa vào lô
    assert b["gross"] == 6_000_000 and b["tax"] == 600_000 and b["net"] == 5_400_000

    # đánh dấu đã chi trước khi xuất file → chặn
    assert admin.post(f"/api/admin/partner-payout-batches/{b['id']}/paid", json={}).status_code == 409
    assert staff.get(f"/api/admin/partner-payout-batches/{b['id']}/export").status_code == 403
    r = admin.get(f"/api/admin/partner-payout-batches/{b['id']}/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8")
    assert text.startswith("﻿") and "0011004455667" in text and "5400000" in text and "TRAN THI BINH" in text
    assert admin.get(f"/api/admin/partner-payout-batches/{b['id']}").json()["status"] == "exported"

    r = admin.post(f"/api/admin/partner-payout-batches/{b['id']}/paid", json={"bank_ref": "VCB-123"})
    assert r.status_code == 200 and r.json()["status"] == "paid"
    s = summary(partner)
    assert s["paid"] == 6_000_000 and s["withdrawing"] == 0 and s["available"] == 1_000_000
    mine = partner.get("/api/partner/withdrawals").json()["items"][0]
    assert mine["status_label"] == "Đã chi" and mine["batch"]["code"] == "LO-20261120"
    assert any("5.400.000đ" in m and "600.000đ" in m for m in mails)

    # tổ chức: nhập số hoá đơn → vào lô sau
    admin.patch(f"/api/admin/partner-withdrawals/{wo['id']}", json={"invoice_no": "HD-0001"})
    b2 = admin.post("/api/admin/partner-payout-batches", json={"pay_date": "2026-11-20"}).json()
    assert b2["code"] == "LO-20261120-2" and b2["count"] == 1 and b2["tax"] == 0

    # báo cáo thuế TNCN theo kỳ
    rep = admin.get("/api/admin/partner-withdrawals/tax-report?year=2026").json()
    assert rep["total_tax"] == 600_000 and rep["items"][0]["legal_name"] == "Trần Thị Bình"


def test_reject_blocked_after_export(partner, admin):
    with_profile(partner)
    fund(admin, partner, 500000)
    w = withdraw(partner, 300000)
    admin.post(f"/api/admin/partner-withdrawals/{w['id']}/approve")
    b = admin.post("/api/admin/partner-payout-batches", json={}).json()
    admin.get(f"/api/admin/partner-payout-batches/{b['id']}/export")
    assert admin.post(f"/api/admin/partner-withdrawals/{w['id']}/reject", json={"reason": "x thử"}).status_code == 409


# ------------------------------------------------------------------ cờ gian lận, snapshot


def test_shared_bank_account_flag(partner, admin, otp_mail):  # noqa: F811
    with_profile(partner)
    other = verified_partner(email="b2@gmail.com", phone="0966777888", full_name="Trần Thị Bình")
    with_profile(other)  # cùng tài khoản ngân hàng
    with new_session() as db:
        p2 = db.scalar(select(PartnerUser).where(PartnerUser.email == "b2@gmail.com"))
        assert db.scalar(select(PartnerEvent).where(PartnerEvent.partner_id == p2.id, PartnerEvent.kind == "fraud_flag")) is not None
    d = admin.get(f"/api/admin/partners/{pid(other)}").json()
    assert d["payout_profile"]["shared_with"] == [admin.get(f"/api/admin/partners/{pid(partner)}").json()["code"]]


def test_payee_snapshot_survives_profile_change(partner, admin):
    with_profile(partner)
    fund(admin, partner, 500000)
    w = withdraw(partner, 300000)
    with_profile(partner, bank_bin="970407", account_no="1900112233")
    item = admin.get("/api/admin/partner-withdrawals").json()["items"][0]
    assert item["account_masked"] == "••••5667" and item["bank_name"] == "Vietcombank" and item["profile_changed"] is True


def test_next_pay_date_and_settings(admin):
    st = {"payout_days": "5,20"}
    assert pay.next_pay_date(st, date(2026, 11, 12)) == date(2026, 11, 20)
    assert pay.next_pay_date(st, date(2026, 11, 20)) == date(2026, 11, 20)
    assert pay.next_pay_date(st, date(2026, 12, 21)) == date(2027, 1, 5)
    assert admin.put("/api/admin/partner-settings", json={"values": {"payout_days": "30"}, "reason": "sai"}).status_code == 422
    r = admin.put("/api/admin/partner-settings", json={"values": {"payout_days": "20, 10", "min_withdraw": 200000}, "reason": "đổi lịch"})
    assert r.status_code == 200 and r.json()["values"]["payout_days"] == "10,20"
    cfg = new_client().get("/api/partner/reward-config").json()
    assert cfg["min_withdraw"] == 200000 and cfg["payout_days"] == "10,20"
