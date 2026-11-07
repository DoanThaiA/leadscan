"""API quản trị: /api/admin/*  (cần đăng nhập; quản lý nhân viên cần vai trò admin)."""

from collections import Counter
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import create_session, current_user, destroy_session, require_admin
from app.config import get_settings
from app.db import get_db, utcnow
from app.models import COMPANY_STATUSES, ROLES, Activity, AdminSession, AdminUser, Company, Contact, Profile
from app.registration_form import OPP_TYPES, REGIONS, SIZES, TICKETS, tax_key
from app.schemas import (
    CompanyListItem,
    CompanyOut,
    CompanyUpdateIn,
    ContactIn,
    ContactOut,
    LoginIn,
    NoteIn,
    PasswordChangeIn,
    ProfileIn,
    ProfileOut,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)
from app.security import DUMMY_HASH, add_hit, client_ip, hash_password, origin_allowed, rate_limited, sha256, verify_password

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
router = APIRouter(prefix="/api/admin")

FIELD_LABELS = {
    "name": "Tên doanh nghiệp",
    "tax_code": "Mã số thuế",
    "industry": "Ngành hàng",
    "company_size": "Quy mô",
    "province": "Tỉnh/thành",
    "address": "Địa chỉ",
    "website": "Website",
}


# ================================================================== đăng nhập


