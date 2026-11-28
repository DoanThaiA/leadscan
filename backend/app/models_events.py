"""Sự kiện (/su-kien) và đăng ký tham dự.

Event               trang sự kiện: nội dung, ảnh, phí tham dự, tài khoản nhận tiền để sinh mã VietQR
  └─ EventRegistration   1 người đăng ký: thông tin liên hệ, nhu cầu xúc tiến, profile PDF (R2),
                         ảnh chuyển khoản (R2) và kết quả đối soát bằng OCR.

Luồng khách: điền form → hệ thống cấp mã đăng ký (dùng làm nội dung chuyển khoản) và mã QR →
khách chuyển khoản, tải ảnh biên lai lên → OCR đọc ảnh, so khớp mã đăng ký + số tiền:
khớp đủ → "Đã thanh toán"; thiếu/không đọc được → "Chờ đối soát" để admin tự xác nhận.

Tệp (profile PDF, ảnh biên lai) nằm trên Cloudflare R2 bucket riêng tư, thư mục SUKIEN/ — DB chỉ giữ key.
"""

from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

EVENT_STATUSES = {"draft": "Bản nháp", "published": "Đang mở", "closed": "Đã đóng"}

# Loại người tham dự → quyết định mức phí
ATTENDEE_TYPES = {"member": "Thành viên CLB", "guest": "Khách mời ngoài CLB"}

EVENT_REG_STATUSES = {
    "new": "Chờ thanh toán",
    "review": "Chờ đối soát",
    "paid": "Đã thanh toán",
    "cancelled": "Đã huỷ",
}

# Kết quả đọc ảnh chuyển khoản bằng OCR.space
OCR_STATUSES = {
    "none": "Chưa có ảnh",
    "matched": "Khớp tự động",
    "mismatch": "Không khớp",
    "unreadable": "Không đọc được chữ",
    "error": "Lỗi gọi OCR",
    "off": "Chưa bật OCR",
}


class Event(Base):
    """Sự kiện hiện trên /su-kien. Chỉ bản "published" được khách xem và đăng ký.

    Các mục nội dung là văn bản thuần với định dạng nhẹ giống bài tuyển dụng:
    dòng "## " = tiêu đề nhỏ, "- " = gạch đầu dòng, "1. " = danh sách số, **chữ đậm**, dòng trống = đoạn mới.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True)  # /su-kien/<slug>
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)

    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")  # 1–2 câu trên thẻ danh sách
    host: Mapped[str] = mapped_column(String(200), default="")  # đơn vị tổ chức
    partner: Mapped[str] = mapped_column(String(200), default="")  # đơn vị phối hợp / chủ nhà

    starts_at: Mapped[datetime | None] = mapped_column(DateTime)  # giờ Việt Nam, lưu naive
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    venue: Mapped[str] = mapped_column(String(200), default="")  # tên địa điểm
    address: Mapped[str] = mapped_column(String(300), default="")
    deadline: Mapped[date | None] = mapped_column(Date)  # hạn đăng ký (hết ngày này tự đóng form)
    capacity: Mapped[int | None] = mapped_column(Integer)  # số chỗ (trống = không giới hạn)

    cover_image: Mapped[str] = mapped_column(String(500), default="")  # ảnh bìa / poster
    banner_image: Mapped[str] = mapped_column(String(500), default="")  # ảnh minh hoạ trong bài

    intro: Mapped[str] = mapped_column(Text, default="")  # tinh thần chương trình
    agenda: Mapped[str] = mapped_column(Text, default="")  # chương trình chi tiết
    content: Mapped[str] = mapped_column(Text, default="")  # khung nội dung chia sẻ
    matching: Mapped[str] = mapped_column(Text, default="")  # kết nối giao thương / nhu cầu hai bên
    notes: Mapped[str] = mapped_column(Text, default="")  # lưu ý, quyền lợi, liên hệ

    # Phí tham dự (VND). 0 = miễn phí cho nhóm đó → bỏ qua bước thanh toán.
    fee_member: Mapped[int] = mapped_column(Integer, default=0)
    fee_guest: Mapped[int] = mapped_column(Integer, default=0)
    fee_note: Mapped[str] = mapped_column(String(300), default="")

    # Tài khoản nhận phí để sinh VietQR (trống = lấy tài khoản thu chung trong cấu hình)
    bank_bin: Mapped[str] = mapped_column(String(10), default="")  # mã BIN NAPAS, vd 970418
    bank_name: Mapped[str] = mapped_column(String(100), default="")
    account_no: Mapped[str] = mapped_column(String(40), default="")
    account_name: Mapped[str] = mapped_column(String(120), default="")

    contact_name: Mapped[str] = mapped_column(String(120), default="")
    contact_phone: Mapped[str] = mapped_column(String(20), default="")
    notify_email: Mapped[str] = mapped_column(String(200), default="")  # email nhận báo đăng ký mới

    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EventRegistration(Base):
    """1 lượt đăng ký tham dự. `code` vừa là mã tra cứu của khách, vừa là nội dung chuyển khoản để đối soát."""

    __tablename__ = "event_registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), index=True)
    event_title: Mapped[str] = mapped_column(String(200))  # giữ lại kể cả khi sự kiện bị xoá
    code: Mapped[str] = mapped_column(String(16), unique=True)  # vd SK7KQ4M2 — nội dung chuyển khoản
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)

    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(150))
    company: Mapped[str] = mapped_column(String(200), default="")
    position: Mapped[str] = mapped_column(String(120), default="")
    attendee_type: Mapped[str] = mapped_column(String(10), default="member")
    needs: Mapped[str] = mapped_column(Text, default="")  # nhu cầu xúc tiến hợp tác

    amount: Mapped[int] = mapped_column(Integer, default=0)  # phí phải nộp (VND)

    # Profile doanh nghiệp (PDF) khách đính kèm — R2, thư mục SUKIEN/profile/
    profile_key: Mapped[str] = mapped_column(String(400), default="")
    profile_filename: Mapped[str] = mapped_column(String(200), default="")
    profile_mime: Mapped[str] = mapped_column(String(100), default="")
    profile_size: Mapped[int] = mapped_column(BigInteger, default=0)

    # Ảnh chụp màn hình chuyển khoản — R2, thư mục SUKIEN/thanh-toan/
    proof_key: Mapped[str] = mapped_column(String(400), default="")
    proof_filename: Mapped[str] = mapped_column(String(200), default="")
    proof_mime: Mapped[str] = mapped_column(String(100), default="")
    proof_size: Mapped[int] = mapped_column(BigInteger, default=0)
    proof_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Đối soát bằng OCR.space
    ocr_status: Mapped[str] = mapped_column(String(12), default="none")
    ocr_text: Mapped[str] = mapped_column(Text, default="")  # chữ đọc được (cắt bớt), để admin xem lại
    ocr_amount: Mapped[int | None] = mapped_column(BigInteger)  # số tiền lớn nhất đọc được
    ocr_checks: Mapped[dict | None] = mapped_column(JSON)  # {"code": true, "amount": true, "account": false}
    ocr_message: Mapped[str] = mapped_column(String(300), default="")
    ocr_at: Mapped[datetime | None] = mapped_column(DateTime)
    ocr_tries: Mapped[int] = mapped_column(Integer, default=0)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    checked_in: Mapped[bool] = mapped_column(Boolean, default=False)

    note: Mapped[str] = mapped_column(Text, default="")  # ghi chú nội bộ của ban tổ chức
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # đã báo ban tổ chức
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    event: Mapped[Event | None] = relationship(lazy="joined")
