"""LeadScan CRM Lite — sổ theo dõi cơ hội đã mua cho thành viên hạng Vàng (/thanh-vien/crm).

CrmLead     1 phiếu đã mua = 1 lead (khoá purchase_id, tự sinh khi mở CRM — app/services/crm.py sync_leads)
  ├─ CrmNote    ghi chú của sale (SĐT / email lạ bị che trước khi lưu)
  ├─ CrmTask    việc cần làm (hạn, người làm, đã xong)
  ├─ CrmEvent   lịch sử: tạo lead, đổi giai đoạn, giao người phụ trách, ghi chú, việc
  └─ CrmAiRun   mỗi lần dùng nút AI (kết quả nháp, token, chi phí — trần ngân sách tháng)

Nguyên tắc: CRM không thu thập thêm dữ liệu cá nhân — thông tin đầu mối chỉ đọc từ bản phiếu đã mua (Purchase.snapshot).
Mọi bảng có company_id; mọi truy vấn lọc theo company_id của thành viên đang đăng nhập.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

CRM_STAGES = {
    "new": "Mới",
    "contacting": "Đang liên hệ",
    "interested": "Có nhu cầu",
    "quoted": "Báo giá",
    "won": "Thắng",
    "lost": "Thua",
}


class CrmLead(Base):
    __tablename__ = "crm_leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), unique=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(16), default="new", index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    purchase = relationship("Purchase", lazy="joined")
    owner = relationship("MemberUser", lazy="joined")


class CrmNote(Base):
    __tablename__ = "crm_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("crm_leads.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    author = relationship("MemberUser", lazy="joined")


class CrmTask(Base):
    __tablename__ = "crm_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("crm_leads.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    done_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    lead = relationship(CrmLead, lazy="joined")
    assignee = relationship("MemberUser", lazy="joined", foreign_keys=[assignee_id])


CRM_AI_KINDS = {"summary": "Tóm tắt công ty", "draft": "Soạn tin mời"}


class CrmAiRun(Base):
    """Mỗi lần bấm nút AI: kết quả (bản nháp — người dùng tự sửa / tự gửi), token và chi phí để giữ trần ngân sách tháng."""

    __tablename__ = "crm_ai_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("crm_leads.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))  # summary | draft
    model: Mapped[str] = mapped_column(String(60), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    result: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    member = relationship("MemberUser", lazy="joined")


class CrmEvent(Base):
    __tablename__ = "crm_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("crm_leads.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("member_users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))  # created | stage | assign | note | task | task_done
    content: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    actor = relationship("MemberUser", lazy="joined")
