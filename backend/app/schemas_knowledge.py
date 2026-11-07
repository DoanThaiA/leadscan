"""Dữ liệu vào/ra của kho doanh nghiệp (knowledge_companies)."""

import re
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models import KNOWLEDGE_AI_STATUSES, KNOWLEDGE_SOURCES
from app.schemas import Line, Out, UtcDatetime


def normalize_tax_code(v: str | None) -> str | None:
    """Chỉ giữ chữ số; MST 13 số (chi nhánh) viết dạng 0101234567-001. Rỗng → None (chưa có MST)."""
    d = re.sub(r"\D", "", v or "")
    if len(d) == 13:
        return f"{d[:10]}-{d[10:]}"
    return d or None


class KnowledgeIn(BaseModel):
    name: Line = Field(min_length=2, max_length=300)
    name_en: Line = Field("", max_length=300)
    tax_code: str | None = Field(None, max_length=20)
    stock_code: Line = Field("", max_length=20)
    industry: Line = Field("", max_length=200)
    address: Line = Field("", max_length=500)
    province: Line = Field("", max_length=80)
    phone: Line = Field("", max_length=100)
    fax: Line = Field("", max_length=100)
    email: Line = Field("", max_length=200)
    website: Line = Field("", max_length=300)
    founded_year: int | None = None
    ceo_name: Line = Field("", max_length=150)
    description: str = Field("", max_length=20000)
    logo_url: Line = Field("", max_length=500)
    rank: int | None = Field(None, ge=1, le=100000)
    rank_label: Line = Field("", max_length=100)
    rank_list: Line = Field("", max_length=200)
    rank_year: int | None = None
    source: str = "manual"
    source_url: Line = Field("", max_length=500)
    ai_status: str = "pending"
    ai_note: str = Field("", max_length=5000)
    note: str = Field("", max_length=5000)

    @field_validator("tax_code")
    @classmethod
    def _tax(cls, v: str | None) -> str | None:
        v = normalize_tax_code(v)
        if v and not re.fullmatch(r"\d{10}(-?\d{3})?", v):
            raise ValueError("Mã số thuế gồm 10 hoặc 13 chữ số.")
        return v

    @field_validator("founded_year", "rank_year")
    @classmethod
    def _year(cls, v: int | None) -> int | None:
        if v is not None and not (1800 <= v <= date.today().year + 1):
            raise ValueError("Năm không hợp lệ.")
        return v

    @field_validator("source")
    @classmethod
    def _src(cls, v: str) -> str:
        if v not in KNOWLEDGE_SOURCES:
            raise ValueError("Nguồn không hợp lệ.")
        return v

    @field_validator("ai_status")
    @classmethod
    def _ai(cls, v: str) -> str:
        if v not in KNOWLEDGE_AI_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v


class KnowledgeOut(Out):
    id: int
    name: str
    name_en: str
    tax_code: str | None
    stock_code: str
    industry: str
    address: str
    province: str
    phone: str
    fax: str
    email: str
    website: str
    founded_year: int | None
    ceo_name: str
    description: str
    logo_url: str
    rank: int | None
    rank_label: str
    rank_list: str
    rank_year: int | None
    source: str
    source_id: str | None
    source_url: str
    extra: dict
    crawled_at: UtcDatetime | None
    ai_status: str
    ai_scanned_at: UtcDatetime | None
    ai_note: str
    note: str
    created_at: UtcDatetime
    updated_at: UtcDatetime


class KnowledgeListItem(Out):
    id: int
    name: str
    tax_code: str | None
    industry: str
    province: str
    rank: int | None
    rank_year: int | None
    source: str
    ai_status: str
    updated_at: UtcDatetime
