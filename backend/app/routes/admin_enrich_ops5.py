"""API giai đoạn 5 — /api/admin/enrich/*: lọc nâng cao + bộ lọc đã lưu (C04, C05), xuất có kiểm soát (C08, C09),
báo cáo thị trường (C11), theo dõi + cảnh báo (C06), lịch tái thu thập (A12), công cụ tuân thủ (mục 10).
"""

import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.enrich import compliance, export, scheduler, search
from app.enrich import permissions as perm
from app.enrich import runner
from app.models import AdminUser
from app.models_enrich import (
    ALERT_KINDS,
    REQUIRED_FIELDS,
    EnrichAlert,
    EnrichCompany,
    SavedFilter,
    Watchlist,
    WatchItem,
)
from app.routes.admin_enrich import _iso, _user_names
from app.schemas import Line

router = APIRouter(prefix="/api/admin/enrich")


# ------------------------------------------------------------------ lọc nâng cao (C04, N03)


@router.get("/search/meta")
def search_meta(user: AdminUser = Depends(perm.require("a.read"))):
    return {**search.meta(), "export_columns": export.columns_for(user), "alert_kinds": ALERT_KINDS}


class SearchIn(BaseModel):
    definition: dict = Field(default_factory=dict)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


@router.post("/companies/search")
def search_companies(body: SearchIn, _: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    try:
        where = search.build(db, body.definition)
    except search.FilterError as e:
        raise HTTPException(422, str(e)) from e
    total = db.scalar(select(func.count()).select_from(EnrichCompany).where(where)) or 0
    rows = db.scalars(
        select(EnrichCompany).where(where).order_by(EnrichCompany.created_at.desc(), EnrichCompany.mst).offset((body.page - 1) * body.page_size).limit(body.page_size)
    ).all()
    return {
        "total": total,
        "items": [
            {
                "mst": c.mst, "ten": c.ten, "tinh": c.tinh, "trang_thai": c.trang_thai, "nganh_nghe": c.nganh_nghe, "ma_ck": c.ma_ck,
                "missing": [f for f in REQUIRED_FIELDS if getattr(c, f) is None], "updated_at": _iso(c.updated_at),
            }
            for c in rows
        ],
    }


# ------------------------------------------------------------------ bộ lọc đã lưu (C05)


class FilterIn(BaseModel):
    name: Line = Field(min_length=2, max_length=200)
    shared: bool = False
    definition: dict = Field(default_factory=dict)


def _filter_out(f: SavedFilter, users: dict, me: AdminUser) -> dict:
    return {
        "id": f.id, "name": f.name, "shared": f.shared, "definition": f.definition, "owner": users.get(f.owner_id),
        "mine": f.owner_id == me.id, "updated_at": _iso(f.updated_at),
    }


@router.get("/filters")
def list_filters(user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedFilter).where(or_(SavedFilter.owner_id == user.id, SavedFilter.shared.is_(True))).order_by(SavedFilter.name)).all()
    users = _user_names(db, [f.owner_id for f in rows])
    return [_filter_out(f, users, user) for f in rows]


def _check_filter(db: Session, d: dict) -> None:
    try:
        search.build(db, d)
    except search.FilterError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/filters", status_code=201)
