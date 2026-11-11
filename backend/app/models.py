"""Dữ liệu riêng của LeadScan (không phụ thuộc hệ thống ngoài).

Company            doanh nghiệp đăng ký / thành viên
  ├─ Contact        người liên hệ (1 người chính + người khác)
  ├─ Profile        tiêu chí tìm cơ hội gần nhất (điền sẵn cho lần gửi yêu cầu sau)
  └─ Activity       lịch sử: tạo hồ sơ, đổi trạng thái, ghi chú chăm sóc
  ├─ MemberUser     tài khoản đăng nhập cổng thành viên
  ├─ WalletTransaction   sổ cái điểm (mỗi lần cộng/trừ 1 dòng, không sửa/xoá)
  ├─ PaymentOrder   đơn nạp tiền / phí thành viên (thanh toán qua cổng MCV → InfoCMS)
  │    ├─ McvPayment      mỗi mã QR MCV cấp cho đơn (1 đơn có thể nhiều payment_code); chống mở dịch vụ 2 lần
  │    └─ InvoiceRequest  thông tin xuất hoá đơn (tự xuất HĐĐT qua IAM Invoice, hoặc kế toán xuất thủ công)
  ├─ SearchRequest      yêu cầu "Enrich tìm kiếm cơ hội" (tiêu chí + mô tả, email báo admin)
  ├─ SavedOpportunity   cơ hội thành viên thêm vào kho (xem/mua sau; cơ hội phù hợp tự vào kho)
  ├─ UserOpportunity    "Tất cả cơ hội" của doanh nghiệp: cơ hội phù hợp + điểm riêng (không trùng)
  ├─ SearchRequestMatch cơ hội phù hợp với từng phiếu tìm cơ hội (xem khi mở phiếu)
  └─ Purchase       phiếu cơ hội đã mua
       └─ EnrichRequest   yêu cầu tìm thêm đầu mối
Opportunity        cơ hội kinh doanh (nhập tay; sau này do crawl + AI tạo)
  └─ OpportunityContact   đầu mối liên hệ — chỉ hiện sau khi mua phiếu
AdminUser / AdminSession   nhân viên quản trị và phiên đăng nhập
MemberSession / PasswordReset   phiên đăng nhập & đặt lại mật khẩu của thành viên
RateHit                    đếm lượt để giới hạn tần suất (đăng ký, đăng nhập)
ApiUsage                   đếm số lần gọi API ngoài theo tháng (Cohere: khoá Trial giới hạn 1.000 lần/tháng)
KnowledgeCompany           kho doanh nghiệp để AI quét (crawl từ bảng xếp hạng như PROFIT500 hoặc nhập tay)
JobPost                    bài tuyển dụng đăng trên /tuyen-dung
  └─ JobApplication         hồ sơ ứng viên gửi qua form (đồng thời email về hộp thư tuyển dụng)

Điểm: 1 điểm = 1đ. Số dư lưu ở Company.points_balance và luôn bằng tổng WalletTransaction.amount.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, EmbeddingVector, utcnow

# Vòng đời khách hàng
COMPANY_STATUSES = {
    "new": "Mới đăng ký",
    "contacted": "Đã liên hệ",
    "active": "Thành viên",
    "suspended": "Tạm khoá",
    "rejected": "Từ chối",
}
ROLES = {"admin": "Quản trị", "staff": "Nhân viên"}


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 của token trong cookie
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")

    user: Mapped[AdminUser] = relationship(lazy="joined")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # mã đăng ký LS-YYYYMMDD-XXXXXX
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)

    name: Mapped[str] = mapped_column(String(150))
    tax_code: Mapped[str] = mapped_column(String(20))
    tax_key: Mapped[str] = mapped_column(String(20), unique=True)  # chỉ chữ số, chống đăng ký trùng
    industry: Mapped[str] = mapped_column(String(300))  # nhiều ngành, cách nhau ", "
    company_size: Mapped[str] = mapped_column(String(40))
    province: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(200), default="")
    website: Mapped[str] = mapped_column(String(200), default="")

    source: Mapped[str] = mapped_column(String(40), default="landing")
    points_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    membership_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    assigned_to: Mapped[AdminUser | None] = relationship(lazy="joined")
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="(Contact.is_primary.desc(), Contact.id)"
    )
    profile: Mapped["Profile | None"] = relationship(back_populates="company", cascade="all, delete-orphan", uselist=False)
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="Activity.id.desc()"
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    position: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(150), default="", index=True)
    phone: Mapped[str] = mapped_column(String(20), default="", index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="contacts")


class Profile(Base):
    """Chân dung cơ hội — đầu vào cho AI matching/scoring ở giai đoạn sau."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True)
    offering: Mapped[str] = mapped_column(Text, default="")
    target_customers: Mapped[str] = mapped_column(Text, default="")
    target_regions: Mapped[list] = mapped_column(JSON, default=list)
    opp_types: Mapped[list] = mapped_column(JSON, default=list)
    expected_tickets: Mapped[str] = mapped_column(String(40), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    # Tiêu chí "Tìm cơ hội phù hợp" thành viên chọn trong cổng:
    # {"industries": [...], "regions": [...], "sizes": [...], "sources": [...], "min_score": 70}
    search: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    company: Mapped[Company] = relationship(back_populates="profile")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20))  # created | status | note | update | assign
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="activities")
    actor: Mapped[AdminUser | None] = relationship(lazy="joined")


