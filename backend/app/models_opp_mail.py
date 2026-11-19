"""Nhật ký gửi phiếu cơ hội cho khách hàng qua email (admin chọn người nhận ở trang phiếu cơ hội).

OpportunityEmail   1 dòng = 1 email gửi 1 người liên hệ (contacts) của doanh nghiệp thành viên về 1 cơ hội
  member_user_id: chỉ có ở các dòng cũ (trước khi chuyển sang gửi người liên hệ) — dòng mới để trống
  status: queued (đã xếp hàng) → sent (gửi được) | failed (Resend/SMTP lỗi, xem error)
Email chỉ chứa phần xem trước công khai của phiếu (không tên bên có nhu cầu, không đầu mối, không chi tiết).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

OPP_EMAIL_STATUSES = {"queued": "Đang gửi", "sent": "Đã gửi", "failed": "Gửi lỗi"}


class OpportunityEmail(Base):
    __tablename__ = "opportunity_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    member_user_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"), index=True)
    email: Mapped[str] = mapped_column(String(150))
    recipient_name: Mapped[str] = mapped_column(String(100), default="")
    note: Mapped[str] = mapped_column(Text, default="")  # lời nhắn của admin trong email
    status: Mapped[str] = mapped_column(String(10), default="queued", index=True)
    error: Mapped[str] = mapped_column(String(300), default="")
    sent_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    company = relationship("Company", lazy="joined")
    sent_by = relationship("AdminUser", lazy="joined")
