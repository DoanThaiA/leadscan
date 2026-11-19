"""Thu thập cơ hội từ Gmail: webhook ký HMAC → lọc sơ bộ → AI (giả lập) → phiếu nháp; trang quản trị duyệt thư."""

import json
import time
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.ai import Reply
from app.config import get_settings
from app.db import new_session, utcnow
from app.models import Opportunity
from app.models_inbound import InboundEmail
from app.routes.gmail_webhook import signature
from app.services import gmail_ingest

URL = "/api/webhooks/gmail"
SECRET = "khoa-gmail-thu-nghiem-0123456789"

LIDL_BODY = """Dear K-Packings,

This is Anh from Sourcing Department of Lidl & Kaufland Asia Pte. Limited.

Lidl and Kaufland are a German global discount supermarket chains operating over 14,000 stores across Europe and the
United States selling food and non food products. We are looking for new business partners for carry bags, shopping bags
with required compliance audit of either BSCI or SA8000 or Better Work.

Please kindly provide the following information:
- Your latest product catalogue;
- Details on your current factories;
- Details on any experience working with German or other European clients.

Best regards,
Anh Nguyen (Nova)
Lidl & Kaufland (Vietnam) Services Co. Limited
5th Floor, CJ Building, 2Bis-4-6 Le Thanh Ton Street, Sai Gon Ward, Ho Chi Minh City, Vietnam
Web: https://lidl.asia/
Email: anh.nguyen@lidl.sg
"""

LIDL_AI = {
    "is_opportunity": True,
    "confidence": 0.9,
    "reason": "Bộ phận Sourcing tìm nhà cung cấp mới cho túi mua sắm, yêu cầu audit tuân thủ.",
    "industry": "Bao bì & in ấn",
    "title": "Chuỗi siêu thị châu Âu tìm nhà cung cấp túi mua sắm (yêu cầu BSCI / SA8000 / Better Work)",
    "summary": "Chuỗi siêu thị giảm giá hơn 14.000 cửa hàng tại châu Âu và Mỹ tìm đối tác sản xuất túi xách, túi mua sắm.",
    "province": "TP. Hồ Chí Minh",
    "region": "Quốc tế",
    "scale": "Chuỗi hơn 14.000 cửa hàng tại châu Âu và Mỹ",
    "estimated_value": None,
    "deadline": None,
    "buyer_name": "Lidl & Kaufland (Vietnam) Services Co. Limited",
    "buyer_tax_id": None,
    "buyer_website": "https://lidl.asia/",
    "buyer_address": "Tầng 5, CJ Building, 2Bis-4-6 Lê Thánh Tôn, phường Sài Gòn, TP. Hồ Chí Minh",
    "detail": "- Sản phẩm: carry bags, shopping bags\n- Chứng nhận: BSCI hoặc SA8000 hoặc Better Work",
    "contacts": [{"full_name": "Anh Nguyen (Nova)", "title": "CM Sourcing DIY & Home SEA", "email": "Anh.Nguyen@lidl.sg", "phone": None}],
}


def mail(**over) -> dict:
    d = {
        "id": "18c2f0a9b1d2e3f4",
        "thread_id": "18c2f0a9b1d2e3f4",
        "from": "Anh Nguyen <anh.nguyen@lidl.sg>",
        "to": "sales@k-packings.vn",
        "subject": "New business partners for carry bags",
        "date": "2026-11-19T02:15:00.000Z",
        "body": LIDL_BODY,
        "attachments": ["Lidl_supplier_form.pdf"],
    }
    d.update(over)
    return d


def post(client, data, ts: int | None = None, secret: str = SECRET, sig: str | None = None):
    body = json.dumps(data).encode()
    ts_s = str(ts if ts is not None else int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-LeadScan-Timestamp": ts_s,
        "X-LeadScan-Signature": sig if sig is not None else signature(secret, ts_s, body),
    }
    return client.post(URL, content=body, headers=headers)


