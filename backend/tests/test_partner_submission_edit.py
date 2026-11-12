"""Đối tác sửa cơ hội đã gửi khi LeadScan chưa bắt đầu xác minh (PUT /api/partner/submissions/{id})."""

from tests.test_partner import otp_mail  # noqa: F401  (fixture)
from tests.test_partner_submissions import partner, sub_form, submit, verified_partner  # noqa: F401


def test_edit_while_submitted(partner, admin):  # noqa: F811
    j = submit(partner)
    assert j["editable"] is True and j["status"] == "submitted"
    body = sub_form(need="Nhà máy mới cần 30.000 thùng carton 5 lớp mỗi tháng, giao hàng tuần, ưu tiên NCC gần KCN Quế Võ, có chứng nhận FSC.",
                    scale="30.000 thùng/tháng", contact_name="", contact_title="", contact_phone="", contact_email="", contact_consent=False)
    body.pop("tax_lookup")  # MST không đổi, không tra lại → giữ kết quả tra cũ
    r = partner.put(f"/api/partner/submissions/{j['id']}", json=body)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["code"] == j["code"] and s["created_at"] == j["created_at"] and s["sla_due_at"] == j["sla_due_at"]
    assert s["scale"] == "30.000 thùng/tháng" and s["contact_name"] == "" and {"Nhu cầu", "Quy mô"} <= set(s["changed"])

    det = partner.get(f"/api/partner/submissions/{j['id']}").json()
    assert [e["kind"] for e in det["events"]] == ["sub_created", "sub_edited"] and "Quy mô" in det["events"][1]["content"]
    a = admin.get(f"/api/admin/partner-submissions/{j['id']}").json()
    assert a["tax_lookup"]["active"] is True  # giữ kết quả tra MST
    assert any(e["kind"] == "sub_edited" for e in a["events"])
    assert admin.get("/api/admin/partner-reports/events?kind=submission").json()["items"][0]["kind_label"] == "Sửa cơ hội"

    # lưu lại y nguyên → không ghi nhật ký
    assert partner.put(f"/api/partner/submissions/{j['id']}", json=body).json()["changed"] == []
    assert len(partner.get(f"/api/partner/submissions/{j['id']}").json()["events"]) == 2


def test_edit_validation_and_ownership(partner, otp_mail):  # noqa: F811
    j = submit(partner)
    r = partner.put(f"/api/partner/submissions/{j['id']}", json=sub_form(need="ngắn", commitment=False))
    assert r.status_code == 422 and {"need", "commitment"} <= set(r.json()["fields"])
    other = verified_partner(email="khac@gmail.com", phone="0977000111")
    assert other.put(f"/api/partner/submissions/{j['id']}", json=sub_form()).status_code == 404
    assert partner.put("/api/partner/submissions/999999", json=sub_form()).status_code == 404


def test_edit_cannot_duplicate_own_submission(partner):  # noqa: F811
    a = submit(partner)
    b = submit(partner, company_name="Công ty Nhựa Đồng Nai", tax_code="3600111222", province="Đồng Nai")
    r = partner.put(f"/api/partner/submissions/{b['id']}", json=sub_form())  # đổi thành đúng cơ hội a
    assert r.status_code == 409 and a["code"] in r.json()["detail"]


def test_locked_once_verifying(partner, staff):  # noqa: F811
    j = submit(partner)
    assert staff.post(f"/api/admin/partner-submissions/{j['id']}/assign", json={}).json()["status"] == "verifying"
    assert partner.get(f"/api/partner/submissions/{j['id']}").json()["editable"] is False
    r = partner.put(f"/api/partner/submissions/{j['id']}", json=sub_form(scale="1 thùng"))
    assert r.status_code == 409 and "bắt đầu xác minh" in r.json()["detail"]
    assert partner.get(f"/api/partner/submissions/{j['id']}").json()["scale"] == "20.000 thùng/tháng"
