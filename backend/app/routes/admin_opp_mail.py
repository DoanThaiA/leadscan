"""API quản trị — gửi phiếu cơ hội cho khách hàng qua email: /api/admin/opportunities/{id}/mail/*

  GET  recipients   tìm NGƯỜI LIÊN HỆ (có email) của doanh nghiệp thành viên để chọn — không dùng email đăng nhập
                    (doanh nghiệp phù hợp với phiếu lên đầu, kèm điểm phù hợp, đã mua chưa, đã gửi email phiếu này chưa)
  GET  preview      xem trước email đúng như người nhận thấy (giá theo điểm riêng của doanh nghiệp)
  POST send         gửi cho các người liên hệ đã chọn (việc nền; mỗi người 1 email riêng)
  GET  history      nhật ký đã gửi
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models import AdminUser, Company, Contact, MemberUser, Opportunity, Purchase, UserOpportunity
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


def _member_companies():
    """Doanh nghiệp còn tài khoản thành viên hoạt động (email phiếu dẫn về cổng thành viên)."""
    return select(MemberUser.company_id).where(MemberUser.is_active)


@router.get("/recipients")
def recipients(
    opp_id: int,
    q: str = Query("", max_length=100),
    scope: str = Query("matched", pattern="^(matched|all)$"),  # matched = chỉ doanh nghiệp được hệ thống chấm là phù hợp
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_user),
):
    """Người nhận = Người liên hệ (có email) của doanh nghiệp thành viên — không dùng email đăng nhập."""
    o = _opp(db, opp_id)
    um = select(UserOpportunity.company_id, UserOpportunity.score).where(UserOpportunity.opportunity_id == o.id).subquery()
    stmt = (
        select(Contact, um.c.score)
        .join(Company, Company.id == Contact.company_id)
        .outerjoin(um, um.c.company_id == Contact.company_id)
        .where(Contact.email != "", Contact.company_id.in_(_member_companies()))
    )
    if scope == "matched":
        stmt = stmt.where(um.c.score.is_not(None))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Company.name.ilike(like), Company.code.ilike(like), Company.tax_code.like(like),
                              Contact.email.ilike(like), Contact.full_name.ilike(like), Company.industry.ilike(like)))
    order = (um.c.score.desc().nulls_last(), Company.name, Contact.is_primary.desc(), Contact.id)
    rows = db.execute(stmt.order_by(*order).limit(100)).unique().all()
    company_ids = {c.company_id for c, _ in rows}
    bought = set(db.scalars(select(Purchase.company_id).where(Purchase.opportunity_id == o.id, Purchase.company_id.in_(company_ids)))) if company_ids else set()
    last: dict[tuple[int, str], OpportunityEmail] = {}
    if company_ids:
        for e in db.scalars(select(OpportunityEmail).where(OpportunityEmail.opportunity_id == o.id, OpportunityEmail.company_id.in_(company_ids))
                            .order_by(OpportunityEmail.id)).unique():
            last[(e.company_id, e.email.lower())] = e
    matched_total = db.scalar(select(func.count()).select_from(UserOpportunity).where(UserOpportunity.opportunity_id == o.id)) or 0
    items = []
    for c, score in rows:
        e = last.get((c.company_id, c.email.lower()))
        items.append({
            "id": c.id, "full_name": c.full_name, "email": c.email, "position": c.position, "is_primary": c.is_primary,
            "company": {"id": c.company.id, "code": c.company.code, "name": c.company.name, "industry": c.company.industry, "province": c.company.province},
            "score": score, "purchased": c.company_id in bought,
            "last_email": {"status": e.status, "at": _iso(e.sent_at or e.created_at)} if e else None,
        })
    return {"can_send": opp_mail.can_send(o) == "", "blocked_reason": opp_mail.can_send(o), "matched_companies": matched_total, "items": items}


@router.get("/preview")
def preview(
    opp_id: int,
    contact_id: int,
    note: str = Query("", max_length=opp_mail.MAX_NOTE),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(current_user),
):
    o = _opp(db, opp_id)
    c = db.get(Contact, contact_id)
    if not c or not c.email:
        raise HTTPException(404, "Không tìm thấy người liên hệ có email.")
    subject, text, html = opp_mail.render(db, o, c.company, c.full_name, note)
    return {"subject": subject, "to": c.email, "html": html, "text": text}


class SendIn(BaseModel):
    contact_ids: list[int] = Field(min_length=1, max_length=opp_mail.MAX_RECIPIENTS)
    note: str = Field("", max_length=opp_mail.MAX_NOTE)


@router.post("/send")
def send(opp_id: int, body: SendIn, db: Session = Depends(get_db), user: AdminUser = Depends(current_user)):
    o = _opp(db, opp_id)
    reason = opp_mail.can_send(o)
    if reason:
        raise HTTPException(409, reason)
    contacts = db.scalars(
        select(Contact).where(Contact.id.in_(set(body.contact_ids)), Contact.email != "", Contact.company_id.in_(_member_companies()))
        .order_by(Contact.id)
    ).unique().all()
    if not contacts:
        raise HTTPException(422, "Không có người liên hệ hợp lệ (có email, thuộc doanh nghiệp thành viên) trong danh sách đã chọn.")
    bought = set(db.scalars(select(Purchase.company_id).where(Purchase.opportunity_id == o.id)))
    queued, skipped, seen = [], [], set()
    for c in contacts:
        email = c.email.strip()
        if c.company_id in bought:
            skipped.append({"email": email, "reason": "Doanh nghiệp đã mua phiếu này."})
            continue
        if (c.company_id, email.lower()) in seen:  # 2 người liên hệ trùng email → 1 email
            continue
        seen.add((c.company_id, email.lower()))
        e = OpportunityEmail(opportunity_id=o.id, company_id=c.company_id, member_user_id=None, email=email[:150],
                             recipient_name=c.full_name[:100], note=body.note.strip(), sent_by_id=user.id)
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
