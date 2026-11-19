"""API quản trị — cơ hội thu thập từ Gmail: /api/admin/inbound-emails/*

Danh sách thư theo trạng thái, xem thư gốc + kết quả AI, tạo phiếu nháp (thư AI loại nhầm / AI tắt), loại thư,
xử lý lại bằng AI, chặn người gửi / tên miền.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app import ai
from app.config import get_settings
from app.db import get_db, utcnow
from app.models import AdminUser
from app.models_inbound import INBOUND_STATUSES, InboundEmail, InboundEmailBlock
from app.services import gmail_ingest
from app.worker import enqueue, gmail_process_task

router = APIRouter(prefix="/api/admin/inbound-emails")


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _opp(e: InboundEmail) -> dict | None:
    o = e.opportunity
    return {"id": o.id, "code": o.code, "status": o.status, "title": o.title} if o else None


def _row(e: InboundEmail) -> dict:
    a = e.ai_json or {}
    return {
        "id": e.id, "from_email": e.from_email, "from_name": e.from_name, "subject": e.subject,
        "received_at": _iso(e.received_at), "created_at": _iso(e.created_at), "status": e.status,
        "reason": e.reason, "error": e.error, "industry": a.get("industry"), "confidence": a.get("confidence"),
        "title": a.get("title"), "opportunity": _opp(e), "purged": bool(e.purged_at),
        "attachment_count": len(e.attachment_names or []),
    }


def _get(db: Session, email_id: int) -> InboundEmail:
    e = db.get(InboundEmail, email_id)
    if not e:
        raise HTTPException(404, "Không tìm thấy thư.")
    return e


@router.get("/meta")
def meta(db: Session = Depends(get_db), _: AdminUser = Depends(current_user)):
    cfg = get_settings()
    counts = dict(db.execute(select(InboundEmail.status, func.count()).group_by(InboundEmail.status)).all())
    return {
        "statuses": INBOUND_STATUSES, "counts": counts, "industries": cfg.gmail_industries,
        "webhook_enabled": bool(cfg.gmail_webhook_secret), "ai_enabled": cfg.gmail_ai_enabled, "ai_model": ai.describe(),
        "ai_month_cost_usd": round(gmail_ingest.month_cost(db), 4), "ai_budget_usd": cfg.gmail_ai_budget_usd,
        "min_confidence": cfg.gmail_min_confidence, "keep_days": cfg.gmail_body_keep_days,
        "last_received_at": _iso(db.scalar(select(func.max(InboundEmail.created_at)))),
    }


@router.get("")
def list_emails(
    status: str = "drafted",  # 1 trạng thái · "pending" = new + processing · "all"
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_user),
):
    stmt = select(InboundEmail)
    if status == "pending":
        stmt = stmt.where(InboundEmail.status.in_(("new", "processing")))
    elif status and status != "all":
        stmt = stmt.where(InboundEmail.status == status)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(InboundEmail.subject.ilike(like), InboundEmail.from_email.ilike(like), InboundEmail.from_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(InboundEmail.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"items": [_row(e) for e in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/blocks")
def list_blocks(db: Session = Depends(get_db), _: AdminUser = Depends(current_user)):
    rows = db.scalars(select(InboundEmailBlock).order_by(InboundEmailBlock.id.desc())).all()
    return {"items": [{"id": b.id, "pattern": b.pattern, "note": b.note, "created_at": _iso(b.created_at)} for b in rows]}


@router.delete("/blocks/{block_id}")
def delete_block(block_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    b = db.get(InboundEmailBlock, block_id)
    if not b:
        raise HTTPException(404, "Không tìm thấy.")
    db.delete(b)
    db.commit()
    return {"ok": True}


@router.get("/{email_id}")
def detail(email_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(current_user)):
    e = _get(db, email_id)
    thread = []
    if e.thread_id:
        thread = [_row(x) for x in db.scalars(
            select(InboundEmail).where(InboundEmail.thread_id == e.thread_id, InboundEmail.id != e.id).order_by(InboundEmail.id)
        ).unique().all()]
    return {
        **_row(e), "to": e.to, "body_text": e.body_text, "attachment_names": e.attachment_names or [], "ai_json": e.ai_json,
        "ai_model": e.ai_model, "ai_tokens": [e.ai_input_tokens, e.ai_output_tokens], "ai_cost_usd": round(e.ai_cost_usd or 0, 5),
        "processed_at": _iso(e.processed_at), "blocked": gmail_ingest.is_blocked(db, e.from_email), "thread": thread,
    }


@router.post("/{email_id}/draft")
def make_draft(email_id: int, db: Session = Depends(get_db), user: AdminUser = Depends(current_user)):
    """Tạo phiếu nháp từ thư (kết quả AI nếu có, không thì từ chính thư) — dùng khi AI loại nhầm / cần xem lại / AI tắt."""
    e = _get(db, email_id)
    if e.opportunity_id:
        raise HTTPException(409, "Thư này đã gắn với một phiếu cơ hội.")
    if e.status in ("new", "processing"):
        raise HTTPException(409, "Thư đang được xử lý, vui lòng thử lại sau ít phút.")
    if e.purged_at:
        raise HTTPException(409, "Nội dung thư đã bị xoá theo thời hạn lưu, không tạo phiếu được.")
    o = gmail_ingest.create_draft(db, e, user.id)
    return {"ok": True, "opportunity": {"id": o.id, "code": o.code}}


class RejectIn(BaseModel):
    reason: str = Field("", max_length=300)


@router.post("/{email_id}/reject")
def reject(email_id: int, body: RejectIn, db: Session = Depends(get_db), user: AdminUser = Depends(current_user)):
    e = _get(db, email_id)
    if e.opportunity_id:
        raise HTTPException(409, "Thư đã có phiếu — xoá / đóng phiếu ở trang Cơ hội nếu không dùng.")
    e.status, e.reason, e.decided_by_id, e.processed_at = "rejected", ("Admin loại. " + body.reason.strip()).strip()[:500], user.id, utcnow()
    db.commit()
    return {"ok": True}


@router.post("/{email_id}/reprocess")
def reprocess(email_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(current_user)):
    e = _get(db, email_id)
    if e.opportunity_id:
        raise HTTPException(409, "Thư đã có phiếu, không xử lý lại.")
    if e.status == "processing":
        raise HTTPException(409, "Thư đang được xử lý.")
    try:
        gmail_ingest.reset_for_reprocess(db, e)
    except ValueError as ex:
        raise HTTPException(409, str(ex)) from ex
    if not enqueue(gmail_process_task, e.id):
        gmail_ingest.process(db, e.id)
    return {"ok": True}


class BlockIn(BaseModel):
    scope: str = Field("email", pattern="^(email|domain)$")


@router.post("/{email_id}/block")
def block_sender(email_id: int, body: BlockIn, db: Session = Depends(get_db), user: AdminUser = Depends(current_user)):
    """Chặn người gửi (hoặc cả tên miền): thư sau của họ bị bỏ qua. Thư này chưa có phiếu thì chuyển sang "Bỏ qua"."""
    e = _get(db, email_id)
    domain = e.from_email.split("@", 1)[-1]
    if body.scope == "domain" and re.fullmatch(r"(gmail|yahoo|outlook|hotmail|icloud)\.[a-z.]+", domain):
        raise HTTPException(422, "Không chặn cả tên miền email miễn phí — hãy chặn từng người gửi.")
    pattern = e.from_email if body.scope == "email" else "@" + domain
    if not db.scalar(select(InboundEmailBlock.id).where(InboundEmailBlock.pattern == pattern)):
        db.add(InboundEmailBlock(pattern=pattern, note=f"Chặn từ thư #{e.id}: {e.subject}"[:300], created_by_id=user.id))
    if not e.opportunity_id and e.status not in ("new", "processing"):
        e.status, e.reason, e.decided_by_id = "skipped", "Người gửi / tên miền đã bị chặn.", user.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True, "pattern": pattern}
