"""API quản trị — mã khuyến mãi: /api/admin/promos

GET     danh sách mã + lượt đã dùng, tổng tiền đã giảm (nhân viên xem được)
POST    tạo mã (chỉ quản trị viên)
PUT     /{id} sửa mã (chỉ quản trị viên; mã đã có đơn dùng thì không đổi được chữ mã)
DELETE  /{id} xoá mã chưa có đơn nào dùng (đã dùng thì tắt mã thay vì xoá)
POST    /banners/init, /banners/{upload_id}/complete  tải ảnh banner thẳng lên R2 → đường dẫn công khai
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app.db import get_db, utcnow
from app.models import PROMO_SCOPES, PROMO_TYPES, AdminUser, PaymentOrder, PromoCode
from app.services import job_covers, promos

router = APIRouter(prefix="/api/admin/promos")


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _state(p: PromoCode, used: int) -> str:
    now = utcnow()
    if not p.is_active:
        return "off"
    if p.ends_at and p.ends_at < now:
        return "ended"
    if p.starts_at and p.starts_at > now:
        return "scheduled"
    if p.max_uses is not None and used >= p.max_uses:
        return "used_up"
    return "active"


def _out(db: Session, p: PromoCode, stats: dict[int, tuple[int, int]] | None = None) -> dict:
    used = promos.used_count(db, p.id)
    paid, total = (stats if stats is not None else promos.paid_stats(db, [p.id])).get(p.id, (0, 0))
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "discount_type": p.discount_type,
        "discount_value": p.discount_value,
        "max_discount": p.max_discount,
        "min_amount": p.min_amount,
        "applies_to": p.applies_to,
        "max_uses": p.max_uses,
        "per_company_limit": p.per_company_limit,
        "starts_on": promos.vn_date(p.starts_at),
        "ends_on": promos.vn_date(p.ends_at),
        "is_active": p.is_active,
        "show_banner": p.show_banner,
        "banner_image": p.banner_image,
        "banner_title": p.banner_title,
        "banner_text": p.banner_text,
        "description": promos.describe(p),
        "state": _state(p, used),
        "used": used,  # đơn đã thanh toán + đơn đang chờ còn hạn
        "paid_count": paid,
        "discount_total": total,
        "created_by": p.created_by.full_name if p.created_by else None,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


@router.get("")
def list_promos(
    q: str = Query("", max_length=100),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(PromoCode)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(PromoCode.code.ilike(like), PromoCode.name.ilike(like)))
    rows = db.scalars(stmt.order_by(PromoCode.id.desc()).limit(500)).unique().all()
    stats = promos.paid_stats(db, [p.id for p in rows])
    return {
        "items": [_out(db, p, stats) for p in rows],
        "types": PROMO_TYPES,
        "scopes": PROMO_SCOPES,
    }


class PromoIn(BaseModel):
    code: str = Field(max_length=40)
    name: str = Field("", max_length=200)
    discount_type: str
    discount_value: int = Field(ge=1, le=10**12)
    max_discount: int | None = Field(None, ge=1, le=10**12)
    min_amount: int = Field(0, ge=0, le=10**12)
    applies_to: str = "all"
    max_uses: int | None = Field(None, ge=1, le=10**9)
    per_company_limit: int | None = Field(1, ge=1, le=10**6)
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool = True
    show_banner: bool = False
    banner_image: str = Field("", max_length=500)
    banner_title: str = Field("", max_length=150)
    banner_text: str = Field("", max_length=500)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = promos.norm_code(v)
        if not promos.CODE_RE.match(v):
            raise ValueError("Mã gồm 3–30 ký tự: chữ cái không dấu, số, gạch ngang hoặc gạch dưới.")
        return v

    @field_validator("discount_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in PROMO_TYPES:
            raise ValueError("Kiểu giảm giá không hợp lệ.")
        return v

    @field_validator("applies_to")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v not in PROMO_SCOPES:
            raise ValueError("Phạm vi áp dụng không hợp lệ.")
        return v

    @model_validator(mode="after")
    def _check(self):
        if self.discount_type == "percent" and self.discount_value > 100:
            raise ValueError("Giảm theo % chỉ từ 1 đến 100.")
        if self.discount_type == "amount":
            self.max_discount = None
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu.")
        self.name = " ".join(self.name.split())
        self.banner_image = self.banner_image.strip()
        self.banner_title = " ".join(self.banner_title.split())
        self.banner_text = self.banner_text.strip()
        if self.banner_image and not promos.BANNER_IMAGE_RE.match(self.banner_image):
            raise ValueError("Ảnh banner phải là ảnh tải lên hoặc đường dẫn https://.")
        if self.show_banner and not self.banner_image:
            raise ValueError("Vui lòng tải ảnh banner trước khi bật hiển thị trên trang chủ.")
        return self


def _apply(p: PromoCode, body: PromoIn) -> None:
    for f in ("code", "name", "discount_type", "discount_value", "max_discount", "min_amount", "applies_to", "max_uses",
              "per_company_limit", "is_active", "show_banner", "banner_image", "banner_title", "banner_text"):
        setattr(p, f, getattr(body, f))
    p.starts_at = promos.start_of_day_utc(body.starts_on) if body.starts_on else None
    p.ends_at = promos.end_of_day_utc(body.ends_on) if body.ends_on else None


def _order_count(db: Session, promo_id: int) -> int:
    return db.scalar(select(func.count(PaymentOrder.id)).where(PaymentOrder.promo_id == promo_id)) or 0


def _save(db: Session, p: PromoCode) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Mã khuyến mãi này đã tồn tại.") from None


class BannerInitIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    size: int = Field(ge=1)


@router.post("/banners/init", status_code=201)
def banner_init(body: BannerInitIn, _: AdminUser = Depends(require_admin)):
    """Ảnh banner: cấp link PUT ký sẵn để trình duyệt tải thẳng lên R2."""
    return job_covers.init_upload(body.filename, body.size, prefix=promos.BANNER_PREFIX)


@router.post("/banners/{upload_id}/complete")
def banner_complete(upload_id: str, _: AdminUser = Depends(require_admin)):
    """Ảnh đã lên R2 → kiểm tra, xoá EXIF, chuẩn hoá WebP → đường dẫn công khai để lưu vào mã."""
    return job_covers.complete_upload(upload_id, prefix=promos.BANNER_PREFIX, public_path=promos.BANNER_PATH)


@router.post("", status_code=201)
def create_promo(body: PromoIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(PromoCode.id).where(PromoCode.code == body.code)):
        raise HTTPException(409, "Mã khuyến mãi này đã tồn tại.")
    p = PromoCode(created_by_id=user.id)
    _apply(p, body)
    db.add(p)
    _save(db, p)
    db.refresh(p)
    return _out(db, p)


@router.put("/{promo_id}")
def update_promo(promo_id: int, body: PromoIn, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(PromoCode, promo_id)
    if not p:
        raise HTTPException(404, "Không tìm thấy mã khuyến mãi.")
    if body.code != p.code and _order_count(db, p.id):
        raise HTTPException(409, "Mã đã có đơn sử dụng nên không đổi được chữ mã. Hãy tắt mã này và tạo mã mới.")
    _apply(p, body)
    _save(db, p)
    db.refresh(p)
    return _out(db, p)


@router.delete("/{promo_id}", status_code=204)
def delete_promo(promo_id: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(PromoCode, promo_id)
    if not p:
        raise HTTPException(404, "Không tìm thấy mã khuyến mãi.")
    if _order_count(db, p.id):
        raise HTTPException(409, "Mã đã có đơn sử dụng — hãy tắt mã thay vì xoá để giữ lịch sử.")
    db.delete(p)
    db.commit()
