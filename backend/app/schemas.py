"""Dữ liệu vào/ra của API quản trị."""

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from app.models import COMPANY_STATUSES, ROLES
from app.registration_form import OPP_TYPES, REGIONS, SIZES, TICKETS

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Thời gian lưu dạng UTC naive → trả ra ISO có "Z" để trình duyệt tự đổi giờ địa phương
UtcDatetime = Annotated[
    datetime, PlainSerializer(lambda d: d.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"), return_type=str)
]


def _strip(v: str) -> str:
    return re.sub(r"\s+", " ", v).strip()


Line = Annotated[str, AfterValidator(_strip)]


def _email(v: str) -> str:
    v = v.strip().lower()
    if v and not EMAIL_RE.match(v):
        raise ValueError("Email chưa đúng định dạng.")
    return v


def _phone(v: str) -> str:
    v = re.sub(r"[\s.\-()]", "", v)
    if v and not re.fullmatch(r"(0|\+84)\d{9,10}", v):
        raise ValueError("Số điện thoại chưa đúng định dạng.")
    return v


def _tax(v: str) -> str:
    v = re.sub(r"[^0-9\-]", "", v)
    if not re.fullmatch(r"\d{10}(-?\d{3})?", v):
        raise ValueError("Mã số thuế gồm 10 hoặc 13 chữ số.")
    return v


Email = Annotated[str, AfterValidator(_email)]
Phone = Annotated[str, AfterValidator(_phone)]
TaxCode = Annotated[str, AfterValidator(_tax)]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ nhân viên


class UserOut(Out):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: UtcDatetime
    last_login_at: UtcDatetime | None


class UserRef(Out):
    id: int
    full_name: str


class LoginIn(BaseModel):
    email: str = Field(max_length=150)
    password: str = Field(max_length=200)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class UserCreateIn(BaseModel):
    email: Email = Field(max_length=150)
    full_name: Line = Field(min_length=1, max_length=100)
    role: str = "staff"
    password: str = Field(min_length=10, max_length=200)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("Vai trò không hợp lệ.")
        return v


class UserUpdateIn(BaseModel):
    full_name: Line | None = Field(None, min_length=1, max_length=100)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=10, max_length=200)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str | None) -> str | None:
        if v is not None and v not in ROLES:
            raise ValueError("Vai trò không hợp lệ.")
        return v


# ------------------------------------------------------------------ khách hàng


class ContactOut(Out):
    id: int
    full_name: str
    position: str
    email: str
    phone: str
    is_primary: bool


class ContactIn(BaseModel):
    full_name: Line = Field(min_length=1, max_length=100)
    position: Line = Field("", max_length=100)
    email: Email = Field("", max_length=150)
    phone: Phone = Field("", max_length=20)
    is_primary: bool = False


class ProfileOut(Out):
    offering: str
    target_customers: str
    target_regions: list[str]
    opp_types: list[str]
    expected_tickets: str
    notes: str
    updated_at: UtcDatetime


class ProfileIn(BaseModel):
    offering: str = Field("", max_length=2000)
    target_customers: str = Field("", max_length=2000)
    target_regions: list[str] = []
    opp_types: list[str] = []
    expected_tickets: str = ""
    notes: str = Field("", max_length=2000)

    @field_validator("target_regions")
    @classmethod
    def _regions(cls, v: list[str]) -> list[str]:
        return [x for x in REGIONS if x in v]

    @field_validator("opp_types")
    @classmethod
    def _opps(cls, v: list[str]) -> list[str]:
        return [x for x in OPP_TYPES if x in v]

    @field_validator("expected_tickets")
    @classmethod
    def _tickets(cls, v: str) -> str:
        return v if v in TICKETS else ""


class ActivityOut(Out):
    id: int
    kind: str
    content: str
    created_at: UtcDatetime
    actor: UserRef | None


class CompanyListItem(Out):
    id: int
    code: str
    status: str
    name: str
    tax_code: str
    industry: str
    province: str
    created_at: UtcDatetime
    assigned_to: UserRef | None
    primary_contact: ContactOut | None = None


class CompanyOut(Out):
    id: int
    code: str
    status: str
    name: str
    tax_code: str
    industry: str
    company_size: str
    province: str
    address: str
    website: str
    source: str
    ip: str
    created_at: UtcDatetime
    updated_at: UtcDatetime
    assigned_to: UserRef | None
    contacts: list[ContactOut]
    profile: ProfileOut | None
    activities: list[ActivityOut]


class CompanyUpdateIn(BaseModel):
    name: Line | None = Field(None, min_length=1, max_length=150)
    tax_code: TaxCode | None = None
    industry: Line | None = Field(None, min_length=1, max_length=100)
    company_size: str | None = None
    province: Line | None = Field(None, min_length=1, max_length=80)
    address: Line | None = Field(None, max_length=200)
    website: Line | None = Field(None, max_length=200)
    status: str | None = None
    assigned_to_id: int | None = None
    unassign: bool = False  # true = bỏ người phụ trách

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in COMPANY_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v

    @field_validator("company_size")
    @classmethod
    def _size(cls, v: str | None) -> str | None:
        if v is not None and v not in SIZES:
            raise ValueError("Quy mô không hợp lệ.")
        return v


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
