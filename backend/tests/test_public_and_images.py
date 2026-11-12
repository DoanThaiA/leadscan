"""Cơ hội công khai (/co-hoi) + mở từ link chia sẻ để mua; ảnh đối tác gắn vào cơ hội gửi (R2 giả lập)."""

from datetime import timedelta
from urllib.parse import unquote

import pytest
from sqlalchemy import select

from app.db import new_session, utcnow
from app.models import OpportunityAttachment, PartnerAttachment, UserOpportunity
from tests.conftest import register
from tests.test_attachments import jpeg_with_exif, r2  # noqa: F401
from tests.test_member import make_opp, member_client, pay_membership
from tests.test_partner import new_client, otp_mail  # noqa: F401
from tests.test_partner_submissions import published_body, sub_form, submit, verified_partner


# ------------------------------------------------------------------ cơ hội công khai


def test_public_shows_preview_only(admin):
    oid = make_opp(admin)
    code = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]["code"]
    anon = new_client()
    d = anon.get(f"/api/public/opportunities/{code.lower()}").json()
    assert d["code"] == code and d["title"].startswith("Cần 200.000 hộp carton") and d["contact_count"] == 1
    assert d["price_from"] >= 1_250_000 and d["remaining"] == 2 and d["attachment_counts"] == {"images": 0, "files": 0}
    for secret in ("buyer_name", "detail", "contacts", "source_url", "source_partner_id", "source_submission_id"):
        assert secret not in d
    assert "Công ty Điện tử ABC" not in str(d) and "0912345678" not in str(d)
    assert d["is_new"] is True and d["related"] == [] and 0 < d["trust"] <= 100 and d["urgency"] == 50
    lst = anon.get("/api/public/opportunities?q=carton").json()
    assert lst["total"] == 1 and lst["items"][0]["code"] == code
    assert lst["stats"] == {"open": 1, "new_7d": 1, "industries": 1} and lst["chips"] == [["Bao bì & in ấn", 1]]
    other = make_opp(admin, title="Cần 50.000 túi giấy kraft in logo", buyer_name="Công ty XYZ")
    rel = anon.get(f"/api/public/opportunities/{code}").json()["related"]
    assert [r["id"] for r in rel] == [other] and "buyer_name" not in rel[0]


def test_public_hides_drafts(admin):
    oid = make_opp(admin, status="draft")
    code = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]["code"]
    assert new_client().get(f"/api/public/opportunities/{code}").status_code == 404
    assert new_client().get("/api/public/opportunities").json()["total"] == 0


def test_member_opens_shared_link_then_buys(admin, client):
    """Thành viên chưa có phiếu tìm cơ hội khớp → không thấy cơ hội; mở từ link chia sẻ → xem & mua được."""
    oid = make_opp(admin)
    register(client)
    m = member_client()
    assert m.get(f"/api/member/opportunities/{oid}").status_code == 404  # chưa so khớp
    assert new_client().post(f"/api/member/opportunities/{oid}/open-shared").status_code == 401  # chưa đăng nhập
    r = m.post(f"/api/member/opportunities/{oid}/open-shared")
    assert r.status_code == 200 and r.json()["id"] == oid
    o = m.get(f"/api/member/opportunities/{oid}").json()["opportunity"]
    assert o["saved"] is True and "liên kết chia sẻ" in o["reasons"][0] and "buyer_name" not in o
    pay_membership(m)
    assert m.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    # gọi lại không tạo trùng
    assert m.post(f"/api/member/opportunities/{oid}/open-shared").status_code == 200
    with new_session() as db:
        assert len(db.scalars(select(UserOpportunity).where(UserOpportunity.opportunity_id == oid)).all()) == 1


def test_shared_row_survives_rematch(admin, client):
    from app.services import matching

    oid = make_opp(admin)
    register(client)
    m = member_client()
    m.post(f"/api/member/opportunities/{oid}/open-shared")
    with new_session() as db:
        from app.models import Opportunity

        matching.match_opportunity(db, db.get(Opportunity, oid))  # so khớp lại: không phiếu tìm nào khớp
        db.commit()
    assert m.get(f"/api/member/opportunities/{oid}").status_code == 200  # vẫn giữ


