"""Đối tác LeadScan — Mốc 5: KPI thí điểm, công nợ, hiệu quả theo đối tác/ngành/tỉnh, cờ gian lận, nhật ký chung."""

from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

from app.db import new_session, utcnow
from app.models import PartnerEvent, PartnerUser
from tests.test_partner import otp_mail  # noqa: F401
from tests.test_partner_submissions import submit, verified_partner
from tests.test_partner_wallet import no_vat, published_sub, sell  # noqa: F401  (no_vat: doanh thu = giá, dễ đối chiếu)


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("LEADSCAN_PARTNER_SECRET_KEY", Fernet.generate_key().decode())
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def partner(otp_mail):  # noqa: F811
    return verified_partner()


def test_kpi_and_gate(partner, admin):
    sid, oid = published_sub(partner, admin)  # đạt + phiếu đang bán
    sell(oid, 1_000_000)
    sell(oid, 1_000_000)  # doanh thu 2tr → hoa hồng 20% = 400k (đã gồm ly cafe)
    j = submit(partner, company_name="Công ty Hai", tax_code="0322222222")
    admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "rejected", "reason": "vague"})
    submit(partner, company_name="Công ty Ba", tax_code="0333333333")  # còn chờ xác minh

    k = admin.get("/api/admin/partner-reports/kpi").json()
    by = {i["key"]: i for i in k["items"]}
    assert by["partners"]["value"] == 1 and by["partners"]["met"] is False  # mục tiêu 200
    assert by["activation"]["value"] == 100.0 and by["activation"]["met"] is True
    assert by["pass_rate"]["value"] == pytest.approx(33.3) and by["pass_rate"]["met"] is False  # 1/3 < 40%
    assert by["sell_rate"]["value"] == 100.0  # 1/1 cơ hội đạt có lượt bán
    assert k["revenue"] == 2_000_000 and k["cost"] == 400_000
    assert by["cost_ratio"]["value"] == 20.0 and by["cost_ratio"]["met"] is True
    assert k["met"] == 3 and k["gate_passed"] is True  # ≥ 3/5 và chi phí ≤ 35%

    # lọc kỳ: kỳ trước khi có dữ liệu → rỗng
    old = admin.get("/api/admin/partner-reports/kpi?from=2026-01-01&to=2026-01-31").json()
    assert old["sent"] == 0 and old["revenue"] == 0 and {i["key"]: i["value"] for i in old["items"]}["pass_rate"] is None


def test_kpi_activation_excludes_young_inactive_partners(otp_mail, admin):  # noqa: F811
    verified_partner()  # mới đăng ký, chưa gửi → chưa tính vào mẫu số
    verified_partner(email="old@gmail.com", phone="0977111222")
    with new_session() as db:
        p = db.query(PartnerUser).filter_by(email="old@gmail.com").one()
        p.created_at = utcnow() - timedelta(days=40)  # đã quá 30 ngày mà chưa gửi → không kích hoạt
        db.commit()
    by = {i["key"]: i for i in admin.get("/api/admin/partner-reports/kpi").json()["items"]}
    assert by["activation"]["value"] == 0.0 and "0/1" in by["activation"]["note"]


def test_liabilities(partner, admin):
    sid, oid = published_sub(partner, admin)
    sell(oid, 1_000_000)  # ly cafe 30k khả dụng + 170k chờ duyệt
    pid = partner.get("/api/partner/auth/me").json()["id"]
    admin.post(f"/api/admin/partners/{pid}/adjust", json={"amount": 300000, "reason": "thưởng"})
    partner.put("/api/partner/payout-profile", json={"legal_name": "Trần Thị Bình", "id_number": "001190012345", "bank_bin": "970436",
                                                      "account_no": "0011004455667", "account_holder": "TRAN THI BINH"})
    assert partner.post("/api/partner/withdrawals", json={"amount": 200000}).status_code == 201
    d = admin.get("/api/admin/partner-reports/liabilities").json()
    row = d["items"][0]
    assert row["pending"] == 170000 and row["available"] == 130000 and row["withdrawing"] == 200000 and row["owed"] == 500000
    assert d["totals"]["owed"] == 500000
    csv = admin.get("/api/admin/partner-reports/liabilities?format=csv")
    assert csv.headers["content-type"].startswith("text/csv") and "LeadScan đang nợ" in csv.content.decode("utf-8")