class RateHit(Base):
    __tablename__ = "rate_hits"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), index=True)  # "reg:<sha256 ip>" / "login:<sha256 ip>"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    __table_args__ = (Index("ix_rate_hits_key_time", "key", "created_at"),)


class ApiUsage(Base):
    """Số lần gọi API bên ngoài theo tháng (giờ UTC) — để không vượt hạn mức của khoá miễn phí."""

    __tablename__ = "api_usage"
    __table_args__ = (UniqueConstraint("provider", "month", name="uq_api_usage_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))  # "cohere"
    month: Mapped[str] = mapped_column(String(7))  # "2026-11"
    calls: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ================================================================== thành viên (cổng khách hàng)

ORDER_KINDS = {"membership": "Phí thành viên", "topup": "Nạp thêm điểm"}
ORDER_STATUSES = {"pending": "Chờ thanh toán", "paid": "Đã thanh toán", "expired": "Hết hạn", "cancelled": "Đã huỷ"}
TX_KINDS = {
    "membership": "Phí thành viên",
    "topup": "Nạp điểm",
    "purchase": "Mua phiếu cơ hội",
    "refund": "Hoàn điểm",
    "adjust": "Điều chỉnh",
}
INVOICE_STATUSES = {"pending": "Chờ xuất", "issued": "Đã xuất"}
OPP_STATUSES = {"draft": "Nháp", "published": "Đang bán", "closed": "Đã đóng"}
OPP_SOURCES = [
    "App đăng mua",
    "Dự án & gói thầu",
    "Nhà máy / FDI mới",
    "Hội chợ & triển lãm",
    "Mạng xã hội & nhóm chat",
    "Website doanh nghiệp",
    "Nguồn chính thống",
    "Email hỏi hàng",
    "Kết nối giao thương",
]
ENRICH_STATUSES = {"open": "Đang xử lý", "done": "Đã xong", "rejected": "Từ chối"}
# Phiếu tìm cơ hội tìm kiếm liên tục: cơ hội mới mở bán khớp phiếu → tự thêm + báo khách. Quản trị có thể từ chối (dừng).
SEARCH_STATUSES = {"open": "Tìm kiếm liên tục", "rejected": "Từ chối"}


class MemberUser(Base):
    __tablename__ = "member_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    company: Mapped[Company] = relationship(lazy="joined")


class MemberSession(Base):
    __tablename__ = "member_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("member_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")

    user: Mapped[MemberUser] = relationship(lazy="joined")


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("member_users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


class WalletTransaction(Base):
    """Sổ cái điểm: chỉ thêm, không sửa/xoá. amount dương = cộng, âm = trừ."""

    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(String(300), default="")
    order_id: Mapped[int | None] = mapped_column(ForeignKey("payment_orders.id", ondelete="SET NULL"))
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.id", ondelete="SET NULL"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    actor: Mapped[AdminUser | None] = relationship(lazy="joined")


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # cũng là nội dung chuyển khoản, vd LSP7K2QX9MA
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(BigInteger)  # số tiền VND phải trả
    points: Mapped[int] = mapped_column(BigInteger)  # số điểm được cộng
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(20), default="infocms")
    provider_txn_id: Mapped[str | None] = mapped_column(String(100), unique=True)  # chống cộng điểm 2 lần
    paid_amount: Mapped[int | None] = mapped_column(BigInteger)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    note: Mapped[str] = mapped_column(String(300), default="")
    raw_callback: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    company: Mapped[Company] = relationship(lazy="joined")
    invoice: Mapped["InvoiceRequest | None"] = relationship(back_populates="order", uselist=False, lazy="joined")
    confirmed_by: Mapped[AdminUser | None] = relationship(lazy="joined")


MCV_STATUSES = {
    "pending": "Đang chờ chuyển khoản",
    "paid": "Đã thanh toán",
    "expired": "Mã QR hết hạn",
    "needs_attention": "Đã nhận tiền nhưng chưa khớp",
    "failed": "Lỗi — thử lại sau",
}


class McvPayment(Base):
    """1 lần thanh toán do cổng MCV cấp (payment_code). Đơn LeadScan gửi sang MCV với order_id = PaymentOrder.code.

    processed_at khác NULL = đã xử lý tín hiệu "paid" (webhook hoặc API tra trạng thái) đúng 1 lần —
    payment_code unique + khoá dòng khi xử lý đảm bảo mỗi payment_code chỉ mở dịch vụ 1 lần.
    """

    __tablename__ = "mcv_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_code: Mapped[str] = mapped_column(String(100), unique=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("payment_orders.id", ondelete="SET NULL"), index=True)
    mcv_order_id: Mapped[str] = mapped_column(String(100), index=True)  # order_id gửi MCV (= PaymentOrder.code)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    paid_amount: Mapped[int | None] = mapped_column(BigInteger)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    test_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    checkout_url: Mapped[str] = mapped_column(String(500), default="")
    qr_data: Mapped[str | None] = mapped_column(Text)
    bank: Mapped[dict | None] = mapped_column(JSON)  # {bank_name, account_no, account_name, transfer_content}
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)  # đã mở dịch vụ / đã xử lý tín hiệu paid
    result: Mapped[str] = mapped_column(String(300), default="")  # kết quả xử lý: credited / lý do bỏ qua
    last_event_id: Mapped[str] = mapped_column(String(100), default="")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime)  # lần gần nhất tra trạng thái với MCV
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    order: Mapped[PaymentOrder | None] = relationship(lazy="joined")


