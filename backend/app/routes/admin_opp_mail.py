"""API quản trị — gửi phiếu cơ hội cho khách hàng qua email: /api/admin/opportunities/{id}/mail/*

  GET  recipients   tìm tài khoản thành viên để chọn (doanh nghiệp phù hợp với phiếu lên đầu, kèm điểm phù hợp,
                    đã mua chưa, đã gửi email phiếu này chưa)
  GET  preview      xem trước email đúng như người nhận thấy (giá theo điểm riêng của doanh nghiệp)
  POST send         gửi cho các tài khoản đã chọn (việc nền; mỗi người 1 email riêng)
  GET  history      nhật ký đã gửi
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models import AdminUser, Company, MemberUser, Opportunity, Purchase, UserOpportunity
from app.models_opp_mail import OPP_EMAIL_STATUSES, OpportunityEmail
from app.services import opp_mail
from app.worker import enqueue, send_opportunity_email_task

router = APIRouter(prefix="/api/admin/opportunities/{opp_id}/mail")


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _opp(db: Session, opp_id: int) -> Opportunity:
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    return o


@router.get("/recipients")
def recipients(
    opp_id: int,
    q: str = Query("", max_length=100),
    scope: str = Query("matched", pattern="^(matched|all)$"),  # matched = chỉ doanh nghiệp được hệ thống chấm là phù hợp
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_user),
):
    o = _opp(db, opp_id)
    um = select(UserOpportunity.company_id, UserOpportunity.score).where(UserOpportunity.opportunity_id == o.id).subquery()
    stmt = (
        select(MemberUser, um.c.score)
        .join(Company, Company.id == MemberUser.company_id)
        .outerjoin(um, um.c.company_id == MemberUser.company_id)
        .where(MemberUser.is_active)
    )
    if scope == "matched":
        stmt = stmt.where(um.c.score.is_not(None))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Company.name.ilike(like), Company.code.ilike(like), Company.tax_code.like(like),
                              MemberUser.email.ilike(like), MemberUser.full_name.ilike(like), Company.industry.ilike(like)))
    rows = db.execute(stmt.order_by(um.c.score.desc().nulls_last(), Company.name, MemberUser.id).limit(100)).unique().all()
    company_ids = {u.company_id for u, _ in rows}
    bought = set(db.scalars(select(Purchase.company_id).where(Purchase.opportunity_id == o.id, Purchase.company_id.in_(company_ids)))) if company_ids else set()
    user_ids = [u.id for u, _ in rows]
    last = {}
    if user_ids:
        for e in db.scalars(select(OpportunityEmail).where(OpportunityEmail.opportunity_id == o.id, OpportunityEmail.member_user_id.in_(user_ids))
                            .order_by(OpportunityEmail.id)).unique():
            last[e.member_user_id] = e
    matched_total = db.scalar(select(func.count()).select_from(UserOpportunity).where(UserOpportunity.opportunity_id == o.id)) or 0
    return {
        "can_send": opp_mail.can_send(o) == "", "blocked_reason": opp_mail.can_send(o), "matched_companies": matched_total,
        "items": [
            {
                "id": u.id, "full_name": u.full_name, "email": u.email,
                "company": {"id": u.company.id, "code": u.company.code, "name": u.company.name, "industry": u.company.industry, "province": u.company.province},
                "score": score, "purchased": u.company_id in bought,
                "last_email": {"status": last[u.id].status, "at": _iso(last[u.id].sent_at or last[u.id].created_at)} if u.id in last else None,
            }
            for u, score in rows
        ],
    }


@router.get("/preview")
def preview(
    opp_id: int,
    member_id: int,
    note: str = Query("", max_length=opp_mail.MAX_NOTE),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_user),
):
    o = _opp(db, opp_id)
    user = db.get(MemberUser, member_id)
    if not user:
        raise HTTPException(404, "Không tìm thấy tài khoản thành viên.")
    subject, text, html = opp_mail.render(db, o, user, note)
    return {"subject": subject, "to": user.email, "html": html, "text": text}


class SendIn(BaseModel):
    member_ids: list[int] = Field(min_length=1, max_length=opp_mail.MAX_RECIPIENTS)
    note: str = Field("", max_length=opp_mail.MAX_NOTE)


@router.post("/send")
def send(opp_id: int, body: SendIn, db: Session = Depends(get_db), user: AdminUser = Depends(current_user)):
    o = _opp(db, opp_id)
    reason = opp_mail.can_send(o)
    if reason:
        raise HTTPException(409, reason)
    members = db.scalars(select(MemberUser).where(MemberUser.id.in_(set(body.member_ids)), MemberUser.is_active)).unique().all()
    if not members:
        raise HTTPException(422, "Không có tài khoản thành viên hợp lệ trong danh sách đã chọn.")
    bought = set(db.scalars(select(Purchase.company_id).where(Purchase.opportunity_id == o.id)))
    queued, skipped = [], []
    for m in members:
        if m.company_id in bought:
            skipped.append({"email": m.email, "reason": "Doanh nghiệp đã mua phiếu này."})
            continue
        e = OpportunityEmail(opportunity_id=o.id, company_id=m.company_id, member_user_id=m.id, email=m.email,
                             recipient_name=m.full_name[:100], note=body.note.strip(), sent_by_id=user.id)
        db.add(e)
        queued.append(e)
    db.commit()
    for e in queued:
        if not enqueue(send_opportunity_email_task, e.id):  # Redis lỗi → gửi luôn trong request
            opp_mail.send_one(db, e.id)
    return {"ok": True, "queued": len(queued), "skipped": skipped}


@router.get("/history")
def history(opp_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(current_user)):
    o = _opp(db, opp_id)
    rows = db.scalars(select(OpportunityEmail).where(OpportunityEmail.opportunity_id == o.id).order_by(OpportunityEmail.id.desc()).limit(200)).unique().all()
    return {
        "items": [
            {
                "id": e.id, "email": e.email, "recipient_name": e.recipient_name, "status": e.status, "status_label": OPP_EMAIL_STATUSES.get(e.status, e.status),
                "error": e.error, "note": e.note, "created_at": _iso(e.created_at), "sent_at": _iso(e.sent_at),
                "company": {"id": e.company.id, "name": e.company.name} if e.company else None,
                "sent_by": e.sent_by.full_name if e.sent_by else None,
            }
            for e in rows
        ]
    }


@router.post("/history/{email_id}/retry")
def retry(opp_id: int, email_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(current_user)):
    e = db.get(OpportunityEmail, email_id)
    if not e or e.opportunity_id != opp_id:
        raise HTTPException(404, "Không tìm thấy.")
    if e.status != "failed":
        raise HTTPException(409, "Chỉ gửi lại email bị lỗi.")
    e.status, e.error = "queued", ""
    db.commit()
    if not enqueue(send_opportunity_email_task, e.id):
        opp_mail.send_one(db, e.id)
    return {"ok": True}
