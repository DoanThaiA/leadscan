"""Hạng thành viên theo tổng tiền đã nạp (phí thành viên + nạp điểm đã thanh toán — Company.topup_total).

- Thường : mặc định.
- Vàng   : tổng nạp từ cfg.gold_topup_threshold (10 triệu) → được MUA ĐỘC QUYỀN phiếu cơ hội (chỉ mình doanh nghiệp được mua,
           đóng các lượt còn lại) với giá = cfg.exclusive_price_multiplier (×2) giá phiếu đang hiển thị cho doanh nghiệp.

Hạng tính từ số đã nạp, không lưu riêng: nạp đủ là lên hạng ngay; không hạ hạng (tổng nạp chỉ tăng).
"""

from app.config import Settings, get_settings
from app.models import Company, Opportunity

TIERS = {"standard": "Thường", "gold": "Vàng"}


def tier_key(c: Company, cfg: Settings | None = None) -> str:
    cfg = cfg or get_settings()
    return "gold" if (c.topup_total or 0) >= cfg.gold_topup_threshold else "standard"


def tier_out(c: Company, cfg: Settings | None = None) -> dict:
    cfg = cfg or get_settings()
    key = tier_key(c, cfg)
    total = c.topup_total or 0
    return {
        "key": key,
        "label": TIERS[key],
        "topup_total": total,
        "gold_threshold": cfg.gold_topup_threshold,
        "to_gold": max(0, cfg.gold_topup_threshold - total),  # còn thiếu bao nhiêu để lên hạng Vàng
        "can_exclusive": key == "gold",
        "exclusive_multiplier": cfg.exclusive_price_multiplier,
    }


def exclusive_price(price: int, cfg: Settings | None = None) -> int:
    cfg = cfg or get_settings()
    return int(round(price * cfg.exclusive_price_multiplier))


def exclusive_offer(c: Company, o: Opportunity, price: int, cfg: Settings | None = None) -> dict:
    """Quyền mua độc quyền 1 phiếu: {available, price, reason}. Chỉ phiếu nhiều lượt mua và CHƯA ai mua mới mua độc quyền được."""
    cfg = cfg or get_settings()
    out = {"available": False, "price": exclusive_price(price, cfg), "reason": ""}
    if o.max_buyers <= 1:
        out["reason"] = "Phiếu này vốn đã độc quyền (chỉ 1 người mua)."
    elif o.sold_count > 0 or o.status != "published":
        out["reason"] = "Phiếu đã có người mua nên không còn mua độc quyền được."
    elif tier_key(c, cfg) != "gold":
        out["reason"] = f"Chỉ thành viên hạng Vàng (tổng nạp từ {cfg.gold_topup_threshold:,}đ) được mua độc quyền.".replace(",", ".")
    else:
        out["available"] = True
    return out
