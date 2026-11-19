"""Gửi phiếu cơ hội cho khách qua email (trang phiếu admin) + giao diện HTML dùng chung cho mọi email."""

import pytest
from sqlalchemy import select

from app.db import new_session
from app.models import Contact, MemberUser, Purchase
from app.models_opp_mail import OpportunityEmail
from app.services import mail_layout, notify
from tests.conftest import register
from tests.test_member import make_opp


@pytest.fixture
def mails(monkeypatch):
    sent = []

    def fake(cfg, subject, body, to=None, reply_to="", attachments=None, html=None):
        if subject.startswith("[LeadScan] Cơ hội phù hợp"):  # bỏ email đăng ký / chào mừng
            sent.append({"to": to, "subject": subject, "text": body, "html": html, "reply_to": reply_to})
        return True

    monkeypatch.setattr(notify, "send_mail", fake)
    monkeypatch.setattr(notify, "mail_provider", lambda cfg: "resend")
    return sent


def members(client) -> list[int]:
    """2 doanh nghiệp thành viên; email người liên hệ KHÁC email đăng nhập. Trả id người liên hệ."""
    register(client)
    register(client, tax_code="0109876543", company_name="Công ty CP Bao Bì Sài Gòn")
    with new_session() as db:
        contacts = list(db.scalars(select(Contact).order_by(Contact.id)))
        contacts[0].email, contacts[0].full_name = "kinhdoanh@minhan.vn", "Nguyễn Văn A"
        contacts[1].email = "muahang@baobisaigon.vn"
        db.add(Contact(company_id=contacts[1].company_id, full_name="Không Email", email=""))  # không có email → không hiện
        db.commit()
        return [c.id for c in contacts]


LOGIN_EMAILS = {"a@minhan.vn", "lienhe0109876543@minhan.vn"}


def url(oid, path):
    return f"/api/admin/opportunities/{oid}/mail/{path}"


def test_requires_login(client):
    assert client.get(url(1, "recipients")).status_code == 401


def test_recipients_and_preview_hide_unlocked_info(admin):
    ids = members(admin)
    oid = make_opp(admin)
    r = admin.get(url(oid, "recipients") + "?scope=all").json()
    assert r["can_send"] and {i["id"] for i in r["items"]} == set(ids)
    assert {i["email"] for i in r["items"]} == {"kinhdoanh@minhan.vn", "muahang@baobisaigon.vn"}  # không phải email đăng nhập
    assert admin.get(url(oid, "recipients") + "?scope=all&q=Sài Gòn").json()["items"][0]["company"]["name"] == "Công ty CP Bao Bì Sài Gòn"

    p = admin.get(url(oid, "preview") + f"?contact_id={ids[0]}&note=Anh xem giúp em nhé <b>gấp</b>").json()
    html = p["html"]
    assert "Cần 200.000 hộp carton 5 lớp/tháng" in html and "CH-" in html and "điểm" in html
    assert f"/thanh-vien/co-hoi/{oid}" in html and "Xem cơ hội &amp; mua phiếu" in html
    assert "Anh xem giúp em nhé &lt;b&gt;gấp&lt;/b&gt;" in html  # lời nhắn được escape
    for secret in ("Công ty Điện tử ABC", "0912345678", "Trần Mua Hàng", "thanh toán 30 ngày"):  # phần chỉ mở khi mua
        assert secret not in html and secret not in p["text"]
    assert "1 đầu mối liên hệ" in html and p["to"] == "kinhdoanh@minhan.vn" and "Nguyễn Văn A" in html


