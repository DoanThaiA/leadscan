"""API quản trị tuyển dụng: đăng / sửa bài tuyển dụng, xem và xử lý hồ sơ ứng viên."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import current_user, require_admin
from app.config import get_settings
from app.db import get_db, utcnow
from app.models import APPLICATION_STATUSES, JOB_STATUSES, JOB_TYPES, AdminUser, JobApplication, JobPost
from app.schemas_jobs import ApplicationAdminIn, ApplicationOut, CoverInitIn, JobIn, JobOut, slugify
from app.services import cv_files, job_covers
from app.services.notify import mail_provider, recruit_inbox
from app.services.storage import StorageError
from app.worker import deliver_job_application

router = APIRouter(prefix="/api/admin")


def _get_job(db: Session, jid: int) -> JobPost:
    j = db.get(JobPost, jid)
    if not j:
        raise HTTPException(404, "Không tìm thấy bài tuyển dụng.")
    return j


def _get_app(db: Session, aid: int) -> JobApplication:
    a = db.get(JobApplication, aid)
    if not a:
        raise HTTPException(404, "Không tìm thấy hồ sơ.")
    return a


def _job_out(db: Session, j: JobPost) -> dict:
    d = JobOut.model_validate(j).model_dump(mode="json")
    d["applications"] = db.scalar(select(func.count()).where(JobApplication.job_id == j.id)) or 0
    return d


def _unique_slug(db: Session, wanted: str, title: str, exclude_id: int | None = None) -> str:
    base = wanted or slugify(title) or "vi-tri"
    slug, n = base, 2
    while True:
        stmt = select(JobPost.id).where(JobPost.slug == slug)
        if exclude_id:
            stmt = stmt.where(JobPost.id != exclude_id)
        if not db.scalar(stmt):
            return slug
        slug, n = f"{base}-{n}", n + 1


def _apply(db: Session, j: JobPost, body: JobIn) -> None:
    data = body.model_dump()
    data["slug"] = _unique_slug(db, data["slug"], data["title"], exclude_id=j.id)
    for f, v in data.items():
        setattr(j, f, v)
    if j.status == "published" and not j.published_at:
        j.published_at = utcnow()


# ------------------------------------------------------------------ bài tuyển dụng


@router.post("/jobs/covers/init", status_code=201)
def cover_init(body: CoverInitIn, _: AdminUser = Depends(current_user)):
    """Ảnh bìa: cấp link PUT ký sẵn để trình duyệt tải thẳng lên R2."""
    return job_covers.init_upload(body.filename, body.size)


@router.post("/jobs/covers/{upload_id}/complete")
def cover_complete(upload_id: str, _: AdminUser = Depends(current_user)):
    """Ảnh bìa đã lên R2 → kiểm tra, chuẩn hoá WebP → trả đường dẫn công khai để lưu vào bài."""
    return job_covers.complete_upload(upload_id)


@router.get("/jobs/meta")
def meta(_: AdminUser = Depends(current_user)):
    cfg = get_settings()
    return {
        "statuses": JOB_STATUSES,
        "types": JOB_TYPES,
        "application_statuses": APPLICATION_STATUSES,
        "recruit_email": recruit_inbox(cfg),  # hộp thư mặc định nhận hồ sơ ("" = chưa cấu hình)
        "mail_ready": bool(mail_provider(cfg)),  # đã cấu hình Resend/SMTP chưa
        "cv_max_mb": cfg.apply_cv_max_mb,
        "storage_ready": cv_files.enabled(),  # đã cấu hình Cloudflare R2 (nhận file CV) chưa
    }


@router.get("/jobs")
def list_jobs(status: str = "", q: str = Query("", max_length=100), _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(JobPost)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(JobPost.title.ilike(like), JobPost.department.ilike(like), JobPost.location.ilike(like)))
    sub = stmt.subquery()
    counts = dict(db.execute(select(sub.c.status, func.count()).group_by(sub.c.status)).all())
    if status:
        stmt = stmt.where(JobPost.status == status)
    jobs = db.scalars(stmt.order_by(JobPost.updated_at.desc(), JobPost.id.desc())).all()

    app_counts = {
        jid: (total, new)
        for jid, total, new in db.execute(
            select(
                JobApplication.job_id,
                func.count(),
                func.sum(case((JobApplication.status == "new", 1), else_=0)),
            ).group_by(JobApplication.job_id)
        ).all()
    }
    items = []
    for j in jobs:
        total, new = app_counts.get(j.id, (0, 0))
        items.append(
            {
                "id": j.id,
                "slug": j.slug,
                "status": j.status,
                "title": j.title,
                "department": j.department,
                "location": j.location,
                "employment_type": j.employment_type,
                "salary": j.salary,
                "deadline": j.deadline.isoformat() if j.deadline else None,
                "applications": total,
                "applications_new": int(new or 0),
                "updated_at": j.updated_at.isoformat() + "Z",
            }
        )
    return {"items": items, "counts": counts}


@router.post("/jobs", status_code=201)
def create_job(body: JobIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    j = JobPost(created_by_id=user.id)
    _apply(db, j, body)
    db.add(j)
    db.commit()
    db.refresh(j)
    return _job_out(db, j)


@router.get("/jobs/{jid}")
def get_job(jid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _job_out(db, _get_job(db, jid))


@router.put("/jobs/{jid}")
def update_job(jid: int, body: JobIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    j = _get_job(db, jid)
    _apply(db, j, body)
    db.commit()
    db.refresh(j)
    return _job_out(db, j)


@router.delete("/jobs/{jid}", status_code=204)
def delete_job(jid: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Xoá bài; hồ sơ đã nhận vẫn giữ (kèm tên vị trí). Muốn ẩn bài mà giữ link thì chuyển "Đã đóng"."""
    j = _get_job(db, jid)
    # tự gỡ liên kết (SQLite khi dev không bật khoá ngoại nên ON DELETE SET NULL không chạy)
    db.execute(update(JobApplication).where(JobApplication.job_id == j.id).values(job_id=None))
    db.delete(j)
    db.commit()


