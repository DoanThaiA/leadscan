"""Chuẩn hoá giá trị dùng chung cho phân hệ làm giàu dữ liệu."""

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime


def bo_dau(s: str | None) -> str:
    """'Công ty Đại Việt' → 'cong ty dai viet' (chữ thường, gộp khoảng trắng) — dùng để tìm kiếm không dấu."""
    if not s:
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass
class MstResult:
    mst: str | None  # dạng chuẩn: 10 số, hoặc 0101234567-001
    error: str = ""  # lý do sai định dạng (khi mst None)
    padded: bool = False  # đã bù số 0 đầu bị Excel làm rơi


def parse_mst(raw: object) -> MstResult:
    """MST hợp lệ gồm 10 hoặc 13 chữ số (A01).

    Excel (và CSV xuất từ Excel) hay làm rơi số 0 đầu: 0101234567 → 101234567. MST luôn có đủ 10/13 số nên
    9 hoặc 12 chữ số được bù một số 0 và báo riêng trong biên bản nhập.
    """
    if raw is None:
        return MstResult(None, "Trống")
    if isinstance(raw, bool):
        return MstResult(None, "Không phải mã số thuế")
    if isinstance(raw, float):
        if not raw.is_integer():
            return MstResult(None, "Không phải mã số thuế")
        raw = int(raw)
    s = str(raw).strip()
    if not s:
        return MstResult(None, "Trống")
    compact = re.sub(r"[\s.]", "", s)
    if not re.fullmatch(r"\d+(-\d+)?", compact):
        return MstResult(None, "Có ký tự không phải chữ số")
    if "-" in compact:
        head, tail = compact.split("-")
        if len(head) == 9:
            head = "0" + head
            padded = True
        else:
            padded = False
        if len(head) != 10 or len(tail) != 3:
            return MstResult(None, "MST chi nhánh phải dạng 10 số - 3 số")
        return MstResult(f"{head}-{tail}", padded=padded)
    d = compact
    padded = False
    if len(d) in (9, 12):
        d = "0" + d
        padded = True
    if len(d) == 10:
        return MstResult(d, padded=padded)
    if len(d) == 13:
        return MstResult(f"{d[:10]}-{d[10:]}", padded=padded)
    return MstResult(None, f"Sai độ dài ({len(compact)} chữ số)")


# ------------------------------------------------------------------ B02: chuẩn hoá giá trị

# 34 tỉnh/thành sau sắp xếp đơn vị hành chính (hiệu lực 1/7/2025). Tên cũ → tên mới để địa chỉ cũ vẫn tách đúng.
PROVINCES_2025 = {
    "Hà Nội": [], "Huế": ["Thừa Thiên Huế"], "Lai Châu": [], "Điện Biên": [], "Sơn La": [],
    "Lạng Sơn": [], "Quảng Ninh": [], "Thanh Hoá": ["Thanh Hóa"], "Nghệ An": [], "Hà Tĩnh": [], "Cao Bằng": [],
    "Tuyên Quang": ["Hà Giang"], "Lào Cai": ["Yên Bái"], "Thái Nguyên": ["Bắc Kạn", "Bắc Cạn"],
    "Phú Thọ": ["Vĩnh Phúc", "Hoà Bình", "Hòa Bình"], "Bắc Ninh": ["Bắc Giang"], "Hưng Yên": ["Thái Bình"],
    "Hải Phòng": ["Hải Dương"], "Ninh Bình": ["Hà Nam", "Nam Định"], "Quảng Trị": ["Quảng Bình"],
    "Đà Nẵng": ["Quảng Nam"], "Quảng Ngãi": ["Kon Tum"], "Gia Lai": ["Bình Định"], "Khánh Hoà": ["Khánh Hòa", "Ninh Thuận"],
    "Lâm Đồng": ["Đắk Nông", "Đăk Nông", "Bình Thuận"], "Đắk Lắk": ["Đăk Lăk", "Đắc Lắc", "Phú Yên"],
    "Hồ Chí Minh": ["Bình Dương", "Bà Rịa Vũng Tàu", "Vũng Tàu", "Sài Gòn", "HCM", "TPHCM"],
    "Đồng Nai": ["Bình Phước"], "Tây Ninh": ["Long An"], "Cần Thơ": ["Sóc Trăng", "Hậu Giang"],
    "Vĩnh Long": ["Bến Tre", "Trà Vinh"], "Đồng Tháp": ["Tiền Giang"], "Cà Mau": ["Bạc Liêu"], "An Giang": ["Kiên Giang"],
}


def _letters(s: str) -> str:
    return re.sub(r"[^a-z]", "", bo_dau(s))


_PROVINCE_KEYS: dict[str, str] = {_letters(n): new for new, olds in PROVINCES_2025.items() for n in [new, *olds]}
_PROVINCE_BY_LEN = sorted(_PROVINCE_KEYS.items(), key=lambda kv: -len(kv[0]))
_PROVINCE_PREFIX = re.compile(r"^(tinh|thanh pho|tp\.?|t\.p\.?)\s*")


