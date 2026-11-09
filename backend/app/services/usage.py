"""Đếm số lần gọi API bên ngoài theo tháng (bảng api_usage) để không vượt hạn mức khoá miễn phí.

Ghi bằng phiên DB riêng và commit ngay: lần gọi đã tính thì vẫn được tính kể cả khi việc so khớp sau đó lỗi/rollback.
"""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db import new_session, utcnow
from app.models import ApiUsage


def this_month() -> str:
    return utcnow().strftime("%Y-%m")


def calls_this_month(provider: str = "cohere") -> int:
    with new_session() as db:
        return db.scalar(select(ApiUsage.calls).where(ApiUsage.provider == provider, ApiUsage.month == this_month())) or 0


def reserve_call(provider: str, limit: int) -> bool:
    """Giữ chỗ 1 lần gọi trong tháng. False = đã hết hạn mức (limit 0 = không giới hạn, vẫn đếm)."""
    month = this_month()
    for _ in range(3):
        with new_session() as db:
            stmt = update(ApiUsage).where(ApiUsage.provider == provider, ApiUsage.month == month)
            if limit > 0:
                stmt = stmt.where(ApiUsage.calls < limit)  # kiểm tra + cộng trong 1 câu lệnh → không vượt khi chạy song song
            if db.execute(stmt.values(calls=ApiUsage.calls + 1, updated_at=utcnow())).rowcount:
                db.commit()
                return True
            if db.scalar(select(ApiUsage.id).where(ApiUsage.provider == provider, ApiUsage.month == month)):
                return False  # đã có dòng của tháng nhưng đạt hạn mức
            db.add(ApiUsage(provider=provider, month=month, calls=1))
            try:
                db.commit()
                return True
            except IntegrityError:  # tiến trình khác vừa tạo dòng của tháng → thử lại bằng UPDATE
                db.rollback()
    return False
