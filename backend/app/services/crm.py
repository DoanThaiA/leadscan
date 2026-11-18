"""CRM Lite cho hạng Vàng: đồng bộ lead từ phiếu đã mua, che dữ liệu cá nhân trong ghi chú, dựng dữ liệu trả về."""

import re
from datetime import date

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import utcnow
from app.models import Company, MemberUser, Purchase
from app.models_crm import CRM_STAGES, CrmEvent, CrmLead, CrmNote, CrmTask
from app.services import catalog, tiers


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


# ------------------------------------------------------------------ ai được dùng CRM


def access(c: Company, cfg: Settings | None = None) -> tuple[bool, str]:
    """(được dùng, lý do nếu không): hạng Vàng, và nằm trong danh sách chạy thử nếu đang chạy thử."""
    cfg = cfg or get_settings()
    if tiers.tier_key(c, cfg) != "gold":
        return False, "CRM dành cho thành viên hạng Vàng."
    pilot = {x.strip().upper() for x in cfg.crm_pilot_codes.split(",") if x.strip()}
    if pilot and c.code.upper() not in pilot:
        return False, "CRM đang chạy thử với một số doanh nghiệp hạng Vàng và sẽ sớm mở cho bạn."
    return True, ""


# ------------------------------------------------------------------ đồng bộ lead


def sync_leads(db: Session, company_id: int) -> int:
    """Mỗi phiếu đã mua của doanh nghiệp có đúng 1 lead (giai đoạn "Mới", giao cho người đã mua). Gọi lại bao nhiêu lần
    cũng không tạo trùng (khoá duy nhất purchase_id). Trả về số lead mới tạo."""
    missing = db.execute(
        select(Purchase.id, Purchase.opportunity_id, Purchase.member_user_id, Purchase.created_at)
        .outerjoin(CrmLead, CrmLead.purchase_id == Purchase.id)
        .where(Purchase.company_id == company_id, CrmLead.id.is_(None))
        .order_by(Purchase.id)
    ).all()
    if not missing:
        return 0
    try:
        # ghi hàng loạt (lần mở CRM đầu tiên có thể là hàng nghìn phiếu) — trùng khoá nổ ngay ở câu INSERT này
        db.execute(insert(CrmLead), [
            {"company_id": company_id, "purchase_id": pid, "opportunity_id": oid, "owner_id": uid, "stage": "new", "created_at": at, "updated_at": at}
            for pid, oid, uid, at in missing
        ])
        made = db.execute(select(CrmLead.id, CrmLead.owner_id, CrmLead.created_at).where(CrmLead.purchase_id.in_([m[0] for m in missing]))).all()
        db.execute(insert(CrmEvent), [
            {"company_id": company_id, "lead_id": lid, "actor_id": uid, "kind": "created", "content": "Phiếu đã mua được đưa vào CRM", "created_at": at}
            for lid, uid, at in made
        ])
        db.commit()
    except IntegrityError:  # 2 yêu cầu mở CRM cùng lúc (2 tab, React dev gọi 2 lần) → bên kia đã tạo
        db.rollback()
        return 0
    return len(missing)


# ------------------------------------------------------------------ che dữ liệu cá nhân trong ghi chú

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w])(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?![\w])")


def _norm_phone(s: str) -> str:
    d = re.sub(r"\D", "", s)
    return "0" + d[2:] if d.startswith("84") else d


def known_contacts(snap: dict) -> tuple[set[str], set[str]]:
    """SĐT / email đầu mối có trong phiếu đã mua — được phép ghi lại trong ghi chú."""
    phones, emails = set(), set()
    for c in snap.get("contacts") or []:
        if c.get("phone"):
            phones.add(_norm_phone(c["phone"]))
        if c.get("email"):
            emails.add(c["email"].strip().lower())
    return phones, emails