class InvoiceRequest(Base):
    """Thông tin xuất hoá đơn khách nhập sau khi thanh toán; kế toán xuất thủ công."""

    __tablename__ = "invoice_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("payment_orders.id", ondelete="CASCADE"), unique=True)
    company_name: Mapped[str] = mapped_column(String(200))
    tax_code: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(300))
    buyer_name: Mapped[str] = mapped_column(String(100), default="")
    receive_email: Mapped[str] = mapped_column(String(150))
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), default="")
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # "member" = khách gửi form · "auto" = hệ thống tự lấy thông tin doanh nghiệp khi thanh toán
    source: Mapped[str] = mapped_column(String(16), default="member")
    # Hoá đơn điện tử IAM (mã tra cứu bên IAM = mã đơn PaymentOrder.code)
    einvoice_id: Mapped[str] = mapped_column(String(50), default="")
    einvoice_serial: Mapped[str] = mapped_column(String(20), default="")  # mẫu số + ký hiệu, vd 1C26TYY
    einvoice_status: Mapped[str] = mapped_column(String(40), default="")  # issueStatusId của IAM
    einvoice_error: Mapped[str] = mapped_column(String(500), default="")
    einvoice_at: Mapped[datetime | None] = mapped_column(DateTime)  # lần gọi IAM gần nhất

    order: Mapped[PaymentOrder] = relationship(back_populates="invoice")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # CH-000123
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)

    # Phần xem trước (thành viên nào cũng thấy)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(100), default="", index=True)
    province: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(20), default="")
    source_type: Mapped[str] = mapped_column(String(60), default="")
    scale: Mapped[str] = mapped_column(String(150), default="")  # quy mô / số lượng
    estimated_value: Mapped[str] = mapped_column(String(100), default="")
    deadline: Mapped[date | None] = mapped_column(Date)
    # Điểm cũ (chấm tay) — không còn dùng; điểm do hệ thống tính riêng cho từng doanh nghiệp (UserOpportunity)
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_fit: Mapped[int] = mapped_column(Integer, default=0)
    score_urgency: Mapped[int] = mapped_column(Integer, default=0)
    score_trust: Mapped[int] = mapped_column(Integer, default=0)
    enrich_round: Mapped[int] = mapped_column(Integer, default=0)
    # Giá cơ bản của phiếu; giá thành viên phải trả = giá cơ bản × hệ số theo điểm của chính họ (xem services/matching.py)
    price: Mapped[int] = mapped_column(BigInteger, default=29000)
    max_buyers: Mapped[int] = mapped_column(Integer, default=3)  # 1 = độc quyền
    sold_count: Mapped[int] = mapped_column(Integer, default=0)

    # Phần chỉ mở khi đã mua phiếu
    buyer_name: Mapped[str] = mapped_column(String(200), default="")  # bên có nhu cầu
    detail: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(500), default="")

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    # Vector ngữ nghĩa (pgvector) của tiêu đề + mô tả — xem services/embedding.py. deferred: không tải khi liệt kê.
    embedding: Mapped[list | None] = mapped_column(EmbeddingVector(1024), deferred=True)
    embedding_model: Mapped[str] = mapped_column(String(80), default="")  # nhãn không gian vector
    embedding_sha: Mapped[str] = mapped_column(String(40), default="")  # sha1 văn bản đã nhúng → không gọi lại API khi chỉ sửa giá
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    contacts: Mapped[list["OpportunityContact"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan", order_by="OpportunityContact.position_order"
    )


class OpportunityContact(Base):
    __tablename__ = "opportunity_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    position_order: Mapped[int] = mapped_column(Integer, default=0)
    full_name: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(100), default="")  # chức vụ
    phone: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(150), default="")
    note: Mapped[str] = mapped_column(String(300), default="")

    opportunity: Mapped[Opportunity] = relationship(back_populates="contacts")


