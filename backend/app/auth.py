"""Phiên đăng nhập quản trị: token ngẫu nhiên trong cookie HttpOnly, DB chỉ lưu sha256 của token."""

import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.models import AdminSession, AdminUser
from app.security import client_ip, origin_allowed, sha256

COOKIE = "ls_admin"
COOKIE_PATH = "/api/admin"

# API tài khoản cổng sự kiện (AdminUser.site) được gọi. Mặc định CHẶN: API admin thêm sau này tự động không mở cho họ.
SITE_USER_PATHS = ("/api/admin/auth/", "/api/admin/meta", "/api/admin/events", "/api/admin/event-registrations")


def create_session(db: Session, user: AdminUser, request: Request, response: Response) -> None:
    cfg = get_settings()
    token = secrets.token_urlsafe(32)
    db.add(
        AdminSession(
            token_hash=sha256(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=cfg.session_days),
            ip=client_ip(request, cfg),
            user_agent=request.headers.get("user-agent", "")[:300],
        )
    )
    user.last_login_at = utcnow()
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=cfg.session_days * 86400,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


def destroy_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(AdminSession).where(AdminSession.token_hash == sha256(token)))
        db.commit()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)


def current_user(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    token = request.cookies.get(COOKIE)
    if token:
        sess = db.scalar(
            select(AdminSession).where(AdminSession.token_hash == sha256(token), AdminSession.expires_at > utcnow())
        )
        if sess and sess.user.is_active:
            # Chặn thao tác ghi gửi từ trang khác (bổ sung cho SameSite=Lax)
            if request.method not in ("GET", "HEAD", "OPTIONS") and not origin_allowed(request, get_settings()):
                raise HTTPException(403, "Yêu cầu không hợp lệ.")
            if sess.user.site and not request.url.path.startswith(SITE_USER_PATHS):
                raise HTTPException(403, "Tài khoản cổng sự kiện chỉ quản lý được sự kiện của cổng mình.")
            return sess.user
    raise HTTPException(401, "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")


def login_allowed(user: AdminUser, request_site: str) -> str | None:
    """Tài khoản được đăng nhập ở trang này không. Trả về lý do khi bị chặn.

    leadscan.net/admin: chỉ nhân viên LeadScan. Cổng c89 / epc: tài khoản của cổng đó + quản trị viên LeadScan (hỗ trợ).
    """
    from app import sites

    if request_site == sites.MAIN:
        if user.site:
            return f"Tài khoản này quản lý sự kiện của {sites.NAMES.get(user.site, user.site)} — đăng nhập tại {sites.admin_url(user.site)}."
        return None
    if user.site == request_site or (user.site is None and user.role == "admin"):
        return None
    return "Tài khoản này không có quyền quản lý cổng sự kiện này."


def require_admin(user: AdminUser = Depends(current_user)) -> AdminUser:
    if user.role != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được thực hiện thao tác này.")
    return user
