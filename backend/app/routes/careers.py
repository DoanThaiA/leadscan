"""API công khai trang tuyển dụng /tuyen-dung: danh sách vị trí, chi tiết, gửi hồ sơ ứng tuyển."""

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.db import new_session
from app.models import JobApplication, JobPost
from app.schemas_jobs import ApplyIn, JobCard, JobPublic, decode_cv
from app.security import add_hit, client_ip, origin_allowed, rate_limited, sha256
from app.services import cv_files
from app.services.storage import StorageError
from app.worker import enqueue_job_application

log = logging.getLogger("leadscan.careers")

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

router = APIRouter(prefix="/api/jobs")


def today_vn():
    return datetime.now(VN_TZ).date()


def is_open(j: JobPost) -> bool:
    """Còn nhận hồ sơ: đang tuyển và chưa quá hạn nộp (hạn tính hết ngày theo giờ Việt Nam)."""
    return j.status == "published" and (j.deadline is None or j.deadline >= today_vn())


def _fail(status: int, message: str, fields: dict | None = None) -> JSONResponse:
    return JSONResponse({"ok": False, "message": message, "fields": fields or {}}, status_code=status, headers={"Cache-Control": "no-store"})


def _get_public(db: Session, slug: str) -> JobPost:
    j = db.scalar(select(JobPost).where(JobPost.slug == slug, JobPost.status != "draft"))
    if not j:
        raise HTTPException(404, "Không tìm thấy vị trí tuyển dụng.")
    return j


@router.get("")
def list_jobs():
    """Các vị trí đang mở, mới đăng trước."""
    with new_session() as db:
        rows = db.scalars(
            select(JobPost)
            .where(JobPost.status == "published", or_(JobPost.deadline.is_(None), JobPost.deadline >= today_vn()))
            .order_by(JobPost.published_at.desc(), JobPost.id.desc())
        ).all()
        return {"items": [JobCard.model_validate(j).model_dump(mode="json") for j in rows]}


@router.get("/{slug}")
def get_job(slug: str):
    with new_session() as db:
        j = _get_public(db, slug)
        return {
            **JobPublic.model_validate(j).model_dump(mode="json"),
            "is_open": is_open(j),
            "cv_upload": cv_files.enabled(),  # chưa cấu hình R2 → form chỉ nhận link CV
            "cv_max_mb": get_settings().apply_cv_max_mb,
        }


@router.post("/{slug}/apply")
async def apply(slug: str, request: Request):
    cfg = get_settings()
    if not origin_allowed(request, cfg):
        return _fail(403, "Yêu cầu không hợp lệ.")
    max_body = (cfg.apply_cv_max_mb * 4 // 3 + 1) * 1024 * 1024 + 64 * 1024  # file base64 + phần chữ
    if int(request.headers.get("content-length") or 0) > max_body:
        return _fail(413, f"Dữ liệu gửi lên quá lớn (file CV tối đa {cfg.apply_cv_max_mb} MB).", {"cv_file": f"File CV tối đa {cfg.apply_cv_max_mb} MB."})
    body = await request.body()
    try:
        data = json.loads(body[:max_body] or b"null")
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")

    # Honeypot: bot điền ô ẩn → giả vờ thành công, không lưu gì
    if str(data.get("website_url") or "").strip():
        return {"ok": True}
    try:
        elapsed = int(data.get("elapsed_ms") or 0)
    except (TypeError, ValueError):
        elapsed = 0
    if elapsed < cfg.min_fill_ms:
        return _fail(429, "Bạn thao tác quá nhanh, vui lòng thử lại.")

    try:
        form = ApplyIn.model_validate(data)
    except ValidationError as e:
        fields: dict[str, str] = {}
        for err in e.errors():
            key = str(err["loc"][0]) if err.get("loc") else "_"
            fields.setdefault(key, str(err.get("msg", "Không hợp lệ")).removeprefix("Value error, "))
        return _fail(422, "Vui lòng kiểm tra lại thông tin.", fields)

    cv: tuple[str, str, bytes] | None = None
    if form.cv_file and not cv_files.enabled():
        msg = "Hiện chưa nhận file CV, vui lòng gửi link CV."
        return _fail(422, msg, {"cv_file": msg})
    if form.cv_file:
        try:
            cv = decode_cv(form.cv_file, cfg.apply_cv_max_mb)
        except ValueError as e:
            return _fail(422, str(e), {"cv_file": str(e)})
    if not cv and not form.cv_url:
        msg = "Vui lòng gửi link CV hoặc tải file CV lên."
        return _fail(422, msg, {"cv_url": msg})

    ip = client_ip(request, cfg)
    ua = request.headers.get("user-agent", "")[:300]
    result = await run_in_threadpool(_save, slug, form, cv, ip, ua, cfg)
    if isinstance(result, JSONResponse):
        return result
    await run_in_threadpool(enqueue_job_application, result)
    return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})


def _save(slug: str, form: ApplyIn, cv, ip: str, ua: str, cfg: Settings) -> int | JSONResponse:
    rl_key = "apply:" + sha256(ip)
    with new_session() as db:
        j = db.scalar(select(JobPost).where(JobPost.slug == slug, JobPost.status != "draft"))
        if not j:
            return _fail(404, "Không tìm thấy vị trí tuyển dụng.")
        if not is_open(j):
            return _fail(410, "Vị trí này đã ngừng nhận hồ sơ.")
        if rate_limited(db, rl_key, cfg.apply_rate_limit_per_hour, timedelta(hours=1)):
            return _fail(429, "Bạn đã gửi quá nhiều hồ sơ. Vui lòng thử lại sau ít phút.")
        a = JobApplication(
            job_id=j.id,
            job_title=j.title,
            full_name=form.full_name,
            phone=form.phone,
            email=form.email,
            cv_url=form.cv_url,
            portfolio_url=form.portfolio_url,
            intro=form.intro,
            ip=ip,
            user_agent=ua,
        )
        if cv:
            # kiểm tra xong mới đẩy file lên R2 (thư mục CV/) — DB chỉ lưu key
            name, mime, data = cv
            try:
                a.cv_key = cv_files.upload(name, mime, data)
            except StorageError:
                log.exception("Không tải được CV lên R2")
                msg = "Chưa tải được file CV lên, vui lòng thử lại hoặc gửi link CV."
                return _fail(503, msg, {"cv_file": msg})
            a.cv_filename, a.cv_mime, a.cv_size = name, mime, len(data)
        db.add(a)
        add_hit(db, rl_key)
        try:
            db.commit()
        except Exception:
            cv_files.purge([a.cv_key])  # không để file mồ côi trên R2
            raise
        return a.id
