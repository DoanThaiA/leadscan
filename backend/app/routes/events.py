"""API công khai trang sự kiện /su-kien: danh sách, chi tiết, đăng ký tham dự, nộp ảnh chuyển khoản.

Luồng của khách:
  1. POST /api/events/{slug}/register   → lưu đăng ký (kèm profile PDF lên R2), trả mã đăng ký + QR thanh toán
  2. GET  /api/events/registrations/{code}        → xem lại QR / trạng thái
  3. POST /api/events/registrations/{code}/proof  → tải ảnh chuyển khoản, OCR đối soát ngay
"""

import json
import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.db import new_session, utcnow
from app.models_events import Event, EventRegistration
from app.schemas_events import (
    EventCard,
    EventPublic,
    ProofIn,
    RegisterIn,
    decode_profile,
    decode_proof,
    new_code,
)
from app.security import add_hit, client_ip, origin_allowed, rate_limited, sha256
from app.services import event_files, events as ev, ocr
from app.services.storage import StorageError
from app.worker import enqueue_event_registration, enqueue_event_paid

log = logging.getLogger("leadscan.events")

router = APIRouter(prefix="/api/events")

LOOKUP_PER_HOUR = 120  # số lần tra cứu / nộp ảnh tối đa mỗi IP trong 1 giờ (chặn dò mã đăng ký, hạn chế gọi OCR phí)


def _fail(status: int, message: str, fields: dict | None = None) -> JSONResponse:
    return JSONResponse({"ok": False, "message": message, "fields": fields or {}}, status_code=status, headers={"Cache-Control": "no-store"})


def _no_store(data: dict) -> JSONResponse:
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


def _get_public(db: Session, slug: str) -> Event:
    e = db.scalar(select(Event).where(Event.slug == slug, Event.status != "draft"))
    if not e:
        raise HTTPException(404, "Không tìm thấy sự kiện.")
    return e


@router.get("")
def list_events():
    """Sự kiện đang mở đăng ký, sắp diễn ra trước."""
    with new_session() as db:
        rows = db.scalars(
            select(Event)
            .where(Event.status == "published", or_(Event.deadline.is_(None), Event.deadline >= ev.today_vn()))
            .order_by(Event.starts_at.asc().nulls_last(), Event.id.desc())
        ).all()
        return {"items": [EventCard.model_validate(e).model_dump(mode="json") for e in rows]}


@router.get("/{slug}")
def get_event(slug: str):
    cfg = get_settings()
    with new_session() as db:
        e = _get_public(db, slug)
        bank = ev.bank_of(e, cfg)
        return {
            **EventPublic.model_validate(e).model_dump(mode="json"),
            "is_open": ev.is_open(e),
            "file_upload": event_files.enabled(),  # chưa cấu hình R2 → ẩn nút đính kèm profile / nộp ảnh
            "profile_max_mb": cfg.event_profile_max_mb,
            "proof_max_mb": cfg.event_proof_max_mb,
            "payment_ready": bool(bank["bank_bin"] and bank["account_no"]),
            "bank_name": bank["bank_name"],
            "account_name": bank["account_name"],
        }


# ------------------------------------------------------------------ đăng ký