def test_performance_groups(partner, admin, otp_mail):  # noqa: F811
    sid, oid = published_sub(partner, admin)  # Bao bì · Bắc Ninh
    sell(oid, 1_000_000)
    other = verified_partner(email="p2@gmail.com", phone="0988000111")
    j = submit(other, company_name="Công ty Nhựa", tax_code="0344444444", industry="Nhựa & cao su", province="Đồng Nai")
    admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "rejected", "reason": "vague"})

    by_partner = admin.get("/api/admin/partner-reports/performance?group=partner").json()
    top = by_partner["items"][0]
    assert top["revenue"] == 1_000_000 and top["cost"] == 200_000 and top["cost_ratio"] == 20.0 and top["sold"] == 1
    assert by_partner["totals"]["sent"] == 2 and by_partner["totals"]["pass_rate"] == 50.0

    ind = {r["label"]: r for r in admin.get("/api/admin/partner-reports/performance?group=industry").json()["items"]}
    assert ind["Bao bì & in ấn"]["ok"] == 1 and ind["Nhựa & cao su"]["ok"] == 0
    prov = {r["label"]: r for r in admin.get("/api/admin/partner-reports/performance?group=province").json()["items"]}
    assert set(prov) == {"Bắc Ninh", "Đồng Nai"}
    csv = admin.get("/api/admin/partner-reports/performance?group=province&format=csv").content.decode("utf-8")
    assert "Tỉnh/thành" in csv and "Đồng Nai" in csv


def test_fraud_flags(partner, admin, otp_mail):  # noqa: F811
    profile = {"id_number": "001190012345", "bank_bin": "970436", "account_no": "0011004455667", "account_holder": "TRAN THI BINH",
               "legal_name": "Trần Thị Bình"}
    other = verified_partner(email="twin@gmail.com", phone="0911999888")
    partner.put("/api/partner/payout-profile", json=profile)
    other.put("/api/partner/payout-profile", json=profile)
    # 5 cơ hội bị từ chối → tỷ lệ không đạt cao
    for i in range(5):
        j = submit(other, company_name=f"Công ty Ảo {i}", tax_code=f"035555555{i}")
        admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "rejected", "reason": "unverifiable"})
    with new_session() as db:
        p = db.query(PartnerUser).filter_by(email="twin@gmail.com").one()
        db.add(PartnerEvent(partner_id=p.id, kind="sale_skip", content="Lượt bán phiếu CH-000009: tài khoản mua có liên quan tới đối tác (trùng email) — không tính hoa hồng"))
        db.commit()

    flags = admin.get("/api/admin/partner-reports/fraud").json()["items"]
    types = {f["type"] for f in flags}
    assert {"same_device", "shared_bank", "high_reject", "related_buyer"} <= types  # TestClient: cùng IP + trình duyệt
    assert flags[0]["severity"] == "high"
    lst = admin.get("/api/admin/partners?q=twin").json()["items"][0]
    assert "Tỷ lệ không đạt / trùng cao" in lst["flags"] and "Nhiều đối tác dùng chung tài khoản ngân hàng" in lst["flags"]
    det = admin.get(f"/api/admin/partners/{lst['id']}").json()
    assert {f["type"] for f in det["flags"]} >= {"high_reject", "related_buyer", "shared_bank"}


def test_global_event_log(partner, admin):
    sid, oid = published_sub(partner, admin)
    sell(oid, 1_000_000)
    all_ = admin.get("/api/admin/partner-reports/events").json()
    assert all_["total"] >= 5 and all_["items"][0]["partner"]["code"].startswith("DT-")
    money = admin.get("/api/admin/partner-reports/events?kind=money").json()["items"]
    assert money and all(e["kind"] in ("credit", "cafe_quota", "sale_skip", "credit_error") for e in money)
    assert any(e["submission"] and e["submission"]["code"].startswith("GT-") for e in money)
    found = admin.get("/api/admin/partner-reports/events?q=ly%20cafe").json()["items"]
    assert found and all("ly cafe" in e["content"].lower() for e in found)
    assert partner.get("/api/admin/partner-reports/events").status_code == 401