def create_filter(body: FilterIn, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    _check_filter(db, body.definition)
    f = SavedFilter(name=body.name, shared=body.shared, definition=body.definition, owner_id=user.id)
    db.add(f)
    db.commit()
    return _filter_out(f, {user.id: user.full_name}, user)


def _own_filter(db: Session, fid: int, user: AdminUser) -> SavedFilter:
    f = db.get(SavedFilter, fid)
    if not f:
        raise HTTPException(404, "Không tìm thấy bộ lọc.")
    if f.owner_id != user.id and user.enrich_access != "quan_tri":
        raise HTTPException(403, "Chỉ người tạo (hoặc quản trị) được sửa / xoá bộ lọc này.")
    return f


@router.put("/filters/{fid}")
def update_filter(fid: int, body: FilterIn, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    f = _own_filter(db, fid, user)
    _check_filter(db, body.definition)
    f.name, f.shared, f.definition = body.name, body.shared, body.definition
    db.commit()
    return _filter_out(f, _user_names(db, [f.owner_id]), user)


@router.delete("/filters/{fid}", status_code=204)
def delete_filter(fid: int, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    db.delete(_own_filter(db, fid, user))
    db.commit()


# ------------------------------------------------------------------ xuất (C08, C09, T02, T04, T11) + báo cáo thị trường (C11)


class ExportIn(BaseModel):
    definition: dict = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    purpose: str
    include_inferred: bool = False


@router.post("/exports")
def create_export(body: ExportIn, request: Request, user: AdminUser = Depends(perm.require("a.export")), db: Session = Depends(get_db)):
    try:
        search.build(db, body.definition)
    except search.FilterError as e:
        raise HTTPException(422, str(e)) from e
    data, rec = export.export_companies(
        db, user, definition=body.definition, columns=body.columns, purpose=body.purpose, include_inferred=body.include_inferred, request=request
    )
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="xuat-{rec.id}-han-{rec.expires_on:%Y%m%d}.csv"',
            "Cache-Control": "no-store",
            "X-Export-Id": str(rec.id),
            "X-Export-Rows": str(rec.row_count),
            "X-Export-Blocked": str(rec.blocked_count),
        },
    )


@router.get("/exports/mine")
def my_exports(user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    return compliance.export_logs(db, user.id, limit=50)


@router.get("/reports/market")
def market(_: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    return export.market_report(db)


@router.get("/reports/market.csv")
def market_csv(user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    r = export.market_report(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Nhóm", "Giá trị", "Số doanh nghiệp"])
    for group, key in (("Tỉnh/thành", "by_tinh"), ("Ngành", "by_nganh"), ("Quy mô vốn", "by_von"), ("Tình trạng", "by_trang_thai")):
        for row in r[key]:
            w.writerow([group, row["key"], row["count"]])
    for f, n in r["coverage"].items():
        w.writerow(["Độ phủ trường", f, n])
    w.writerow(["Có người ra quyết định", "", r["decision_maker"]])
    w.writerow(["Tổng", "", r["total"]])
    return Response(content=("﻿" + buf.getvalue()).encode(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="bao-cao-thi-truong.csv"'})


# ------------------------------------------------------------------ theo dõi + cảnh báo (C06)


class WatchlistIn(BaseModel):
    name: Line = Field(min_length=2, max_length=200)
    shared: bool = False
    kinds: list[str] = Field(default_factory=list)
    email_digest: bool = False


def _wl_out(db: Session, w: Watchlist, users: dict, me: AdminUser) -> dict:
    n = db.scalar(select(func.count()).select_from(WatchItem).where(WatchItem.watchlist_id == w.id)) or 0
    return {"id": w.id, "name": w.name, "shared": w.shared, "kinds": w.kinds, "email_digest": w.email_digest, "owner": users.get(w.owner_id), "mine": w.owner_id == me.id, "count": n}


def _own_wl(db: Session, wid: int, user: AdminUser, write: bool = True) -> Watchlist:
    w = db.get(Watchlist, wid)
    if not w or (not w.shared and w.owner_id != user.id):
        raise HTTPException(404, "Không tìm thấy danh sách theo dõi.")
    if write and w.owner_id != user.id:
        raise HTTPException(403, "Chỉ người tạo được sửa danh sách này.")
    return w


@router.get("/watchlists")
def list_watchlists(user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Watchlist).where(or_(Watchlist.owner_id == user.id, Watchlist.shared.is_(True))).order_by(Watchlist.name)).all()
    users = _user_names(db, [w.owner_id for w in rows])
    return [_wl_out(db, w, users, user) for w in rows]


@router.post("/watchlists", status_code=201)
def create_watchlist(body: WatchlistIn, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    if any(k not in ALERT_KINDS for k in body.kinds):
        raise HTTPException(422, "Loại cảnh báo không hợp lệ.")
    w = Watchlist(name=body.name, shared=body.shared, kinds=body.kinds, email_digest=body.email_digest, owner_id=user.id)
    db.add(w)
    db.commit()
    return _wl_out(db, w, {user.id: user.full_name}, user)


@router.put("/watchlists/{wid}")
def update_watchlist(wid: int, body: WatchlistIn, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    w = _own_wl(db, wid, user)
    if any(k not in ALERT_KINDS for k in body.kinds):
        raise HTTPException(422, "Loại cảnh báo không hợp lệ.")
    w.name, w.shared, w.kinds, w.email_digest = body.name, body.shared, body.kinds, body.email_digest
    db.commit()
    return _wl_out(db, w, {user.id: user.full_name}, user)


@router.delete("/watchlists/{wid}", status_code=204)
def delete_watchlist(wid: int, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    db.delete(_own_wl(db, wid, user))
    db.commit()


@router.get("/watchlists/{wid}")
def get_watchlist(wid: int, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    w = _own_wl(db, wid, user, write=False)
    items = db.execute(
        select(WatchItem.mst, WatchItem.added_at, EnrichCompany.ten, EnrichCompany.ma_ck, EnrichCompany.trang_thai)
        .join(EnrichCompany, EnrichCompany.mst == WatchItem.mst)
        .where(WatchItem.watchlist_id == w.id)
        .order_by(EnrichCompany.ten_khong_dau)
    ).all()
    out = _wl_out(db, w, _user_names(db, [w.owner_id]), user)
    out["items"] = [{"mst": m, "added_at": _iso(a), "ten": t, "ma_ck": ck, "trang_thai": tt} for m, a, t, ck, tt in items]
    return out


class ItemsIn(BaseModel):
    msts: list[str] = Field(default_factory=list)
    definition: dict | None = None  # thêm mọi doanh nghiệp khớp bộ lọc


@router.post("/watchlists/{wid}/items")
def add_items(wid: int, body: ItemsIn, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    w = _own_wl(db, wid, user)
    msts = set(body.msts)
    if body.definition is not None:
        try:
            msts |= set(db.scalars(select(EnrichCompany.mst).where(search.build(db, body.definition)).limit(5001)))
        except search.FilterError as e:
            raise HTTPException(422, str(e)) from e
    if len(msts) > 5000:
        raise HTTPException(422, "Tối đa 5.000 doanh nghiệp mỗi lần thêm.")
    known = set(db.scalars(select(EnrichCompany.mst).where(EnrichCompany.mst.in_(msts)))) if msts else set()
    have = set(db.scalars(select(WatchItem.mst).where(WatchItem.watchlist_id == w.id)))
    new = known - have
    db.add_all([WatchItem(watchlist_id=w.id, mst=m) for m in new])
    db.commit()
    return {"added": len(new), "already": len(known & have), "unknown": len(msts - known)}


@router.delete("/watchlists/{wid}/items/{mst}", status_code=204)
def remove_item(wid: int, mst: str, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    w = _own_wl(db, wid, user)
    item = db.scalar(select(WatchItem).where(WatchItem.watchlist_id == w.id, WatchItem.mst == mst))
    if item:
        db.delete(item)
        db.commit()


@router.get("/alerts")
def list_alerts(unread: bool = False, limit: int = Query(100, ge=1, le=500), user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    stmt = select(EnrichAlert, EnrichCompany.ten).join(EnrichCompany, EnrichCompany.mst == EnrichAlert.mst, isouter=True).where(EnrichAlert.user_id == user.id)
    if unread:
        stmt = stmt.where(EnrichAlert.read_at.is_(None))
    rows = db.execute(stmt.order_by(EnrichAlert.id.desc()).limit(limit)).all()
    n_unread = db.scalar(select(func.count()).select_from(EnrichAlert).where(EnrichAlert.user_id == user.id, EnrichAlert.read_at.is_(None))) or 0
    return {
        "unread": n_unread,
        "items": [
            {"id": a.id, "mst": a.mst, "ten": ten, "kind": a.kind, "kind_name": ALERT_KINDS.get(a.kind, a.kind), "summary": a.summary, "read": a.read_at is not None, "created_at": _iso(a.created_at), "watchlist_id": a.watchlist_id}
            for a, ten in rows
        ],
    }


class ReadIn(BaseModel):
    ids: list[int] = Field(default_factory=list)
    all: bool = False


@router.post("/alerts/read")
def mark_read(body: ReadIn, user: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    stmt = update(EnrichAlert).where(EnrichAlert.user_id == user.id, EnrichAlert.read_at.is_(None))
    if not body.all:
        stmt = stmt.where(EnrichAlert.id.in_(body.ids or [0]))
    n = db.execute(stmt.values(read_at=utcnow())).rowcount
    db.commit()
    return {"updated": n or 0}


# ------------------------------------------------------------------ lịch tái thu thập (A12)


@router.get("/ops/schedule")
def schedule_info(_: AdminUser = Depends(perm.require("run.read")), db: Session = Depends(get_db)):
    return {"recrawl": {**scheduler.DEFAULT_RECRAWL, **runner.get_setting(db, "recrawl")}, "file_reminders": scheduler.file_reminders(db)}


class RecrawlIn(BaseModel):
    enabled: bool | None = None
    daily_limit: int | None = Field(None, ge=1, le=50_000)


@router.put("/ops/schedule")
def set_schedule(body: RecrawlIn, user: AdminUser = Depends(perm.require("source.manage")), db: Session = Depends(get_db)):
    v = {k: x for k, x in body.model_dump().items() if x is not None}
    return {"recrawl": {**scheduler.DEFAULT_RECRAWL, **runner.set_setting(db, "recrawl", v, user)}}


@router.post("/ops/recrawl-now")
def recrawl_now(_: AdminUser = Depends(perm.require("run.manage")), db: Session = Depends(get_db)):
    from app.routes.admin_enrich_ops import _kick

    created = scheduler.schedule_recrawl(db)
    if created:
        _kick()
    return {"runs": created}


# ------------------------------------------------------------------ tuân thủ (mục 10)


def _cerr(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except compliance.ComplianceError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/compliance/optouts")
def optouts(q: str = "", _: AdminUser = Depends(perm.require("compliance.read")), db: Session = Depends(get_db)):
    return {"kinds": compliance.OPTOUT_KINDS, "items": compliance.list_optouts(db, q)}


class OptOutIn(BaseModel):
    kind: str
    value: str = Field(min_length=1, max_length=200)
    reason: str = Field("", max_length=2000)


@router.post("/compliance/optouts", status_code=201)
def add_optout(body: OptOutIn, user: AdminUser = Depends(perm.require("compliance.manage")), db: Session = Depends(get_db)):
    o = _cerr(compliance.add_optout, db, user, body.kind, body.value, body.reason)
    return {"id": o.id, "kind": o.kind, "value": o.value}


@router.get("/compliance/subjects")
def find_subjects(request: Request, q: str = Query(..., max_length=100), user: AdminUser = Depends(perm.require("compliance.manage")), db: Session = Depends(get_db)):
    return _cerr(compliance.find_subject, db, user, q, request)


@router.get("/compliance/subjects/{pid}/report")
def subject_report(pid: int, request: Request, download: bool = False, user: AdminUser = Depends(perm.require("compliance.manage")), db: Session = Depends(get_db)):
    rep = compliance.subject_report(db, user, pid, request)
    if download:
        return Response(
            content=json.dumps(rep, ensure_ascii=False, indent=2).encode(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="du-lieu-ca-nhan-{pid}-{date.today():%Y%m%d}.json"', "Cache-Control": "no-store"},
        )
    return rep


class EraseIn(BaseModel):
    mode: str = Field(pattern="^(hide|delete)$")
    reason: str = Field(min_length=3, max_length=2000)


@router.post("/compliance/subjects/{pid}/erase")
def subject_erase(pid: int, body: EraseIn, request: Request, user: AdminUser = Depends(perm.require("compliance.manage")), db: Session = Depends(get_db)):
    return _cerr(compliance.subject_erase, db, user, pid, body.mode, body.reason, request)


@router.get("/compliance/retention")
def retention(_: AdminUser = Depends(perm.require("compliance.read")), db: Session = Depends(get_db)):
    return {"months": compliance.get_settings().enrich_retention_months, "items": compliance.retention_due(db)}


@router.get("/compliance/dpia")
def dpia(download: bool = False, _: AdminUser = Depends(perm.require("compliance.read")), db: Session = Depends(get_db)):
    rep = compliance.dpia(db)
    if download:
        return Response(content=json.dumps(rep, ensure_ascii=False, indent=2).encode(), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="dpia-{date.today():%Y%m%d}.json"'})
    return rep


@router.get("/compliance/access-logs")
def access_logs(
    action: str = "", user_id: int | None = None, since: date | None = None, _: AdminUser = Depends(perm.require("compliance.read")), db: Session = Depends(get_db)
):
    return compliance.access_logs(db, action, user_id, since)


@router.get("/compliance/exports")
def export_logs(_: AdminUser = Depends(perm.require("compliance.read")), db: Session = Depends(get_db)):
    return compliance.export_logs(db)
