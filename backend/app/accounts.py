"""Một tài khoản LeadScan cho cả cổng thành viên và cổng đối tác.

Dữ liệu 2 cổng vẫn ở 2 bảng (member_users gắn doanh nghiệp, partner_users là cá nhân/tổ chức giới thiệu cơ hội),
nhưng cùng EMAIL = cùng 1 tài khoản: dùng chung mật khẩu, đăng nhập ở cổng nào cũng mở phiên cho cả 2 cổng
(nếu email có hồ sơ ở cổng đó) và mỗi cổng vẫn hiện giao diện riêng.

- Đăng ký hồ sơ thứ 2 bằng email đã có (thành viên → đối tác hoặc ngược lại) phải nhập đúng mật khẩu hiện có;
  hồ sơ mới dùng lại đúng mật khẩu đó.
- Đổi / đặt lại mật khẩu ở cổng nào cũng áp dụng cho cả 2 cổng.
- Đăng xuất ở cổng nào cũng đăng xuất cả 2 cổng.
- Dữ liệu cũ có 2 hồ sơ cùng email nhưng khác mật khẩu: mật khẩu khớp hồ sơ nào thì mở hồ sơ đó; lần đổi / đặt
  lại mật khẩu tiếp theo sẽ đồng bộ cả 2.
"""

from fastapi import Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, object_session

from app import member_auth, partner_auth
from app.models import MemberSession, MemberUser, PartnerSession, PartnerUser
from app.security import DUMMY_HASH, verify_password

MEMBER_HOME = "/thanh-vien"
PARTNER_HOME = "/doi-tac/tong-quan"


def norm_email(email: str) -> str:
    return (email or "").strip().lower()


def member_by_email(db: Session, email: str) -> MemberUser | None:
    return db.scalar(select(MemberUser).where(MemberUser.email == norm_email(email)))


def partner_by_email(db: Session, email: str) -> PartnerUser | None:
    return db.scalar(select(PartnerUser).where(PartnerUser.email == norm_email(email)))


def member_usable(m: MemberUser | None) -> bool:
    return bool(m and m.is_active and m.company.status not in ("suspended", "rejected"))


def partner_usable(p: PartnerUser | None) -> bool:
    return bool(p and p.status == "active")


def authenticate(db: Session, email: str, password: str) -> tuple[MemberUser | None, PartnerUser | None]:
    """Hồ sơ thành viên / đối tác của email mà mật khẩu khớp (chưa xét bị khoá)."""
    m, p = member_by_email(db, email), partner_by_email(db, email)
    if not m and not p:
        verify_password(password, DUMMY_HASH)  # thời gian phản hồi như khi có tài khoản
        return None, None
    m_ok = bool(m) and verify_password(password, m.password_hash)
    if p and m and p.password_hash == m.password_hash:
        p_ok = m_ok  # đã dùng chung mật khẩu → khỏi băm lần 2
    else:
        p_ok = bool(p) and verify_password(password, p.password_hash)
    return (m if m_ok else None), (p if p_ok else None)


def portals(db: Session, email: str) -> dict:
    """Email này dùng được cổng nào (để hiện nút chuyển cổng)."""
    return {"member": member_usable(member_by_email(db, email)), "partner": partner_usable(partner_by_email(db, email))}


def portals_of(obj: MemberUser | PartnerUser) -> dict:
    db = object_session(obj)
    return portals(db, obj.email) if db else {"member": isinstance(obj, MemberUser), "partner": isinstance(obj, PartnerUser)}


def open_sessions(db: Session, m: MemberUser | None, p: PartnerUser | None, request: Request, response: Response) -> None:
    """Mở phiên cho mọi hồ sơ dùng được trong số đã xác thực mật khẩu."""
    if member_usable(m):
        member_auth.create_session(db, m, request, response)
    if partner_usable(p):
        partner_auth.create_session(db, p, request, response)


def logout_all(db: Session, request: Request, response: Response) -> None:
    member_auth.destroy_session(db, request, response)
    partner_auth.destroy_session(db, request, response)


def other_hash_for_signup(db: Session, other: MemberUser | PartnerUser | None, password: str) -> str | None:
    """Đăng ký hồ sơ ở cổng thứ 2: email đã có hồ sơ ở cổng kia → mật khẩu phải khớp, trả về hash dùng chung.

    Trả về None nếu chưa có hồ sơ ở cổng kia; raise ValueError nếu mật khẩu không khớp.
    """
    if other is None:
        return None
    if not verify_password(password, other.password_hash):
        raise ValueError("password")
    return other.password_hash


def sync_password(db: Session, email: str, pw_hash: str, *, end_sessions: bool) -> None:
    """Đặt cùng mật khẩu cho cả 2 hồ sơ của email. end_sessions: đăng xuất mọi phiên (đặt lại mật khẩu / admin đổi)."""
    m, p = member_by_email(db, email), partner_by_email(db, email)
    if m:
        m.password_hash = pw_hash
        if end_sessions:
            db.execute(delete(MemberSession).where(MemberSession.user_id == m.id))
    if p:
        p.password_hash = pw_hash
        if end_sessions:
            db.execute(delete(PartnerSession).where(PartnerSession.partner_id == p.id))