def test_fraud_flag_review_and_reopen(partner, admin, client, staff_id, otp_mail):  # noqa: F811
    from tests.conftest import STAFF_PW

    verified_partner(email="twin@gmail.com", phone="0911999888")  # cùng IP + trình duyệt với partner
    d = admin.get("/api/admin/partner-reports/fraud").json()
    flag = next(f for f in d["items"] if f["type"] == "same_device")
    assert flag["status"] == "open" and flag["review"] is None and d["open"] >= 1
    twin = next(p for p in flag["partners"] if p["code"] != partner.get("/api/partner/auth/me").json()["code"])

    # bắt buộc lý do; nhân viên không được bỏ qua cờ
    assert admin.post("/api/admin/partner-reports/fraud/review", json={"key": flag["key"], "note": " "}).status_code == 422
    assert admin.post("/api/admin/partner-reports/fraud/review", json={"key": "same_ip:999", "note": "x"}).status_code == 409

    r = admin.post("/api/admin/partner-reports/fraud/review", json={"key": flag["key"], "note": "Hai vợ chồng dùng chung wifi"})
    assert r.status_code == 200, r.text
    assert admin.post("/api/admin/partner-reports/fraud/review", json={"key": flag["key"], "note": "lần 2"}).status_code == 409
    f2 = next(f for f in admin.get("/api/admin/partner-reports/fraud").json()["items"] if f["key"] == flag["key"])
    assert f2["status"] == "reviewed" and f2["review"]["note"] == "Hai vợ chồng dùng chung wifi" and f2["review"]["actor"] == "Quản Trị"
    # đã xem xét → không còn hiện ở danh sách / chi tiết đối tác
    assert admin.get("/api/admin/partners?q=twin").json()["items"][0]["flags"] == []
    assert admin.get(f"/api/admin/partners/{twin['id']}").json()["flags"] == []
    # ghi nhật ký cho từng đối tác liên quan
    log = admin.get("/api/admin/partner-reports/events?kind=fraud").json()["items"]
    assert len(log) == 2 and all("bỏ qua — Hai vợ chồng" in e["content"] and e["kind_label"] == "Cờ gian lận" for e in log)

    # dấu hiệu mới (thêm tài khoản cùng IP) → khoá đổi → cờ mới cần xem xét
    verified_partner(email="third@gmail.com", phone="0911999777")
    f3 = [f for f in admin.get("/api/admin/partner-reports/fraud").json()["items"] if f["type"] == "same_device"]
    assert len(f3) == 1 and f3[0]["status"] == "open" and f3[0]["key"] != flag["key"]

    # mở lại cờ cũ (không còn khớp cờ hiện tại vẫn mở lại được)
    assert admin.post("/api/admin/partner-reports/fraud/reopen", json={"key": flag["key"], "note": "kiểm tra lại"}).status_code == 200
    assert admin.post("/api/admin/partner-reports/fraud/reopen", json={"key": flag["key"]}).status_code == 409

    staff = client.__class__(client.app)
    assert staff.post("/api/admin/auth/login", json={"email": "staff@leadscan.vn", "password": STAFF_PW}).status_code == 200
    assert staff.get("/api/admin/partner-reports/fraud").status_code == 200
    assert staff.post("/api/admin/partner-reports/fraud/review", json={"key": f3[0]["key"], "note": "x"}).status_code == 403


def test_fraud_flag_resurfaces_on_new_evidence(partner, admin, otp_mail):  # noqa: F811
    other = verified_partner(email="bad@gmail.com", phone="0911222333")
    for i in range(5):
        j = submit(other, company_name=f"Công ty Ảo {i}", tax_code=f"035555555{i}")
        admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "rejected", "reason": "unverifiable"})
    flag = next(f for f in admin.get("/api/admin/partner-reports/fraud").json()["items"] if f["type"] == "high_reject")
    assert admin.post("/api/admin/partner-reports/fraud/review", json={"key": flag["key"], "note": "mới làm quen"}).status_code == 200
    assert next(f for f in admin.get("/api/admin/partner-reports/fraud").json()["items"] if f["type"] == "high_reject")["status"] == "reviewed"
    j = submit(other, company_name="Công ty Ảo 9", tax_code="0355555559")
    admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "rejected", "reason": "unverifiable"})
    again = next(f for f in admin.get("/api/admin/partner-reports/fraud").json()["items"] if f["type"] == "high_reject")
    assert again["status"] == "open" and again["review"]["note"] == "mới làm quen"  # vẫn giữ lần xem xét trước để tham khảo
    # xem xét lại cờ đã hiện lại → cập nhật
    assert admin.post("/api/admin/partner-reports/fraud/review", json={"key": flag["key"], "note": "đã gọi xác nhận"}).status_code == 200


def test_event_log_filters_and_csv(partner, admin):
    sid, oid = published_sub(partner, admin)
    pid = partner.get("/api/partner/auth/me").json()["id"]
    one = admin.get(f"/api/admin/partner-reports/events?partner_id={pid}&kind=submission").json()
    assert one["total"] >= 2 and all(e["partner"]["id"] == pid and e["kind_label"] for e in one["items"])
    assert admin.get(f"/api/admin/partner-reports/events?partner_id={pid + 99}").json()["total"] == 0
    assert admin.get("/api/admin/partner-reports/events?from=2026-01-01&to=2026-01-31").json()["total"] == 0
    r = admin.get(f"/api/admin/partner-reports/events?partner_id={pid}&kind=submission&format=csv")
    assert r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0].startswith("Thời điểm (giờ VN)") and len(lines) == one["total"] + 1 and "GT-" in text