class OpportunityAttachment(Base):
    """Ảnh / tài liệu admin gắn vào phiếu cơ hội — nằm ở "Phần mở khoá sau khi mua" (chỉ người đã mua thấy).

    Tệp lưu trên Cloudflare R2 (bucket riêng tư). Admin upload khi đang soạn phiếu nên opportunity_id còn trống
    cho tới khi bấm lưu; tệp không được gắn sau 24 giờ thì việc dọn dẹp xoá.
    status: pending (đã cấp link upload) → ready (đã kiểm tra tệp trên R2).
    """

    __tablename__ = "opportunity_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    key: Mapped[str] = mapped_column(String(400), unique=True)
    thumb_key: Mapped[str] = mapped_column(String(400), default="")
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    kind: Mapped[str] = mapped_column(String(10), default="file")  # image | file
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    caption: Mapped[str] = mapped_column(String(300), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    member_user_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    price: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    company: Mapped[Company] = relationship(lazy="joined")
    opportunity: Mapped[Opportunity] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("company_id", "opportunity_id", name="uq_purchase_once"),)


class SearchRequest(Base):
    """Yêu cầu "Enrich tìm kiếm cơ hội": thành viên gửi tiêu chí + mô tả, hệ thống so khớp ngay và trả kết quả.

    status: open = tìm kiếm liên tục (mỗi cơ hội mới mở bán đều được so với phiếu, khớp thì báo khách);
    rejected = quản trị từ chối, phiếu dừng tìm. Quản trị nhận email để nắm tình hình, có thể trả lời khách.
    """

    __tablename__ = "search_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    member_user_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    # {"industries": [...], "regions": [...], "sizes": [...], "sources": [...], "min_score": 70}
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")  # mô tả yêu cầu khách tự viết
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    reply: Mapped[str] = mapped_column(Text, default="")  # phản hồi của LeadScan, khách thấy trong cổng
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # đã gửi email báo admin
    embedding: Mapped[list | None] = mapped_column(EmbeddingVector(1024), deferred=True)  # vector của mô tả + tiêu chí
    embedding_model: Mapped[str] = mapped_column(String(80), default="")
    embedding_sha: Mapped[str] = mapped_column(String(40), default="")
    # So khớp chạy nền (Celery): pending → running → done | error
    match_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    match_error: Mapped[str] = mapped_column(String(300), default="")
    matched_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    company: Mapped[Company] = relationship(lazy="joined")
    member_user: Mapped["MemberUser | None"] = relationship(lazy="joined")