# ------------------------------------------------------------------ hồ sơ ứng tuyển


def _app_out(a: JobApplication) -> dict:
    d = ApplicationOut.model_validate(a).model_dump(mode="json")
    d["job_slug"] = a.job.slug if a.job else None
    return d


@router.get("/job-applications")
def list_applications(
    job_id: int | None = None,
    status: str = "",
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(JobApplication)
    if job_id:
        stmt = stmt.where(JobApplication.job_id == job_id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                JobApplication.full_name.ilike(like),
                JobApplication.email.ilike(like),
                JobApplication.phone.ilike(like),
                JobApplication.job_title.ilike(like),
            )
        )
    sub = stmt.subquery()
    counts = dict(db.execute(select(sub.c.status, func.count()).group_by(sub.c.status)).all())
    if status:
        stmt = stmt.where(JobApplication.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(JobApplication.created_at.desc(), JobApplication.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"total": total, "page": page, "page_size": page_size, "counts": counts, "items": [_app_out(a) for a in rows]}


@router.get("/job-applications/{aid}")
def get_application(aid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _app_out(_get_app(db, aid))


@router.patch("/job-applications/{aid}")
def update_application(aid: int, body: ApplicationAdminIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    a = _get_app(db, aid)
    if body.status is not None:
        a.status = body.status
    if body.note is not None:
        a.note = body.note.strip()
    db.commit()
    db.refresh(a)
    return _app_out(a)


@router.get("/job-applications/{aid}/cv")
def download_cv(aid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Chuyển tới link tải ký sẵn trên R2 (hết hạn sau vài phút) — bucket riêng tư, không có link công khai."""
    a = _get_app(db, aid)
    if not a.cv_key:
        raise HTTPException(404, "Hồ sơ không có file CV.")
    try:
        url = cv_files.download_url(a.cv_key, a.cv_filename or "cv")
    except StorageError as e:
        raise HTTPException(503, "Chưa kết nối được kho lưu trữ CV (Cloudflare R2).") from e
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


@router.post("/job-applications/{aid}/resend")
async def resend_application(aid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Gửi lại hồ sơ về hộp thư tuyển dụng ngay (đồng bộ để admin biết kết quả)."""
    a = _get_app(db, aid)
    cfg = get_settings()
    if not recruit_inbox(cfg, a.job):
        raise HTTPException(400, "Chưa cấu hình email nhận hồ sơ (LEADSCAN_RECRUIT_EMAIL hoặc email riêng của bài).")
    if not mail_provider(cfg):
        raise HTTPException(400, "Chưa cấu hình gửi email (Resend hoặc SMTP).")
    a.email_sent_at = None
    db.commit()
    if not await run_in_threadpool(deliver_job_application, aid):
        raise HTTPException(502, "Gửi email chưa thành công (lỗi gửi mail hoặc không lấy được CV trên R2), vui lòng thử lại sau.")
    db.refresh(a)
    return _app_out(a)


@router.delete("/job-applications/{aid}", status_code=204)
def delete_application(aid: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    a = _get_app(db, aid)
    key = a.cv_key
    db.delete(a)
    db.commit()
    cv_files.purge([key])  # xoá luôn file CV trên R2
