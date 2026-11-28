"""Dữ liệu vào/ra của sự kiện: trang sự kiện (admin + công khai), đăng ký tham dự và ảnh chuyển khoản."""

import base64
import binascii
import re
import secrets
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models_events import ATTENDEE_TYPES, EVENT_REG_STATUSES, EVENT_STATUSES
from app.schemas import Email, Line, Out, Phone, UtcDatetime
from app.schemas_jobs import clean_cover, slugify

# Mã đăng ký: chữ HOA + số, bỏ ký tự dễ đọc nhầm (0/O, 1/I, 2/Z, 5/S, 8/B) vì khách gõ lại vào app ngân hàng
CODE_ALPHABET = "34679ACDEFGHJKLMNPQRTUVWXY"
CODE_PREFIX = "SK"


def new_code(length: int = 6) -> str:
    return CODE_PREFIX + "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


# ------------------------------------------------------------------ sự kiện (admin)


class EventIn(BaseModel):
    title: Line = Field(min_length=3, max_length=200)
    slug: str = Field("", max_length=160)  # trống = tự sinh từ tiêu đề
    status: str = "draft"
    subtitle: Line = Field("", max_length=300)
    summary: str = Field("", max_length=1000)
    host: Line = Field("", max_length=200)
    partner: Line = Field("", max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    venue: Line = Field("", max_length=200)
    address: Line = Field("", max_length=300)
    deadline: date | None = None
    capacity: int | None = Field(None, ge=1, le=100000)
    cover_image: str = Field("", max_length=500)
    banner_image: str = Field("", max_length=500)
    intro: str = Field("", max_length=20000)
    agenda: str = Field("", max_length=20000)
    content: str = Field("", max_length=20000)
    matching: str = Field("", max_length=20000)
    notes: str = Field("", max_length=20000)
    fee_member: int = Field(0, ge=0, le=1_000_000_000)
    fee_guest: int = Field(0, ge=0, le=1_000_000_000)
    fee_note: Line = Field("", max_length=300)
    bank_bin: str = Field("", max_length=10)
    bank_name: Line = Field("", max_length=100)
    account_no: str = Field("", max_length=40)
    account_name: Line = Field("", max_length=120)
    contact_name: Line = Field("", max_length=120)
    contact_phone: Phone = Field("", max_length=20)
    notify_email: Email = Field("", max_length=200)

    @field_validator("cover_image", "banner_image")
    @classmethod
    def _cover(cls, v: str) -> str:
        return clean_cover(v)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        return slugify(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in EVENT_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v

    @field_validator("bank_bin", "account_no")
    @classmethod
    def _digits(cls, v: str) -> str:
        v = re.sub(r"\s", "", v)
        if v and not v.isdigit():
            raise ValueError("Chỉ gồm chữ số.")
        return v

    @field_validator("summary", "intro", "agenda", "content", "matching", "notes")
    @classmethod
    def _text(cls, v: str) -> str:
        return v.replace("\r\n", "\n").strip()


class EventPublic(Out):
    """Thông tin công khai trên /su-kien (không có email báo, người tạo…)."""

    slug: str
    status: str
    title: str
    subtitle: str
    summary: str
    host: str
    partner: str
    starts_at: datetime | None
    ends_at: datetime | None
    venue: str
    address: str
    deadline: date | None
    capacity: int | None
    cover_image: str
    banner_image: str
    intro: str
    agenda: str
    content: str
    matching: str
    notes: str
    fee_member: int
    fee_guest: int
    fee_note: str
    contact_name: str
    contact_phone: str
    published_at: UtcDatetime | None
    updated_at: UtcDatetime


class EventCard(Out):
    slug: str
    title: str
    subtitle: str
    summary: str
    host: str
    partner: str
    starts_at: datetime | None
    venue: str
    address: str
    deadline: date | None
    cover_image: str
    fee_member: int
    fee_guest: int
    published_at: UtcDatetime | None


class EventOut(EventPublic):
    id: int
    bank_bin: str
    bank_name: str
    account_no: str
    account_name: str
    notify_email: str
    created_at: UtcDatetime


# ------------------------------------------------------------------ đăng ký tham dự

PROFILE_TYPES = {
    # đuôi file → (mime chuẩn, chữ ký đầu file)
    "pdf": ("application/pdf", (b"%PDF",)),
}
PROOF_TYPES = {
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "webp": ("image/webp", (b"RIFF",)),
}


class UploadFile(BaseModel):
    name: str = Field(max_length=200)
    data: str  # base64 (có thể kèm tiền tố data:...;base64,)


def _decode(f: UploadFile, types: dict, max_mb: int, label: str) -> tuple[str, str, bytes]:
    name = re.sub(r"[\\/\x00-\x1f\"<>:|?*]+", "_", f.name).strip(" .") or label
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    kinds = ", ".join(sorted({k.upper() for k in types}))
    if ext not in types:
        raise ValueError(f"Chỉ nhận tệp {kinds}.")
    raw = f.data.split(",", 1)[1] if f.data.startswith("data:") else f.data
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Tệp bị lỗi, vui lòng chọn lại.") from None
    if not data:
        raise ValueError("Tệp trống.")
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError(f"Tệp tối đa {max_mb} MB.")
    mime, magics = types[ext]
    if not data.startswith(magics):
        raise ValueError(f"Tệp không đúng định dạng {ext.upper()}.")
    return name[-200:], mime, data


def decode_profile(f: UploadFile, max_mb: int) -> tuple[str, str, bytes]:
    """Profile doanh nghiệp: chỉ nhận PDF."""
    return _decode(f, PROFILE_TYPES, max_mb, "profile.pdf")


def decode_proof(f: UploadFile, max_mb: int) -> tuple[str, str, bytes]:
    """Ảnh chuyển khoản: JPG / PNG / WEBP."""
    return _decode(f, PROOF_TYPES, max_mb, "bien-lai.jpg")


class RegisterIn(BaseModel):
    full_name: Line = Field(min_length=2, max_length=100)
    phone: Phone
    email: Email
    company: Line = Field("", max_length=200)
    position: Line = Field("", max_length=120)
    attendee_type: str = "member"
    needs: str = Field("", max_length=5000)
    profile_file: UploadFile | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def _name_required(cls, v):
        if not str(v or "").strip():
            raise ValueError("Vui lòng nhập họ và tên.")
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def _phone_required(cls, v):
        if not str(v or "").strip():
            raise ValueError("Vui lòng nhập số điện thoại.")
        return v

    @field_validator("email", mode="before")
    @classmethod
    def _email_required(cls, v):
        if not str(v or "").strip():
            raise ValueError("Vui lòng nhập email.")
        return v

    @field_validator("attendee_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in ATTENDEE_TYPES:
            raise ValueError("Vui lòng chọn hình thức tham dự.")
        return v

    @field_validator("needs")
    @classmethod
    def _needs(cls, v: str) -> str:
        v = v.replace("\r\n", "\n").strip()
        if len(v) < 10:
            raise ValueError("Vui lòng mô tả nhu cầu xúc tiến hợp tác (ít nhất 10 ký tự).")
        return v


class ProofIn(BaseModel):
    image: UploadFile


class RegistrationAdminIn(BaseModel):
    status: str | None = None
    note: str | None = Field(None, max_length=5000)
    checked_in: bool | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in EVENT_REG_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v


class RegistrationOut(Out):
    id: int
    event_id: int | None
    event_title: str
    code: str
    status: str
    full_name: str
    phone: str
    email: str
    company: str
    position: str
    attendee_type: str
    needs: str
    amount: int
    profile_filename: str
    profile_size: int
    proof_filename: str
    proof_size: int
    proof_at: UtcDatetime | None
    ocr_status: str
    ocr_text: str
    ocr_amount: int | None
    ocr_checks: dict | None
    ocr_message: str
    ocr_at: UtcDatetime | None
    paid_at: UtcDatetime | None
    checked_in: bool
    checked_in_at: UtcDatetime | None = None
    note: str
    email_sent_at: UtcDatetime | None
    receipt_sent_at: UtcDatetime | None = None
    confirm_sent_at: UtcDatetime | None = None
    created_at: UtcDatetime