@pytest.fixture
def hook(monkeypatch):
    monkeypatch.setenv("LEADSCAN_GMAIL_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()


@pytest.fixture
def ai(monkeypatch, hook):
    """Bật AI, thay call_model bằng kết quả cố định (đổi được qua ai['result'] / ai['error'])."""
    monkeypatch.setenv("LEADSCAN_GMAIL_AI_ENABLED", "true")
    get_settings.cache_clear()
    state = {"result": LIDL_AI, "error": None, "calls": []}

    def fake(text, cfg):
        state["calls"].append(text)
        if state["error"]:
            raise state["error"]
        return Reply("", "deepseek", "deepseek-flash", 1200, 300, data=dict(state["result"]))

    monkeypatch.setattr(gmail_ingest, "call_model", fake)
    return state


def email_row(gid="18c2f0a9b1d2e3f4") -> InboundEmail:
    with new_session() as db:
        return db.scalar(select(InboundEmail).where(InboundEmail.gmail_message_id == gid))


# ------------------------------------------------------------------ webhook


def test_disabled_without_secret(client):
    assert post(client, mail()).status_code == 404


def test_signature_required(client, hook):
    assert post(client, mail(), sig="").status_code == 401
    assert post(client, mail(), secret="khoa-sai").status_code == 401
    assert post(client, mail(), ts=int(time.time()) - 3600).status_code == 401  # gói cũ gửi lại
    with new_session() as db:
        assert db.scalar(select(InboundEmail.id)) is None


def test_brute_force_blocked(client, hook):
    for _ in range(20):
        post(client, mail(), secret="sai")
    assert post(client, mail()).status_code == 429


def test_receive_and_duplicate(client, hook):
    r = post(client, mail())
    assert r.status_code == 201, r.text
    r2 = post(client, mail())
    assert r2.status_code == 200 and r2.json()["duplicate"] and r2.json()["id"] == r.json()["id"]
    e = email_row()
    assert e.from_email == "anh.nguyen@lidl.sg" and e.from_name == "Anh Nguyen"
    assert e.received_at.hour == 2 and e.attachment_names == ["Lidl_supplier_form.pdf"]


def test_missing_fields_422(client, hook):
    r = post(client, mail(id="", **{"from": "khong-phai-email"}))
    assert r.status_code == 422 and set(r.json()["fields"]) == {"id", "from"}


def test_ai_disabled_goes_to_review(client, hook):
    post(client, mail())
    e = email_row()
    assert e.status == "review" and "AI đang tắt" in e.reason


# ------------------------------------------------------------------ AI → phiếu nháp


def test_lidl_email_becomes_draft(client, ai):
    assert post(client, mail()).status_code == 201
    e = email_row()
    assert e.status == "drafted", (e.status, e.reason, e.error)
    assert e.ai_input_tokens == 1200 and e.ai_cost_usd > 0
    assert "<email>" in ai["calls"][0] and "Lidl" in ai["calls"][0]
    with new_session() as db:
        o = db.get(Opportunity, e.opportunity_id)
        assert o.status == "draft" and o.code.startswith("CH-")
        assert o.industry == "Bao bì & in ấn" and o.region == "Quốc tế" and o.source_type == "Email hỏi hàng"
        assert o.buyer_name.startswith("Lidl & Kaufland")
        assert "Lidl" not in o.title  # phần xem trước công khai không lộ tên bên mua
        assert "Website: https://lidl.asia/" in o.detail and "Lidl_supplier_form.pdf" in o.detail and "Nguồn: email" in o.detail
        assert [(c.full_name, c.email) for c in o.contacts] == [("Anh Nguyen (Nova)", "anh.nguyen@lidl.sg")]


@pytest.mark.parametrize("over, status, text", [
    ({"is_opportunity": False, "reason": "Thư quảng cáo."}, "rejected", "Thư quảng cáo."),
    ({"industry": "Logistics & vận tải"}, "rejected", "ngoài lĩnh vực"),
    ({"confidence": 0.4}, "review", "chưa chắc chắn"),
    ({"industry": "Ngành bịa"}, "rejected", "Khác"),  # ngành ngoài danh sách → "Khác"
])
def test_ai_decisions(client, ai, over, status, text):
    ai["result"] = {**LIDL_AI, **over}
    post(client, mail())
    e = email_row()
    assert e.status == status and text in e.reason and e.opportunity_id is None


def test_ai_errors(client, ai):
    ai["error"] = gmail_ingest.AiError("tạm thời", retryable=True)
    post(client, mail())
    assert email_row().status == "new"  # lượt quét sau thử lại
    ai["error"] = gmail_ingest.AiError("JSON sai")
    with new_session() as db:
        assert gmail_ingest.process(db, email_row().id) == "error"


def test_budget_exhausted_waits(client, ai, monkeypatch):
    monkeypatch.setenv("LEADSCAN_GMAIL_AI_BUDGET_USD", "0")
    get_settings.cache_clear()
    post(client, mail())
    e = email_row()
    assert e.status == "new" and "ngân sách" in e.error and not ai["calls"]


@pytest.mark.parametrize("over, text", [
    ({"from": "no-reply@shopee.vn"}, "tự động"),
    ({"body": "Cảm ơn anh, em đã nhận được."}, "quá ngắn"),
    ({"body": "Ok anh.\n\nOn Mon, 18 Nov 2026 at 10:00 Anh wrote:\n> " + "x" * 500}, "quá ngắn"),
])
def test_prefilter_skips_without_ai(client, ai, over, text):
    post(client, mail(**over))
    e = email_row()
    assert e.status == "skipped" and text in e.reason and not ai["calls"]


def test_same_thread_merged(client, ai):
    post(client, mail())
    first = email_row()
    post(client, mail(id="18c2f0a9b1d2ffff", body=LIDL_BODY + "\nPS: deadline end of December."))
    second = email_row("18c2f0a9b1d2ffff")
    assert second.status == "merged" and second.opportunity_id == first.opportunity_id
    assert len(ai["calls"]) == 1
    with new_session() as db:
        assert db.scalar(select(Opportunity.id).where(Opportunity.id != first.opportunity_id)) is None


def test_clean_ai_sanitizes():
    a = gmail_ingest.clean_ai({**LIDL_AI, "confidence": 7, "region": "Sao Hoả", "deadline": "31/12/2026", "title": "x" * 500,
                               "contacts": [{"full_name": None, "title": None, "email": "khong-hop-le", "phone": None}]})
    assert a["confidence"] == 1.0 and a["region"] == "" and a["deadline"] is None and len(a["title"]) == 200 and a["contacts"] == []


def test_strip_quoted():
    text = "Chào anh,\nBên em cần 10.000 hộp.\n\nVào Th 2, 18 thg 11, 2026 lúc 10:00 Nguyễn A đã viết:\n> thư cũ\n> nữa"
    assert gmail_ingest.strip_quoted(text) == "Chào anh,\nBên em cần 10.000 hộp."


def test_purge_old_rejected(client, ai):
    ai["result"] = {**LIDL_AI, "is_opportunity": False}
    post(client, mail())
    with new_session() as db:
        e = db.get(InboundEmail, email_row().id)
        e.processed_at = utcnow() - timedelta(days=8)
        db.commit()
        assert gmail_ingest.purge_old(db) == 1
    e = email_row()
    assert e.body_text == "" and e.ai_json is None and e.purged_at and e.subject  # giữ tiêu đề + lý do


def test_sweep_processes_missed_and_stuck(client, hook):
    with new_session() as db:
        d, _ = gmail_ingest.normalize_payload(mail())
        e, _ = gmail_ingest.save_email(db, d)  # như khi Redis lỗi: thư nằm ở "new"
        e.created_at = utcnow() - timedelta(minutes=10)
        e2, _ = gmail_ingest.save_email(db, {**d, "gmail_message_id": "18c2f0a9b1d2aaaa", "thread_id": "khac"})
        e2.status, e2.processed_at, e2.created_at = "processing", utcnow() - timedelta(hours=1), utcnow() - timedelta(hours=1)
        db.commit()
    from app.worker import gmail_sweep_task

    assert gmail_sweep_task() == 2
    assert email_row().status == "review" and email_row("18c2f0a9b1d2aaaa").status == "review"


# ------------------------------------------------------------------ quản trị


def test_admin_requires_login(client):
    assert client.get("/api/admin/inbound-emails").status_code == 401


def test_admin_flow(admin, hook):
    post(admin, mail())  # AI tắt → cần xem lại
    eid = email_row().id
    m = admin.get("/api/admin/inbound-emails/meta").json()
    assert m["counts"] == {"review": 1} and m["industries"] == ["Bao bì & in ấn"] and m["webhook_enabled"]
    items = admin.get("/api/admin/inbound-emails?status=review").json()["items"]
    assert [i["id"] for i in items] == [eid]
    d = admin.get(f"/api/admin/inbound-emails/{eid}").json()
    assert "Lidl" in d["body_text"] and d["thread"] == []

    r = admin.post(f"/api/admin/inbound-emails/{eid}/draft")
    assert r.status_code == 200, r.text
    with new_session() as db:
        o = db.get(Opportunity, r.json()["opportunity"]["id"])
        assert o.status == "draft" and o.title == "New business partners for carry bags" and o.contacts[0].email == "anh.nguyen@lidl.sg"
    assert admin.post(f"/api/admin/inbound-emails/{eid}/draft").status_code == 409
    assert admin.post(f"/api/admin/inbound-emails/{eid}/reject", json={}).status_code == 409


def test_admin_reject_block_reprocess(admin, ai):
    ai["result"] = {**LIDL_AI, "confidence": 0.3}
    post(admin, mail())
    eid = email_row().id
    assert email_row().status == "review"
    ai["result"] = LIDL_AI
    assert admin.post(f"/api/admin/inbound-emails/{eid}/reprocess").status_code == 200
    assert email_row().status == "drafted"

    ai["result"] = {**LIDL_AI, "is_opportunity": False, "reason": "Chào bán sản phẩm."}
    post(admin, mail(id="spam00000001", thread_id="t2", **{"from": "Sale <sale@spam.vn>"}))
    assert email_row("spam00000001").status == "rejected"
    sid = email_row("spam00000001").id
    assert admin.post(f"/api/admin/inbound-emails/{sid}/block", json={"scope": "domain"}).status_code == 200
    assert email_row("spam00000001").status == "skipped"
    post(admin, mail(id="spam00000002", thread_id="t3", **{"from": "khac@spam.vn"}))
    assert email_row("spam00000002").status == "skipped" and "chặn" in email_row("spam00000002").reason
    assert admin.post(f"/api/admin/inbound-emails/{sid}/block", json={"scope": "domain"}).status_code == 200  # chặn lại không lỗi

    post(admin, mail(id="free00000001", thread_id="t4", **{"from": "a@gmail.com"}))
    fid = email_row("free00000001").id
    assert admin.post(f"/api/admin/inbound-emails/{fid}/block", json={"scope": "domain"}).status_code == 422
    blocks = admin.get("/api/admin/inbound-emails/blocks").json()["items"]
    assert [b["pattern"] for b in blocks] == ["@spam.vn"]
    assert admin.delete(f"/api/admin/inbound-emails/blocks/{blocks[0]['id']}").status_code == 200
