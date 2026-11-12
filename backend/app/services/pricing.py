"""Công thức giá phiếu cơ hội — tham số chỉnh được trên trang quản trị (/admin/co-hoi/cong-thuc-gia).

Giá thành viên phải trả = giá cơ bản × hệ số điểm phù hợp × hệ số gấp (hạn chót) × hệ số đủ thông tin × hệ số giá trị đơn,
làm tròn tới `round_to`, không thấp hơn giá cơ bản và `min_price`. Giá cơ bản 0 = phiếu miễn phí.

  hệ số điểm      = 1 + (score_max_mult − 1) × ((điểm − score_from) / (100 − score_from)) ^ score_curve   (điểm ≤ score_from: ×1)
  hệ số gấp       = urg_3 / urg_7 / urg_14 / urg_30 theo số ngày còn tới hạn chót (không có hạn / còn > 30 ngày / quá hạn: ×1)
  hệ số thông tin = 1 + (info_full_mult − 1) × tỷ lệ thông tin có đủ (0–1)
  hệ số giá trị   = value_m0 … value_m4 theo ngưỡng value_t1 < value_t2 < value_t3 < value_t4 (đ)

Giá lưu cố định vào từng lượt mua → đổi công thức chỉ ảnh hưởng giá hiển thị / lượt mua từ lúc lưu.
Tham số được nhớ tạm CACHE_SECONDS giây trong mỗi tiến trình (giá tính cho cả danh sách phiếu ở mỗi lần tải trang).
"""

import logging
import time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdminUser, PricingSetting, PricingSettingLog

log = logging.getLogger(__name__)

CACHE_SECONDS = 30

# key: (kiểu, mặc định, nhãn, min, max)
SETTINGS: dict[str, tuple] = {
    "min_price": (int, 29_000, "Giá tối thiểu 1 phiếu (đ)", 0, 100_000_000),
    "round_to": (int, 1_000, "Làm tròn giá tới (đ)", 1, 1_000_000),
    "score_from": (int, 50, "Điểm bắt đầu tăng giá", 0, 99),
    "score_max_mult": (float, 3.0, "Hệ số khi điểm phù hợp = 100", 1, 20),
    "score_curve": (float, 1.5, "Độ cong (1 = tăng đều; > 1 = càng gần 100 tăng càng nhanh)", 0.3, 5),
    "urg_3": (float, 1.4, "Còn ≤ 3 ngày tới hạn chót", 1, 10),
    "urg_7": (float, 1.32, "Còn ≤ 7 ngày", 1, 10),
    "urg_14": (float, 1.24, "Còn ≤ 14 ngày", 1, 10),
    "urg_30": (float, 1.12, "Còn ≤ 30 ngày", 1, 10),
    "info_full_mult": (float, 1.5, "Hệ số khi phiếu đủ 100% thông tin", 1, 10),
    "value_t1": (int, 100_000_000, "Ngưỡng 1 (đ)", 0, 10**15),
    "value_t2": (int, 1_000_000_000, "Ngưỡng 2 (đ)", 0, 10**15),
    "value_t3": (int, 5_000_000_000, "Ngưỡng 3 (đ)", 0, 10**15),
    "value_t4": (int, 20_000_000_000, "Ngưỡng 4 (đ)", 0, 10**15),
    "value_m0": (float, 1.0, "Dưới ngưỡng 1 / không rõ giá trị", 0.1, 20),
    "value_m1": (float, 1.15, "Từ ngưỡng 1", 0.1, 20),
    "value_m2": (float, 1.3, "Từ ngưỡng 2", 0.1, 20),
    "value_m3": (float, 1.5, "Từ ngưỡng 3", 0.1, 20),
    "value_m4": (float, 1.8, "Từ ngưỡng 4", 0.1, 20),
}
DEFAULTS = {k: v[1] for k, v in SETTINGS.items()}

_cache: tuple[float, dict] | None = None


def clear_cache() -> None:
    global _cache
    _cache = None


def load(db: Session) -> dict:
    out = dict(DEFAULTS)
    for row in db.scalars(select(PricingSetting)):
        spec = SETTINGS.get(row.key)
        if spec:
            try:
                out[row.key] = spec[0](row.value)
            except ValueError:
                log.warning("Tham số giá %s không hợp lệ: %r", row.key, row.value)
    return out


