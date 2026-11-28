"""Quy tắc dùng chung của sự kiện: còn nhận đăng ký không, phí theo loại khách, tài khoản thu + mã VietQR."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models_events import Event, EventRegistration
from app.services.vietqr import build_payload

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def today_vn():
    return datetime.now(VN_TZ).date()


def is_open(e: Event) -> bool:
    """Còn nhận đăng ký: đang mở và chưa quá hạn (hạn tính hết ngày theo giờ Việt Nam)."""
    return e.status == "published" and (e.deadline is None or e.deadline >= today_vn())


def web_counts(db: Session, event_ids: list[int]) -> dict[int, int]:
    """Số đăng ký trên web chưa huỷ của từng sự kiện (giữ chỗ kể cả khi chưa thanh toán)."""
    if not event_ids:
        return {}
    rows = db.execute(
        select(EventRegistration.event_id, func.count())
        .where(EventRegistration.event_id.in_(event_ids), EventRegistration.status != "cancelled")
        .group_by(EventRegistration.event_id)
    ).all()
    return {eid: int(n) for eid, n in rows}


def ticket_stats(e: Event, web: int) -> dict:
    """Tổng vé · đã đăng ký · còn lại. total = None → không giới hạn chỗ (không bao giờ hết vé)."""
    registered = int(e.tickets_sold or 0) + int(web or 0)
    total = e.ticket_total
    remaining = None if total is None else max(0, total - registered)
    return {
        "total": total,
        "registered": registered,
        "remaining": remaining,
        "sold_out": remaining == 0,
        "web": int(web or 0),
        "offline": int(e.tickets_sold or 0),
    }


def stats_for(db: Session, e: Event) -> dict:
    return ticket_stats(e, web_counts(db, [e.id]).get(e.id, 0))


def public_tickets(t: dict) -> dict:
    """Bản cho trang công khai — không tách số bán ngoài form / trên web."""
    return {k: t[k] for k in ("total", "registered", "remaining", "sold_out")}


def fee_for(e: Event, attendee_type: str) -> int:
    return int(e.fee_guest if attendee_type == "guest" else e.fee_member)


def bank_of(e: Event, cfg: Settings | None = None) -> dict:
    """Tài khoản nhận phí của sự kiện; trống thì dùng tài khoản thu chung trong cấu hình."""
    cfg = cfg or get_settings()
    return {
        "bank_bin": e.bank_bin or cfg.payment_bank_bin,
        "bank_name": e.bank_name or cfg.payment_bank_name,
        "account_no": e.account_no or cfg.payment_account_no,
        "account_name": e.account_name or cfg.payment_account_name,
    }


def payment_info(e: Event, r: EventRegistration, cfg: Settings | None = None) -> dict:
    """Thông tin để trang web vẽ mã QR và hướng dẫn chuyển khoản.

    qr_payload là chuỗi VietQR (EMVCo) đã gồm số tiền và nội dung = mã đăng ký; trình duyệt tự vẽ
    thành ảnh QR. Thiếu BIN/số tài khoản → qr_payload rỗng, trang chỉ hiện thông tin chuyển khoản thủ công.
    """
    cfg = cfg or get_settings()
    bank = bank_of(e, cfg)
    payload = ""
    if r.amount > 0 and bank["bank_bin"] and bank["account_no"]:
        payload = build_payload(bank["bank_bin"], bank["account_no"], r.amount, r.code)
    return {
        **bank,
        "amount": r.amount,
        "transfer_content": r.code,
        "qr_payload": payload,
        "configured": bool(bank["bank_bin"] and bank["account_no"]) or r.amount == 0,
    }


def mask_email(email: str) -> str:
    """"binh@minhan.vn" → "b***@minhan.vn" — đủ để khách nhận ra hộp thư của mình mà không lộ địa chỉ đầy đủ."""
    name, sep, domain = email.partition("@")
    if not sep:
        return "***"
    return f"{name[:1]}***@{domain}"


def public_state(e: Event, r: EventRegistration, cfg: Settings | None = None) -> dict:
    """Trạng thái đơn đăng ký trả về cho khách.

    Mã đăng ký là thứ duy nhất cần để xem đơn này, nên chỉ trả thông tin tối thiểu: không có ghi chú nội bộ,
    chữ OCR, SĐT, và email bị che bớt — ai đoán trúng mã cũng không lấy được dữ liệu liên hệ.
    """
    return {
        "code": r.code,
        "status": r.status,
        "amount": r.amount,
        "attendee_type": r.attendee_type,
        "full_name": r.full_name,
        "email": mask_email(r.email),
        "has_profile": bool(r.profile_key),
        "has_proof": bool(r.proof_key),
        "ocr_status": r.ocr_status,
        "ocr_message": r.ocr_message,
        "paid_at": r.paid_at.isoformat() + "Z" if r.paid_at else None,
        "payment": payment_info(e, r, cfg),
    }
