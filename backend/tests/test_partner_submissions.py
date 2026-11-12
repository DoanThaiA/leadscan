"""Đối tác LeadScan — Mốc 2: gửi cơ hội, kiểm tra trùng, điểm chất lượng, hàng đợi xác minh, tạo phiếu gắn đối tác nguồn."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import new_session, utcnow
from app.models import Opportunity, PartnerSubmission, PartnerUser
from app.services.partner_submissions import name_key, sla_due
from tests.test_partner import new_client, signup_form, sms  # noqa: F401  (fixture sms)


def verified_partner(**over) -> TestClient:
    c = new_client()
    r = c.post("/api/partner/auth/register", json=signup_form(**over))
    assert r.status_code == 201, r.text
    with new_session() as db:
        p = db.get(PartnerUser, r.json()["me"]["id"])
        p.phone_verified_at = utcnow()
        db.commit()
    return c


@pytest.fixture
def partner(sms) -> TestClient:
    return verified_partner()


@pytest.fixture
def partner2(sms) -> TestClient:
    return verified_partner(email="khac@gmail.com", phone="0987654321")


def sub_form(**over) -> dict:
    form = {
        "company_name": "Công ty TNHH Điện tử Quế Võ",
        "tax_code": "2300123456",
        "tax_lookup": {"name": "CÔNG TY TNHH ĐIỆN TỬ QUẾ VÕ", "status": "NNT đang hoạt động", "active": True},
        "province": "Bắc Ninh",
        "industry": "Bao bì & in ấn",
        "kind": "new_plant",
        "need": "Nhà máy mới mở line SMT thứ 3, cần nhà cung cấp thùng carton 5 lớp và khay nhựa chống tĩnh điện, giao hàng tuần, ưu tiên NCC trong bán kính 50km.",
        "scale": "20.000 thùng/tháng",
        "timing": "Từ tháng 1/2027",
        "source_type": "relationship",
        "source_url": "",
        "certainty": "confirmed",
        "evidence": "",
        "contact_name": "Nguyễn Thu Mua",
        "contact_title": "Trưởng phòng mua hàng",
        "contact_phone": "0912 000 111",
        "contact_email": "",
        "contact_consent": True,
        "can_connect": "yes",
        "commitment": True,
    }
    form.update(over)
    return form


def submit(c: TestClient, **over) -> dict:
    r = c.post("/api/partner/submissions", json=sub_form(**over))
    assert r.status_code == 201, r.text
    return r.json()


def published_body(o: dict, **over) -> dict:
    keys = ("title", "summary", "industry", "province", "region", "source_type", "scale", "estimated_value", "deadline",
            "enrich_round", "price", "max_buyers", "buyer_name", "detail", "source_url", "contacts")
    body = {k: o[k] for k in keys if k in o}
    body["contacts"] = [{k: c.get(k, "") for k in ("full_name", "title", "phone", "email", "note")} for c in o.get("contacts", [])]
    body.update(status="published", **over)
    return body


# ------------------------------------------------------------------ gửi cơ hội


def test_requires_verified_phone(sms):
    c = new_client()
    assert c.post("/api/partner/auth/register", json=signup_form()).status_code == 201
    r = c.post("/api/partner/submissions", json=sub_form())
    assert r.status_code == 403 and "xác thực số điện thoại" in r.json()["detail"]
    assert c.get("/api/partner/submissions").status_code == 403
    assert new_client().post("/api/partner/submissions", json=sub_form()).status_code == 401


def test_submit_scores_and_hides_internal_fields(partner):
    j = submit(partner)
    assert j["code"].startswith("GT-") and j["status"] == "submitted" and j["status_label"] == "Đã gửi"
    assert j["score"] is None  # điểm chỉ hiện sau khi có quyết định
    for k in ("dup_hints", "internal_note", "auto_score", "score_detail"):
        assert k not in j
    with new_session() as db:
        s = db.scalar(select(PartnerSubmission))
        # MST 15 + đang hoạt động 5 + nhu cầu chi tiết 15 + quy mô 10 + thời điểm 10 + đã xác nhận 20 + mối quan hệ 8 + người liên hệ 5
        assert s.auto_score == 88, s.score_detail
        assert s.tax_key == "2300123456" and s.contact_consent is True
        assert s.sla_due_at > s.created_at
    lst = partner.get("/api/partner/submissions").json()
    assert lst["total"] == 1 and lst["counts"] == {"submitted": 1}
    d = partner.get("/api/partner/dashboard").json()
    assert d["sent"] == 1 and d["open"] == 1 and d["ok"] == 0 and d["recent"][0]["code"] == j["code"]


def test_submit_validation(partner):
    r = partner.post("/api/partner/submissions", json=sub_form(company_name="", tax_code="12", province="", industry="Khác", kind="x",
                                                               need="ngắn quá", source_type="", certainty="", commitment=False))
    assert r.status_code == 422
    assert set(r.json()["fields"]) == {"company_name", "tax_code", "province", "industry", "kind", "need", "source_type", "certainty", "commitment"}
    # nguồn công khai phải có link
    r = partner.post("/api/partner/submissions", json=sub_form(source_type="public", source_url=""))
    assert r.status_code == 422 and "source_url" in r.json()["fields"]
    # người liên hệ phải có xác nhận đồng ý
    r = partner.post("/api/partner/submissions", json=sub_form(contact_consent=False))
    assert r.status_code == 422 and "contact_consent" in r.json()["fields"]


def test_rejects_personal_data_lists(partner):
    need = "Danh sách khách cần mua: 0912345678, 0987654321, 0909123456, 0933444555 — gọi giúp tôi."
    r = partner.post("/api/partner/submissions", json=sub_form(need=need))
    assert r.status_code == 422 and "danh sách" in r.json()["fields"]["need"]


def test_mst_optional_and_score_lower(partner):
    j = submit(partner, tax_code="", tax_lookup=None, scale="", timing="", certainty="public", source_type="public",
               source_url="https://example.com/tin", contact_name="", contact_title="", contact_phone="", contact_consent=False)
    with new_session() as db:
        s = db.get(PartnerSubmission, j["id"])
        assert s.tax_key == "" and s.auto_score < 60


def test_same_partner_cannot_resubmit_same_opportunity(partner):
    submit(partner)
    r = partner.post("/api/partner/submissions", json=sub_form(need="Gửi lại cùng doanh nghiệp cùng nhóm nhu cầu, mô tả khác đi một chút cho dài."))
    assert r.status_code == 409 and "đã gửi cơ hội này" in r.json()["detail"]
    # khác nhóm nhu cầu (ngành) thì vẫn gửi được
    submit(partner, industry="Nhựa & cao su")


def test_daily_limit(partner, monkeypatch):
    monkeypatch.setenv("LEADSCAN_PARTNER_SUBMIT_PER_DAY", "2")
    from app.config import get_settings

    get_settings.cache_clear()
    submit(partner, tax_code="0100000001", company_name="Công ty Một")
    submit(partner, tax_code="0100000002", company_name="Công ty Hai")
    r = partner.post("/api/partner/submissions", json=sub_form(tax_code="0100000003", company_name="Công ty Ba"))
    assert r.status_code == 429


def test_partner_sees_only_own(partner, partner2):
    j = submit(partner)
    assert partner2.get(f"/api/partner/submissions/{j['id']}").status_code == 404
    assert partner2.get("/api/partner/submissions").json()["total"] == 0


# ------------------------------------------------------------------ trùng


def test_duplicate_hints_other_partner_first(partner, partner2, staff):
    first = submit(partner)
    second = submit(partner2, company_name="Điện Tử Quế Võ Co., Ltd")  # cùng MST
    d = staff.get(f"/api/admin/partner-submissions/{second['id']}").json()
    assert d["dup_strong"] is True and d["dup_hints"][0]["code"] == first["code"] and d["dup_hints"][0]["match"] == "tax"
    assert d["auto_score"] == 88 - 30
    # đối tác thứ 2 không thấy mình trùng với ai
    mine = partner2.get(f"/api/partner/submissions/{second['id']}").json()
    assert "dup_hints" not in mine and "partner" not in mine


def test_duplicate_by_name_without_tax(partner, partner2):
    submit(partner, tax_code="", tax_lookup=None)
    second = submit(partner2, tax_code="", tax_lookup=None, company_name="CÔNG TY CỔ PHẦN điện tử quế võ")
    with new_session() as db:
        s = db.get(PartnerSubmission, second["id"])
        assert s.dup_hints and s.dup_hints[0]["match"] == "name"


def test_duplicate_with_existing_opportunity(partner, admin):
    from tests.test_member import make_opp

    make_opp(admin, buyer_name="Công ty TNHH Điện tử Quế Võ")
    j = submit(partner, tax_code="", tax_lookup=None)
    d = admin.get(f"/api/admin/partner-submissions/{j['id']}").json()
    assert d["dup_hints"][0]["type"] == "opportunity" and d["dup_strong"] is True


def test_name_key_and_sla():
    assert name_key("Công ty TNHH Điện tử Quế Võ") == name_key("ĐIỆN TỬ QUẾ VÕ CO., LTD") == "dien tu que vo"
    fri = datetime(2026, 11, 13, 9, 0)  # thứ Sáu
    assert sla_due(fri, 2) == datetime(2026, 11, 17, 9, 0)  # bỏ T7, CN → thứ Ba


# ------------------------------------------------------------------ hàng đợi & quyết định


def test_queue_assign_and_verify(partner, staff, monkeypatch):
    from app.services import notify

    mails: list[str] = []
    monkeypatch.setattr(notify, "send_mail", lambda cfg, subject, body, to=None, **kw: mails.append(f"{to}|{subject}|{body}") or True)

    j = submit(partner)
    q = staff.get("/api/admin/partner-submissions").json()
    assert q["queue"] == 1 and q["items"][0]["code"] == j["code"] and q["items"][0]["partner"]["code"].startswith("DT-")

    r = staff.post(f"/api/admin/partner-submissions/{j['id']}/assign", json={})
    assert r.status_code == 200 and r.json()["status"] == "verifying" and r.json()["assigned_to"]["full_name"] == "Nhân Viên"
    assert partner.get(f"/api/partner/submissions/{j['id']}").json()["status_label"] == "Đang xác minh"

    # dưới ngưỡng không được Đạt
    r = staff.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "verified", "final_score": 55})
    assert r.status_code == 422 and "ngưỡng 60" in r.json()["detail"]
    r = staff.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "verified", "is_large": True, "partner_note": "Cơ hội tốt, cảm ơn bạn!", "internal_note": "Đã gọi xác nhận"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "verified" and d["final_score"] == 88 and d["is_large"] is True and d["internal_note"] == "Đã gọi xác nhận"

    mine = partner.get(f"/api/partner/submissions/{j['id']}").json()
    assert mine["status_label"] == "Đạt xác minh" and mine["score"] == 88 and mine["partner_note"] == "Cơ hội tốt, cảm ơn bạn!"
    assert "internal_note" not in mine
    assert [e["kind"] for e in mine["events"]] == ["sub_created", "sub_verifying", "sub_decided", "credit"]  # không lộ việc phân công
    assert len(mails) == 1 and "binh@gmail.com" in mails[0] and "Đạt xác minh" in mails[0]
    assert partner.get("/api/partner/dashboard").json()["ok"] == 1


def test_reject_needs_reason_and_staff_cannot_redecide(partner, staff, admin):
    j = submit(partner)
    url = f"/api/admin/partner-submissions/{j['id']}/decide"
    assert staff.post(url, json={"decision": "rejected"}).status_code == 422
    assert staff.post(url, json={"decision": "rejected", "reason": "other"}).status_code == 422  # lý do khác cần ghi rõ
    r = staff.post(url, json={"decision": "rejected", "reason": "vague", "partner_note": "Bổ sung quy mô và thời điểm nhé."})
    assert r.status_code == 200
    mine = partner.get(f"/api/partner/submissions/{j['id']}").json()
    assert mine["status"] == "rejected" and mine["reject_label"] == "Nhu cầu chung chung, thiếu cụ thể"
    # đã có kết quả: nhân viên không đổi được, quản trị viên đổi được (ghi nhật ký)
    assert staff.post(url, json={"decision": "verified"}).status_code == 403
    r = admin.post(url, json={"decision": "duplicate", "partner_note": "Đối tác khác đã gửi trước."})
    assert r.status_code == 200 and r.json()["status"] == "duplicate" and r.json()["reject_reason"] == ""
    assert "Đổi quyết định" in r.json()["events"][0]["content"]


def test_supplement_decision(partner, staff):
    j = submit(partner)
    r = staff.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "supplement", "partner_note": "Thông tin người ra quyết định rất giá trị."})
    assert r.status_code == 200 and r.json()["status_label"] == "Đóng góp bổ sung"
    assert staff.post(f"/api/admin/partner-submissions/{j['id']}/create-opportunity").status_code == 409  # bổ sung không tạo phiếu mới


def test_overdue_flag(partner, staff):
    j = submit(partner)
    with new_session() as db:
        db.get(PartnerSubmission, j["id"]).sla_due_at = utcnow() - timedelta(hours=1)
        db.commit()
    q = staff.get("/api/admin/partner-submissions").json()
    assert q["overdue"] == 1 and q["items"][0]["overdue"] is True


# ------------------------------------------------------------------ tạo phiếu → xuất bản


def test_create_opportunity_and_publish_marks_published(partner, admin):
    j = submit(partner)
    url = f"/api/admin/partner-submissions/{j['id']}"
    assert admin.post(f"{url}/create-opportunity").status_code == 409  # chưa Đạt
    admin.post(f"{url}/decide", json={"decision": "verified"})
    r = admin.post(f"{url}/create-opportunity")
    assert r.status_code == 201, r.text
    oid = r.json()["opportunity_id"]
    assert admin.post(f"{url}/create-opportunity").status_code == 409  # 1 cơ hội 1 phiếu
    assert admin.post(f"{url}/decide", json={"decision": "rejected", "reason": "other", "partner_note": "x"}).status_code == 409

    with new_session() as db:
        o = db.get(Opportunity, oid)
        assert o.status == "draft" and o.source_submission_id == j["id"] and o.buyer_tax_key == "2300123456"
        assert o.source_partner_id == db.scalar(select(PartnerUser.id)) and o.source_type == "Nhà máy / FDI mới"
        assert "Quế Võ" in o.buyer_name and "SMT" in o.detail and o.contacts[0].phone == "0912000111"
        assert "Quế Võ" not in o.summary  # phần xem trước không lộ tên bên mua

    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    r = admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=1_250_000, region="Miền Bắc"))
    assert r.status_code == 200, r.text
    mine = partner.get(f"/api/partner/submissions/{j['id']}").json()
    assert mine["status"] == "published" and mine["published_at"]
    assert mine["events"][-1]["kind"] == "sub_published"
    with new_session() as db:  # phiếu sửa tiếp (vòng enrich) vẫn giữ đối tác nguồn
        assert db.get(Opportunity, oid).source_submission_id == j["id"]
    admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=1_250_000, enrich_round=2))
    with new_session() as db:
        assert db.get(Opportunity, oid).source_partner_id is not None


def test_member_never_sees_source_partner(partner, admin, client):
    """Thành viên mua phiếu không thấy đối tác nguồn (brief 8.1)."""
    from tests.test_member import ask, member_client, pay_membership
    from tests.conftest import register

    j = submit(partner)
    admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "verified"})
    oid = admin.post(f"/api/admin/partner-submissions/{j['id']}/create-opportunity").json()["opportunity_id"]
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=1_250_000, region="Miền Bắc"))

    register(client)
    m = member_client()
    pay_membership(m)
    ask(m, "Cần cung cấp thùng carton 5 lớp cho nhà máy điện tử ở Bắc Ninh, line SMT mới")
    r = m.get(f"/api/member/opportunities/{oid}")
    assert r.status_code == 200, r.text  # cơ hội đã được so khớp với doanh nghiệp
    for leak in ("source_partner", "source_submission", "buyer_tax_key", "DT-", "GT-"):
        assert leak not in r.text
    assert m.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    for path in ("/api/member/purchases", f"/api/member/opportunities/{oid}"):
        blob = m.get(path).text
        assert "source_partner" not in blob and "GT-" not in blob


def test_admin_partner_detail_has_submission_stats(partner, staff):
    submit(partner)
    pid = partner.get("/api/partner/auth/me").json()["id"]
    d = staff.get(f"/api/admin/partners/{pid}").json()
    assert d["submissions"]["total"] == 1 and d["submissions"]["by_status"] == {"submitted": 1}