class UserOpportunity(Base):
    """Cơ hội nằm trong "Tất cả cơ hội" của một doanh nghiệp, kèm điểm RIÊNG của doanh nghiệp đó.

    Mỗi (doanh nghiệp, cơ hội) đúng 1 dòng dù cơ hội khớp nhiều phiếu tìm — điểm là điểm cao nhất trong các phiếu.
    """

    __tablename__ = "user_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)  # điểm tổng 0–100
    score_fit: Mapped[int] = mapped_column(Integer, default=0)  # khớp yêu cầu (tiêu chí + ngữ nghĩa + từ khoá)
    score_urgency: Mapped[int] = mapped_column(Integer, default=0)
    score_trust: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)  # vì sao phù hợp (hiển thị cho khách)
    best_request_id: Mapped[int | None] = mapped_column(ForeignKey("search_requests.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    opportunity: Mapped[Opportunity] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("company_id", "opportunity_id", name="uq_user_opp_once"),)


class SearchRequestMatch(Base):
    """Cơ hội phù hợp với một phiếu tìm cơ hội (xem khi bấm vào phiếu)."""

    __tablename__ = "search_request_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("search_requests.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_fit: Mapped[int] = mapped_column(Integer, default=0)
    score_urgency: Mapped[int] = mapped_column(Integer, default=0)
    score_trust: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    opportunity: Mapped[Opportunity] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("request_id", "opportunity_id", name="uq_request_opp_once"),)


class MemberNotification(Base):
    """Thông báo trong cổng thành viên: cơ hội mới mở bán phù hợp với phiếu tìm cơ hội (tìm kiếm liên tục).

    Mỗi (phiếu tìm, cơ hội) báo đúng 1 lần — cơ hội sửa đi sửa lại không báo lặp. Email gộp nhiều thông báo/lần gửi.
    """

    __tablename__ = "member_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("search_requests.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="match")
    score: Mapped[int] = mapped_column(Integer, default=0)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    opportunity: Mapped[Opportunity] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("request_id", "opportunity_id", name="uq_notify_request_opp_once"),)


class SavedOpportunity(Base):
    """Cơ hội thành viên "thêm vào kho" để xem/mua sau."""

    __tablename__ = "saved_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    member_user_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    opportunity: Mapped[Opportunity] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("company_id", "opportunity_id", name="uq_saved_once"),)


class EnrichRequest(Base):
    __tablename__ = "enrich_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    reply: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    purchase: Mapped[Purchase] = relationship(lazy="joined")


# Kho doanh nghiệp để AI quét
KNOWLEDGE_AI_STATUSES = {
    "pending": "Chờ quét",
    "done": "Đã quét",
    "error": "Lỗi",
    "skip": "Bỏ qua",
}
KNOWLEDGE_SOURCES = {"manual": "Nhập tay", "profit500": "PROFIT500"}


