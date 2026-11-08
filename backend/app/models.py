"""Dữ liệu riêng của LeadScan (không phụ thuộc hệ thống ngoài).

Company            doanh nghiệp đăng ký / thành viên
  ├─ Contact        người liên hệ (1 người chính + người khác)
  ├─ Profile        tiêu chí tìm cơ hội phù hợp (thành viên chọn trong cổng)
  └─ Activity       lịch sử: tạo hồ sơ, đổi trạng thái, ghi chú chăm sóc
  ├─ MemberUser     tài khoản đăng nhập cổng thành viên
  ├─ WalletTransaction   sổ cái điểm (mỗi lần cộng/trừ 1 dòng, không sửa/xoá)
  ├─ PaymentOrder   đơn nạp tiền / phí thành viên (thanh toán qua InfoCMS)
  │    └─ InvoiceRequest  thông tin xuất hoá đơn (xuất thủ công)
  ├─ SavedOpportunity   cơ hội thành viên thêm vào kho (xem/mua sau)
  └─ Purchase       phiếu cơ hội đã mua
       └─ EnrichRequest   yêu cầu tìm thêm đầu mối
Opportunity        cơ hội kinh doanh (nhập tay; sau này do crawl + AI tạo)
  └─ OpportunityContact   đầu mối liên hệ — chỉ hiện sau khi mua phiếu
AdminUser / AdminSession   nhân viên quản trị và phiên đăng nhập
MemberSession / PasswordReset   phiên đăng nhập & đặt lại mật khẩu của thành viên
RateHit                    đếm lượt để giới hạn tần suất (đăng ký, đăng nhập)
KnowledgeCompany           kho doanh nghiệp để AI quét (crawl từ bảng xếp hạng như PROFIT500 hoặc nhập tay)

Điểm: 1 điểm = 1đ. Số dư lưu ở Company.points_balance và luôn bằng tổng WalletTransaction.amount.
"""

from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

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
]
ENRICH_STATUSES = {"open": "Đang xử lý", "done": "Đã xong", "rejected": "Từ chối"}


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
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_fit: Mapped[int] = mapped_column(Integer, default=0)
    score_urgency: Mapped[int] = mapped_column(Integer, default=0)
    score_trust: Mapped[int] = mapped_column(Integer, default=0)
    enrich_round: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[int] = mapped_column(BigInteger, default=29000)
    max_buyers: Mapped[int] = mapped_column(Integer, default=3)  # 1 = độc quyền
    sold_count: Mapped[int] = mapped_column(Integer, default=0)

    # Phần chỉ mở khi đã mua phiếu
    buyer_name: Mapped[str] = mapped_column(String(200), default="")  # bên có nhu cầu
    detail: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(500), default="")

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
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
