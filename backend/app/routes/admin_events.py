"""API quản trị sự kiện: tạo/sửa trang sự kiện và xử lý danh sách đăng ký tham dự.

Mục "Đăng ký sự kiện" của admin hiển thị đủ: thông tin người đăng ký, nhu cầu xúc tiến, profile PDF
đính kèm, ảnh chuyển khoản và kết quả đối soát OCR (có nút đọc lại ảnh / xác nhận thủ công).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import current_user, require_admin
from app.config import get_settings
from app.db import get_db, utcnow
from app.models import AdminUser
from app.models_events import ATTENDEE_TYPES, EVENT_REG_STATUSES, EVENT_STATUSES, OCR_STATUSES, Event, EventRegistration
from app.schemas_events import EventIn, EventOut, RegistrationAdminIn, RegistrationOut
from app.schemas_jobs import slugify
from app.services import event_files, events as ev, ocr
from app.services.notify import event_inbox, mail_provider
from app.services.storage import StorageError
from app.worker import deliver_event_registration

log = logging.getLogger("leadscan.admin.events")

router = APIRouter(prefix="/api/admin")


def _get_event(db: Session, eid: int) -> Event:
    e = db.get(Event, eid)
    if not e:
        raise HTTPException(404, "Không tìm thấy sự kiện.")
    return e


def _get_reg(db: Session, rid: int) -> EventRegistration:
    r = db.get(EventRegistration, rid)
    if not r:
        raise HTTPException(404, "Không tìm thấy đăng ký.")
    return r


def _event_out(db: Session, e: Event) -> dict:
    d = EventOut.model_validate(e).model_dump(mode="json")
    d["registrations"] = db.scalar(select(func.count()).where(EventRegistration.event_id == e.id)) or 0
    d["paid"] = db.scalar(
        select(func.count()).where(EventRegistration.event_id == e.id, EventRegistration.status == "paid")
    ) or 0
    return d


def _unique_slug(db: Session, wanted: str, title: str, exclude_id: int | None = None) -> str:
    base = wanted or slugify(title) or "su-kien"
    slug, n = base, 2
    while True:
        stmt = select(Event.id).where(Event.slug == slug)
        if exclude_id:
            stmt = stmt.where(Event.id != exclude_id)
        if not db.scalar(stmt):
            return slug
        slug, n = f"{base}-{n}", n + 1


def _apply(db: Session, e: Event, body: EventIn) -> None:
    data = body.model_dump()
    data["slug"] = _unique_slug(db, data["slug"], data["title"], exclude_id=e.id)
    for f, v in data.items():
        setattr(e, f, v)
    if e.status == "published" and not e.published_at:
        e.published_at = utcnow()


# ------------------------------------------------------------------ sự kiện


@router.get("/events/meta")
def meta(_: AdminUser = Depends(current_user)):
    cfg = get_settings()
    return {
        "statuses": EVENT_STATUSES,
        "registration_statuses": EVENT_REG_STATUSES,
        "attendee_types": ATTENDEE_TYPES,
        "ocr_statuses": OCR_STATUSES,
        "event_email": event_inbox(cfg),
        "mail_ready": bool(mail_provider(cfg)),
        "storage_ready": event_files.enabled(),
        "ocr_ready": ocr.enabled(cfg),
        "profile_max_mb": cfg.event_profile_max_mb,
        "proof_max_mb": cfg.event_proof_max_mb,
        "default_bank": {
            "bank_bin": cfg.payment_bank_bin,
            "bank_name": cfg.payment_bank_name,
            "account_no": cfg.payment_account_no,
            "account_name": cfg.payment_account_name,
        },
    }


@router.get("/events")
def list_events(status: str = "", q: str = Query("", max_length=100), _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Event)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Event.title.ilike(like), Event.venue.ilike(like), Event.partner.ilike(like)))
    sub = stmt.subquery()
    counts = dict(db.execute(select(sub.c.status, func.count()).group_by(sub.c.status)).all())
    if status:
        stmt = stmt.where(Event.status == status)
    rows = db.scalars(stmt.order_by(Event.starts_at.desc().nulls_last(), Event.id.desc())).all()

    agg = {
        eid: (total, paid)
        for eid, total, paid in db.execute(
            select(
                EventRegistration.event_id,
                func.count(),
                func.sum(case((EventRegistration.status == "paid", 1), else_=0)),
            ).group_by(EventRegistration.event_id)
        ).all()
    }
    items = []
    for e in rows:
        total, paid = agg.get(e.id, (0, 0))
        items.append(
            {
                "id": e.id,
                "slug": e.slug,
                "status": e.status,
                "title": e.title,
                "partner": e.partner,
                "venue": e.venue,
                "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                "deadline": e.deadline.isoformat() if e.deadline else None,
                "fee_member": e.fee_member,
                "fee_guest": e.fee_guest,
                "registrations": total,
                "paid": int(paid or 0),
                "updated_at": e.updated_at.isoformat() + "Z",
            }
        )
    return {"items": items, "counts": counts}


@router.post("/events", status_code=201)
def create_event(body: EventIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    e = Event(created_by_id=user.id)
    _apply(db, e, body)
    db.add(e)
    db.commit()
    db.refresh(e)
    return _event_out(db, e)


@router.get("/events/{eid}")
def get_event(eid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _event_out(db, _get_event(db, eid))


@router.put("/events/{eid}")
def update_event(eid: int, body: EventIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    e = _get_event(db, eid)
    _apply(db, e, body)
    db.commit()
    db.refresh(e)
    return _event_out(db, e)


@router.delete("/events/{eid}", status_code=204)
def delete_event(eid: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Xoá sự kiện; các đăng ký đã nhận vẫn giữ (kèm tên sự kiện). Muốn ẩn mà giữ link thì chuyển "Đã đóng"."""
    e = _get_event(db, eid)
    # tự gỡ liên kết (SQLite khi dev không bật khoá ngoại nên ON DELETE SET NULL không chạy)
    db.execute(update(EventRegistration).where(EventRegistration.event_id == e.id).values(event_id=None))
    db.delete(e)
    db.commit()


