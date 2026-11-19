"""Gửi phiếu cơ hội cho khách hàng qua email — admin chọn NGƯỜI LIÊN HỆ của doanh nghiệp thành viên ở trang phiếu.

Người nhận là email trong mục Người liên hệ của khách hàng (bảng contacts), không phải email đăng nhập tài khoản thành viên.

Email chỉ có PHẦN XEM TRƯỚC (giống người chưa mua thấy trong cổng thành viên): tiêu đề, tóm tắt, ngành, khu vực,
quy mô, giá trị, hạn chót, số lượt còn lại, giá phiếu theo điểm phù hợp RIÊNG của doanh nghiệp nhận.
Tên bên có nhu cầu, chi tiết, đầu mối, tài liệu: chỉ mở khi khách mua phiếu trong cổng thành viên.
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import utcnow
from sqlalchemy import select

from app.models import Company, MemberUser, Opportunity
from app.models_opp_mail import OpportunityEmail
from app.services import catalog, mail_layout
from app.services.mail_layout import BRAND, BRAND_SOFT, INK, LINE, MUTED, esc
from app.services.matching import price_of, urgency_of

log = logging.getLogger("leadscan.opp_mail")

MAX_RECIPIENTS = 100  # mỗi lần bấm gửi
MAX_NOTE = 1000


def is_member(db: Session, company_id: int) -> bool:
    """Doanh nghiệp còn ít nhất 1 tài khoản thành viên hoạt động (email dẫn về cổng thành viên)."""
    return bool(db.scalar(select(MemberUser.id).where(MemberUser.company_id == company_id, MemberUser.is_active).limit(1)))


def _pts(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " điểm"


def can_send(o: Opportunity) -> str:
    """Lý do không gửi được ("" = gửi được)."""
    if o.status != "published":
        return "Phiếu chưa mở bán — mở bán trước khi gửi cho khách."
    if o.sold_count >= o.max_buyers:
        return "Phiếu đã hết lượt mua."
    return ""


def _facts(o: Opportunity, today: date) -> list[tuple[str, str]]:
    rows = []
    if o.industry:
        rows.append(("Ngành", o.industry))
    where = " · ".join(x for x in (o.province, o.region) if x)
    if where:
        rows.append(("Khu vực", where))
    if o.scale:
        rows.append(("Quy mô", o.scale))
    if o.estimated_value:
        rows.append(("Giá trị ước tính", o.estimated_value))
    if o.deadline:
        left = (o.deadline - today).days
        rows.append(("Hạn chót", f"{o.deadline:%d/%m/%Y}" + (f" (còn {left} ngày)" if left >= 0 else " (đã qua)")))
    if o.source_type:
        rows.append(("Nguồn tin", o.source_type))
    remaining = max(0, o.max_buyers - o.sold_count)
    rows.append(("Lượt mua", "Độc quyền — chỉ 1 doanh nghiệp được mua" if o.max_buyers == 1 else f"Còn {remaining}/{o.max_buyers} lượt"))
    return rows


def render(db: Session, o: Opportunity, company: Company, name: str, note: str = "", cfg: Settings | None = None) -> tuple[str, str, str]:
    """(tiêu đề, bản chữ, bản HTML) của email gửi 1 cơ hội cho 1 người liên hệ của doanh nghiệp thành viên."""
    cfg = cfg or get_settings()
    today = date.today()
    name = (name or "").strip() or "Quý khách"
    um = catalog.user_match(db, company.id, o.id)
    score = um.score if um else 0
    price = price_of(o, score, urgency_of(o, today))
    reasons = [r for r in (um.reasons or []) if isinstance(r, str)][:3] if um else []
    link = f"{cfg.member_url.rstrip('/')}/co-hoi/{o.id}"
    facts = _facts(o, today)
    note = (note or "").strip()[:MAX_NOTE]
    n_contacts = len(o.contacts)
    unlock = ["Tên doanh nghiệp / tổ chức có nhu cầu", "Chi tiết nhu cầu và yêu cầu kỹ thuật"]
    if n_contacts:
        unlock.append(f"{n_contacts} đầu mối liên hệ (họ tên, chức vụ, điện thoại, email)")
    unlock.append("Tài liệu, hình ảnh kèm theo (nếu có)")

    title = o.title.strip()
    subject = f"[LeadScan] Cơ hội phù hợp: {title}"
    if len(subject) > 120:
        subject = subject[:119] + "…"

    # ---------- bản chữ
    text = [f"Chào {name},", "", f"LeadScan gửi {company.name} một cơ hội kinh doanh có thể phù hợp:", ""]
    if note:
        text += ["LỜI NHẮN TỪ LEADSCAN", note, ""]
    text += [f"{title} ({o.code})", ""]
    if o.summary:
        text += [o.summary.strip(), ""]
    text += [f"{k:<18}: {v}" for k, v in facts]
    text.append(f"{'Giá phiếu của bạn':<18}: {_pts(price)}")
    if um:
        text.append(f"{'Độ phù hợp':<18}: {score}/100")
    text += [""]
    if reasons:
        text += ["VÌ SAO PHÙ HỢP", *[f"  • {r}" for r in reasons], ""]
    text += ["MỞ KHOÁ KHI MUA PHIẾU", *[f"  • {x}" for x in unlock], "", f"Xem cơ hội và mua phiếu: {link}", "",
             "Trân trọng,", "Đội ngũ LeadScan"]

    # ---------- bản HTML
    badge = (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:999px;background:{BRAND_SOFT};color:{BRAND};'
        f'font-size:12px;font-weight:700;font-family:Consolas,Menlo,monospace">{esc(o.code)}</span>'
    )
    fit = (
        f'<span style="display:inline-block;margin-left:6px;padding:3px 10px;border-radius:999px;background:#e6f6ec;color:#157f3b;'
        f'font-size:12px;font-weight:700">Phù hợp {score}/100</span>' if um else ""
    )
    card = [
        f'<div style="border:1px solid {LINE};border-radius:10px;padding:18px 18px 4px;margin:0 0 18px">',
        f'<div style="margin-bottom:10px">{badge}{fit}</div>',
        f'<h2 style="margin:0 0 8px;font-size:19px;line-height:1.35;color:{INK}">{esc(title)}</h2>',
    ]
    if o.summary:
        card.append(f'<p style="margin:0 0 14px;color:{MUTED};line-height:1.6">{esc(o.summary.strip())}</p>')
    card.append(mail_layout.info_table(facts))
    card.append(
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 14px;background:{BRAND_SOFT};border-radius:8px">'
        f'<tr><td style="padding:12px 14px;font-size:13px;color:{MUTED}">Giá phiếu dành cho {esc(company.name)}</td>'
        f'<td align="right" style="padding:12px 14px;font-size:18px;font-weight:800;color:{BRAND};white-space:nowrap">{esc(_pts(price))}</td></tr></table>'
    )
    card.append("</div>")

    inner = [
        f'<p style="margin:0 0 12px">Chào <b>{esc(name)}</b>,</p>',
        f'<p style="margin:0 0 18px;line-height:1.6">LeadScan gửi <b>{esc(company.name)}</b> một cơ hội kinh doanh có thể phù hợp với doanh nghiệp của bạn.</p>',
    ]
    if note:
        inner.append(mail_layout.note_box("Lời nhắn từ LeadScan", note))
    inner += card
    if reasons:
        lis = "".join(f'<li style="margin:0 0 5px">{esc(r)}</li>' for r in reasons)
        inner.append(f'<h3 style="margin:0 0 8px;font-size:14px;color:{BRAND}">Vì sao phù hợp với bạn</h3><ul style="margin:0 0 16px;padding-left:20px;line-height:1.55">{lis}</ul>')
    lis = "".join(f'<li style="margin:0 0 5px">{esc(x)}</li>' for x in unlock)
    inner.append(f'<h3 style="margin:0 0 8px;font-size:14px;color:{BRAND}">Mở khoá khi mua phiếu</h3><ul style="margin:0 0 18px;padding-left:20px;line-height:1.55">{lis}</ul>')
    inner.append(mail_layout.button("Xem cơ hội & mua phiếu", link))
    inner.append(f'<p style="margin:0 0 14px;font-size:13px;color:{MUTED}">Nút không bấm được? Mở link: {mail_layout.linkify(esc(link))}</p>')
    inner.append('<p style="margin:0 0 6px;line-height:1.6">Trân trọng,<br><b>Đội ngũ LeadScan</b></p>')
    footer = (
        f"Bạn nhận email này vì {esc(company.name)} là thành viên LeadScan. "
        "Không muốn nhận gợi ý cơ hội qua email? Trả lời email này để báo cho chúng tôi."
    )
    html = mail_layout.wrap(subject, "\n".join(inner), preheader=(o.summary or title)[:140], footer_note=footer, cfg=cfg)
    return subject, "\n".join(text) + "\n", html


def send_one(db: Session, email_id: int) -> str:
    """Gửi 1 dòng nhật ký đang "queued". Trả trạng thái mới."""
    from app.services import notify

    cfg = get_settings()
    e = db.get(OpportunityEmail, email_id)
    if not e or e.status != "queued":
        return e.status if e else ""
    o = db.get(Opportunity, e.opportunity_id)
    company = db.get(Company, e.company_id) if e.company_id else None
    reason = (
        "Doanh nghiệp không còn tài khoản thành viên hoạt động." if not company or not is_member(db, company.id)
        else (can_send(o) if o else "Phiếu đã bị xoá.")
    )
    if reason:
        e.status, e.error = "failed", reason
        db.commit()
        return "failed"
    subject, text, html = render(db, o, company, e.recipient_name, e.note, cfg)
    ok = notify.send_mail(cfg, subject, text, to=e.email, reply_to=cfg.notify_email or "", html=html)
    if ok:
        e.status, e.error, e.sent_at = "sent", "", utcnow()
    else:
        e.status = "failed"
        e.error = "Chưa cấu hình gửi email (Resend/SMTP)." if not notify.mail_provider(cfg) else "Máy chủ email từ chối hoặc lỗi kết nối — xem log."
    db.commit()
    log.info("Gửi cơ hội %s tới %s: %s", o.code, e.email, e.status)
    return e.status
