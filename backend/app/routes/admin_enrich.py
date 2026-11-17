"""API phân hệ làm giàu dữ liệu doanh nghiệp theo MST — /api/admin/enrich/* (giai đoạn 1: nền dữ liệu).

Quyền theo vai trò làm giàu dữ liệu (app/enrich/permissions.py). Dữ liệu kho B chỉ đọc qua app/enrich/khob.py.
Mọi trường hồ sơ đều hiển thị; trường chưa có bằng chứng thì không kèm nguồn (nguồn về sau sẽ ghi đè).
"""

import base64
import binascii
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.enrich import importer, khob, merge, sources
from app.enrich import permissions as perm
from app.enrich.normalize import bo_dau, parse_mst
from app.enrich.sources import all_sources
from app.models import AdminUser
from app.models_enrich import (
    COMPANY_FIELDS,
    ENRICH_ROLES,
    JOB_STATUSES,
    METHODS,
    RUN_STATUSES,
    SIGNAL_KINDS,
    PURPOSES,
    REQUIRED_FIELDS,
    CompanyChange,
    CompanyEvidence,
    EnrichBatch,
    EnrichBatchItem,
    EnrichCompany,
    EnrichContact,
    EnrichSignal,
    OptOut,
)
from app.schemas import Line

router = APIRouter(prefix="/api/admin/enrich")

MAX_B64 = importer.MAX_FILE_BYTES * 4 // 3 + 16


def _iso(d) -> str | None:
    return None if d is None else d.isoformat() + ("Z" if hasattr(d, "hour") else "")


def _get_company(db: Session, mst: str) -> EnrichCompany:
    res = parse_mst(mst)
    c = db.get(EnrichCompany, res.mst) if res.mst else None
    if not c:
        raise HTTPException(404, "Không tìm thấy doanh nghiệp với mã số thuế này.")
    return c


def _display(field: str, v):
    if v is None:
        return None
    if field == "ngay_thanh_lap":
        return v.isoformat()
    return v


# ------------------------------------------------------------------ danh mục


@router.get("/meta")
def meta(user: AdminUser = Depends(perm.require("a.read"))):
    return {
        "roles": ENRICH_ROLES,
        "purposes": PURPOSES,
        "fields": COMPANY_FIELDS,
        "required_fields": list(REQUIRED_FIELDS),
        "methods": METHODS,
        "job_statuses": JOB_STATUSES,
        "run_statuses": RUN_STATUSES,
        "signal_kinds": SIGNAL_KINDS,
        "my_role": user.enrich_access,
        "caps": sorted(perm.caps_of(user)),
    }


