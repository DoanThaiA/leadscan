"""Thu thập cơ hội từ Gmail: webhook ký HMAC → lọc sơ bộ → AI (giả lập) → phiếu nháp; trang quản trị duyệt thư."""

import base64
import io
import json
import time
import zipfile
from datetime import timedelta
from email.message import EmailMessage

import pytest
from sqlalchemy import select

from app.ai import Reply
from app.config import get_settings
from app.db import new_session, utcnow
from app.models import Opportunity
from app.models_inbound import InboundEmail
from app.routes.gmail_webhook import signature
from app.services import gmail_files, gmail_ingest

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


# ------------------------------------------------------------------ thư chuyển tiếp + tệp đính kèm

FWD_BODY = """Chị xem giúp em cơ hội này nhé.

---------- Forwarded message ---------
From: Anh Nguyen <anh.nguyen@lidl.sg>
Date: Tue, Nov 19, 2026 at 9:15 AM
Subject: New business partners for carry bags
To: <sales@k-packings.vn>

""" + LIDL_BODY


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def make_docx(paragraphs: list[str], table: list[list[str]]) -> bytes:
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    p = "".join(f"<w:p><w:r><w:t>{x}</w:t></w:r></w:p>" for x in paragraphs)
    rows = "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in r) + "</w:tr>" for r in table)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document {w}><w:body>{p}<w:tbl>{rows}</w:tbl></w:body></w:document>")
    return buf.getvalue()