def province_of(address: str | None) -> str | None:
    """Tách tỉnh/thành (tên sau 1/7/2025) từ địa chỉ: xét các đoạn cuối, bỏ "Việt Nam", "Tỉnh", "Thành phố"."""
    if not address:
        return None
    parts = [p.strip() for p in re.split(r"[,;]", address) if p.strip()]
    for part in reversed(parts[-3:]):
        key = bo_dau(part)
        if key in ("viet nam", "vietnam", "vn"):
            continue
        key = re.sub(r"[^a-z]", "", _PROVINCE_PREFIX.sub("", key))
        if key in _PROVINCE_KEYS:
            return _PROVINCE_KEYS[key]
    # không tách được theo dấu phẩy: khớp đuôi địa chỉ
    tail = _letters(re.sub(r"(?i)vi[eệ]t\s*nam\s*$", "", address.strip(" ,.")))
    for k, v in _PROVINCE_BY_LEN:
        if len(k) >= 5 and tail.endswith(k):
            return v
    return None


# Loại hình doanh nghiệp tách từ tên (khớp trên tên không dấu); cụm dài trước
COMPANY_TYPES = [
    (r"cong ty trach nhiem huu han mot thanh vien|cong ty tnhh mot thanh vien|cong ty tnhh mtv", "Công ty TNHH một thành viên"),
    (r"cong ty trach nhiem huu han|cong ty tnhh|^tnhh", "Công ty TNHH"),
    (r"^tong cong ty", "Tổng công ty"),
    (r"cong ty co phan|^ctcp|cong ty cp\b", "Công ty cổ phần"),
    (r"cong ty hop danh", "Công ty hợp danh"),
    (r"doanh nghiep tu nhan|^dntn", "Doanh nghiệp tư nhân"),
    (r"lien hiep hop tac xa", "Liên hiệp hợp tác xã"),
    (r"hop tac xa|^htx", "Hợp tác xã"),
    (r"^chi nhanh", "Chi nhánh"),
    (r"^van phong dai dien", "Văn phòng đại diện"),
    (r"^dia diem kinh doanh", "Địa điểm kinh doanh"),
]


def company_type(name: str | None) -> str | None:
    key = bo_dau(name)
    for pattern, label in COMPANY_TYPES:
        if re.search(pattern, key):
            return label
    return None


# Tình trạng hoạt động chuẩn hoá (cách gọi trên Cổng ĐKKD / tra cứu người nộp thuế)
STATUSES = [
    (r"dang lam thu tuc giai the|dang giai the", "Đang làm thủ tục giải thể"),
    (r"da giai the|giai the", "Đã giải thể"),
    (r"thu hoi", "Bị thu hồi giấy chứng nhận"),
    (r"tam ngung|tam dung", "Tạm ngừng kinh doanh"),
    (r"khong hoat dong tai dia chi", "Không hoạt động tại địa chỉ đã đăng ký"),
    (r"ngung hoat dong.*(da dong|cham dut)|da dong ma so thue|cham dut hieu luc ma so thue", "Ngừng hoạt động, đã đóng MST"),
    (r"ngung hoat dong", "Ngừng hoạt động, chưa đóng MST"),
    (r"pha san", "Phá sản"),
    (r"dang hoat dong|con hoat dong|hoat dong binh thuong", "Đang hoạt động"),
]


def normalize_status(raw: str | None) -> str | None:
    key = bo_dau(raw)
    if not key:
        return None
    for pattern, label in STATUSES:
        if re.search(pattern, key):
            return label
    return " ".join(str(raw).split())[:120]


def normalize_phone(raw: str | None) -> str | None:
    """Điện thoại về dạng +84… (B02). Không nhận ra thì None."""
    d = re.sub(r"[^\d+]", "", raw or "")
    if d.startswith("+84"):
        d = "0" + d[3:]
    elif d.startswith("84") and len(d) in (11, 12):
        d = "0" + d[2:]
    if not re.fullmatch(r"0\d{9,10}", d):
        return None
    return "+84" + d[1:]


def parse_date(raw) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def parse_money(raw) -> int | None:
    """'1.500.000.000', '1,500,000,000 đồng', '2,5 tỷ', 1500000000.0 → số đồng."""
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    s = bo_dau(str(raw))
    mult = 1_000_000_000 if re.search(r"\bty\b", s) else 1_000_000 if "trieu" in s else 1
    m = re.search(r"\d[\d.,\s]*", s)
    if not m:
        return None
    num = re.sub(r"\s", "", m.group(0)).strip(".,")
    if mult > 1:
        num = num.replace(",", ".")
        if num.count(".") > 1:
            num = num.replace(".", "")
        try:
            return int(float(num) * mult)
        except ValueError:
            return None
    digits = re.sub(r"[.,]", "", num)
    return int(digits) if digits else None


def normalize_website(raw: str | None) -> tuple[str | None, str | None]:
    """(website có https://, tên miền không www)."""
    s = (raw or "").strip()
    if not s or " " in s or "." not in s:
        return None, None
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s
    m = re.match(r"^https?://([^/:?#]+)", s, re.I)
    if not m:
        return None, None
    host = m.group(1).lower()
    return s.rstrip("/"), host[4:] if host.startswith("www.") else host


def clean_text(raw, limit: int = 600) -> str | None:
    if raw is None:
        return None
    s = " ".join(str(raw).split())
    return s[:limit] or None


def json_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)