@router.get("/stats")
def stats(_: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    """Độ phủ hồ sơ (mục 1): ≥ 95% MST có đủ tên, địa chỉ, tình trạng, ngành nghề; ≥ 70% có người ra quyết định."""
    total = db.scalar(select(func.count()).select_from(EnrichCompany)) or 0
    per_field = {}
    for f in REQUIRED_FIELDS:
        per_field[f] = db.scalar(select(func.count()).select_from(EnrichCompany).where(getattr(EnrichCompany, f).is_not(None))) or 0
    full = (
        db.scalar(
            select(func.count())
            .select_from(EnrichCompany)
            .where(and_(*[getattr(EnrichCompany, f).is_not(None) for f in REQUIRED_FIELDS]))
        )
        or 0
    )
    return {
        "total": total,
        "by_field": per_field,
        "full_profile": full,
        "with_decision_maker": khob.decision_maker_company_count(db),
        # giai đoạn 3: DN niêm yết có đủ HĐQT + Ban điều hành (mục tiêu ≥ 90%)
        **dict(zip(("listed", "listed_full_board"), khob.listed_full_board_count(db))),
        "batches": db.scalar(select(func.count()).select_from(EnrichBatch)) or 0,
    }


# ------------------------------------------------------------------ doanh nghiệp (kho A)


@router.get("/companies")
def list_companies(
    q: str = Query("", max_length=200),
    batch_id: int | None = None,
    missing: str = Query("", max_length=40),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(perm.require("a.read")),
    db: Session = Depends(get_db),
):
    stmt = select(EnrichCompany)
    q = q.strip()
    if q:
        digits = re.sub(r"[^\d-]", "", q)
        conds = [EnrichCompany.ten_khong_dau.like(f"%{bo_dau(q)}%")]
        if len(digits) >= 3:
            conds.append(EnrichCompany.mst.like(f"{digits}%"))
        stmt = stmt.where(or_(*conds))
    if batch_id:
        stmt = stmt.where(EnrichCompany.mst.in_(select(EnrichBatchItem.mst).where(EnrichBatchItem.batch_id == batch_id)))
    if missing:
        if missing not in REQUIRED_FIELDS and missing not in COMPANY_FIELDS:
            raise HTTPException(422, "Trường không hợp lệ.")
        stmt = stmt.where(getattr(EnrichCompany, missing).is_(None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(EnrichCompany.created_at.desc(), EnrichCompany.mst).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "mst": c.mst,
                "ten": c.ten,
                "tinh": c.tinh,
                "trang_thai": c.trang_thai,
                "nganh_nghe": c.nganh_nghe,
                "missing": [f for f in REQUIRED_FIELDS if getattr(c, f) is None],
                "updated_at": _iso(c.updated_at),
            }
            for c in rows
        ],
    }


