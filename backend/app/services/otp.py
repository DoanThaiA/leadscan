"""OTP xác thực số điện thoại đối tác.

Nhà cung cấp chọn bằng LEADSCAN_SMS_PROVIDER. Hiện chỉ có "log": mã được ghi vào log máy chủ (chạy thử / chờ ký hợp đồng
SMS brandname hoặc Zalo ZNS). Thêm nhà cung cấp thật = thêm 1 nhánh trong deliver().
Khi chưa có nhà cung cấp, admin xác nhận SĐT bằng tay ở trang quản trị Đối tác (gọi điện / nhắn Zalo đối chiếu).
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


def mask_phone(phone: str) -> str:
    return phone[:3] + "•" * max(0, len(phone) - 6) + phone[-3:] if len(phone) > 6 else phone


def deliver(cfg: Settings, phone: str, code: str) -> str:
    """Gửi mã tới SĐT; trả về tên nhà cung cấp đã dùng."""
    provider = (cfg.sms_provider or "log").lower()
    msg = f"Ma xac thuc Doi tac LeadScan cua ban la {code}. Hieu luc {cfg.otp_ttl_minutes} phut. Khong chia se ma nay."
    # Nhà cung cấp thật (eSMS, SpeedSMS, Zalo ZNS…) thêm ở đây khi có tài khoản + brandname/template đã duyệt.
    log.warning("[OTP:%s] %s → %s", provider, phone, msg)
    return "log"


def resend_after(db: Session, cfg: Settings, partner_id: int) -> int:
    """Số giây còn phải chờ trước khi được gửi mã mới (0 = gửi được)."""
    last: datetime | None = db.scalar(select(func.max(PartnerOtp.created_at)).where(PartnerOtp.partner_id == partner_id))
    if not last:
        return 0
    wait = cfg.otp_resend_seconds - int((utcnow() - last).total_seconds())
    return max(0, wait)


def send(db: Session, cfg: Settings, p: PartnerUser) -> dict:
    if p.phone_verified_at:
        raise HTTPException(409, "Số điện thoại đã được xác thực.")
    wait = resend_after(db, cfg, p.id)
    if wait:
        raise HTTPException(429, f"Vui lòng chờ {wait} giây rồi gửi lại mã.")
    hour = db.scalar(
        select(func.count()).select_from(PartnerOtp).where(PartnerOtp.partner_id == p.id, PartnerOtp.created_at > utcnow() - timedelta(hours=1))
    )
    if (hour or 0) >= cfg.otp_max_per_hour:
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều mã. Vui lòng thử lại sau 1 giờ hoặc liên hệ LeadScan.")
    code = f"{secrets.randbelow(10**6):06d}"
    provider = deliver(cfg, p.phone, code)
    db.add(PartnerOtp(partner_id=p.id, phone=p.phone, code_hash=_hash(p.id, code), expires_at=utcnow() + timedelta(minutes=cfg.otp_ttl_minutes), provider=provider))
    db.commit()
    return {"sent": True, "phone": mask_phone(p.phone), "resend_after": cfg.otp_resend_seconds, "ttl_minutes": cfg.otp_ttl_minutes}


def verify(db: Session, cfg: Settings, p: PartnerUser, code: str) -> None:
    if p.phone_verified_at:
        return
    otp = db.scalar(
        select(PartnerOtp)
        .where(PartnerOtp.partner_id == p.id, PartnerOtp.used_at.is_(None))
        .order_by(PartnerOtp.created_at.desc(), PartnerOtp.id.desc())
        .limit(1)
    )
    if not otp or otp.expires_at < utcnow() or otp.phone != p.phone:
        raise HTTPException(400, "Mã đã hết hạn. Vui lòng bấm gửi lại mã.")
    if otp.attempts >= cfg.otp_max_attempts:
        raise HTTPException(400, "Bạn đã nhập sai quá nhiều lần. Vui lòng bấm gửi lại mã.")
    if not secrets.compare_digest(otp.code_hash, _hash(p.id, code.strip())):
        otp.attempts += 1
        db.commit()
        left = cfg.otp_max_attempts - otp.attempts
        raise HTTPException(400, f"Mã xác thực không đúng. Còn {left} lần thử." if left else "Mã xác thực không đúng. Vui lòng bấm gửi lại mã.")
    otp.used_at = p.phone_verified_at = utcnow()
    db.add(PartnerEvent(partner_id=p.id, kind="phone_verified", content=f"Xác thực SĐT {mask_phone(p.phone)} bằng OTP"))
    db.commit()