def current() -> dict:
    """Tham số đang áp dụng (nhớ tạm CACHE_SECONDS giây). Lỗi đọc DB → dùng bản nhớ gần nhất hoặc mặc định."""
    global _cache
    now = time.monotonic()
    if _cache and now - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    from app.db import new_session

    try:
        with new_session() as db:
            vals = load(db)
    except Exception as e:  # noqa: BLE001 — bảng chưa migrate / DB lỗi: không làm hỏng việc hiển thị giá
        log.warning("Không đọc được tham số giá, dùng %s: %s", "bản nhớ gần nhất" if _cache else "mặc định", e)
        vals = _cache[1] if _cache else dict(DEFAULTS)
    _cache = (now, vals)
    return vals


def validate(changes: dict, base: dict) -> dict:
    """Kiểm tra & chuẩn hoá giá trị mới (gộp với base). Lỗi → HTTP 422 kèm nhãn tham số."""
    out = dict(base)
    for k, v in changes.items():
        spec = SETTINGS.get(k)
        if not spec:
            raise HTTPException(422, f"Tham số không hợp lệ: {k}")
        typ, _, label, lo, hi = spec
        try:
            v = typ(v)
        except (TypeError, ValueError):
            raise HTTPException(422, f"{label}: phải là số{' nguyên' if typ is int else ''}.") from None
        if typ is float:
            v = round(v, 4)
        if v < lo or v > hi:
            raise HTTPException(422, f"{label}: từ {lo:,} đến {hi:,}.".replace(",", "."))
        out[k] = v
    t = [out[f"value_t{i}"] for i in range(1, 5)]
    if any(a >= b for a, b in zip(t, t[1:])):
        raise HTTPException(422, "Các ngưỡng giá trị đơn hàng phải tăng dần (ngưỡng 1 < 2 < 3 < 4).")
    return out


def update(db: Session, changes: dict, actor: AdminUser, reason: str) -> dict:
    cur = load(db)
    new = validate(changes, cur)
    for k in SETTINGS:
        if new[k] == cur[k]:
            continue
        row = db.get(PricingSetting, k) or PricingSetting(key=k)
        row.value, row.updated_by_id = str(new[k]), actor.id
        db.add(row)
        db.add(PricingSettingLog(key=k, old_value=str(cur[k]), new_value=str(new[k]), reason=reason[:300], actor_id=actor.id))
    db.commit()
    clear_cache()
    return load(db)


# ------------------------------------------------------------------ các hệ số


def score_factor(c: dict, score: int) -> float:
    s = max(0, min(100, score))
    start = c["score_from"]
    if s <= start:
        return 1.0
    return 1 + (c["score_max_mult"] - 1) * ((s - start) / (100 - start)) ** c["score_curve"]


def urgency_factor(c: dict, urgency: int) -> float:
    """urgency theo matching.urgency_of: 100 (≤3 ngày) · 90 (≤7) · 80 (≤14) · 65 (≤30) · 50 (không hạn / xa) · 0 (quá hạn)."""
    if urgency >= 100:
        return c["urg_3"]
    if urgency >= 90:
        return c["urg_7"]
    if urgency >= 80:
        return c["urg_14"]
    if urgency >= 65:
        return c["urg_30"]
    return 1.0


def info_factor(c: dict, info: float) -> float:
    return 1 + (c["info_full_mult"] - 1) * max(0.0, min(1.0, info))


def value_factor(c: dict, value_vnd: int) -> float:
    for i in range(1, 5):
        if value_vnd < c[f"value_t{i}"]:
            return c[f"value_m{i - 1}"]
    return c["value_m4"]


def breakdown(base_price: int, score: int, urgency: int = 50, info: float = 0.0, value_vnd: int = 0, c: dict | None = None) -> dict:
    """Giá và từng hệ số (dùng cho trang quản trị xem thử)."""
    c = c or current()
    if base_price <= 0:
        return {"base": 0, "score": 1.0, "urgency": 1.0, "info": 1.0, "value": 1.0, "price": 0}
    base = max(base_price, c["min_price"])
    f = {"score": score_factor(c, score), "urgency": urgency_factor(c, urgency), "info": info_factor(c, info), "value": value_factor(c, value_vnd)}
    raw = base * f["score"] * f["urgency"] * f["info"] * f["value"]
    step = max(1, c["round_to"])
    return {"base": base, **{k: round(v, 4) for k, v in f.items()}, "price": max(base, round(raw / step) * step)}


def price_for(base_price: int, score: int, urgency: int = 50, info: float = 0.0, value_vnd: int = 0, c: dict | None = None) -> int:
    return breakdown(base_price, score, urgency, info, value_vnd, c)["price"]
