"""Hàng đợi thủ công (A10): nguồn có captcha → nhân viên xử lý theo lô, mỗi lần một MST và một form nhập.

Một việc được "giữ" cho người đang mở trong LOCK_MINUTES để hai người không làm trùng.
Giá trị nhân viên nhập là bằng chứng của NGUỒN (method "nhap_tay", trỏ về trang tra cứu) — không phải quyết định
biên tập, nên vẫn hợp nhất theo độ tin cậy nguồn như mọi bằng chứng khác.
"""

import hashlib
import json
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.enrich import sources
from app.enrich.apply import Origin, apply_facts
from app.enrich.connectors import registry
from app.enrich.connectors.base import CompanyFact, Facts, ManualField, PersonFact
from app.models import AdminUser
from app.models_enrich import COMPANY_FIELDS, CrawlJob, EnrichCompany, EnrichRun

LOCK_MINUTES = 15
SKIP_HOURS = 24

GENERIC_FIELDS = [
    ManualField("ten", "Tên doanh nghiệp"),
    ManualField("dia_chi", "Địa chỉ trụ sở", "textarea"),
    ManualField("trang_thai", "Tình trạng hoạt động"),
]


class ManualError(ValueError):
    pass


def _available(user: AdminUser):
    now = utcnow()
    return (
        CrawlJob.status == "manual",
        or_(CrawlJob.next_attempt_at.is_(None), CrawlJob.next_attempt_at <= now),
        or_(
            CrawlJob.handled_by_id.is_(None),
            CrawlJob.handled_by_id == user.id,
            CrawlJob.started_at < now - timedelta(minutes=LOCK_MINUTES),
        ),
    )


def counts(db: Session) -> list[dict]:
    rows = db.execute(
        select(CrawlJob.connector, func.count()).where(CrawlJob.status == "manual").group_by(CrawlJob.connector)
    ).all()
    srcs = sources.all_sources(db)
    return [{"connector": c, "name": srcs[c].name if c in srcs else c, "count": n} for c, n in rows]


def _fields(code: str) -> list[ManualField]:
    c = registry.get(code)
    return (c.manual_fields if c and c.manual_fields else GENERIC_FIELDS)


def task_out(db: Session, job: CrawlJob) -> dict:
    c = registry.get(job.connector)
    company = db.get(EnrichCompany, job.mst)
    current = {}
    if company:
        for k in COMPANY_FIELDS:
            v = getattr(company, k, None)
            if v not in (None, "", []):
                current[k] = v if not hasattr(v, "isoformat") else v.isoformat()
    remaining = db.scalar(select(func.count()).select_from(CrawlJob).where(CrawlJob.status == "manual", CrawlJob.connector == job.connector)) or 0
    run = db.get(EnrichRun, job.run_id) if job.run_id else None
    return {
        "job_id": job.id,
        "mst": job.mst,
        "connector": job.connector,
        "connector_name": sources.ensure(db, job.connector).name,
        "lookup_url": c.manual_url(job.mst) if c else "",
        "hint": (c.manual_hint(job.mst) if c else "") or job.error,
        "fields": [{"key": f.key, "label": f.label, "kind": f.kind, "options": f.options} for f in _fields(job.connector)],
        "current": current,
        "remaining": remaining,
        "run": {"id": run.id, "name": run.name} if run else None,
    }


def next_task(db: Session, user: AdminUser, connector: str = "", after_id: int = 0) -> dict | None:
    stmt = select(CrawlJob).where(*_available(user))
    if connector:
        stmt = stmt.where(CrawlJob.connector == connector)
    if after_id:
        stmt = stmt.where(CrawlJob.id != after_id)
    job = db.scalar(stmt.order_by((CrawlJob.handled_by_id == user.id).desc(), CrawlJob.id).limit(1))
    if not job:
        return None
    job.handled_by_id = user.id
    job.started_at = utcnow()
    db.commit()
    return task_out(db, job)


def submit(db: Session, user: AdminUser, job_id: int, action: str, values: dict, source_url: str) -> CrawlJob:
    job = db.get(CrawlJob, job_id)
    if not job or job.status != "manual":
        raise ManualError("Việc này đã được xử lý hoặc không còn trong hàng đợi.")
    if job.handled_by_id not in (None, user.id) and job.started_at and job.started_at > utcnow() - timedelta(minutes=LOCK_MINUTES):
        raise ManualError("Người khác đang xử lý MST này.")
    now = utcnow()
    if action == "skip":
        job.handled_by_id = None
        job.next_attempt_at = now + timedelta(hours=SKIP_HOURS)
        db.commit()
        return job
    if action == "not_found":
        job.status = "not_found"
        job.handled_by_id = user.id
        job.finished_at = now
        db.commit()
        return job
    if action != "save":
        raise ManualError("Thao tác không hợp lệ.")

    allowed = {f.key for f in _fields(job.connector)}
    clean = {k: str(v).strip() for k, v in (values or {}).items() if k in allowed and v is not None and str(v).strip()}
    if not clean:
        raise ManualError("Chưa nhập thông tin nào. Không tìm thấy trên nguồn thì bấm “Nguồn không có MST này”.")
    c = registry.get(job.connector)
    url = (source_url or "").strip() or (c.manual_url(job.mst) if c else "")
    if not url:
        raise ManualError("Ghi đường dẫn trang đã tra cứu.")
    src = sources.ensure(db, job.connector)
    excerpt = f"{user.full_name} tra cứu MST {job.mst} trên {src.name} lúc {now:%d/%m/%Y %H:%M} UTC"
    facts = Facts()
    for k, v in clean.items():
        if k == "nguoi_dai_dien":
            for name in [x.strip() for x in v.replace("\n", ";").split(";") if x.strip()]:
                facts.people.append(PersonFact(name, "Người đại diện theo pháp luật", excerpt))
        else:
            facts.company.append(CompanyFact(k, v, excerpt))
    h = hashlib.sha256(json.dumps({"mst": job.mst, "v": clean, "src": src.code, "at": now.isoformat()}, ensure_ascii=False).encode()).hexdigest()
    apply_facts(db, job.mst, facts, Origin(source=src, source_url=url, content_hash=h, method="nhap_tay", fetched_at=now, actor_id=user.id))
    job.status = "done"
    job.handled_by_id = user.id
    job.error = ""
    job.finished_at = now
    db.commit()
    return job