@router.post("/{slug}/register")
async def register(slug: str, request: Request):
    cfg = get_settings()
    if not origin_allowed(request, cfg):
        return _fail(403, "Yêu cầu không hợp lệ.")
    max_body = (cfg.event_profile_max_mb * 4 // 3 + 1) * 1024 * 1024 + 64 * 1024
    if int(request.headers.get("content-length") or 0) > max_body:
        return _fail(413, f"Dữ liệu gửi lên quá lớn (profile tối đa {cfg.event_profile_max_mb} MB).", {"profile_file": f"Profile tối đa {cfg.event_profile_max_mb} MB."})
    body = await request.body()
    try:
        data = json.loads(body[:max_body] or b"null")
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")

    # Honeypot: bot điền ô ẩn → giả vờ thành công, không lưu gì
    if str(data.get("website_url") or "").strip():
        return _no_store({"ok": True, "code": ""})
    try:
        elapsed = int(data.get("elapsed_ms") or 0)
    except (TypeError, ValueError):
        elapsed = 0
    if elapsed < cfg.min_fill_ms:
        return _fail(429, "Bạn thao tác quá nhanh, vui lòng thử lại.")

    try:
        form = RegisterIn.model_validate(data)
    except ValidationError as e:
        fields: dict[str, str] = {}
        for err in e.errors():
            key = str(err["loc"][0]) if err.get("loc") else "_"
            fields.setdefault(key, str(err.get("msg", "Không hợp lệ")).removeprefix("Value error, "))
        return _fail(422, "Vui lòng kiểm tra lại thông tin.", fields)

    profile: tuple[str, str, bytes] | None = None
    if form.profile_file:
        if not event_files.enabled():
            msg = "Hiện chưa nhận tệp đính kèm, vui lòng gửi profile qua email cho ban tổ chức."
            return _fail(422, msg, {"profile_file": msg})
        try:
            profile = decode_profile(form.profile_file, cfg.event_profile_max_mb)
        except ValueError as e:
            return _fail(422, str(e), {"profile_file": str(e)})

    ip = client_ip(request, cfg)
    ua = request.headers.get("user-agent", "")[:300]
    result = await run_in_threadpool(_save, slug, form, profile, ip, ua, cfg)
    if isinstance(result, JSONResponse):
        return result
    reg_id, state = result
    await run_in_threadpool(enqueue_event_registration, reg_id)
    return _no_store({"ok": True, **state})


def _save(slug: str, form: RegisterIn, profile, ip: str, ua: str, cfg: Settings):
    rl_key = "event:" + sha256(ip)
    with new_session() as db:
        e = db.scalar(select(Event).where(Event.slug == slug, Event.status != "draft"))
        if not e:
            return _fail(404, "Không tìm thấy sự kiện.")
        if not ev.is_open(e):
            return _fail(410, "Sự kiện đã ngừng nhận đăng ký.")
        if rate_limited(db, rl_key, cfg.event_rate_limit_per_hour, timedelta(hours=1)):
            return _fail(429, "Bạn đã gửi quá nhiều đăng ký. Vui lòng thử lại sau ít phút.")

        amount = ev.fee_for(e, form.attendee_type)
        r = EventRegistration(
            event_id=e.id,
            event_title=e.title,
            code=_free_code(db),
            status="paid" if amount == 0 else "new",
            full_name=form.full_name,
            phone=form.phone,
            email=form.email,
            company=form.company,
            position=form.position,
            attendee_type=form.attendee_type,
            needs=form.needs,
            amount=amount,
            ocr_status="none",
            paid_at=utcnow() if amount == 0 else None,
            ip=ip,
            user_agent=ua,
        )
        if profile:
            name, mime, data = profile
            try:
                r.profile_key = event_files.upload_profile(name, mime, data)
            except StorageError:
                log.exception("Không tải được profile lên R2")
                msg = "Chưa tải được tệp profile lên, vui lòng thử lại hoặc bỏ tệp đính kèm."
                return _fail(503, msg, {"profile_file": msg})
            r.profile_filename, r.profile_mime, r.profile_size = name, mime, len(data)
        db.add(r)
        add_hit(db, rl_key)
        try:
            db.commit()
        except Exception:
            event_files.purge([r.profile_key])  # không để tệp mồ côi trên R2
            raise
        db.refresh(r)
        return r.id, ev.public_state(e, r, cfg)


def _free_code(db: Session) -> str:
    for _ in range(20):
        code = new_code()
        if not db.scalar(select(EventRegistration.id).where(EventRegistration.code == code)):
            return code
    raise HTTPException(503, "Không cấp được mã đăng ký, vui lòng thử lại.")


# ------------------------------------------------------------------ tra cứu & ảnh chuyển khoản


def _get_reg(db: Session, code: str) -> tuple[Event, EventRegistration]:
    r = db.scalar(select(EventRegistration).where(EventRegistration.code == code.strip().upper()))
    if not r or not r.event:
        raise HTTPException(404, "Không tìm thấy đăng ký.")
    return r.event, r


@router.get("/registrations/{code}")
def registration_state(code: str, request: Request):
    """Khách mở lại trang để tiếp tục thanh toán. Giới hạn tần suất để không ai dò mã đăng ký hàng loạt."""
    cfg = get_settings()
    with new_session() as db:
        rl_key = "event-lookup:" + sha256(client_ip(request, cfg))
        if rate_limited(db, rl_key, LOOKUP_PER_HOUR, timedelta(hours=1)):
            raise HTTPException(429, "Bạn tra cứu quá nhiều lần, vui lòng thử lại sau ít phút.")
        add_hit(db, rl_key)
        db.commit()
        e, r = _get_reg(db, code)
        return _no_store(ev.public_state(e, r, cfg))


@router.post("/registrations/{code}/proof")
async def upload_proof(code: str, request: Request):
    """Khách tải ảnh chuyển khoản → lưu R2 → OCR đọc và so khớp mã đăng ký + số tiền."""
    cfg = get_settings()
    if not origin_allowed(request, cfg):
        return _fail(403, "Yêu cầu không hợp lệ.")
    max_body = (cfg.event_proof_max_mb * 4 // 3 + 1) * 1024 * 1024 + 16 * 1024
    if int(request.headers.get("content-length") or 0) > max_body:
        return _fail(413, f"Ảnh tối đa {cfg.event_proof_max_mb} MB.", {"image": f"Ảnh tối đa {cfg.event_proof_max_mb} MB."})
    body = await request.body()
    try:
        data = json.loads(body[:max_body] or b"null")
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")
    try:
        form = ProofIn.model_validate(data)
    except ValidationError:
        return _fail(422, "Vui lòng chọn ảnh chuyển khoản.", {"image": "Vui lòng chọn ảnh chuyển khoản."})
    if not event_files.enabled():
        return _fail(503, "Hiện chưa nhận ảnh chuyển khoản, vui lòng gửi cho ban tổ chức qua email.")
    try:
        name, mime, raw = decode_proof(form.image, cfg.event_proof_max_mb)
    except ValueError as e:
        return _fail(422, str(e), {"image": str(e)})

    result = await run_in_threadpool(_save_proof, code, name, mime, raw, client_ip(request, cfg), cfg)
    if isinstance(result, JSONResponse):
        return result
    reg_id, paid, state = result
    if paid:
        await run_in_threadpool(enqueue_event_paid, reg_id)
    return _no_store({"ok": True, **state})


def _save_proof(code: str, name: str, mime: str, raw: bytes, ip: str, cfg: Settings):
    with new_session() as db:
        rl_key = "event-proof:" + sha256(ip)
        if rate_limited(db, rl_key, LOOKUP_PER_HOUR, timedelta(hours=1)):
            return _fail(429, "Bạn gửi ảnh quá nhiều lần, vui lòng thử lại sau ít phút.")
        add_hit(db, rl_key)
        db.commit()
        e, r = _get_reg(db, code)
        if r.status == "cancelled":
            return _fail(410, "Đăng ký này đã bị huỷ.")
        if r.status == "paid":
            return _fail(409, "Đăng ký này đã được xác nhận thanh toán.")
        old_key = r.proof_key
        try:
            r.proof_key = event_files.upload_proof(name, mime, raw)
        except StorageError:
            log.exception("Không tải được ảnh chuyển khoản lên R2")
            return _fail(503, "Chưa tải được ảnh lên, vui lòng thử lại.")
        r.proof_filename, r.proof_mime, r.proof_size = name, mime, len(raw)
        r.proof_at = utcnow()

        bank = ev.bank_of(e, cfg)
        res = ocr.verify(raw, name, mime, r.code, r.amount, bank["account_no"], cfg)
        _apply_ocr(r, res)
        try:
            db.commit()
        except Exception:
            event_files.purge([r.proof_key])
            raise
        if old_key and old_key != r.proof_key:
            event_files.purge([old_key])  # bỏ ảnh gửi lần trước
        db.refresh(r)
        return r.id, r.status == "paid", ev.public_state(e, r, cfg)


def _apply_ocr(r: EventRegistration, res: ocr.OcrResult) -> None:
    """Ghi kết quả OCR vào đăng ký. Khớp đủ → "Đã thanh toán"; còn lại → "Chờ đối soát"."""
    r.ocr_status = res.status
    r.ocr_text = res.text
    r.ocr_amount = res.amount
    r.ocr_checks = res.checks or None
    r.ocr_message = res.message[:300]
    r.ocr_at = utcnow()
    r.ocr_tries = (r.ocr_tries or 0) + 1
    if res.status == "matched":
        r.status = "paid"
        r.paid_at = r.paid_at or utcnow()
    else:
        r.status = "review"
        if res.status == "off":
            r.ocr_message = "Ban tổ chức sẽ đối soát ảnh chuyển khoản và xác nhận cho bạn."