def test_open_shared_rejects_closed(admin, client):
    oid = make_opp(admin, status="closed")
    register(client)
    assert member_client().post(f"/api/member/opportunities/{oid}/open-shared").status_code == 404


# ------------------------------------------------------------------ ảnh đối tác


@pytest.fixture
def partner(otp_mail):  # noqa: F811
    return verified_partner()


def upload(c, st, name="anh.jpg", data=None) -> int:
    data = data or jpeg_with_exif()
    r = c.post("/api/partner/attachments/init", json={"filename": name, "size": len(data)})
    assert r.status_code == 201, r.text
    key = unquote(r.json()["upload_url"].removeprefix("memory://put/").split("?")[0])
    st.put_bytes(key, data, r.json()["content_type"])
    done = c.post(f"/api/partner/attachments/{r.json()['id']}/complete")
    assert done.status_code == 200, done.text
    return r.json()["id"]


def test_images_need_storage(partner):
    assert partner.get("/api/partner/attachments/config").json()["enabled"] is False
    assert partner.post("/api/partner/attachments/init", json={"filename": "a.jpg", "size": 100}).status_code == 503


def test_partner_attaches_images(partner, admin, r2):  # noqa: F811
    assert partner.get("/api/partner/attachments/config").json()["enabled"] is True
    assert partner.post("/api/partner/attachments/init", json={"filename": "a.pdf", "size": 100}).status_code == 400  # chỉ ảnh
    a, b = upload(partner, r2), upload(partner, r2, "b.png")
    r = partner.post("/api/partner/submissions", json={**sub_form(), "attachment_ids": [b, a]})
    assert r.status_code == 201, r.text
    j = r.json()
    assert [i["id"] for i in j["images"]] == [b, a] and j["images"][0]["thumb_url"]
    with new_session() as db:
        row = db.get(PartnerAttachment, a)
        assert row.submission_id == j["id"] and row.width == 20 and row.height == 40  # xoay theo EXIF, bỏ EXIF
    # admin thấy ảnh
    assert len(admin.get(f"/api/admin/partner-submissions/{j['id']}").json()["images"]) == 2
    # đối tác khác không dùng được ảnh của mình
    other = verified_partner(email="o@gmail.com", phone="0933000444")
    r = other.post("/api/partner/submissions", json={**sub_form(company_name="Công ty Khác", tax_code="0377777777"), "attachment_ids": [a]})
    assert r.status_code == 201 and "chưa gắn được ảnh" in r.json()["warning"]

    # sửa cơ hội: bỏ 1 ảnh → xoá trên R2
    r = partner.put(f"/api/partner/submissions/{j['id']}", json={**sub_form(), "attachment_ids": [a]})
    assert r.status_code == 200, r.text
    assert [i["id"] for i in r.json()["images"]] == [a] and "Ảnh" in r.json()["changed"]
    with new_session() as db:
        assert db.get(PartnerAttachment, b) is None

    # Đạt → tạo phiếu: ảnh được chép sang phiếu (phần mở khoá sau khi mua)
    admin.post(f"/api/admin/partner-submissions/{j['id']}/decide", json={"decision": "verified"})
    oid = admin.post(f"/api/admin/partner-submissions/{j['id']}/create-opportunity").json()["opportunity_id"]
    with new_session() as db:
        imgs = db.scalars(select(OpportunityAttachment).where(OpportunityAttachment.opportunity_id == oid)).all()
        assert len(imgs) == 1 and imgs[0].status == "ready" and imgs[0].key.startswith("opportunities/") and "GT-" not in imgs[0].caption
        assert r2.head(imgs[0].key) is not None
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    admin.put(f"/api/admin/opportunities/{oid}", json=published_body(o, price=29000, region="Miền Bắc"))
    assert new_client().get(f"/api/public/opportunities/{o['code']}").json()["attachment_counts"]["images"] == 1


def test_orphan_partner_images_cleaned(partner, r2):  # noqa: F811
    from app.worker import cleanup_task

    a = upload(partner, r2)
    with new_session() as db:
        row = db.get(PartnerAttachment, a)
        row.created_at = utcnow() - timedelta(hours=25)
        key = row.key
        db.commit()
    cleanup_task.apply()
    with new_session() as db:
        assert db.get(PartnerAttachment, a) is None
    assert r2.head(key) is None