def mask_pii(text: str, snap: dict) -> tuple[str, int]:
    """Che SĐT và email KHÔNG thuộc đầu mối của phiếu (CRM không thu thập thêm dữ liệu cá nhân). Trả (nội dung, số chỗ đã che)."""
    phones, emails = known_contacts(snap)
    n = 0

    def email(m):
        nonlocal n
        if m.group(0).lower() in emails:
            return m.group(0)
        n += 1
        return "[đã ẩn email]"

    def phone(m):
        nonlocal n
        if _norm_phone(m.group(0)) in phones:
            return m.group(0)
        n += 1
        return "[đã ẩn SĐT]"

    text = _EMAIL.sub(email, text)
    text = _PHONE.sub(phone, text)
    return text, n


# ------------------------------------------------------------------ dữ liệu trả về


def snapshot(lead: CrmLead) -> dict:
    """Bản phiếu khách đã mua (đúng nội dung + đầu mối lúc mua); phiếu mua trước khi có bản lưu → bản hiện tại."""
    p = lead.purchase
    return p.snapshot or catalog.full(p.opportunity)


def _user(u: MemberUser | None) -> dict | None:
    return {"id": u.id, "full_name": u.full_name} if u else None


def task_stats(db: Session, company_id: int) -> dict[int, tuple[int, date | None]]:
    """{lead_id: (số việc chưa xong, hạn gần nhất)}"""
    rows = db.execute(
        select(CrmTask.lead_id, func.count(CrmTask.id), func.min(CrmTask.due_date))
        .where(CrmTask.company_id == company_id, CrmTask.done_at.is_(None))
        .group_by(CrmTask.lead_id)
    ).all()
    return {lid: (n, due) for lid, n, due in rows}


def lead_out(lead: CrmLead, stats: tuple[int, date | None] | None = None) -> dict:
    s = snapshot(lead)
    open_tasks, next_due = stats or (0, None)
    return {
        "id": lead.id,
        "stage": lead.stage,
        "stage_label": CRM_STAGES.get(lead.stage, lead.stage),
        "owner": _user(lead.owner),
        "opportunity_id": lead.opportunity_id,
        "code": s.get("code", ""),
        "title": s.get("title", ""),
        "industry": s.get("industry", ""),
        "province": s.get("province", ""),
        "buyer_name": s.get("buyer_name", ""),
        "score": s.get("score", 0),
        "price": lead.purchase.price,
        "refunded": bool(lead.purchase.refunded_at),
        "open_tasks": open_tasks,
        "next_due": next_due.isoformat() if next_due else None,
        "overdue": bool(next_due and next_due < date.today()),
        "created_at": _iso(lead.created_at),
        "updated_at": _iso(lead.updated_at),
    }


def note_out(n: CrmNote) -> dict:
    return {"id": n.id, "content": n.content, "author": _user(n.author), "created_at": _iso(n.created_at)}


def task_out(t: CrmTask, with_lead: bool = False) -> dict:
    out = {
        "id": t.id,
        "lead_id": t.lead_id,
        "title": t.title,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "overdue": bool(t.due_date and not t.done_at and t.due_date < date.today()),
        "assignee": _user(t.assignee),
        "done": bool(t.done_at),
        "done_at": _iso(t.done_at),
        "created_at": _iso(t.created_at),
    }
    if with_lead:
        s = snapshot(t.lead)
        out["lead"] = {"id": t.lead_id, "code": s.get("code", ""), "title": s.get("title", ""), "stage": t.lead.stage}
    return out


def event_out(e: CrmEvent) -> dict:
    return {"id": e.id, "kind": e.kind, "content": e.content, "actor": _user(e.actor), "created_at": _iso(e.created_at)}


def log(db: Session, lead: CrmLead, actor: MemberUser, kind: str, content: str) -> None:
    db.add(CrmEvent(company_id=lead.company_id, lead_id=lead.id, actor_id=actor.id, kind=kind, content=content[:500]))
    lead.updated_at = utcnow()
