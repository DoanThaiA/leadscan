"""Mã OTP kích hoạt tài khoản đối tác — gửi qua email đăng nhập (không dùng SMS).

Email gửi qua Resend/SMTP như các email khác (hàng đợi Celery; không có Redis thì gửi ngay trong request).
Chưa cấu hình gửi mail (máy dev) → mã chỉ ghi vào log máy chủ. Đối tác không nhận được mã → admin kích hoạt tay
ở trang quản trị Đối tác.
"""

import logging
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import PartnerEvent, PartnerOtp, PartnerUser
from app.security import sha256

log = logging.getLogger(__name__)


def _hash(partner_id: int, code: str) -> str:
    return sha256(f"{partner_id}:{code}")


def mask_email(email: str) -> str:
    """"nguyenvana@gmail.com" → "ng•••••••a@gmail.com"."""
    name, _, domain = email.partition("@")
    if len(name) <= 2:
        return name[:1] + "•" * max(0, len(name) - 1) + "@" + domain
    return name[:2] + "•" * (len(name) - 3) + name[-1] + "@" + domain


def deliver(cfg: Settings, email: str, code: str, name: str = "") -> str:
    """Gửi mã tới email; trả về kênh đã dùng ("email" hoặc "log")."""
    from app.services.notify import mail_provider, send_partner_otp
    from app.worker import enqueue, send_partner_otp_task

    if not mail_provider(cfg):
        log.warning("[OTP:log] Chưa cấu hình gửi email — mã kích hoạt đối tác %s: %s", email, code)
        return "log"
    if not enqueue(send_partner_otp_task, email, name, code):
        send_partner_otp(cfg, email, name, code)  # không có Redis → gửi ngay
    return "email"


def resend_after(db: Session, cfg: Settings, partner_id: int) -> int:
    """Số giây còn phải chờ trước khi được gửi mã mới (0 = gửi được)."""
    last: datetime | None = db.scalar(select(func.max(PartnerOtp.created_at)).where(PartnerOtp.partner_id == partner_id))
    if not last:
        return 0
    wait = cfg.otp_resend_seconds - int((utcnow() - last).total_seconds())
    return max(0, wait)


def send(db: Session, cfg: Settings, p: PartnerUser) -> dict:
    if p.email_verified_at:
        raise HTTPException(409, "Email đã được xác thực.")
    wait = resend_after(db, cfg, p.id)
    if wait:
        raise HTTPException(429, f"Vui lòng chờ {wait} giây rồi gửi lại mã.")
    hour = db.scalar(
        select(func.count()).select_from(PartnerOtp).where(PartnerOtp.partner_id == p.id, PartnerOtp.created_at > utcnow() - timedelta(hours=1))
    )
    if (hour or 0) >= cfg.otp_max_per_hour:
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều mã. Vui lòng thử lại sau 1 giờ hoặc liên hệ LeadScan.")
    code = f"{secrets.randbelow(10**6):06d}"
    provider = deliver(cfg, p.email, code, p.full_name)
    db.add(PartnerOtp(partner_id=p.id, email=p.email, phone="", code_hash=_hash(p.id, code),
                      expires_at=utcnow() + timedelta(minutes=cfg.otp_ttl_minutes), provider=provider))
    db.commit()
    return {"sent": True, "email": mask_email(p.email), "resend_after": cfg.otp_resend_seconds, "ttl_minutes": cfg.otp_ttl_minutes}


def verify(db: Session, cfg: Settings, p: PartnerUser, code: str) -> None:
    if p.email_verified_at:
        return
    otp = db.scalar(
        select(PartnerOtp)
        .where(PartnerOtp.partner_id == p.id, PartnerOtp.used_at.is_(None))
        .order_by(PartnerOtp.created_at.desc(), PartnerOtp.id.desc())
        .limit(1)
    )
    if not otp or otp.expires_at < utcnow() or otp.email != p.email:
        raise HTTPException(400, "Mã đã hết hạn. Vui lòng bấm gửi lại mã.")
    if otp.attempts >= cfg.otp_max_attempts:
        raise HTTPException(400, "Bạn đã nhập sai quá nhiều lần. Vui lòng bấm gửi lại mã.")
    if not secrets.compare_digest(otp.code_hash, _hash(p.id, code.strip())):
        otp.attempts += 1
        db.commit()
        left = cfg.otp_max_attempts - otp.attempts
        raise HTTPException(400, f"Mã xác thực không đúng. Còn {left} lần thử." if left else "Mã xác thực không đúng. Vui lòng bấm gửi lại mã.")
    otp.used_at = p.email_verified_at = utcnow()
    db.add(PartnerEvent(partner_id=p.id, kind="email_verified", content=f"Xác thực email {mask_email(p.email)} bằng mã OTP"))
    db.commit()
