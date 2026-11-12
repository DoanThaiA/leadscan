"""API quản trị Đối tác: /api/admin/partners/*

Mốc 1: danh sách & chi tiết đối tác, xác nhận SĐT bằng tay (khi chưa có nhà cung cấp SMS), khoá/mở, đổi hạng, ghi chú.
Khoá tài khoản và đổi hạng (ảnh hưởng tiền hoa hồng) chỉ quản trị viên; nhân viên xác nhận SĐT và ghi chú.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app.db import get_db, utcnow
from app.models import PARTNER_KINDS, PARTNER_STATUSES, PARTNER_TIERS, AdminUser, PartnerEvent, PartnerUser
from app.partner_auth import end_all_sessions
from app.routes.partner import me_out
from app.services import partner_reports, partner_wallet
from app.services.partner_submissions import partner_stats

router = APIRouter(prefix="/api/admin/partners")


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _item(p: PartnerUser) -> dict:
    d = me_out(p)
    d.update(
        status=p.status,
        status_label=PARTNER_STATUSES.get(p.status, p.status),
        last_login_at=_iso(p.last_login_at),
    )
    return d


def _detail(db: Session, p: PartnerUser) -> dict:
    d = _item(p)
    events = db.scalars(select(PartnerEvent).where(PartnerEvent.partner_id == p.id).order_by(PartnerEvent.id.desc()).limit(100)).all()
    d.update(
        note=p.note,
        terms_version=p.terms_version,
        terms_accepted_at=_iso(p.terms_accepted_at),
        signup_ip=p.signup_ip,
        submissions=partner_stats(db, p.id),
        custom_rate=p.custom_rate,
        custom_cafe_quota=p.custom_cafe_quota,
        wallet=partner_wallet.wallet_summary(db, p),
        payout_profile=_payout_profile(db, p),
        flags=[f for f in partner_reports.fraud_flags(db) if any(x["id"] == p.id for x in f["partners"])],
        phone_verified_by=p.phone_verified_by_id,
        events=[
            {"id": e.id, "kind": e.kind, "content": e.content, "actor": e.actor.full_name if e.actor else None, "created_at": _iso(e.created_at)}
            for e in events
        ],
    )
    return d


def _payout_profile(db: Session, p: PartnerUser) -> dict | None:
    from app.services import partner_payouts as pay

    prof = pay.get_profile(db, p.id)
    out = pay.profile_out(prof)
    if out:
        out["shared_with"] = pay.shared_account_partners(db, prof.account_hash, p.id)  # cờ gian lận: trùng tài khoản ngân hàng
    return out


def _get(db: Session, partner_id: int) -> PartnerUser:
    p = db.get(PartnerUser, partner_id)
    if not p:
        raise HTTPException(404, "Không tìm thấy đối tác.")
    return p


@router.get("/meta")
def meta(_: AdminUser = Depends(current_user)):
    return {"statuses": PARTNER_STATUSES, "tiers": PARTNER_TIERS, "kinds": PARTNER_KINDS}


@router.get("")
def list_partners(
    q: str = Query("", max_length=100),
    status: str = "",
    verified: str = "",  # "" tất cả · "yes" đã xác thực SĐT · "no" chưa
    tier: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(PartnerUser)
    if q.strip():
        like = f"%{q.strip()}%"
        conds = [PartnerUser.full_name.ilike(like), PartnerUser.email.ilike(like), PartnerUser.code.ilike(like), PartnerUser.org_name.ilike(like)]
        digits = "".join(ch for ch in q if ch.isdigit())
        if len(digits) >= 4:
            conds += [PartnerUser.phone.like(f"%{digits}%"), PartnerUser.org_tax_code.like(f"%{digits}%")]
        stmt = stmt.where(or_(*conds))
    if status:
        stmt = stmt.where(PartnerUser.status == status)
    if tier:
        stmt = stmt.where(PartnerUser.tier == tier)
    if verified == "yes":
        stmt = stmt.where(PartnerUser.phone_verified_at.is_not(None))
    elif verified == "no":
        stmt = stmt.where(PartnerUser.phone_verified_at.is_(None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PartnerUser.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    counts = {
        "all": db.scalar(select(func.count()).select_from(PartnerUser)) or 0,
        "unverified": db.scalar(select(func.count()).select_from(PartnerUser).where(PartnerUser.phone_verified_at.is_(None), PartnerUser.status == "active")) or 0,
    }
    flags = partner_reports.flags_by_partner(db)
    items = [{**_item(p), "flags": flags.get(p.id, [])} for p in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items, "counts": counts}


@router.get("/{partner_id}")
def get_partner(partner_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _detail(db, _get(db, partner_id))


class VerifyPhoneIn(BaseModel):
    note: str = Field("", max_length=200)  # vd "Đã gọi xác nhận 12/11"


@router.post("/{partner_id}/verify-phone")
def verify_phone(partner_id: int, body: VerifyPhoneIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Xác nhận SĐT bằng tay (đã gọi điện / nhắn Zalo đúng số) — dùng khi chưa có nhà cung cấp OTP."""
    p = _get(db, partner_id)
    if p.phone_verified_at:
        raise HTTPException(409, "Số điện thoại đã được xác thực.")
    p.phone_verified_at, p.phone_verified_by_id = utcnow(), user.id
    note = f": {body.note.strip()}" if body.note.strip() else ""
    db.add(PartnerEvent(partner_id=p.id, kind="phone_verified", actor_id=user.id, content=f"Quản trị xác nhận SĐT {p.phone} bằng tay{note}"[:500]))
    db.commit()
    return _detail(db, p)


