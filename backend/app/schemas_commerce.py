"""Dữ liệu vào/ra cho ví, thanh toán, hoá đơn, cơ hội, phiếu."""

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models import ENRICH_STATUSES, INVOICE_STATUSES, OPP_SOURCES, OPP_STATUSES
from app.registration_form import REGIONS
from app.schemas import Email, Line, Out, TaxCode, UserRef, UtcDatetime


# ------------------------------------------------------------------ ví & đơn


class TxOut(Out):
    id: int
    kind: str
    amount: int
    balance_after: int
    note: str
    created_at: UtcDatetime
    actor: UserRef | None = None


class InvoiceOut(Out):
    id: int
    company_name: str
    tax_code: str
    address: str
    buyer_name: str
    receive_email: str
    note: str
    status: str
    invoice_number: str
    email_sent_at: UtcDatetime | None
    issued_at: UtcDatetime | None
    created_at: UtcDatetime
    source: str = "member"
    einvoice_serial: str = ""
    einvoice_status: str = ""
    einvoice_error: str = ""
    einvoice_at: UtcDatetime | None = None


class OrderOut(Out):
    id: int
    code: str
    kind: str
    amount: int
    points: int
    status: str
    provider: str
    paid_amount: int | None
    paid_at: UtcDatetime | None
    expires_at: UtcDatetime
    created_at: UtcDatetime
    note: str
    invoice: InvoiceOut | None


class OrderCreateIn(BaseModel):
    kind: str
    amount: int | None = None  # chỉ dùng cho topup

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in ("membership", "topup"):
            raise ValueError("Loại đơn không hợp lệ.")
        return v


class InvoiceIn(BaseModel):
    company_name: Line = Field(min_length=1, max_length=200)
    tax_code: TaxCode
    address: Line = Field(min_length=1, max_length=300)
    buyer_name: Line = Field("", max_length=100)
    receive_email: Email = Field(min_length=3, max_length=150)
    note: str = Field("", max_length=1000)


class InvoiceAdminIn(BaseModel):
    status: str | None = None
    invoice_number: Line | None = Field(None, max_length=50)

    @field_validator("status")
    @classmethod
    def _st(cls, v: str | None) -> str | None:
        if v is not None and v not in INVOICE_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v


class ConfirmOrderIn(BaseModel):
    paid_amount: int | None = Field(None, ge=0)
    note: str = Field(min_length=3, max_length=300)  # vd "Đã đối soát sao kê VCB ngày 07/11"


class AdjustIn(BaseModel):
    amount: int  # dương = cộng, âm = trừ
    note: str = Field(min_length=3, max_length=300)

    @field_validator("amount")
    @classmethod
    def _nz(cls, v: int) -> int:
        if v == 0 or abs(v) > 1_000_000_000:
            raise ValueError("Số điểm điều chỉnh không hợp lệ.")
        return v


# ------------------------------------------------------------------ cơ hội


class OppContactOut(Out):
    id: int
    full_name: str
    title: str
    phone: str
    email: str
    note: str


class OppContactIn(BaseModel):
    full_name: Line = Field("", max_length=100)
    title: Line = Field("", max_length=100)
    phone: Line = Field("", max_length=30)
    email: Line = Field("", max_length=150)
    note: Line = Field("", max_length=300)


class OppPreview(Out):
    """Phần ai cũng thấy (không có tên bên mua, chi tiết, đầu mối)."""

    id: int
    code: str
    title: str
    summary: str
    industry: str
    province: str
    region: str
    source_type: str
    scale: str
    estimated_value: str
    deadline: date | None
    score: int
    score_fit: int
    score_urgency: int
    score_trust: int
    enrich_round: int
    price: int
    max_buyers: int
    sold_count: int
    published_at: UtcDatetime | None
    contact_count: int = 0
    purchased: bool = False
    saved: bool = False  # đã thêm vào kho của thành viên
    sold_out: bool = False
    reasons: list[str] = Field(default_factory=list)  # vì sao phù hợp với doanh nghiệp này


class OppFull(OppPreview):
    buyer_name: str
    detail: str
    source_url: str
    contacts: list[OppContactOut]


class OppAdminOut(OppFull):
    status: str
    match_count: int = 0  # số doanh nghiệp được cơ hội này khớp
    created_at: UtcDatetime
    updated_at: UtcDatetime


class OppIn(BaseModel):
    title: Line = Field(min_length=3, max_length=200)
    summary: str = Field("", max_length=3000)
    industry: Line = Field("", max_length=100)
    province: Line = Field("", max_length=80)
    region: str = ""
    source_type: str = ""
    scale: Line = Field("", max_length=150)
    estimated_value: Line = Field("", max_length=100)
    deadline: date | None = None
    enrich_round: int = Field(0, ge=0, le=10)
    price: int = Field(29000, ge=0, le=1_000_000_000)  # giá cơ bản; giá theo từng thành viên tính theo điểm của họ
    max_buyers: int = Field(3, ge=1, le=1000)
    buyer_name: Line = Field("", max_length=200)
    detail: str = Field("", max_length=10000)
    source_url: Line = Field("", max_length=500)
    status: str = "draft"
    contacts: list[OppContactIn] = Field(default_factory=list, max_length=20)
    # Ảnh & tài liệu (phần mở khoá sau khi mua), đúng thứ tự hiển thị. None = giữ nguyên tệp đang có.
    attachment_ids: list[int] | None = Field(None, max_length=50)
    attachment_captions: dict[int, str] | None = None  # {id tệp: chú thích} — lưu cùng lúc với phiếu

    @field_validator("status")
    @classmethod
    def _st(cls, v: str) -> str:
        if v not in OPP_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v

    @field_validator("region")
    @classmethod
    def _rg(cls, v: str) -> str:
        if v and v not in REGIONS:
            raise ValueError("Khu vực không hợp lệ.")
        return v

    @field_validator("source_type")
    @classmethod
    def _src(cls, v: str) -> str:
        if v and v not in OPP_SOURCES:
            raise ValueError("Nguồn không hợp lệ.")
        return v


# ------------------------------------------------------------------ phiếu & enrich


class EnrichOut(Out):
    id: int
    note: str
    status: str
    reply: str
    created_at: UtcDatetime
    resolved_at: UtcDatetime | None


class EnrichIn(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


class EnrichAdminIn(BaseModel):
    status: str
    reply: str = Field("", max_length=4000)

    @field_validator("status")
    @classmethod
    def _st(cls, v: str) -> str:
        if v not in ENRICH_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v


class MemberCreateIn(BaseModel):
    email: Email = Field(min_length=3, max_length=150)
    full_name: Line = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class MemberUpdateIn(BaseModel):
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=200)