@router.get("/companies/{mst}")
def get_company(mst: str, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    c = _get_company(db, mst)
    srcs = all_sources(db)
    trust = {k: s.trust for k, s in srcs.items()}
    views = merge.views_for(db.scalars(select(CompanyEvidence).where(CompanyEvidence.mst == c.mst)), trust)

    now = utcnow()
    fields = []
    for key, label in COMPANY_FIELDS.items():
        v = views.get(key)
        if not v:
            # chưa có bằng chứng: vẫn hiển thị giá trị đang có trong cột (hoặc trống); nguồn nào về sau sẽ ghi đè
            fields.append(
                {
                    "key": key,
                    "label": label,
                    "value": c.mst if key == "mst" else _display(key, getattr(c, key)),
                    "source": None,
                    "source_url": None,
                    "method": None,
                    "is_inferred": False,
                    "fetched_at": None,
                    "evidence_count": 0,
                    "agree": 0,
                    "conflict": False,
                    "score": None,
                    "stale": False,
                    "recrawl_days": 0,
                }
            )
            continue
        e = v.chosen
        src = srcs.get(e.source_code)
        recrawl = int(sources.setting(src, "recrawl_days", 90)) if src and e.source_code not in sources.INTERNAL else 0
        score, stale = merge.field_score(v, trust, recrawl, now)
        fields.append(
            {
                "key": key,
                "label": label,
                "value": c.mst if key == "mst" else _display(key, getattr(c, key)),
                "source": {"code": e.source_code, "name": srcs[e.source_code].name if e.source_code in srcs else e.source_code, "trust": trust.get(e.source_code)},
                "source_url": e.source_url,
                "method": e.method,
                "is_inferred": e.is_inferred,
                "fetched_at": _iso(e.fetched_at),
                "evidence_count": v.count,
                "agree": v.agree,
                "conflict": v.conflict,
                "score": score,  # B08
                "stale": stale,  # B13
                "recrawl_days": recrawl,
            }
        )
    missing = [f["label"] for f in fields if f["value"] in (None, "", [])]

    batches = db.execute(
        select(EnrichBatch.id, EnrichBatch.name, EnrichBatch.purposes, EnrichBatch.created_at, EnrichBatchItem.row_no)
        .join(EnrichBatchItem, EnrichBatchItem.batch_id == EnrichBatch.id)
        .where(EnrichBatchItem.mst == c.mst)
        .order_by(EnrichBatch.created_at)
    ).all()
    purposes = sorted({p for b in batches for p in (b.purposes or [])}, key=list(PURPOSES).index)
    changes = db.scalars(select(CompanyChange).where(CompanyChange.mst == c.mst).order_by(CompanyChange.detected_at.desc()).limit(200)).all()
    signals = db.scalars(select(EnrichSignal).where(EnrichSignal.mst == c.mst).order_by(EnrichSignal.created_at.desc()).limit(200)).all()
    # liên hệ chung của doanh nghiệp (tổng đài, info@) — cùng mức với cột "email / điện thoại doanh nghiệp" khi xuất kho A
    blocked = {v.strip().lower() for (v,) in db.execute(select(OptOut.value).where(OptOut.kind.in_(("email", "phone"))))}
    contacts = [
        {"kind": ct.kind, "value": ct.value, "source_code": ct.source_code, "source_name": srcs[ct.source_code].name if ct.source_code in srcs else ct.source_code}
        for ct in db.scalars(
            select(EnrichContact).where(EnrichContact.owner_type == "company", EnrichContact.owner_id == c.mst).order_by(EnrichContact.kind, EnrichContact.id)
        )
        if ct.value.strip().lower() not in blocked
    ]
    return {
        "contacts": contacts,
        "mst": c.mst,
        "ten": c.ten,
        "loai_hinh": c.loai_hinh,
        "fields": fields,
        "missing_fields": missing,
        "purposes": purposes,
        "batches": [
            {"id": b.id, "name": b.name, "purposes": b.purposes, "created_at": _iso(b.created_at), "row_no": b.row_no} for b in batches
        ],
        "changes": [
            {
                "field": ch.field,
                "label": COMPANY_FIELDS.get(ch.field, ch.field),
                "old_value": ch.old_value,
                "new_value": ch.new_value,
                "source_code": ch.source_code,
                "detected_at": _iso(ch.detected_at),
            }
            for ch in changes
        ],
        "signals": [
            {
                "kind": s.kind,
                "label": SIGNAL_KINDS.get(s.kind, s.kind),
                "payload": s.payload,
                "day": _iso(s.day),
                "source_code": s.source_code,
                "source_name": srcs[s.source_code].name if s.source_code in srcs else s.source_code,
                "source_url": s.source_url,
                "detected_at": _iso(s.created_at),
            }
            for s in signals
        ],
        "can": {"people": perm.has(user, "b.read"), "evidence": perm.has(user, "a.evidence")},
        "created_at": _iso(c.created_at),
    }


@router.get("/companies/{mst}/evidence")
def company_evidence(mst: str, _: AdminUser = Depends(perm.require("a.evidence")), db: Session = Depends(get_db)):
    """Tab "Nguồn gốc": mọi bằng chứng của từng trường, đánh dấu bằng chứng đang được dùng để hiển thị."""
    c = _get_company(db, mst)
    srcs = all_sources(db)
    evs = db.scalars(select(CompanyEvidence).where(CompanyEvidence.mst == c.mst)).all()
    views = merge.views_for(evs, {k: s.trust for k, s in srcs.items()})
    chosen = {v.chosen.id for v in views.values()}
    order = list(COMPANY_FIELDS)
    evs = sorted(evs, key=lambda e: (order.index(e.field) if e.field in order else 99, e.id not in chosen, -e.id))
    batch_names = dict(db.execute(select(EnrichBatch.id, EnrichBatch.name).where(EnrichBatch.id.in_({e.batch_id for e in evs if e.batch_id}))).all())
    return [
        {
            "id": e.id,
            "field": e.field,
            "label": COMPANY_FIELDS.get(e.field, e.field),
            "value": e.value,
            "source_code": e.source_code,
            "source_name": srcs[e.source_code].name if e.source_code in srcs else e.source_code,
            "trust": srcs[e.source_code].trust if e.source_code in srcs else None,
            "source_url": e.source_url,
            "excerpt": e.excerpt,
            "method": e.method,
            "is_inferred": e.is_inferred,
            "batch": {"id": e.batch_id, "name": batch_names.get(e.batch_id, "")} if e.batch_id else None,
            "fetched_at": _iso(e.fetched_at),
            "in_use": e.id in chosen,
            "conflict": views[e.field].conflict if e.field in views else False,
        }
        for e in evs
    ]


# ------------------------------------------------------------------ kho B (qua khob — kiểm quyền + ghi nhật ký)


@router.get("/companies/{mst}/people")
def company_people(mst: str, request: Request, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    c = _get_company(db, mst)
    return khob.company_people(db, user, c.mst, request)


@router.get("/persons")
def list_persons(
    request: Request,
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AdminUser = Depends(perm.require("a.read")),
    db: Session = Depends(get_db),
):
    return khob.list_persons(db, user, q, page, page_size, request)


# ------------------------------------------------------------------ lô MST


class FileIn(BaseModel):
    file_name: Line = Field(min_length=1, max_length=255)
    file_b64: str = Field(min_length=1, max_length=MAX_B64)

    def data(self) -> bytes:
        try:
            return base64.b64decode(self.file_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(422, "File gửi lên không hợp lệ.") from e


class BatchIn(FileIn):
    name: Line = Field(min_length=2, max_length=200)
    list_source: Line = Field(min_length=2, max_length=300)
    purposes: list[str] = Field(min_length=1)
    note: str = Field("", max_length=5000)

    @field_validator("purposes")
    @classmethod
    def _purposes(cls, v: list[str]) -> list[str]:
        bad = [p for p in v if p not in PURPOSES]
        if bad:
            raise ValueError("Mục đích sử dụng không hợp lệ.")
        return sorted(set(v), key=list(PURPOSES).index)


def _batch_out(b: EnrichBatch, users: dict[int, str]) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "list_source": b.list_source,
        "purposes": b.purposes,
        "note": b.note,
        "file_name": b.file_name,
        "mst_count": b.mst_count,
        "new_count": b.new_count,
        "report": b.report,
        "created_by": users.get(b.created_by_id) if b.created_by_id else None,
        "created_at": _iso(b.created_at),
    }


def _user_names(db: Session, ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(db.execute(select(AdminUser.id, AdminUser.full_name).where(AdminUser.id.in_(ids))).all())


@router.get("/batches")
def list_batches(_: AdminUser = Depends(perm.require("batch.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(EnrichBatch).order_by(EnrichBatch.created_at.desc(), EnrichBatch.id.desc())).all()
    users = _user_names(db, [b.created_by_id for b in rows])
    return [_batch_out(b, users) for b in rows]


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int, _: AdminUser = Depends(perm.require("batch.read")), db: Session = Depends(get_db)):
    b = db.get(EnrichBatch, batch_id)
    if not b:
        raise HTTPException(404, "Không tìm thấy lô.")
    return _batch_out(b, _user_names(db, [b.created_by_id]))


@router.post("/batches/preview")
def preview_batch(body: FileIn, _: AdminUser = Depends(perm.require("batch.import")), db: Session = Depends(get_db)):
    """Kiểm tra file trước khi nhập: số dòng hợp lệ, trùng, sai định dạng (A01) — chưa ghi gì vào CSDL."""
    try:
        return importer.preview(db, body.file_name, body.data())
    except importer.ImportError_ as e:
        raise HTTPException(422, str(e)) from e


@router.post("/batches", status_code=201)
def create_batch(body: BatchIn, user: AdminUser = Depends(perm.require("batch.import")), db: Session = Depends(get_db)):
    try:
        b = importer.create_batch(
            db,
            user,
            name=body.name,
            list_source=body.list_source,
            purposes=body.purposes,
            note=body.note,
            file_name=body.file_name,
            data=body.data(),
        )
    except importer.ImportError_ as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    return _batch_out(b, {user.id: user.full_name})