class KnowledgeCompany(Base):
    """Doanh nghiệp trong kho tri thức — danh sách đầu vào để AI quét tìm cơ hội.

    Thông tin lấy từ phần "Giới thiệu chung" của trang nguồn (vd profit500.vn) hoặc admin nhập tay.
    Chống trùng: (source, source_id) với dữ liệu crawl; tax_code (nếu có) là duy nhất trên toàn bảng.
    """

    __tablename__ = "knowledge_companies"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_knowledge_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # Định danh
    name: Mapped[str] = mapped_column(String(300), index=True)
    name_en: Mapped[str] = mapped_column(String(300), default="")
    tax_code: Mapped[str | None] = mapped_column(String(20), unique=True)  # None = chưa có MST
    stock_code: Mapped[str] = mapped_column(String(20), default="")  # rỗng = chưa niêm yết

    # Giới thiệu chung
    industry: Mapped[str] = mapped_column(String(200), default="", index=True)
    address: Mapped[str] = mapped_column(String(500), default="")  # trụ sở chính
    province: Mapped[str] = mapped_column(String(80), default="", index=True)  # tách từ địa chỉ để lọc
    phone: Mapped[str] = mapped_column(String(100), default="")
    fax: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    website: Mapped[str] = mapped_column(String(300), default="")
    founded_year: Mapped[int | None] = mapped_column(Integer)
    ceo_name: Mapped[str] = mapped_column(String(150), default="")
    description: Mapped[str] = mapped_column(Text, default="")  # đoạn "Giới thiệu", dạng chữ thuần
    logo_url: Mapped[str] = mapped_column(String(500), default="")

    # Xếp hạng tại nguồn
    rank: Mapped[int | None] = mapped_column(Integer)
    rank_label: Mapped[str] = mapped_column(String(100), default="")  # nguyên văn, vd "52(B1/2026)"
    rank_list: Mapped[str] = mapped_column(String(200), default="")  # tên bảng xếp hạng
    rank_year: Mapped[int | None] = mapped_column(Integer)

    # Nguồn dữ liệu
    source: Mapped[str] = mapped_column(String(30), default="manual", index=True)
    source_id: Mapped[str | None] = mapped_column(String(50))  # mã doanh nghiệp tại nguồn
    source_url: Mapped[str] = mapped_column(String(500), default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # các dòng thông tin khác chưa có cột riêng
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Trạng thái AI quét
    ai_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    ai_scanned_at: Mapped[datetime | None] = mapped_column(DateTime)
    ai_note: Mapped[str] = mapped_column(Text, default="")  # kết quả / lỗi lần quét gần nhất

    note: Mapped[str] = mapped_column(Text, default="")  # ghi chú nội bộ
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ------------------------------------------------------------------ tuyển dụng

JOB_STATUSES = {"draft": "Bản nháp", "published": "Đang tuyển", "closed": "Đã đóng"}
JOB_TYPES = {
    "full_time": "Toàn thời gian",
    "part_time": "Bán thời gian",
    "intern": "Thực tập",
    "contract": "Hợp đồng / Freelance",
    "remote": "Làm việc từ xa",
}
APPLICATION_STATUSES = {
    "new": "Mới nhận",
    "reviewing": "Đang xem xét",
    "interview": "Hẹn phỏng vấn",
    "hired": "Đã tuyển",
    "rejected": "Chưa phù hợp",
}


class JobPost(Base):
    """Bài tuyển dụng. Chỉ bài "published" (và chưa quá hạn nộp) hiện trên /tuyen-dung.

    Các mục nội dung (mục tiêu, mô tả, yêu cầu, quyền lợi, cách ứng tuyển) là văn bản thuần với định dạng nhẹ:
    dòng "## " = tiêu đề nhỏ, dòng "- " = gạch đầu dòng, **chữ đậm**, dòng trống = đoạn mới.
    """

    __tablename__ = "job_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True)  # đường dẫn /tuyen-dung/<slug>
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)

    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str] = mapped_column(String(300), default="")
    department: Mapped[str] = mapped_column(String(100), default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    employment_type: Mapped[str] = mapped_column(String(20), default="full_time")
    salary: Mapped[str] = mapped_column(String(150), default="")  # vd "10 – 14 triệu/tháng", "Thoả thuận"
    work_time: Mapped[str] = mapped_column(String(200), default="")
    reports_to: Mapped[str] = mapped_column(String(150), default="")
    quantity: Mapped[int | None] = mapped_column(Integer)
    deadline: Mapped[date | None] = mapped_column(Date)  # hạn nộp hồ sơ (hết ngày này thì tự ẩn)
    # Ảnh bìa (banner): đường dẫn trên website ("/careers/x.webp", file trong web/public) hoặc URL https
    cover_image: Mapped[str] = mapped_column(String(500), default="")

    summary: Mapped[str] = mapped_column(Text, default="")  # 1–2 câu trên thẻ danh sách
    objective: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    benefits: Mapped[str] = mapped_column(Text, default="")
    how_to_apply: Mapped[str] = mapped_column(Text, default="")

    apply_email: Mapped[str] = mapped_column(String(200), default="")  # trống = LEADSCAN_RECRUIT_EMAIL

    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class JobApplication(Base):
    """Hồ sơ ứng tuyển. Email gửi về hộp thư tuyển dụng (kèm file CV lấy từ R2); DB giữ thông tin để tra cứu / gửi lại."""

    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("job_posts.id", ondelete="SET NULL"), index=True)
    job_title: Mapped[str] = mapped_column(String(200))  # giữ lại tên vị trí kể cả khi bài bị xoá
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)

    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(150))
    cv_url: Mapped[str] = mapped_column(String(500), default="")
    portfolio_url: Mapped[str] = mapped_column(String(500), default="")
    intro: Mapped[str] = mapped_column(Text, default="")

    # File CV tải lên (PDF/DOC/DOCX ≤ 5 MB) lưu trên Cloudflare R2, thư mục CV/ (bucket riêng tư)
    cv_key: Mapped[str] = mapped_column(String(400), default="")  # vd CV/2026-11/<uuid>/CV Nguyen Van A.pdf
    cv_filename: Mapped[str] = mapped_column(String(200), default="")
    cv_mime: Mapped[str] = mapped_column(String(100), default="")
    cv_size: Mapped[int] = mapped_column(Integer, default=0)

    note: Mapped[str] = mapped_column(Text, default="")  # ghi chú nội bộ của người tuyển dụng
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # đã gửi về hộp thư tuyển dụng
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    job: Mapped[JobPost | None] = relationship(lazy="joined")