# ------------------------------------------------------------------ đăng ký tham dự


def _reg_out(r: EventRegistration) -> dict:
    d = RegistrationOut.model_validate(r).model_dump(mode="json")
    d["event_slug"] = r.event.slug if r.event else None
    return d


@router.get("/event-registrations")
def list_registrations(
    event_id: int | None = None,
    status: str = "",
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(EventRegistration)
    if event_id:
        stmt = stmt.where(EventRegistration.event_id == event_id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                EventRegistration.full_name.ilike(like),
                EventRegistration.email.ilike(like),
                EventRegistration.phone.ilike(like),
                EventRegistration.company.ilike(like),
                EventRegistration.code.ilike(like),
                EventRegistration.event_title.ilike(like),
            )
        )
    sub = stmt.subquery()
    counts = dict(db.execute(select(sub.c.status, func.count()).group_by(sub.c.status)).all())
    revenue = db.scalar(select(func.sum(sub.c.amount)).where(sub.c.status == "paid")) or 0
    if status:
        stmt = stmt.where(EventRegistration.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(EventRegistration.created_at.desc(), EventRegistration.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": counts,
        "revenue": int(revenue),
        "items": [_reg_out(r) for r in rows],
    }


@router.get("/event-registrations/{rid}")
def get_registration(rid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _reg_out(_get_reg(db, rid))


@router.patch("/event-registrations/{rid}")
def update_registration(rid: int, body: RegistrationAdminIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    r = _get_reg(db, rid)
    if body.status is not None and body.status != r.status:
        r.status = body.status
        if body.status == "paid":
            r.paid_at = r.paid_at or utcnow()
            r.confirmed_by_id = user.id
        elif body.status in ("new", "cancelled"):
            r.paid_at = None
    if body.note is not None:
        r.note = body.note.strip()
    if body.checked_in is not None:
        r.checked_in = body.checked_in
    db.commit()
    db.refresh(r)
    return _reg_out(r)


def _file_redirect(key: str, filename: str, inline: bool, missing: str):
    if not key:
        raise HTTPException(404, missing)
    try:
        url = event_files.view_url(key, filename or "tep", inline)
    except StorageError as e:
        raise HTTPException(503, "Chưa kết nối được kho lưu trữ tệp (Cloudflare R2).") from e
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


@router.get("/event-registrations/{rid}/profile")
def download_profile(rid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    r = _get_reg(db, rid)
    return _file_redirect(r.profile_key, r.profile_filename, False, "Đăng ký này không đính kèm profile.")


@router.get("/event-registrations/{rid}/proof")
def view_proof(rid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    r = _get_reg(db, rid)
    return _file_redirect(r.proof_key, r.proof_filename, True, "Đăng ký này chưa có ảnh chuyển khoản.")


@router.post("/event-registrations/{rid}/recheck")
async def recheck(rid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Đọc lại ảnh chuyển khoản bằng OCR (ảnh mờ / OCR lỗi tạm thời)."""
    r = _get_reg(db, rid)
    if not r.proof_key:
        raise HTTPException(400, "Đăng ký này chưa có ảnh chuyển khoản.")
    cfg = get_settings()
    if not ocr.enabled(cfg):
        raise HTTPException(400, "Chưa cấu hình OCR_SPACE_API_KEY nên không đọc được ảnh tự động.")
    try:
        raw = await run_in_threadpool(event_files.fetch, r.proof_key)
    except StorageError as e:
        raise HTTPException(503, "Không đọc được ảnh trên kho lưu trữ (Cloudflare R2).") from e
    account_no = ev.bank_of(r.event, cfg)["account_no"] if r.event else cfg.payment_account_no
    res = await run_in_threadpool(ocr.verify, raw, r.proof_filename, r.proof_mime, r.code, r.amount, account_no, cfg)

    from app.routes.events import _apply_ocr

    _apply_ocr(r, res)
    db.commit()
    db.refresh(r)
    return _reg_out(r)


@router.post("/event-registrations/{rid}/resend")
async def resend(rid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Gửi lại đăng ký về hộp thư ban tổ chức ngay (đồng bộ để admin biết kết quả)."""
    r = _get_reg(db, rid)
    cfg = get_settings()
    if not event_inbox(cfg, r.event):
        raise HTTPException(400, "Chưa cấu hình email nhận đăng ký (LEADSCAN_EVENT_EMAIL hoặc email riêng của sự kiện).")
    if not mail_provider(cfg):
        raise HTTPException(400, "Chưa cấu hình gửi email (Resend hoặc SMTP).")
    r.email_sent_at = None
    db.commit()
    if not await run_in_threadpool(deliver_event_registration, rid):
        raise HTTPException(502, "Gửi email chưa thành công, vui lòng thử lại sau.")
    db.refresh(r)
    return _reg_out(r)


@router.delete("/event-registrations/{rid}", status_code=204)
def delete_registration(rid: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Xoá vĩnh viễn 1 đăng ký kèm tệp trên R2."""
    r = _get_reg(db, rid)
    keys = [r.profile_key, r.proof_key]
    db.delete(r)
    db.commit()
    event_files.purge(keys)
