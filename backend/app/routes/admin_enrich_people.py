"""API người (kho B) — /api/admin/enrich/* (giai đoạn 4).

Hồ sơ người (C02), đồ thị quan hệ (C03) + xuất danh sách bên liên quan, cặp nghi trùng (B06), gộp / tách / hoàn tác (B07),
nhập MST cá nhân nội bộ, suy luận email (B10). Mọi đọc / ghi kho B đi qua app/enrich/khob.py hoặc people.py và có nhật ký.
"""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.enrich import emails, khob, people
from app.enrich import permissions as perm
from app.models import AdminUser
from app.models_enrich import PURPOSES
from app.routes.admin_enrich import FileIn, _iso
from app.schemas import Line

router = APIRouter(prefix="/api/admin/enrich")


@router.get("/persons/{person_id}")
def get_person(person_id: int, request: Request, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    return khob.person_profile(db, user, person_id, request)


@router.get("/persons/{person_id}/graph")
def person_graph(person_id: int, request: Request, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    return khob.person_graph(db, user, person_id, request)


@router.get("/persons/{person_id}/related.csv")
def related_csv(
    person_id: int,
    request: Request,
    purpose: str = Query(...),
    include_inferred: bool = False,
    user: AdminUser = Depends(perm.require("a.read")),
    db: Session = Depends(get_db),
):
    if purpose not in PURPOSES:
        raise HTTPException(422, "Khai mục đích sử dụng của bản xuất.")
    rows = khob.related_rows(db, user, person_id, purpose, include_inferred, request)
    buf = io.StringIO()
    cols = ["nguoi", "nguoi_dang_xem", "chuc_danh", "dang_giu", "doanh_nghiep", "mst_doanh_nghiep", "lien_he_cong_viec"]
    heads = ["Người", "Người đang xem", "Chức danh", "Đang giữ", "Doanh nghiệp", "MST doanh nghiệp", "Liên hệ công việc"]
    w = csv.writer(buf)
    w.writerow(heads)
    for r in rows:
        w.writerow([r[c] for c in cols])
    return Response(
        content="﻿" + buf.getvalue(),  # BOM để Excel đọc đúng tiếng Việt
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ben-lien-quan-{person_id}.csv"', "Cache-Control": "no-store"},
    )


# ------------------------------------------------------------------ nghi trùng, gộp, tách, hoàn tác


@router.get("/merge-candidates")
def list_candidates(request: Request, status: str = "pending", user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    if status not in ("pending", "merged", "rejected"):
        raise HTTPException(422, "Trạng thái không hợp lệ.")
    return khob.merge_candidates(db, user, status, request=request)


class CandidateIn(BaseModel):
    action: str = Field(pattern="^(merge|reject)$")
    keep: str = Field("a", pattern="^(a|b)$")


@router.post("/merge-candidates/{cand_id}")
def decide_candidate(cand_id: int, body: CandidateIn, user: AdminUser = Depends(perm.require("people.manage")), db: Session = Depends(get_db)):
    try:
        c = people.decide_candidate(db, user, cand_id, body.action, body.keep)
    except people.PeopleError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    return {"id": c.id, "status": c.status}


def _op_out(op) -> dict:
    return {"id": op.id, "op": op.op, "person_id": op.person_id, "other_person_id": op.other_person_id, "created_at": _iso(op.created_at), "undone_at": _iso(op.undone_at)}


class MergeIn(BaseModel):
    keep_id: int
    drop_id: int
    note: str = Field("", max_length=2000)


@router.post("/persons/merge")
def merge_persons(body: MergeIn, user: AdminUser = Depends(perm.require("people.manage")), db: Session = Depends(get_db)):
    try:
        return _op_out(people.merge(db, user, body.keep_id, body.drop_id, body.note))
    except people.PeopleError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e


class SplitIn(BaseModel):
    role_ids: list[int] = Field(min_length=1)
    note: str = Field("", max_length=2000)


@router.post("/persons/{person_id}/split")
def split_person(person_id: int, body: SplitIn, user: AdminUser = Depends(perm.require("people.manage")), db: Session = Depends(get_db)):
    try:
        return _op_out(people.split(db, user, person_id, body.role_ids, body.note))
    except people.PeopleError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e


@router.post("/entity-ops/{op_id}/undo")
def undo_op(op_id: int, user: AdminUser = Depends(perm.require("people.manage")), db: Session = Depends(get_db)):
    try:
        return _op_out(people.undo(db, user, op_id))
    except people.PeopleError as e:
        db.rollback()
        raise HTTPException(409, str(e)) from e


# ------------------------------------------------------------------ nhập MST cá nhân, suy luận email


class PersonalMstIn(FileIn):
    source_note: Line = Field(min_length=3, max_length=500)
    confirmed: bool = False


@router.post("/persons/import-mst")
def import_personal_mst(body: PersonalMstIn, user: AdminUser = Depends(perm.require("people.manage")), db: Session = Depends(get_db)):
    try:
        return people.import_personal_mst(db, user, file_name=body.file_name, data=body.data(), source_note=body.source_note, confirmed=body.confirmed)
    except people.PeopleError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e


class InferIn(BaseModel):
    mst: str = ""


@router.post("/emails/infer")
def infer_emails(body: InferIn, user: AdminUser = Depends(perm.require("people.manage")), db: Session = Depends(get_db)):
    """B10: suy luận email cho người ra quyết định — một doanh nghiệp, hoặc mọi doanh nghiệp có tên miền."""
    if body.mst:
        return emails.infer_company(db, body.mst, user.id)
    return emails.infer_all(db, user.id)
