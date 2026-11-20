"""Khung connector (mục 3, A04, N09): mỗi nguồn là một lớp độc lập, nhận MST và trả về các trường kèm bằng chứng.

Ba kiểu nguồn:
  http    tự tải theo MST (qua runner: giới hạn tốc độ theo tên miền, robots.txt, lưu bản gốc, thử lại)
  manual  nguồn có captcha / không cho tự động — MST vào hàng đợi thủ công, nhân viên tra rồi nhập (A10)
  file    file công bố hàng loạt hoặc dữ liệu mua — nhập ở trang "Nhập nguồn chính thức"

Thêm nguồn mới = thêm một lớp + đăng ký trong registry.py, không sửa lõi hay connector khác (N09).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar


@dataclass
class CompanyFact:
    field: str  # khoá trong COMPANY_FIELDS
    value: Any
    excerpt: str = ""
    is_inferred: bool = False


@dataclass
class PersonFact:
    ho_ten: str
    chuc_danh: str
    excerpt: str = ""
    tu_ngay: date | None = None
    den_ngay: date | None = None  # có → vai trò đã kết thúc (miễn nhiệm, từ nhiệm)
    mst_ca_nhan: str | None = None  # chỉ nguồn nội bộ có (khớp người chắc chắn — B06)
    email: str | None = None  # email công việc thấy ngay cạnh tên người (website)
    phone: str | None = None  # điện thoại công việc (đã chuẩn hoá +84…) — hiện chỉ biên tập viên nhập tay


@dataclass
class SignalFact:
    kind: str  # khoá trong SIGNAL_KINDS
    payload: dict
    day: date | None = None
    excerpt: str = ""


@dataclass
class Facts:
    company: list[CompanyFact] = field(default_factory=list)
    people: list[PersonFact] = field(default_factory=list)
    signals: list[SignalFact] = field(default_factory=list)
    contacts: list[tuple[str, str]] = field(default_factory=list)  # (email|phone, giá trị) của doanh nghiệp
    follow: list[str] = field(default_factory=list)  # đường dẫn cùng website nên tải tiếp (connector tự động)
    method: str = "luat"  # cách bóc tách đã dùng (cau_truc | luat | mo_hinh)

    def empty(self) -> bool:
        return not (self.company or self.people or self.signals)


class NeedsHuman(Exception):
    """Nguồn trả về captcha / chặn tự động → chuyển MST sang hàng đợi thủ công (A10), không vượt captcha."""


class NotFound(Exception):
    """Nguồn không có thông tin cho MST này."""


@dataclass
class ManualField:
    key: str  # khoá CompanyFact.field, hoặc "nguoi_dai_dien" (kho B)
    label: str
    kind: str = "text"  # text | textarea | date | select
    options: list[str] = field(default_factory=list)


class Connector:
    code: ClassVar[str]
    name: ClassVar[str]
    kind: ClassVar[str]  # http | manual | file | document
    domain: ClassVar[str] = ""
    default_trust: ClassVar[float] = 0.5
    legal_basis: ClassVar[str] = ""
    defaults: ClassVar[dict] = {"min_interval_s": 2.0, "timeout_s": 20, "max_retries": 3, "recrawl_days": 90}

    # --- http
    def urls(self, mst: str) -> list[str]:
        raise NotImplementedError

    def urls_for(self, mst: str, company) -> list[str]:
        """Đường dẫn cần tải cho MST; connector cần thông tin hồ sơ (vd website) thì ghi đè hàm này."""
        return self.urls(mst)

    def parse(self, mst: str, url: str, content: bytes, content_type: str) -> Facts:
        """Bóc tách một trang đã tải. Phải chạy lại được trên bản gốc đã lưu (A09) — không gọi mạng ở đây."""
        raise NotImplementedError

    # --- manual
    manual_fields: ClassVar[list[ManualField]] = []

    def manual_url(self, mst: str) -> str:
        return ""

    def manual_hint(self, mst: str) -> str:
        return ""
