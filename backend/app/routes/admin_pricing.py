"""API quản trị — công thức giá phiếu cơ hội: /api/admin/pricing

GET   tham số đang áp dụng + lịch sử thay đổi
PUT   lưu tham số (chỉ quản trị viên, bắt buộc lý do) — áp dụng cho giá hiển thị & lượt mua từ lúc lưu
POST  /preview  xem thử giá theo bộ tham số đang sửa (chưa lưu) so với bộ đang áp dụng
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app.db import get_db
from app.models import AdminUser, Opportunity, PricingSettingLog
from app.services import pricing
from app.services.matching import info_completeness, parse_value_vnd, urgency_from_days, urgency_of

router = APIRouter(prefix="/api/admin/pricing")


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _out(db: Session) -> dict:
    logs = db.scalars(select(PricingSettingLog).order_by(PricingSettingLog.id.desc()).limit(50)).unique().all()
    return {
        "values": pricing.load(db),
        "fields": [{"key": k, "label": v[2], "type": "int" if v[0] is int else "float", "min": v[3], "max": v[4], "default": v[1]}
                   for k, v in pricing.SETTINGS.items()],
        "logs": [{"key": x.key, "old": x.old_value, "new": x.new_value, "reason": x.reason, "actor": x.actor.full_name if x.actor else None,
                  "created_at": _iso(x.created_at)} for x in logs],
    }


@router.get("")
def get_pricing(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return _out(db)


class PricingIn(BaseModel):
    values: dict[str, float | int]
    reason: str = Field(min_length=3, max_length=300)


@router.put("")
def put_pricing(body: PricingIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    pricing.update(db, body.values, user, body.reason.strip())
    return _out(db)


class Scenario(BaseModel):
    score: int = Field(ge=0, le=100)
    base: int = Field(29_000, ge=0, le=1_000_000_000)
    days_left: int | None = Field(None, ge=-3650, le=3650)  # None = không có hạn chót
    info_pct: int = Field(0, ge=0, le=100)
    value_vnd: int = Field(0, ge=0, le=10**15)
    opp_code: str = Field("", max_length=30)  # có mã phiếu → lấy giá cơ bản, hạn chót, độ đủ thông tin, giá trị từ phiếu thật


class PreviewIn(BaseModel):
    values: dict[str, float | int] = {}
    scenarios: list[Scenario] = Field(min_length=1, max_length=20)


@router.post("/preview")
def preview(body: PreviewIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    cur = pricing.load(db)
    draft = pricing.validate(body.values, cur)
    out = []
    for sc in body.scenarios:
        base, urgency, info, value, opp = sc.base, urgency_from_days(sc.days_left), sc.info_pct / 100, sc.value_vnd, None
        if sc.opp_code.strip():
            o = db.scalar(select(Opportunity).where(Opportunity.code == sc.opp_code.strip().upper()))
            if not o:
                raise HTTPException(404, f"Không tìm thấy phiếu {sc.opp_code.strip().upper()}.")
            base, urgency, info, value = o.price, urgency_of(o, date.today()), info_completeness(o), parse_value_vnd(o.estimated_value)
            opp = {"code": o.code, "title": o.title, "base": o.price, "deadline": o.deadline.isoformat() if o.deadline else None,
                   "info_pct": round(info * 100), "value_vnd": value, "estimated_value": o.estimated_value}
        out.append({
            "opportunity": opp,
            "current": pricing.breakdown(base, sc.score, urgency, info, value, cur),
            "draft": pricing.breakdown(base, sc.score, urgency, info, value, draft),
        })
    return {"items": out}
