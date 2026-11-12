"""Cơ hội công khai: /api/public/opportunities/*  — ai cũng xem được phần "chưa mua" để gửi link đi (Zalo, email…).

Chỉ trả phần xem trước như thành viên chưa mua: KHÔNG có tên bên có nhu cầu, chi tiết, đầu mối, link nguồn, tệp đính kèm
(chỉ đếm số lượng), không có đối tác nguồn. Giá: "từ" = giá khi điểm phù hợp chưa vượt ngưỡng tăng giá (giá thật mỗi thành viên
tính theo điểm phù hợp riêng). Mua: phải là thành viên — trang web chuyển sang đăng ký / đăng nhập.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Opportunity
from app.registration_form import INDUSTRIES, REGIONS
from app.services import attachments
from app.services.matching import price_of, urgency_of

router = APIRouter(prefix="/api/public/opportunities")


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def public_out(o: Opportunity, counts: dict | None = None) -> dict:
    today = date.today()
    out = {
        "id": o.id, "code": o.code, "title": o.title, "summary": o.summary, "industry": o.industry, "province": o.province,
        "region": o.region, "source_type": o.source_type, "scale": o.scale, "estimated_value": o.estimated_value,
        "deadline": o.deadline.isoformat() if o.deadline else None, "enrich_round": o.enrich_round,
        "max_buyers": o.max_buyers, "sold_count": o.sold_count, "remaining": max(0, o.max_buyers - o.sold_count),
        "exclusive": o.max_buyers == 1, "sold_out": o.sold_count >= o.max_buyers or o.status == "closed", "status": o.status,
        "contact_count": len(o.contacts), "price_from": price_of(o, 0, urgency_of(o, today)), "published_at": _iso(o.published_at),
    }
    if counts is not None:
        out["attachment_counts"] = counts
    return out


@router.get("")
def list_public(
    q: str = Query("", max_length=100),
    industry: str = "",
    region: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=60),
    db: Session = Depends(get_db),
):
    stmt = select(Opportunity).where(Opportunity.status == "published")
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Opportunity.title.ilike(like), Opportunity.summary.ilike(like), Opportunity.code.ilike(like)))
    if industry:
        stmt = stmt.where(Opportunity.industry == industry)
    if region:
        stmt = stmt.where(or_(Opportunity.region == region, Opportunity.province == region))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.options(selectinload(Opportunity.contacts)).order_by(Opportunity.published_at.desc().nullslast(), Opportunity.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [public_out(o) for o in rows],
            "industries": INDUSTRIES, "regions": REGIONS}


@router.get("/{code}")
def get_public(code: str, db: Session = Depends(get_db)):
    o = db.scalar(select(Opportunity).options(selectinload(Opportunity.contacts)).where(func.upper(Opportunity.code) == code.strip().upper()))
    if not o or o.status == "draft":
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    return public_out(o, attachments.counts(db, o.id))
