"""Dữ liệu vào/ra của tuyển dụng: bài tuyển dụng (admin + công khai) và hồ sơ ứng tuyển."""

import base64
import binascii
import re
import unicodedata
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models import APPLICATION_STATUSES, JOB_STATUSES, JOB_TYPES
from app.schemas import Email, Line, Out, Phone, UtcDatetime


def slugify(text: str, max_len: int = 120) -> str:
    """"Chuyên viên Kinh doanh B2B" → "chuyen-vien-kinh-doanh-b2b" (bỏ dấu tiếng Việt)."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-")


def _url(v: str) -> str:
    v = v.strip()
    if not v:
        return ""
    if not re.match(r"^https?://", v, re.I):
        v = "https://" + v
    if " " in v or not re.match(r"^https?://[^/\s]+\.[^/\s]+", v, re.I):
        raise ValueError("Đường dẫn chưa đúng định dạng.")
    return v


# ------------------------------------------------------------------ bài tuyển dụng (admin)


class JobIn(BaseModel):
    title: Line = Field(min_length=3, max_length=200)
    slug: str = Field("", max_length=160)  # trống = tự sinh từ tiêu đề
    status: str = "draft"
    subtitle: Line = Field("", max_length=300)
    department: Line = Field("", max_length=100)
    location: Line = Field("", max_length=300)
    employment_type: str = "full_time"
    salary: Line = Field("", max_length=150)
    work_time: Line = Field("", max_length=200)
    reports_to: Line = Field("", max_length=150)
    quantity: int | None = Field(None, ge=1, le=1000)
    deadline: date | None = None
    cover_image: str = Field("", max_length=500)
    summary: str = Field("", max_length=1000)
    objective: str = Field("", max_length=20000)
    description: str = Field("", max_length=20000)
    requirements: str = Field("", max_length=20000)
    benefits: str = Field("", max_length=20000)
    how_to_apply: str = Field("", max_length=20000)
    apply_email: Email = Field("", max_length=200)

    @field_validator("cover_image")
    @classmethod
    def _cover(cls, v: str) -> str:
        """Ảnh bìa: đường dẫn trên website (bắt đầu bằng "/") hoặc URL http(s)."""
        v = v.strip()
        if not v:
            return ""
        if v.startswith("/") and not v.startswith("//"):
            if re.search(r"\s|\.\.", v):
                raise ValueError("Đường dẫn ảnh chưa đúng định dạng.")
            return v
        return _url(v)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        return slugify(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in JOB_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v

    @field_validator("employment_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in JOB_TYPES:
            raise ValueError("Hình thức làm việc không hợp lệ.")
        return v

    @field_validator("summary", "objective", "description", "requirements", "benefits", "how_to_apply")
    @classmethod
    def _text(cls, v: str) -> str:
        return v.replace("\r\n", "\n").strip()


class JobPublic(Out):
    """Thông tin công khai trên /tuyen-dung (không có email nhận hồ sơ, người tạo...)."""

    slug: str
    status: str
    title: str
    subtitle: str
    department: str
    location: str
    employment_type: str
    salary: str
    work_time: str
    reports_to: str
    quantity: int | None
    deadline: date | None
    cover_image: str
    summary: str
    objective: str
    description: str
    requirements: str
    benefits: str
    how_to_apply: str
    published_at: UtcDatetime | None
    updated_at: UtcDatetime


class JobCard(Out):
    slug: str
    title: str
    department: str
    location: str
    employment_type: str
    salary: str
    quantity: int | None
    deadline: date | None
    cover_image: str
    summary: str
    published_at: UtcDatetime | None


class JobOut(JobPublic):
    id: int
    apply_email: str
    created_at: UtcDatetime


class CoverInitIn(BaseModel):
    """Khai báo ảnh bìa trước khi tải thẳng lên R2."""

    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=0)


# ------------------------------------------------------------------ hồ sơ ứng tuyển

CV_TYPES = {
    # đuôi file → (mime chuẩn, chữ ký đầu file)
    "pdf": ("application/pdf", (b"%PDF",)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)),
    "doc": ("application/msword", (b"\xd0\xcf\x11\xe0",)),
}


class CvFile(BaseModel):
    name: str = Field(max_length=200)
    data: str  # base64


class ApplyIn(BaseModel):
    full_name: Line = Field(min_length=2, max_length=100)
    phone: Phone
    email: Email
    cv_url: str = Field("", max_length=500)
    portfolio_url: str = Field("", max_length=500)
    intro: str = Field("", max_length=3000)
    cv_file: CvFile | None = None

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

    @field_validator("cv_url", "portfolio_url")
    @classmethod
    def _links(cls, v: str) -> str:
        return _url(v)

    @field_validator("intro")
    @classmethod
    def _intro(cls, v: str) -> str:
        return v.replace("\r\n", "\n").strip()


def decode_cv(f: CvFile, max_mb: int) -> tuple[str, str, bytes]:
    """Kiểm tra file CV (đuôi + chữ ký đầu file + dung lượng) → (tên file, mime, nội dung). Lỗi → ValueError."""
    name = re.sub(r"[\\/\x00-\x1f\"<>:|?*]+", "_", f.name).strip(" .") or "cv"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in CV_TYPES:
        raise ValueError("Chỉ nhận file PDF, DOC hoặc DOCX.")
    raw = f.data.split(",", 1)[1] if f.data.startswith("data:") else f.data
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("File CV bị lỗi, vui lòng chọn lại.") from None
    if not data:
        raise ValueError("File CV trống.")
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError(f"File CV tối đa {max_mb} MB.")
    mime, magics = CV_TYPES[ext]
    if not data.startswith(magics):
        raise ValueError("File không đúng định dạng PDF/DOC/DOCX.")
    return name[-200:], mime, data


class ApplicationAdminIn(BaseModel):
    status: str | None = None
    note: str | None = Field(None, max_length=5000)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in APPLICATION_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v


class ApplicationOut(Out):
    id: int
    job_id: int | None
    job_title: str
    status: str
    full_name: str
    phone: str
    email: str
    cv_url: str
    portfolio_url: str
    intro: str
    cv_filename: str
    cv_size: int
    note: str
    email_sent_at: UtcDatetime | None
    created_at: UtcDatetime
