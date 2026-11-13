"""Phiên đăng nhập cổng thành viên (tách riêng cookie & bảng với admin)."""

import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.models import MemberSession, MemberUser
from app.security import client_ip, origin_allowed, sha256

COOKIE = "ls_member"
# Cookie gửi tới mọi /api/* để đăng nhập / đăng xuất 1 lần cho cả cổng thành viên và cổng đối tác (app/accounts.py).
# Phiên vẫn chỉ mở được API của đúng cổng: mỗi cổng đọc cookie và bảng phiên riêng.
COOKIE_PATH = "/api"
LEGACY_COOKIE_PATH = "/api/member"  # cookie cũ trước khi dùng chung tài khoản


def create_session(db: Session, user: MemberUser, request: Request, response: Response) -> None:
    cfg = get_settings()
    token = secrets.token_urlsafe(32)
    db.add(
        MemberSession(
            token_hash=sha256(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=cfg.session_days),
            ip=client_ip(request, cfg),
        )
    )
    user.last_login_at = utcnow()
    db.commit()
    response.set_cookie(
        COOKIE, token, max_age=cfg.session_days * 86400, httponly=True, secure=cfg.cookie_secure, samesite="lax", path=COOKIE_PATH
    )
    response.delete_cookie(COOKIE, path=LEGACY_COOKIE_PATH)


def destroy_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(MemberSession).where(MemberSession.token_hash == sha256(token)))
        db.commit()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    response.delete_cookie(COOKIE, path=LEGACY_COOKIE_PATH)


def current_member(request: Request, db: Session = Depends(get_db)) -> MemberUser:
    token = request.cookies.get(COOKIE)
    if token:
        sess = db.scalar(select(MemberSession).where(MemberSession.token_hash == sha256(token), MemberSession.expires_at > utcnow()))
        if sess and sess.user.is_active and sess.user.company.status not in ("suspended", "rejected"):
            if request.method not in ("GET", "HEAD", "OPTIONS") and not origin_allowed(request, get_settings()):
                raise HTTPException(403, "Yêu cầu không hợp lệ.")
            return sess.user
    raise HTTPException(401, "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")
