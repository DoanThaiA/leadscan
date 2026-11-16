"""API doanh nghiệp niêm yết — /api/admin/enrich/* (giai đoạn 3).

Danh sách niêm yết + độ phủ HĐQT/Ban điều hành · tài liệu công bố thông tin (nạp, tải, bóc tách, duyệt).
Kết quả bóc tách chứa họ tên người (kho B): xem chi tiết / tải file gốc cần quyền b.evidence và luôn ghi nhật ký.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.enrich import documents, khob, raw_store
from app.enrich import permissions as perm
from app.enrich.normalize import bo_dau
from app.models import AdminUser
from app.models_enrich import DOC_STATUSES, DOC_TYPES, PERSON_GROUPS, EnrichCompany, EnrichDocument, SourcePage
from app.routes.admin_enrich import FileIn, _iso, _user_names
from app.schemas import Line

router = APIRouter(prefix="/api/admin/enrich")


def _kick() -> None:
    from app.routes.admin_enrich_ops import _kick as kick

    kick()


# ------------------------------------------------------------------ doanh nghiệp niêm yết


@router.get("/listed")
def listed(
    q: str = Query("", max_length=100),
    only_missing: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: AdminUser = Depends(perm.require("a.read")),
    db: Session = Depends(get_db),
):
    stmt = select(EnrichCompany).where(EnrichCompany.niem_yet.is_(True))
    if q.strip():
        like = f"%{bo_dau(q)}%"
        stmt = stmt.where((EnrichCompany.ten_khong_dau.like(like)) | (func.upper(EnrichCompany.ma_ck) == q.strip().upper()) | (EnrichCompany.mst.like(f"{q.strip()}%")))
    companies = db.scalars(stmt.order_by(EnrichCompany.ma_ck)).all()
    counts = khob.board_counts(db, [c.mst for c in companies])
    docs = {
        mst: (n, last)
        for mst, n, last in db.execute(
            select(EnrichDocument.mst, func.count(), func.max(EnrichDocument.created_at)).group_by(EnrichDocument.mst)
        )
    }
    review = dict(
        db.execute(select(EnrichDocument.mst, func.count()).where(EnrichDocument.status == "needs_review").group_by(EnrichDocument.mst)).all()
    )
    rows = []
    for c in companies:
        k = counts.get(c.mst, {"board": 0, "exec": 0})
        full = bool(k["board"] and k["exec"])
        if only_missing and full:
            continue
        n, last = docs.get(c.mst, (0, None))
        rows.append(
            {
                "mst": c.mst,
                "ten": c.ten,
                "ma_ck": c.ma_ck,
                "board": k["board"],
                "exec": k["exec"],
                "full": full,
                "documents": n,
                "needs_review": review.get(c.mst, 0),
                "last_document_at": _iso(last),
            }
        )
    total, full_n = khob.listed_full_board_count(db)
    start = (page - 1) * page_size
    return {"total_listed": total, "full_board": full_n, "count": len(rows), "items": rows[start : start + page_size]}


# ------------------------------------------------------------------ tài liệu


def _doc_row(d: EnrichDocument, companies: dict[str, EnrichCompany], users: dict[int, str]) -> dict:
    c = companies.get(d.mst)
    ex = d.extracted or {}
    return {
        "id": d.id,
        "mst": d.mst,
        "ten": c.ten if c else None,
        "ma_ck": c.ma_ck if c else None,
        "doc_type": d.doc_type,
        "period": d.period,
        "source_url": d.source_url,
        "status": d.status,
        "method": d.method,
        "people_count": len(ex.get("people", [])),
        "has_board": ex.get("has_board", False),
        "has_exec": ex.get("has_exec", False),
        "error": d.error,
        "created_by": users.get(d.created_by_id) if d.created_by_id else None,
        "created_at": _iso(d.created_at),
        "parsed_at": _iso(d.parsed_at),
    }


@router.get("/documents/meta")
def docs_meta(_: AdminUser = Depends(perm.require("a.read"))):
    return {"types": DOC_TYPES, "statuses": DOC_STATUSES, "groups": PERSON_GROUPS}


@router.get("/documents")
def list_documents(
    status: str = "",
    mst: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: AdminUser = Depends(perm.require("a.read")),
    db: Session = Depends(get_db),
):
    """Danh sách tài liệu — chỉ siêu dữ liệu và số người tìm được, không có họ tên."""
    stmt = select(EnrichDocument)
    if status:
        stmt = stmt.where(EnrichDocument.status == status)
    if mst:
        stmt = stmt.where(EnrichDocument.mst == mst)
    counts = dict(db.execute(select(EnrichDocument.status, func.count()).group_by(EnrichDocument.status)).all())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    docs = db.scalars(stmt.order_by(EnrichDocument.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    companies = {c.mst: c for c in db.scalars(select(EnrichCompany).where(EnrichCompany.mst.in_({d.mst for d in docs})))}
    users = _user_names(db, [d.created_by_id for d in docs])
    return {"total": total, "counts": counts, "items": [_doc_row(d, companies, users) for d in docs]}


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, request: Request, user: AdminUser = Depends(perm.require("b.evidence")), db: Session = Depends(get_db)):
    d = db.get(EnrichDocument, doc_id)
    if not d:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    c = db.get(EnrichCompany, d.mst)
    users = _user_names(db, [d.created_by_id, d.reviewed_by_id])
    out = _doc_row(d, {d.mst: c} if c else {}, users)
    page = db.get(SourcePage, d.source_page_id) if d.source_page_id else None
    out.update(
        {
            "extracted": d.extracted or {},
            "reviewed_by": users.get(d.reviewed_by_id) if d.reviewed_by_id else None,
            "reviewed_at": _iso(d.reviewed_at),
            "file": {"content_type": page.content_type, "size": page.size, "content_hash": page.content_hash} if page else None,
        }
    )
    khob.log_access(db, user, request, "read", f"document:{d.id}", len((d.extracted or {}).get("people", [])))
    return out


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: int, request: Request, user: AdminUser = Depends(perm.require("b.evidence")), db: Session = Depends(get_db)):
    """Bản gốc — có thể chứa dữ liệu cá nhân (danh sách người nội bộ) nên chỉ vai trò được xem bằng chứng kho B, có ghi nhật ký."""
    d = db.get(EnrichDocument, doc_id)
    page = db.get(SourcePage, d.source_page_id) if d and d.source_page_id else None
    if not page:
        raise HTTPException(404, "Tài liệu chưa được tải về.")
    data = raw_store.get(page.storage_key)
    khob.log_access(db, user, request, "read", f"document:{d.id}/file", 1)
    ext = {"application/pdf": "pdf", "text/html": "html"}.get(page.content_type, "txt")
    return Response(
        content=data,
        media_type=page.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="tai-lieu-{d.id}.{ext}"', "Cache-Control": "no-store"},
    )


class UploadIn(FileIn):
    ref: Line = Field(min_length=3, max_length=20)  # MST hoặc mã CK
    doc_type: str = "bao_cao_quan_tri"
    period: Line = Field("", max_length=40)
    source_url: Line = Field("", max_length=1000)


@router.post("/documents/upload", status_code=201)
def upload_document(body: UploadIn, user: AdminUser = Depends(perm.require("docs.manage")), db: Session = Depends(get_db)):
    try:
        d = documents.add_upload(
            db, user, ref=body.ref, doc_type=body.doc_type, period=body.period, source_url=body.source_url,
            file_name=body.file_name, data=body.data(),
        )
    except documents.DocError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    return {"id": d.id, "status": d.status}


class UrlsIn(BaseModel):
    text: str = Field(min_length=3, max_length=200_000)  # mỗi dòng: MST hoặc mã CK, URL[, kỳ]
    doc_type: str = "bao_cao_quan_tri"


@router.post("/documents/urls", status_code=201)
def add_document_urls(body: UrlsIn, user: AdminUser = Depends(perm.require("docs.manage")), db: Session = Depends(get_db)):
    items = []
    for line in body.text.splitlines():
        parts = [p.strip() for p in re.split(r"[,;\t]", line) if p.strip()]
        if not parts:
            continue
        url = next((p for p in parts if p.lower().startswith(("http://", "https://"))), "")
        rest = [p for p in parts if p != url]
        items.append({"ref": rest[0] if rest else "", "url": url, "period": rest[1] if len(rest) > 1 else "", "doc_type": body.doc_type})
    if not items:
        raise HTTPException(422, "Chưa có dòng nào.")
    if len(items) > 5000:
        raise HTTPException(422, "Tối đa 5.000 dòng mỗi lần.")
    try:
        rep = documents.add_urls(db, user, items)
    except documents.DocError as e:
        raise HTTPException(422, str(e)) from e
    if rep["created"]:
        _kick()
    return rep


class ReviewIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    people: list[dict] = Field(default_factory=list)


@router.post("/documents/{doc_id}/review")
def review_document(doc_id: int, body: ReviewIn, request: Request, user: AdminUser = Depends(perm.require("docs.manage")), db: Session = Depends(get_db)):
    try:
        d = documents.review(db, user, doc_id, body.action, body.people)
    except documents.DocError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    khob.log_access(db, user, request, "edit", f"document:{d.id}/{body.action}", len(body.people))
    return {"id": d.id, "status": d.status}


@router.post("/documents/{doc_id}/reparse")
def reparse_document(doc_id: int, _: AdminUser = Depends(perm.require("docs.manage")), db: Session = Depends(get_db)):
    d = db.get(EnrichDocument, doc_id)
    if not d or not d.source_page_id:
        raise HTTPException(404, "Tài liệu chưa được tải về.")
    if d.status in ("approved", "rejected"):
        raise HTTPException(409, "Tài liệu đã được duyệt / từ chối.")
    return {"id": d.id, "status": documents.parse_document(db, d.id)}
