"""API quản trị — hàng đợi xác minh cơ hội đối tác: /api/admin/partner-submissions/*

Phân công, SLA, nghi trùng tự động, điểm chất lượng, quyết định Đạt / Trùng / Không đạt / Đóng góp bổ sung (lý do chuẩn hoá),
tạo phiếu nháp gắn đối tác nguồn.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app.config import get_settings
from app.db import get_db, utcnow
from app.models import (
    REJECT_REASONS,
    SUBMISSION_CERTAINTY,
    SUBMISSION_KINDS,
    SUBMISSION_OPEN,
    SUBMISSION_SOURCES,
    SUBMISSION_STATUSES,
    AdminUser,
    PartnerSubmission,
    PartnerUser,
)
from app.services import partner_submissions as subs
from app.services import partner_wallet
from app.worker import enqueue, send_partner_submission_update_task

router = APIRouter(prefix="/api/admin/partner-submissions")


def _get(db: Session, sub_id: int) -> PartnerSubmission:
    s = db.get(PartnerSubmission, sub_id)
    if not s:
        raise HTTPException(404, "Không tìm thấy cơ hội đối tác.")
    return s


@router.get("/meta")
def meta(_: AdminUser = Depends(current_user)):
    cfg = get_settings()
    return {
        "statuses": SUBMISSION_STATUSES, "kinds": SUBMISSION_KINDS, "sources": SUBMISSION_SOURCES, "certainty": SUBMISSION_CERTAINTY,
        "reject_reasons": {k: v for k, v in REJECT_REASONS.items() if k != "fraud"}, "min_score": cfg.partner_min_score, "dup_days": cfg.partner_dup_days,
    }


@router.get("")
def list_submissions(
    status: str = "queue",  # queue = Đã gửi + Đang xác minh · all · hoặc 1 trạng thái
    assigned: str = "",  # "" · me · none · <id>
    partner_id: int | None = None,
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(PartnerSubmission)
    if status == "queue":
        stmt = stmt.where(PartnerSubmission.status.in_(SUBMISSION_OPEN))
    elif status and status != "all":
        stmt = stmt.where(PartnerSubmission.status == status)
    if assigned == "me":
        stmt = stmt.where(PartnerSubmission.assigned_to_id == user.id)
    elif assigned == "none":
        stmt = stmt.where(PartnerSubmission.assigned_to_id.is_(None))
    elif assigned.isdigit():
        stmt = stmt.where(PartnerSubmission.assigned_to_id == int(assigned))
    if partner_id:
        stmt = stmt.where(PartnerSubmission.partner_id == partner_id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.join(PartnerUser, PartnerUser.id == PartnerSubmission.partner_id).where(
            or_(PartnerSubmission.code.ilike(like), PartnerSubmission.company_name.ilike(like), PartnerSubmission.tax_code.like(like),
                PartnerSubmission.need.ilike(like), PartnerUser.code.ilike(like), PartnerUser.full_name.ilike(like))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    # Hàng đợi: hạn SLA gần nhất lên trước; còn lại: mới nhất trước
    order = (PartnerSubmission.sla_due_at.asc(), PartnerSubmission.id.asc()) if status == "queue" else (PartnerSubmission.id.desc(),)
    rows = db.scalars(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)).unique().all()
    counts = dict(db.execute(select(PartnerSubmission.status, func.count()).group_by(PartnerSubmission.status)).all())
    overdue = db.scalar(
        select(func.count()).select_from(PartnerSubmission)
        .where(PartnerSubmission.status.in_(SUBMISSION_OPEN), PartnerSubmission.sla_due_at < utcnow())
    ) or 0
    return {
        "total": total, "page": page, "page_size": page_size, "items": [subs.admin_out(db, s) for s in rows],
        "counts": counts, "queue": sum(counts.get(k, 0) for k in SUBMISSION_OPEN), "overdue": overdue,
    }


@router.get("/{sub_id}")
def get_submission(sub_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return subs.admin_out(db, _get(db, sub_id), detail=True)


class AssignIn(BaseModel):
    user_id: int | None = None  # bỏ trống = tự nhận


@router.post("/{sub_id}/assign")
def assign(sub_id: int, body: AssignIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    s = _get(db, sub_id)
    if s.status not in SUBMISSION_OPEN:
        raise HTTPException(409, "Cơ hội đã có kết quả xác minh.")
    who = db.get(AdminUser, body.user_id) if body.user_id else user
    if not who or not who.is_active:
        raise HTTPException(404, "Không tìm thấy nhân viên.")
    subs.assign(db, s, who, user)
    return subs.admin_out(db, s, detail=True)


class DecideIn(BaseModel):
    decision: str
    reason: str = ""  # mã lý do (bắt buộc khi Không đạt)
    partner_note: str = Field("", max_length=2000)  # đối tác thấy
    internal_note: str | None = Field(None, max_length=5000)
    final_score: int | None = None
    is_large: bool = False


@router.post("/{sub_id}/decide")
def decide(sub_id: int, body: DecideIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    s = _get(db, sub_id)
    subs.decide(
        db, get_settings(), s, user, body.decision, reason=body.reason, partner_note=body.partner_note,
        internal_note=body.internal_note, final_score=body.final_score, is_large=body.is_large,
    )
    enqueue(send_partner_submission_update_task, s.id)  # email báo đối tác kết quả
    return subs.admin_out(db, s, detail=True)


class NoteIn(BaseModel):
    internal_note: str = Field("", max_length=5000)


@router.patch("/{sub_id}")
def update_note(sub_id: int, body: NoteIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    s = _get(db, sub_id)
    s.internal_note = body.internal_note
    db.commit()
    return subs.admin_out(db, s, detail=True)


@router.post("/{sub_id}/create-opportunity", status_code=201)
def create_opportunity(sub_id: int, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    o = subs.create_opportunity(db, _get(db, sub_id), user)
    return {"opportunity_id": o.id, "code": o.code}



class FraudIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)
    lock_partner: bool = True


@router.post("/{sub_id}/fraud")
def mark_fraud(sub_id: int, body: FraudIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Cơ hội gian lận: huỷ khoản Chờ duyệt, thu hồi khoản Khả dụng (cả ly cafe), chuyển Không đạt, khoá tài khoản (mặc định).
    Phiếu đang bán (nếu có) KHÔNG tự đóng — quản trị đóng ở trang phiếu nếu cần."""
    s = _get(db, sub_id)
    if s.reject_reason == "fraud":
        raise HTTPException(409, "Cơ hội đã được đánh dấu gian lận.")
    partner_wallet.mark_fraud(db, s, user, body.reason.strip(), body.lock_partner)
    db.refresh(s)
    return subs.admin_out(db, s, detail=True)