def test_send_history_and_draft_blocked(admin, mails):
    ids = members(admin)
    draft = make_opp(admin, status="draft")
    assert admin.post(url(draft, "send"), json={"contact_ids": ids}).status_code == 409

    oid = make_opp(admin)
    r = admin.post(url(oid, "send"), json={"contact_ids": ids, "note": "Cơ hội mới cho anh chị"})
    assert r.status_code == 200 and r.json()["queued"] == 2
    assert sorted(m["to"] for m in mails) == ["kinhdoanh@minhan.vn", "muahang@baobisaigon.vn"]
    assert not LOGIN_EMAILS & {m["to"] for m in mails}
    m = mails[0]
    assert m["html"].startswith("<!doctype html>") and "Cơ hội mới cho anh chị" in m["html"] and "Cơ hội mới cho anh chị" in m["text"]
    assert m["subject"] == "[LeadScan] Cơ hội phù hợp: Cần 200.000 hộp carton 5 lớp/tháng"
    h = admin.get(url(oid, "history")).json()["items"]
    assert [x["status"] for x in h] == ["sent", "sent"] and h[0]["sent_by"] == "Quản Trị"
    rec = admin.get(url(oid, "recipients") + "?scope=all").json()["items"]
    assert all(x["last_email"]["status"] == "sent" for x in rec)


def test_skip_company_that_already_bought(admin, mails):
    ids = members(admin)
    oid = make_opp(admin)
    with new_session() as db:
        first = db.scalar(select(MemberUser).order_by(MemberUser.id))
        db.add(Purchase(company_id=first.company_id, opportunity_id=oid, member_user_id=first.id, price=1_250_000))
        db.commit()
    r = admin.post(url(oid, "send"), json={"contact_ids": ids}).json()
    assert r["queued"] == 1 and r["skipped"][0]["email"] == "kinhdoanh@minhan.vn"
    assert [m["to"] for m in mails] == ["muahang@baobisaigon.vn"]
    rec = {x["email"]: x["purchased"] for x in admin.get(url(oid, "recipients") + "?scope=all").json()["items"]}
    assert rec == {"kinhdoanh@minhan.vn": True, "muahang@baobisaigon.vn": False}


def test_mail_not_configured_then_retry(admin, monkeypatch):
    ids = members(admin)
    oid = make_opp(admin)
    admin.post(url(oid, "send"), json={"contact_ids": ids[:1]})
    with new_session() as db:
        e = db.scalar(select(OpportunityEmail))
        assert e.status == "failed" and "Chưa cấu hình" in e.error
    sent = []
    monkeypatch.setattr(notify, "send_mail", lambda *a, **k: sent.append(k["to"]) or True)
    monkeypatch.setattr(notify, "mail_provider", lambda cfg: "resend")
    assert admin.post(url(oid, f"history/{e.id}/retry")).status_code == 200
    assert sent == ["kinhdoanh@minhan.vn"] and admin.get(url(oid, "history")).json()["items"][0]["status"] == "sent"
    assert admin.post(url(oid, f"history/{e.id}/retry")).status_code == 409


def test_validation(admin):
    oid = make_opp(admin)
    assert admin.post(url(oid, "send"), json={"contact_ids": []}).status_code == 422
    assert admin.post(url(oid, "send"), json={"contact_ids": [999]}).status_code == 422
    assert admin.post(url(999, "send"), json={"contact_ids": [1]}).status_code == 404


def test_company_without_active_member_not_listed(admin, mails):
    ids = members(admin)
    oid = make_opp(admin)
    with new_session() as db:
        for u in db.scalars(select(MemberUser).where(MemberUser.company_id == db.get(Contact, ids[1]).company_id)):
            u.is_active = False
        db.commit()
    assert [i["id"] for i in admin.get(url(oid, "recipients") + "?scope=all").json()["items"]] == [ids[0]]
    assert admin.post(url(oid, "send"), json={"contact_ids": [ids[1]]}).status_code == 422


# ------------------------------------------------------------------ giao diện HTML chung


def test_text_to_html_layout():
    text = (
        "Chào Lan,\n\nLeadScan đã nhận thanh toán.\n\n"
        "Mã đơn            : DH-001\nSố tiền           : 5.000.000đ\n\n"
        "THÔNG TIN XUẤT HOÁ ĐƠN\n  • Đăng nhập: https://leadscan.net/thanh-vien/dang-nhap\n  1. Bước một <script>\n"
    )
    h = mail_layout.from_text("[LeadScan] Thử", text)
    assert "<table" in h and "DH-001" in h and "<ul" in h and "<h3" in h
    assert '<a href="https://leadscan.net/thanh-vien/dang-nhap"' in h
    assert "<script>" not in h and "&lt;script&gt;" in h