def make_xlsx(rows: list[list]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    """PDF 1 trang có lớp chữ (Helvetica, ASCII)."""
    stream = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % x for x in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def make_eml(body: str, attach: tuple[str, bytes, str] | None = None) -> bytes:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = "Tran Binh <binh@hopgiay.vn>", "sales@k-packings.vn", "Hoi gia thung carton"
    m.set_content(body)
    if attach:
        maintype, subtype = attach[2].split("/")
        m.add_attachment(attach[1], maintype=maintype, subtype=subtype, filename=attach[0])
    return bytes(m)


def test_forwarded_email_reads_original(client, ai):
    """Thư forward: trước đây bị cắt mất phần thư gốc → "quá ngắn". Giờ AI đọc cả thư gốc."""
    assert post(client, mail(subject="Fwd: New business partners for carry bags", body=FWD_BODY)).status_code == 201
    e = email_row()
    assert e.status == "drafted", (e.status, e.reason)
    prompt = ai["calls"][0]
    assert "CHUYỂN TIẾP" in prompt and "BSCI or SA8000" in prompt and "anh.nguyen@lidl.sg" in prompt


@pytest.mark.parametrize("subject, body", [
    ("Fwd: hỏi hàng", FWD_BODY),  # Gmail
    ("FW: hỏi hàng", "Nhờ anh xử lý.\n\n________________________________\nFrom: Anh Nguyen <anh.nguyen@lidl.sg>\nSent: Tuesday\n\n" + LIDL_BODY),  # Outlook
    ("hỏi hàng", "---------- Thư được chuyển tiếp ----------\nTừ: Anh Nguyen <anh.nguyen@lidl.sg>\n\n" + LIDL_BODY),
])
def test_forward_detection(subject, body):
    assert gmail_ingest.is_forward(subject, body)
    assert gmail_ingest.forwarded_from(body) == ("Anh Nguyen", "anh.nguyen@lidl.sg")
    e = InboundEmail(subject=subject, body_text=body)
    assert "BSCI or SA8000" in gmail_ingest.main_text(e)


def test_reply_still_strips_quote():
    e = InboundEmail(subject="Re: hỏi hàng", body_text="Ok anh.\n\nOn Mon, 18 Nov 2026 at 10:00 Anh wrote:\n> " + "x" * 500)
    assert not gmail_ingest.is_forward(e.subject, e.body_text) and gmail_ingest.main_text(e) == "Ok anh."


def test_forward_admin_draft_uses_original_sender(admin, hook):
    post(admin, mail(subject="Fwd: New business partners for carry bags", body=FWD_BODY, **{"from": "Nhan vien <nv@leadscan.net>"}))
    e = email_row()
    assert e.status == "review"
    r = admin.post(f"/api/admin/inbound-emails/{e.id}/draft")
    with new_session() as db:
        o = db.get(Opportunity, r.json()["opportunity"]["id"])
        assert o.title == "New business partners for carry bags"
        assert [(c.full_name, c.email) for c in o.contacts] == [("Anh Nguyen", "anh.nguyen@lidl.sg")]
        assert "BSCI or SA8000" in o.detail
    assert admin.get(f"/api/admin/inbound-emails/{e.id}").json()["is_forward"] is True


def test_attachments_read_and_sent_to_ai(client, ai):
    docx = make_docx(["Yeu cau bao gia thung carton 5 lop"], [["Quy cach", "So luong"], ["60x40x40 cm", "20.000 thung"]])
    xlsx = make_xlsx([["San pham", "So luong"], ["Hop giay kraft", 5000]])
    pdf = make_pdf("RFQ: tui giay kraft, han chot 15/12/2026")
    eml = make_eml("Ben em can mua 3.000 tem nhan decal.", ("specs.txt", "Kich thuoc tem 5x3 cm".encode(), "text/plain"))
    files = [
        {"name": "RFQ.docx", "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "size": len(docx), "data": b64(docx)},
        {"name": "list.xlsx", "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "size": len(xlsx), "data": b64(xlsx)},
        {"name": "rfq.pdf", "type": "application/pdf", "size": len(pdf), "data": b64(pdf)},
        {"name": "Fwd hoi gia.eml", "type": "message/rfc822", "size": len(eml), "data": b64(eml)},
        {"name": "anh.jpg", "type": "image/jpeg", "size": 1000},
        {"name": "catalog.pdf", "type": "application/pdf", "size": 50_000_000, "skipped": "too_large"},
        {"name": "old.doc", "type": "application/msword", "size": 100},
    ]
    assert post(client, mail(body="Anh xem file dinh kem giup em.", attachments=files)).status_code == 201
    e = email_row()
    assert e.status == "drafted", (e.status, e.reason)  # thân thư ngắn nhưng tệp có nội dung → không bị bỏ qua
    assert e.attachment_names == [f["name"] for f in files]
    got = {f["name"]: f for f in e.attachments}
    assert "60x40x40 cm | 20.000 thung" in got["RFQ.docx"]["text"]
    assert "Hop giay kraft | 5000" in got["list.xlsx"]["text"]
    assert "han chot 15/12/2026" in got["rfq.pdf"]["text"]
    assert "3.000 tem nhan" in got["Fwd hoi gia.eml"]["text"] and "binh@hopgiay.vn" in got["Fwd hoi gia.eml"]["text"]
    assert "Kich thuoc tem 5x3 cm" in got["Fwd hoi gia.eml"]["text"]  # tệp bên trong thư đính kèm
    assert "Ảnh" in got["anh.jpg"]["note"] and "quá lớn" in got["catalog.pdf"]["note"] and "Định dạng cũ" in got["old.doc"]["note"]
    prompt = ai["calls"][0]
    assert '<tep ten="RFQ.docx">' in prompt and "20.000 thung" in prompt and "Hop giay kraft" in prompt and "3.000 tem nhan" in prompt
    assert '<tep ten="anh.jpg">(Ảnh' in prompt
    with new_session() as db:
        assert "RFQ.docx" in db.get(Opportunity, e.opportunity_id).detail


def test_attachment_errors_do_not_break_email(client, hook):
    files = [
        {"name": "hong.pdf", "type": "application/pdf", "data": b64(b"khong phai pdf")},
        {"name": "hong.docx", "type": "", "data": b64(b"PK khong phai zip")},
        {"name": "rac.txt", "type": "text/plain", "data": "!!!khong-phai-base64"},
    ]
    assert post(client, mail(attachments=files)).status_code == 201
    got = {f["name"]: f for f in email_row().attachments}
    assert got["hong.pdf"]["note"] and got["hong.docx"]["note"] and not got["hong.pdf"]["text"]


def test_zip_bomb_rejected(monkeypatch):
    monkeypatch.setattr(gmail_files, "MAX_UNZIPPED", 1000)
    item = gmail_files.extract_one("a.docx", "", make_docx(["x" * 5000], []))
    assert item["text"] == "" and "quá lớn" in item["note"]


def test_purge_clears_attachment_text(client, ai):
    ai["result"] = {**LIDL_AI, "is_opportunity": False}
    post(client, mail(attachments=[{"name": "a.txt", "type": "text/plain", "data": b64("bi mat".encode())}]))
    assert email_row().attachments[0]["text"] == "bi mat"
    with new_session() as db:
        e = db.get(InboundEmail, email_row().id)
        e.processed_at = utcnow() - timedelta(days=8)
        db.commit()
        gmail_ingest.purge_old(db)
    assert email_row().attachments == []