class PartnerUpdateIn(BaseModel):
    status: Literal["active", "locked"] | None = None
    tier: Literal["new", "silver", "strategic"] | None = None
    note: str | None = Field(None, max_length=5000)
    custom_rate: int | None = Field(None, ge=0, le=50)  # gửi null để bỏ thoả thuận riêng
    custom_cafe_quota: int | None = Field(None, ge=0, le=10_000)
    reason: str = Field("", max_length=300)  # lý do khoá/mở/đổi hạng — ghi vào nhật ký


@router.patch("/{partner_id}")
def update_partner(partner_id: int, body: PartnerUpdateIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    p = _get(db, partner_id)
    why = f" — {body.reason.strip()}" if body.reason.strip() else ""
    if (body.status is not None and body.status != p.status) or (body.tier is not None and body.tier != p.tier):
        if user.role != "admin":
            raise HTTPException(403, "Chỉ quản trị viên được khoá tài khoản hoặc đổi hạng đối tác.")
    if body.status is not None and body.status != p.status:
        if body.status == "locked" and not body.reason.strip():
            raise HTTPException(422, "Vui lòng ghi lý do khoá tài khoản.")
        p.status = body.status
        if body.status == "locked":
            end_all_sessions(db, p.id)
        label = "Khoá tài khoản" if body.status == "locked" else "Mở khoá tài khoản"
        db.add(PartnerEvent(partner_id=p.id, kind="status", actor_id=user.id, content=f"{label}{why}"[:500]))
    if body.tier is not None and body.tier != p.tier:
        old = PARTNER_TIERS.get(p.tier, p.tier)
        p.tier = body.tier
        db.add(PartnerEvent(partner_id=p.id, kind="tier", actor_id=user.id, content=f"Đổi hạng {old} → {PARTNER_TIERS[body.tier]}{why}"[:500]))
    for field, label in (("custom_rate", "Hoa hồng riêng (%)"), ("custom_cafe_quota", "Hạn mức ly cafe riêng/tháng")):
        if field in body.model_fields_set and getattr(body, field) != getattr(p, field):
            if user.role != "admin":
                raise HTTPException(403, "Chỉ quản trị viên được đặt thoả thuận riêng.")
            new = getattr(body, field)
            if field == "custom_rate" and new is not None and new > partner_wallet.settings(db)["rate_max"]:
                raise HTTPException(422, f"Hoa hồng riêng tối đa {partner_wallet.settings(db)['rate_max']}%.")
            old_v = getattr(p, field)
            setattr(p, field, new)
            db.add(PartnerEvent(partner_id=p.id, kind="tier", actor_id=user.id,
                                content=f"{label}: {'theo hạng' if old_v is None else old_v} → {'theo hạng' if new is None else new}{why}"[:500]))
    if body.note is not None and body.note != p.note:
        p.note = body.note
        db.add(PartnerEvent(partner_id=p.id, kind="note", actor_id=user.id, content="Cập nhật ghi chú nội bộ"))
    db.commit()
    return _detail(db, p)


# ================================================================== ví hoa hồng


@router.get("/{partner_id}/wallet")
def partner_wallet_view(
    partner_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    from app.models import PartnerCredit

    p = _get(db, partner_id)
    partner_wallet.release_due(db, p.id)
    stmt = select(PartnerCredit).where(PartnerCredit.partner_id == p.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PartnerCredit.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"summary": partner_wallet.wallet_summary(db, p), "total": total, "items": [partner_wallet.credit_out(c, admin=True) for c in rows]}


class AdjustIn(BaseModel):
    amount: int = Field(ge=-1_000_000_000, le=1_000_000_000)
    reason: str = Field(min_length=3, max_length=300)


@router.post("/{partner_id}/adjust")
def adjust_wallet(partner_id: int, body: AdjustIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Điều chỉnh tay (Khả dụng ngay) — vd. bù lỗi tính, khoản thưởng riêng theo hợp đồng. Bắt buộc lý do, ghi nhật ký."""
    p = _get(db, partner_id)
    partner_wallet.adjust(db, p, body.amount, body.reason.strip(), user)
    return _detail(db, p)


# ================================================================== cấu hình thưởng

settings_router = APIRouter(prefix="/api/admin/partner-settings")


def _settings_out(db: Session) -> dict:
    from app.models import PartnerSettingLog

    vals = partner_wallet.settings(db)
    logs = db.scalars(select(PartnerSettingLog).order_by(PartnerSettingLog.id.desc()).limit(50)).unique().all()
    return {
        "values": vals,
        "fields": [{"key": k, "label": v[2], "type": "int" if v[0] is int else "choice", "min": v[3] if v[0] is int else None,
                    "max": v[4], "default": v[1], "choices": partner_wallet.MODES if k == "reward_mode" else None} for k, v in partner_wallet.SETTINGS.items()],
        "logs": [{"key": x.key, "old": x.old_value, "new": x.new_value, "reason": x.reason, "actor": x.actor.full_name if x.actor else None,
                  "created_at": _iso(x.created_at)} for x in logs],
    }


@settings_router.get("")
def get_settings_view(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _settings_out(db)


class SettingsIn(BaseModel):
    values: dict[str, int | str]
    reason: str = Field(min_length=3, max_length=300)


@settings_router.put("")
def put_settings(body: SettingsIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Chỉ áp dụng cho các khoản ghi SAU khi đổi; khoản đã ghi giữ nguyên (có căn cứ tính trong từng khoản)."""
    partner_wallet.update_settings(db, body.values, user, body.reason.strip())
    return _settings_out(db)
