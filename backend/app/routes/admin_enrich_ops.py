"""API vận hành thu thập — /api/admin/enrich/* (giai đoạn 2).

Nguồn & cấu hình (A04, A07, A13) · vòng thu thập + tiến trình (A06, A11) · nhật ký tốc độ theo tên miền (A08)
· hàng đợi thủ công (A10) · nhập file nguồn chính thức (A03, nợ thuế, đấu thầu).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.enrich import manual, official, runner, sources
from app.enrich import permissions as perm
from app.enrich.connectors import registry
from app.enrich.importer import ImportError_
from app.models import AdminUser
from app.models_enrich import CrawlJob, EnrichBatch, EnrichImport, EnrichRun, EnrichSource
from app.routes.admin_enrich import FileIn, _iso, _user_names
from app.schemas import Line

router = APIRouter(prefix="/api/admin/enrich")


def _kick() -> None:
    """Giao việc ngay (không chờ beat 1 phút). Redis lỗi thì beat sẽ làm sau.

    Gửi trong luồng nền để request không phải chờ kết nối Redis (vd. Redis chậm / chưa chạy trên máy dev).
    """
    import threading

    from app.config import get_settings
    from app.worker import enqueue, enrich_dispatch_task

    if get_settings().celery_eager:  # test: chạy ngay, tuần tự
        enqueue(enrich_dispatch_task)
    else:
        threading.Thread(target=enqueue, args=(enrich_dispatch_task,), daemon=True).start()


# ------------------------------------------------------------------ nguồn (A04, A13, T12)


def _source_out(db: Session, s: EnrichSource) -> dict:
    c = registry.get(s.code)
    bad, total = runner.error_rate(db, s.code)
    return {
        "code": s.code,
        "name": s.name,
        "kind": c.kind if c else (s.config or {}).get("kind", "internal"),
        "domain": c.domain if c else "",
        "trust": s.trust,
        "enabled": s.enabled,
        "legal_basis": s.legal_basis,
        "min_interval_s": sources.setting(s, "min_interval_s"),
        "timeout_s": sources.setting(s, "timeout_s", 20),
        "max_retries": sources.setting(s, "max_retries", 3),
        "recrawl_days": sources.setting(s, "recrawl_days", 90),
        "paused_reason": s.paused_reason,
        "paused_at": _iso(s.paused_at),
        "errors_last_hour": bad,
        "requests_last_hour": total,
        "updated_at": _iso(s.updated_at),
    }


@router.get("/sources")
def list_sources(_: AdminUser = Depends(perm.require("a.read")), db: Session = Depends(get_db)):
    return [_source_out(db, s) for s in sources.ensure_all(db)]


class SourceIn(BaseModel):
    enabled: bool | None = None
    trust: float | None = Field(None, ge=0, le=1)
    legal_basis: str | None = Field(None, max_length=5000)
    min_interval_s: float | None = Field(None, ge=sources.MIN_INTERVAL_S, le=3600)
    timeout_s: int | None = Field(None, ge=1, le=300)
    max_retries: int | None = Field(None, ge=0, le=10)
    recrawl_days: int | None = Field(None, ge=1, le=3650)


@router.patch("/sources/{code}")
def update_source(code: str, body: SourceIn, _: AdminUser = Depends(perm.require("source.manage")), db: Session = Depends(get_db)):
    try:
        s = sources.ensure(db, code)
    except KeyError as e:
        raise HTTPException(404, "Không có nguồn này.") from e
    if body.trust is not None:
        s.trust = body.trust
    if body.legal_basis is not None:
        s.legal_basis = body.legal_basis.strip()
    cfg = dict(s.config or {})
    for k in ("min_interval_s", "timeout_s", "max_retries", "recrawl_days"):
        v = getattr(body, k)
        if v is not None:
            cfg[k] = v
    s.config = cfg
    if body.enabled is True:
        why = sources.can_enable(s)
        if why:
            raise HTTPException(422, why)
        s.enabled = True
        s.paused_reason = ""
        s.paused_at = None
    elif body.enabled is False:
        s.enabled = False
    elif not s.legal_basis:
        s.enabled = False  # xoá cơ sở pháp lý thì tắt luôn (T12)
    db.commit()
    if s.enabled:
        _kick()
    return _source_out(db, s)


@router.post("/sources/{code}/reparse")
def reparse(code: str, _: AdminUser = Depends(perm.require("source.manage")), db: Session = Depends(get_db)):
    try:
        return runner.reparse_source(db, code)
    except runner.RunError as e:
        raise HTTPException(422, str(e)) from e


# ------------------------------------------------------------------ cấu hình vận hành (A07)


class OpsIn(BaseModel):
    paused: bool | None = None
    pause_reason: str = Field("", max_length=300)
    window_enabled: bool | None = None
    window_start: int | None = Field(None, ge=0, le=23)
    window_end: int | None = Field(None, ge=0, le=23)
    per_connector: int | None = Field(None, ge=1, le=20)


def _ops_out(db: Session) -> dict:
    ok, why = runner.can_run_now(db)
    return {
        "paused": runner.get_setting(db, "paused"),
        "window": runner.get_setting(db, "window"),
        "max_running": runner.get_setting(db, "max_running"),
        "running_now": ok,
        "blocked_reason": why,
    }


@router.get("/ops")
def get_ops(_: AdminUser = Depends(perm.require("run.read")), db: Session = Depends(get_db)):
    return _ops_out(db)


@router.put("/ops")
def set_ops(body: OpsIn, user: AdminUser = Depends(perm.require("source.manage")), db: Session = Depends(get_db)):
    if body.paused is not None:
        runner.set_setting(db, "paused", {"on": body.paused, "reason": body.pause_reason.strip() if body.paused else ""}, user)
    w = {k: v for k, v in {"enabled": body.window_enabled, "start": body.window_start, "end": body.window_end}.items() if v is not None}
    if w:
        runner.set_setting(db, "window", w, user)
    if body.per_connector is not None:
        runner.set_setting(db, "max_running", {"per_connector": body.per_connector}, user)
    if body.paused is False:
        _kick()
    return _ops_out(db)


@router.get("/ops/domains")
def domain_log(hours: int = Query(24, ge=1, le=24 * 30), _: AdminUser = Depends(perm.require("run.read")), db: Session = Depends(get_db)):
    """A08: bằng chứng không tên miền nào bị gọi dày hơn giới hạn."""
    return {"min_interval_s": sources.MIN_INTERVAL_S, "domains": runner.domain_gaps(db, hours)}


# ------------------------------------------------------------------ vòng thu thập (A06, A11)


def _run_out(db: Session, r: EnrichRun, users: dict[int, str], detail: bool = False) -> dict:
    prog = runner.progress(db, r)
    totals = {k: sum(c[k] for c in prog["connectors"]) for k in ("total", "done", "not_found", "failed", "manual", "skipped", "remaining")}
    out = {
        "id": r.id,
        "name": r.name,
        "connectors": prog["connectors"],
        "batch": None,
        "status": r.status,
        "totals": totals,
        "eta_seconds": prog["eta_seconds"],
        "created_by": users.get(r.created_by_id) if r.created_by_id else None,
        "created_at": _iso(r.created_at),
        "finished_at": _iso(r.finished_at),
    }
    if r.batch_id:
        b = db.get(EnrichBatch, r.batch_id)
        out["batch"] = {"id": r.batch_id, "name": b.name if b else ""}
    if detail:
        out["errors"] = [
            {"mst": j.mst, "connector": j.connector, "status": j.status, "attempts": j.attempts, "error": j.error, "at": _iso(j.finished_at or j.started_at)}
            for j in db.scalars(
                select(CrawlJob)
                .where(CrawlJob.run_id == r.id, CrawlJob.error != "")
                .order_by(CrawlJob.id.desc())
                .limit(50)
            )
        ]
    return out


@router.get("/runs")
def list_runs(_: AdminUser = Depends(perm.require("run.read")), db: Session = Depends(get_db)):
    runs = db.scalars(select(EnrichRun).order_by(EnrichRun.id.desc()).limit(50)).all()
    users = _user_names(db, [r.created_by_id for r in runs])
    return {"ops": _ops_out(db), "runs": [_run_out(db, r, users) for r in runs]}


@router.get("/runs/{run_id}")
def get_run(run_id: int, _: AdminUser = Depends(perm.require("run.read")), db: Session = Depends(get_db)):
    r = db.get(EnrichRun, run_id)
    if not r:
        raise HTTPException(404, "Không tìm thấy vòng thu thập.")
    return _run_out(db, r, _user_names(db, [r.created_by_id]), detail=True)


class RunIn(BaseModel):
    name: Line = Field(min_length=2, max_length=200)
    connectors: list[str] = Field(min_length=1)
    batch_id: int | None = None


@router.post("/runs", status_code=201)
def create_run(body: RunIn, user: AdminUser = Depends(perm.require("run.manage")), db: Session = Depends(get_db)):
    try:
        r = runner.create_run(db, user, body.name, body.connectors, body.batch_id)
    except runner.RunError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    _kick()
    return _run_out(db, r, {user.id: user.full_name})


class RunStatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _s(cls, v: str) -> str:
        if v not in ("running", "paused", "cancelled"):
            raise ValueError("Trạng thái không hợp lệ.")
        return v


@router.post("/runs/{run_id}/status")
def set_run_status(run_id: int, body: RunStatusIn, user: AdminUser = Depends(perm.require("run.manage")), db: Session = Depends(get_db)):
    r = db.get(EnrichRun, run_id)
    if not r:
        raise HTTPException(404, "Không tìm thấy vòng thu thập.")
    if r.status in ("done", "cancelled"):
        raise HTTPException(409, "Vòng này đã kết thúc.")
    runner.set_run_status(db, r, body.status)
    if body.status == "running":
        _kick()
    return _run_out(db, r, _user_names(db, [r.created_by_id]))


# ------------------------------------------------------------------ hàng đợi thủ công (A10)


@router.get("/manual")
def manual_overview(_: AdminUser = Depends(perm.require("manual.work")), db: Session = Depends(get_db)):
    return {"queues": manual.counts(db)}


@router.get("/manual/next")
def manual_next(
    connector: str = "",
    after: int = 0,
    user: AdminUser = Depends(perm.require("manual.work")),
    db: Session = Depends(get_db),
):
    return {"task": manual.next_task(db, user, connector, after)}


class ManualIn(BaseModel):
    action: str = Field(pattern="^(save|not_found|skip)$")
    values: dict[str, str] = Field(default_factory=dict)
    source_url: str = Field("", max_length=1000)


@router.post("/manual/{job_id}")
def manual_submit(job_id: int, body: ManualIn, user: AdminUser = Depends(perm.require("manual.work")), db: Session = Depends(get_db)):
    try:
        job = manual.submit(db, user, job_id, body.action, body.values, body.source_url)
    except manual.ManualError as e:
        raise HTTPException(422, str(e)) from e
    return {"job_id": job.id, "status": job.status}


# ------------------------------------------------------------------ nhập file nguồn chính thức


class ImportPreviewIn(FileIn):
    kind: str

    @field_validator("kind")
    @classmethod
    def _k(cls, v: str) -> str:
        if v not in official.KINDS:
            raise ValueError("Loại nguồn không hợp lệ.")
        return v


class ImportIn(ImportPreviewIn):
    source_url: Line = Field(min_length=3, max_length=1000)
    data_date: date | None = None
    note: str = Field("", max_length=5000)


def _import_out(i: EnrichImport, users: dict[int, str]) -> dict:
    return {
        "id": i.id,
        "kind": i.source_code,
        "kind_name": official.KINDS.get(i.source_code, i.source_code),
        "file_name": i.file_name,
        "source_url": i.source_url,
        "data_date": i.data_date.isoformat() if i.data_date else None,
        "note": i.note,
        "report": i.report,
        "created_by": users.get(i.created_by_id) if i.created_by_id else None,
        "created_at": _iso(i.created_at),
    }


@router.get("/imports")
def list_imports(_: AdminUser = Depends(perm.require("data.import")), db: Session = Depends(get_db)):
    rows = db.scalars(select(EnrichImport).order_by(EnrichImport.id.desc()).limit(100)).all()
    users = _user_names(db, [i.created_by_id for i in rows])
    return {"kinds": official.KINDS, "items": [_import_out(i, users) for i in rows]}


@router.post("/imports/preview")
def preview_import(body: ImportPreviewIn, _: AdminUser = Depends(perm.require("data.import")), db: Session = Depends(get_db)):
    try:
        return official.preview(db, body.kind, body.file_name, body.data())
    except ImportError_ as e:
        raise HTTPException(422, str(e)) from e


@router.post("/imports", status_code=201)
def create_import(body: ImportIn, user: AdminUser = Depends(perm.require("data.import")), db: Session = Depends(get_db)):
    try:
        imp = official.import_file(
            db,
            user,
            kind=body.kind,
            file_name=body.file_name,
            data=body.data(),
            source_url=body.source_url,
            data_date=body.data_date,
            note=body.note,
        )
    except ImportError_ as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    return _import_out(imp, {user.id: user.full_name})


# ------------------------------------------------------------------ tổng quan việc cần làm


@router.get("/ops/summary")
def ops_summary(_: AdminUser = Depends(perm.require("run.read")), db: Session = Depends(get_db)):
    rows = db.execute(select(CrawlJob.status, func.count()).group_by(CrawlJob.status)).all()
    return {"jobs": dict(rows), "at": _iso(utcnow())}
