"""Băm mật khẩu, IP khách, kiểm tra Origin, giới hạn tần suất."""

import hashlib
import os
import hmac
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import RateHit

# scrypt (thư viện chuẩn): N=2^15, r=8, p=1 ≈ 32 MB RAM mỗi lần băm
_N, _R, _P = int(os.environ.get("LEADSCAN_SCRYPT_N", 2**15)), 8, 1  # test đặt N nhỏ cho nhanh


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=64 * 1024 * 1024)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=64 * 1024 * 1024
        )
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, TypeError):
        return False


# Băm sẵn 1 mật khẩu giả để thời gian xử lý như nhau khi email không tồn tại
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def client_ip(request: Request, cfg: Settings) -> str:
    if cfg.client_ip_header:
        v = request.headers.get(cfg.client_ip_header, "").split(",")[0].strip()
        if v:
            return v[:64]
    return (request.client.host if request.client else "0.0.0.0")[:64]


def origin_allowed(request: Request, cfg: Settings) -> bool:
    """Chặn gửi chéo trang: Origin (nếu có) phải là chính host hoặc nằm trong allowed_hosts."""
    origin = request.headers.get("origin", "")
    if not origin:
        return True
    host = (urlparse(origin).hostname or "").lower()
    self_host = request.headers.get("host", "").split(":")[0].lower()
    return host == self_host or host in {h.lower() for h in cfg.allowed_hosts}


def rate_limited(db: Session, key: str, limit: int, window: timedelta) -> bool:
    since = utcnow() - window
    hits = db.scalar(select(func.count()).select_from(RateHit).where(RateHit.key == key, RateHit.created_at > since))
    return (hits or 0) >= limit


def add_hit(db: Session, key: str) -> None:
    db.add(RateHit(key=key))