@router.post("/auth/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    cfg = get_settings()
    if not origin_allowed(request, cfg):
        raise HTTPException(403, "Yêu cầu không hợp lệ.")
    key = "login:" + sha256(client_ip(request, cfg))
    if rate_limited(db, key, cfg.login_attempts_per_15min, timedelta(minutes=15)):
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.")

    user = db.scalar(select(AdminUser).where(AdminUser.email == body.email.strip().lower()))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok or not user.is_active:
        add_hit(db, key)  # chỉ đếm lần sai
        db.commit()
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    create_session(db, user, request, response)
    return user


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    destroy_session(db, request, response)


@router.get("/auth/me", response_model=UserOut)
def me(user: AdminUser = Depends(current_user)):
    return user


@router.post("/auth/password", status_code=204)
def change_password(body: PasswordChangeIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")
    user.password_hash = hash_password(body.new_password)
    db.commit()


# ================================================================== danh mục & thống kê


@router.get("/meta")
def meta(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    staff = db.scalars(select(AdminUser).where(AdminUser.is_active).order_by(AdminUser.full_name)).all()
    return {
        "statuses": COMPANY_STATUSES,
        "roles": ROLES,
        "sizes": SIZES,
        "regions": REGIONS,
        "opp_types": OPP_TYPES,
        "tickets": TICKETS,
        "staff": [{"id": u.id, "full_name": u.full_name} for u in staff],
    }


@router.get("/stats")
def stats(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(Company.status, func.count()).group_by(Company.status)).all())
    now = utcnow()
    since = now - timedelta(days=30)
    created = db.scalars(select(Company.created_at).where(Company.created_at >= since)).all()
    vn = lambda d: d.replace(tzinfo=UTC).astimezone(VN_TZ).date()  # noqa: E731
    per_day = Counter(vn(d) for d in created)
    today = vn(now)
    daily = [
        {"date": (today - timedelta(days=i)).isoformat(), "count": per_day.get(today - timedelta(days=i), 0)}
        for i in range(29, -1, -1)
    ]
    recent = db.scalars(select(Company).options(selectinload(Company.contacts)).order_by(Company.id.desc()).limit(8)).unique().all()
    return {
        "total": sum(by_status.values()),
        "by_status": {k: by_status.get(k, 0) for k in COMPANY_STATUSES},
        "new_today": per_day.get(today, 0),
        "new_7d": sum(per_day.get(today - timedelta(days=i), 0) for i in range(7)),
        "daily": daily,
        "recent": [_list_item(c) for c in recent],
    }


# ================================================================== khách hàng


def _list_item(c: Company) -> dict:
    item = CompanyListItem.model_validate(c)
    item.primary_contact = ContactOut.model_validate(c.contacts[0]) if c.contacts else None
    return item.model_dump(mode="json")


def _get_company(db: Session, company_id: int) -> Company:
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Không tìm thấy khách hàng.")
    return c


def _log(c: Company, user: AdminUser, kind: str, content: str) -> None:
    c.activities.append(Activity(kind=kind, content=content, actor_id=user.id))


@router.get("/companies")
def list_companies(
    q: str = Query("", max_length=100),
    status: str = "",
    assigned: str = "",  # "" tất cả · "me" của tôi · "none" chưa giao · "<id>"
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Company)
    if q.strip():
        like = f"%{q.strip()}%"
        digits = "".join(ch for ch in q if ch.isdigit())
        contact_conds = [Contact.full_name.ilike(like), Contact.email.ilike(like)]
        if len(digits) >= 4:
            contact_conds.append(Contact.phone.like(f"%{digits}%"))
        contact_match = select(Contact.company_id).where(or_(*contact_conds))
        stmt = stmt.where(
            or_(Company.name.ilike(like), Company.code.ilike(like), Company.tax_code.like(like), Company.id.in_(contact_match))
        )
    if status:
        stmt = stmt.where(Company.status == status)
    if assigned == "me":
        stmt = stmt.where(Company.assigned_to_id == user.id)
    elif assigned == "none":
        stmt = stmt.where(Company.assigned_to_id.is_(None))
    elif assigned.isdigit():
        stmt = stmt.where(Company.assigned_to_id == int(assigned))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.options(selectinload(Company.contacts)).order_by(Company.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_list_item(c) for c in rows]}


@router.get("/companies/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _get_company(db, company_id)


@router.patch("/companies/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int, body: CompanyUpdateIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)
):
    c = _get_company(db, company_id)
    changes = body.model_dump(exclude_unset=True, exclude={"status", "assigned_to_id", "unassign"})

    if body.tax_code:
        new_key = tax_key(body.tax_code)
        if new_key != c.tax_key and db.scalar(select(Company.id).where(Company.tax_key == new_key, Company.id != c.id)):
            raise HTTPException(409, "Mã số thuế này đã thuộc về khách hàng khác.")

    changed = []
    for field, value in changes.items():
        if value is not None and getattr(c, field) != value:
            setattr(c, field, value)
            changed.append(FIELD_LABELS[field])
            if field == "tax_code":
                c.tax_key = tax_key(value)
    if changed:
        _log(c, user, "update", "Cập nhật: " + ", ".join(changed))

    if body.status and body.status != c.status:
        _log(c, user, "status", f"{COMPANY_STATUSES[c.status]} → {COMPANY_STATUSES[body.status]}")
        c.status = body.status

    if body.unassign and c.assigned_to_id is not None:
        c.assigned_to_id = None
        _log(c, user, "assign", "Bỏ người phụ trách")
    elif body.assigned_to_id is not None and body.assigned_to_id != c.assigned_to_id:
        staff = db.get(AdminUser, body.assigned_to_id)
        if not staff or not staff.is_active:
            raise HTTPException(400, "Nhân viên được giao không tồn tại hoặc đã khoá.")
        c.assigned_to_id = staff.id
        _log(c, user, "assign", f"Giao cho {staff.full_name}")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Mã số thuế này đã thuộc về khách hàng khác.") from None
    db.refresh(c)
    return c


@router.delete("/companies/{company_id}", status_code=204)
def delete_company(company_id: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(_get_company(db, company_id))
    db.commit()


@router.put("/companies/{company_id}/profile", response_model=ProfileOut)
def update_profile(company_id: int, body: ProfileIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    c = _get_company(db, company_id)
    if c.profile is None:
        c.profile = Profile()
    for k, v in body.model_dump().items():
        setattr(c.profile, k, v)
    _log(c, user, "update", "Cập nhật chân dung cơ hội")
    db.commit()
    db.refresh(c.profile)
    return c.profile


@router.post("/companies/{company_id}/notes", status_code=201)
def add_note(company_id: int, body: NoteIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    c = _get_company(db, company_id)
    _log(c, user, "note", body.content.strip())
    db.commit()
    return {"ok": True}


def _set_primary(c: Company, contact: Contact) -> None:
    for other in c.contacts:
        other.is_primary = other is contact


@router.post("/companies/{company_id}/contacts", response_model=ContactOut, status_code=201)
def add_contact(company_id: int, body: ContactIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    c = _get_company(db, company_id)
    contact = Contact(**body.model_dump())
    c.contacts.append(contact)
    if body.is_primary or len(c.contacts) == 1:
        _set_primary(c, contact)
    _log(c, user, "update", f"Thêm người liên hệ {contact.full_name}")
    db.commit()
    db.refresh(contact)
    return contact


def _get_contact(db: Session, contact_id: int) -> Contact:
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(404, "Không tìm thấy người liên hệ.")
    return contact


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, body: ContactIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    contact = _get_contact(db, contact_id)
    for k, v in body.model_dump(exclude={"is_primary"}).items():
        setattr(contact, k, v)
    if body.is_primary:
        _set_primary(contact.company, contact)
    _log(contact.company, user, "update", f"Sửa người liên hệ {contact.full_name}")
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    contact = _get_contact(db, contact_id)
    c = contact.company
    if len(c.contacts) <= 1:
        raise HTTPException(400, "Khách hàng phải có ít nhất 1 người liên hệ.")
    was_primary = contact.is_primary
    c.contacts.remove(contact)
    if was_primary:
        c.contacts[0].is_primary = True
    _log(c, user, "update", f"Xoá người liên hệ {contact.full_name}")
    db.commit()


# ================================================================== nhân viên (chỉ admin)


@router.get("/users", response_model=list[UserOut])
def list_users(_: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(AdminUser).order_by(AdminUser.id)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreateIn, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(AdminUser.id).where(AdminUser.email == body.email)):
        raise HTTPException(409, "Email này đã có tài khoản.")
    u = AdminUser(email=body.email, full_name=body.full_name, role=body.role, password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdateIn, me_: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(AdminUser, user_id)
    if not u:
        raise HTTPException(404, "Không tìm thấy nhân viên.")
    if u.id == me_.id and (body.is_active is False or (body.role and body.role != "admin")):
        raise HTTPException(400, "Không thể tự khoá hoặc tự bỏ quyền quản trị của chính mình.")
    if body.full_name is not None:
        u.full_name = body.full_name
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        u.password_hash = hash_password(body.password)
    if body.is_active is False or body.password:
        db.execute(delete(AdminSession).where(AdminSession.user_id == u.id))  # đăng xuất mọi thiết bị
    db.commit()
    db.refresh(u)
    return u
