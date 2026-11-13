"""Mã khuyến mãi giảm tiền đơn thanh toán (phí thành viên / nạp điểm).

- Giảm theo % (có thể đặt mức giảm tối đa) hoặc giảm số tiền cố định; không bao giờ giảm quá giá trị đơn.
- Điểm cộng vào ví vẫn theo giá gốc — khuyến mãi chỉ giảm số tiền phải trả.
- Đơn còn 0đ sau khi giảm → kích hoạt luôn, không cần thanh toán (routes/member.create_order).
- Lượt dùng = đơn đã thanh toán + đơn đang chờ thanh toán còn hạn có gắn mã. Đơn huỷ / hết hạn trả lại lượt.
"""

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, lazyload

from app.db import utcnow
from app.models import PROMO_SCOPES, PaymentOrder, PromoCode

VN = ZoneInfo("Asia/Ho_Chi_Minh")
CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,29}$")


def norm_code(raw: str | None) -> str:
    return re.sub(r"\s+", "", raw or "").upper()[:30]


def vnd(n: int) -> str:
    return f"{n:,}đ".replace(",", ".")


# ------------------------------------------------------------------ ngày áp dụng (nhập theo giờ Việt Nam, lưu UTC)


def start_of_day_utc(d: date) -> datetime:
    return datetime.combine(d, time.min, VN).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def end_of_day_utc(d: date) -> datetime:
    return start_of_day_utc(d + timedelta(days=1)) - timedelta(seconds=1)


def vn_date(dt: datetime | None) -> str | None:
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(VN).date().isoformat() if dt else None


# ------------------------------------------------------------------ tính giảm & kiểm tra


def compute_discount(p: PromoCode, amount: int) -> int:
    if amount <= 0:
        return 0
    if p.discount_type == "percent":
        d = amount * p.discount_value // 100
        if p.max_discount:
            d = min(d, p.max_discount)
    else:
        d = p.discount_value
    return max(0, min(d, amount))


def _live_orders(promo_id: int):
    """Đơn đang giữ lượt của mã: đã thanh toán, hoặc đang chờ thanh toán còn hạn."""
    return and_(
        PaymentOrder.promo_id == promo_id,
        or_(PaymentOrder.status == "paid", and_(PaymentOrder.status == "pending", PaymentOrder.expires_at > utcnow())),
    )


def used_count(db: Session, promo_id: int, company_id: int | None = None) -> int:
    stmt = select(func.count(PaymentOrder.id)).where(_live_orders(promo_id))
    if company_id is not None:
        stmt = stmt.where(PaymentOrder.company_id == company_id)
    return db.scalar(stmt) or 0


def paid_stats(db: Session, promo_ids: list[int]) -> dict[int, tuple[int, int]]:
    """{promo_id: (số đơn đã thanh toán, tổng tiền đã giảm)}"""
    if not promo_ids:
        return {}
    rows = db.execute(
        select(PaymentOrder.promo_id, func.count(PaymentOrder.id), func.coalesce(func.sum(PaymentOrder.discount), 0))
        .where(PaymentOrder.promo_id.in_(promo_ids), PaymentOrder.status == "paid")
        .group_by(PaymentOrder.promo_id)
    ).all()
    return {r[0]: (int(r[1]), int(r[2])) for r in rows}


def check(db: Session, raw_code: str, kind: str, amount: int, company_id: int, *, lock: bool = False) -> tuple[PromoCode, int]:
    """Mã hợp lệ cho đơn này → (mã, số tiền giảm). Không hợp lệ → HTTPException 400 kèm lý do cho khách.

    lock=True khi tạo đơn: khoá dòng mã khuyến mãi tới hết giao dịch để 2 đơn đồng thời không vượt số lượt.
    """
    code = norm_code(raw_code)
    stmt = select(PromoCode).where(PromoCode.code == code)
    if lock:
        # Không JOIN người tạo mã (created_by lazy="joined"): PostgreSQL không cho FOR UPDATE trên LEFT OUTER JOIN
        stmt = stmt.options(lazyload(PromoCode.created_by)).with_for_update(of=PromoCode)
    p = db.scalar(stmt) if code else None
    now = utcnow()
    if not p or not p.is_active:
        raise HTTPException(400, "Mã khuyến mãi không tồn tại hoặc đã ngừng áp dụng.")
    if p.starts_at and p.starts_at > now:
        raise HTTPException(400, f"Mã khuyến mãi áp dụng từ ngày {_fmt_date(p.starts_at)}.")
    if p.ends_at and p.ends_at < now:
        raise HTTPException(400, "Mã khuyến mãi đã hết hạn.")
    if p.applies_to != "all" and p.applies_to != kind:
        raise HTTPException(400, f"Mã này chỉ áp dụng cho đơn {PROMO_SCOPES[p.applies_to].lower()}.")
    if amount < (p.min_amount or 0):
        raise HTTPException(400, f"Mã này áp dụng cho đơn từ {vnd(p.min_amount)}.")
    if p.max_uses is not None and used_count(db, p.id) >= p.max_uses:
        raise HTTPException(400, "Mã khuyến mãi đã hết lượt sử dụng.")
    if p.per_company_limit is not None and used_count(db, p.id, company_id) >= p.per_company_limit:
        raise HTTPException(400, "Doanh nghiệp của bạn đã dùng hết lượt của mã khuyến mãi này.")
    return p, compute_discount(p, amount)


def _fmt_date(dt: datetime) -> str:
    d = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(VN)
    return d.strftime("%d/%m/%Y")


def describe(p: PromoCode) -> str:
    """vd "Giảm 20% (tối đa 50.000đ)" / "Giảm 30.000đ" """
    if p.discount_type == "percent":
        s = f"Giảm {p.discount_value}%"
        return s + (f" (tối đa {vnd(p.max_discount)})" if p.max_discount else "")
    return f"Giảm {vnd(p.discount_value)}"


# ------------------------------------------------------------------ banner trang chủ

BANNER_PREFIX = "promo-banners"  # thư mục ảnh trên R2
BANNER_PATH = "/api/promos/banners"  # đường dẫn công khai đọc ảnh
BANNER_IMAGE_RE = re.compile(r"^(/(?!/)\S*|https://\S+)$")  # ảnh tải lên / ảnh trong web/public / URL https
MAX_BANNERS = 10


def usable_now(db: Session, p: PromoCode) -> bool:
    """Mã đang dùng được với khách nói chung (bật, trong thời gian, còn lượt)."""
    now = utcnow()
    if not p.is_active or (p.starts_at and p.starts_at > now) or (p.ends_at and p.ends_at < now):
        return False
    return p.max_uses is None or used_count(db, p.id) < p.max_uses


def active_banners(db: Session) -> list[dict]:
    """Banner khuyến mãi hiện trên trang chủ: mã bật banner, có ảnh và còn dùng được. Mới nhất trước."""
    rows = db.scalars(
        select(PromoCode)
        .where(PromoCode.show_banner.is_(True), PromoCode.is_active.is_(True), PromoCode.banner_image != "")
        .order_by(PromoCode.id.desc())
        .limit(50)
    ).unique().all()
    out = []
    for p in rows:
        if not usable_now(db, p):
            continue
        out.append({
            "id": p.id,
            "code": p.code,
            "title": p.banner_title or p.name or describe(p),
            "text": p.banner_text,
            "description": describe(p),
            "applies_to": p.applies_to,
            "applies_label": PROMO_SCOPES[p.applies_to],
            "image": p.banner_image,
            "ends_on": vn_date(p.ends_at),
        })
        if len(out) >= MAX_BANNERS:
            break
    return out
