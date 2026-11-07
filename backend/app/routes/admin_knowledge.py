"""API quản trị kho doanh nghiệp (knowledge_companies) — danh sách đầu vào để AI quét."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app.db import get_db
from app.models import KNOWLEDGE_AI_STATUSES, KNOWLEDGE_SOURCES, AdminUser, KnowledgeCompany
from app.schemas_knowledge import KnowledgeIn, KnowledgeListItem, KnowledgeOut

router = APIRouter(prefix="/api/admin/knowledge-companies")


def _out(k: KnowledgeCompany) -> dict:
    return KnowledgeOut.model_validate(k).model_dump(mode="json")


def _get(db: Session, kid: int) -> KnowledgeCompany:
    k = db.get(KnowledgeCompany, kid)
    if not k:
        raise HTTPException(404, "Không tìm thấy doanh nghiệp.")
    return k


def _check_tax_unique(db: Session, tax_code: str | None, exclude_id: int | None = None) -> None:
    if not tax_code:
        return
    stmt = select(KnowledgeCompany.id, KnowledgeCompany.name).where(KnowledgeCompany.tax_code == tax_code)
    if exclude_id:
        stmt = stmt.where(KnowledgeCompany.id != exclude_id)
    dup = db.execute(stmt).first()
    if dup:
        raise HTTPException(409, f"Mã số thuế đã có trong kho: {dup.name} (#{dup.id}).")


@router.get("/meta")
def meta(_: AdminUser = Depends(current_user)):
    return {"ai_statuses": KNOWLEDGE_AI_STATUSES, "sources": KNOWLEDGE_SOURCES}


@router.get("")
def list_items(
    q: str = Query("", max_length=100),
    ai_status: str = "",
    source: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("updated", pattern="^(updated|rank|name)$"),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(KnowledgeCompany)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                KnowledgeCompany.name.ilike(like),
                KnowledgeCompany.name_en.ilike(like),
                KnowledgeCompany.tax_code.ilike(like),
                KnowledgeCompany.industry.ilike(like),
                KnowledgeCompany.province.ilike(like),
            )
        )
    if source:
        stmt = stmt.where(KnowledgeCompany.source == source)
    # Đếm theo trạng thái trên cùng bộ lọc tìm kiếm/nguồn (trước khi lọc trạng thái) để hiện số trên tab
    sub = stmt.subquery()
    counts = dict(db.execute(select(sub.c.ai_status, func.count()).group_by(sub.c.ai_status)).all())
    if ai_status:
        stmt = stmt.where(KnowledgeCompany.ai_status == ai_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {
        "updated": [KnowledgeCompany.updated_at.desc(), KnowledgeCompany.id.desc()],
        "rank": [KnowledgeCompany.rank_year.desc(), KnowledgeCompany.rank.asc(), KnowledgeCompany.id],
        "name": [KnowledgeCompany.name.asc()],
    }[sort]
    rows = db.scalars(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": counts,
        "items": [KnowledgeListItem.model_validate(k).model_dump(mode="json") for k in rows],
    }


@router.post("", status_code=201)
def create_item(body: KnowledgeIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    _check_tax_unique(db, body.tax_code)
    k = KnowledgeCompany(**body.model_dump(), created_by_id=user.id)
    db.add(k)
    db.commit()
    db.refresh(k)
    return _out(k)


@router.get("/{kid}")
def get_item(kid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _out(_get(db, kid))


@router.put("/{kid}")
def update_item(kid: int, body: KnowledgeIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    k = _get(db, kid)
    _check_tax_unique(db, body.tax_code, exclude_id=k.id)
    for f, v in body.model_dump().items():
        setattr(k, f, v)
    db.commit()
    db.refresh(k)
    return _out(k)


@router.delete("/{kid}", status_code=204)
def delete_item(kid: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(_get(db, kid))
    db.commit()
