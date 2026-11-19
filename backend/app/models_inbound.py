"""Thu thập cơ hội từ Gmail: thư khách gửi vào hộp thư → AI lọc + trích xuất → phiếu cơ hội NHÁP.

InboundEmail       1 thư Gmail (Apps Script đẩy qua POST /api/webhooks/gmail; chống trùng theo gmail_message_id)
InboundEmailBlock  người gửi / tên miền admin chặn (thư của họ bị bỏ qua, không gọi AI)

Trạng thái thư (status):
  new       vừa nhận, chờ xử lý (hoặc tạm hoãn: AI lỗi tạm thời / hết ngân sách AI)
  processing  worker đang xử lý (kẹt quá 30 phút → trả về new)
  skipped   lọc tầng 1 loại (noreply, thư quá ngắn, người gửi bị chặn) — không gọi AI
  rejected  AI: không phải cơ hội / ngoài lĩnh vực quan tâm (hoặc admin loại)
  review    cần admin xem: AI không chắc chắn, hoặc AI đang tắt
  drafted   đã tạo phiếu cơ hội nháp (opportunity_id)
  merged    cùng luồng thư với thư đã có phiếu → gắn vào phiếu đó, không tạo phiếu mới
  error     lỗi gọi AI / dữ liệu AI sai mẫu (thử lại bằng nút "Xử lý lại")

Quyền riêng tư: thư skipped / rejected bị xoá nội dung (body_text, ai_json) sau cfg.gmail_body_keep_days ngày,
chỉ giữ người gửi, tiêu đề, lý do.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

INBOUND_STATUSES = {
    "drafted": "Đã tạo nháp",
    "review": "Cần xem lại",
    "merged": "Gộp vào phiếu có sẵn",
    "rejected": "Không phải cơ hội",
    "skipped": "Bỏ qua (lọc sơ bộ)",
    "error": "Lỗi",
    "new": "Chờ xử lý",
    "processing": "Đang xử lý",
}


class InboundEmail(Base):
    __tablename__ = "inbound_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_message_id: Mapped[str] = mapped_column(String(100), unique=True)
    thread_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    from_email: Mapped[str] = mapped_column(String(200), default="", index=True)
    from_name: Mapped[str] = mapped_column(String(200), default="")
    to: Mapped[str] = mapped_column(String(500), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    body_text: Mapped[str] = mapped_column(Text, default="")
    attachment_names: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[str] = mapped_column(String(12), default="new", index=True)
    reason: Mapped[str] = mapped_column(String(500), default="")  # lý do bỏ qua / loại / cần xem lại
    error: Mapped[str] = mapped_column(String(500), default="")
    ai_json: Mapped[dict | None] = mapped_column(JSON)  # kết quả AI trích xuất (đã kiểm tra schema)
    ai_model: Mapped[str] = mapped_column(String(60), default="")
    ai_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    ai_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    ai_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))

    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime)  # đã xoá nội dung thư (quyền riêng tư)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    opportunity = relationship("Opportunity", lazy="joined")


class InboundEmailBlock(Base):
    """Chặn người gửi: pattern là email đầy đủ (a@b.com) hoặc tên miền (@b.com)."""

    __tablename__ = "inbound_email_blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(200), unique=True)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
