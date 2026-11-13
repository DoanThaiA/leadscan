"""Phiên đăng nhập cổng đối tác — cookie ls_partner và bảng partner_sessions riêng với cổng thành viên.

Cùng email = cùng 1 tài khoản cho cả 2 cổng (app/accounts.py): đăng nhập 1 lần mở phiên của từng cổng mà email có
hồ sơ. Phiên đối tác chỉ mở API cổng đối tác, phiên thành viên chỉ mở API cổng thành viên.
"""

import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.models import PartnerSession, PartnerUser
from app.security import client_ip, origin_allowed, sha256

COOKIE = "ls_partner"
# Cookie gửi tới mọi /api/* để đăng nhập / đăng xuất 1 lần cho cả cổng thành viên và cổng đối tác (app/accounts.py).
# Phiên vẫn chỉ mở được API của đúng cổng: mỗi cổng đọc cookie và bảng phiên riêng.
COOKIE_PATH = "/api"
LEGACY_COOKIE_PATH = "/api/partner"  # cookie cũ trước khi dùng chung tài khoản


def create_session(db: Session, partner: PartnerUser, request: Request, response: Response) -> None:
    cfg = get_settings()
    token = secrets.token_urlsafe(32)
    db.add(
        PartnerSession(
            token_hash=sha256(token),
            partner_id=partner.id,
            expires_at=utcnow() + timedelta(days=cfg.session_days),
            ip=client_ip(request, cfg),
            user_agent=request.headers.get("user-agent", "")[:300],
        )
    )
    partner.last_login_at = utcnow()
    db.commit()
    response.set_cookie(
        COOKIE, token, max_age=cfg.session_days * 86400, httponly=True, secure=cfg.cookie_secure, samesite="lax", path=COOKIE_PATH
    )
    response.delete_cookie(COOKIE, path=LEGACY_COOKIE_PATH)


def destroy_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(PartnerSession).where(PartnerSession.token_hash == sha256(token)))
        db.commit()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    response.delete_cookie(COOKIE, path=LEGACY_COOKIE_PATH)


def end_all_sessions(db: Session, partner_id: int) -> None:
    db.execute(delete(PartnerSession).where(PartnerSession.partner_id == partner_id))


def current_partner(request: Request, db: Session = Depends(get_db)) -> PartnerUser:
    """Đối tác đã đăng nhập (kể cả chưa xác thực email — chỉ dùng cho các bước kích hoạt tài khoản)."""
    token = request.cookies.get(COOKIE)
    if token:
        sess = db.scalar(select(PartnerSession).where(PartnerSession.token_hash == sha256(token), PartnerSession.expires_at > utcnow()))
        if sess and sess.partner.status == "active":
            if request.method not in ("GET", "HEAD", "OPTIONS") and not origin_allowed(request, get_settings()):
                raise HTTPException(403, "Yêu cầu không hợp lệ.")
            return sess.partner
    raise HTTPException(401, "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")


def verified_partner(partner: PartnerUser = Depends(current_partner)) -> PartnerUser:
    """Đối tác đã kích hoạt (xác thực email) — điều kiện để gửi cơ hội, xem ví, rút tiền."""
    if not partner.email_verified_at:
        raise HTTPException(403, "Vui lòng xác thực email để kích hoạt tài khoản đối tác.")
    return partner
