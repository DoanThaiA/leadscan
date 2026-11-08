"""Chuẩn hoá và kiểm tra dữ liệu form đăng ký (giữ nguyên quy tắc của bản PHP cũ)."""

import re
from urllib.parse import urlparse

REGIONS = ["Miền Bắc", "Miền Trung", "Miền Nam", "Toàn quốc", "Quốc tế"]
OPP_TYPES = [
    "Đăng mua (App đăng mua)",
    "Dự án & gói thầu",
    "Nhà máy / dự án FDI mới",
    "Hội chợ & triển lãm",
    "Mạng xã hội & nhóm chat",
    "Nguồn chính thống (Trang vàng, Bộ Công Thương, Công báo)",
]
# Ngành hàng gợi ý (form đăng ký chọn nhiều; tối đa MAX_INDUSTRIES)
INDUSTRIES = [
    "Sản xuất công nghiệp",
    "Bao bì & in ấn",
    "Nhựa & cao su",
    "Điện tử & linh kiện",
    "Cơ khí & máy móc",
    "Hoá chất & vật tư",
    "Dệt may & da giày",
    "Xuất nhập khẩu",
    "Thương mại & phân phối",
    "Logistics & vận tải",
    "Xây dựng & vật liệu",
    "Thực phẩm & đồ uống",
    "Nông sản & thuỷ sản",
    "Dịch vụ B2B",
    "Công nghệ thông tin",
]
MAX_INDUSTRIES = 8
# Khu vực gợi ý cho "Tìm cơ hội phù hợp" (miền + tỉnh/thành hay có cơ hội)
AREAS = [
    "Toàn quốc", "Miền Bắc", "Miền Trung", "Miền Nam",
    "Hà Nội", "TP. Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Bắc Ninh", "Bắc Giang", "Hải Dương", "Hưng Yên",
    "Vĩnh Phúc", "Thái Nguyên", "Quảng Ninh", "Đồng Nai", "Bình Dương", "Long An", "Bà Rịa - Vũng Tàu", "Cần Thơ",
]
# Quy mô khách hàng mục tiêu — lưu để AI chấm điểm "khớp nhu cầu", không dùng để lọc cứng
CUSTOMER_SIZES = ["Dưới 50 nhân sự", "50–200 nhân sự", "200+ nhân sự", "Doanh nghiệp FDI"]
SIZES = ["Dưới 10 nhân sự", "10–49 nhân sự", "50–199 nhân sự", "200–499 nhân sự", "Từ 500 nhân sự"]
TICKETS = ["Dưới 50 phiếu", "50–200 phiếu", "200–1.000 phiếu", "Trên 1.000 phiếu", "Chưa xác định"]

_CTRL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean(v: object, max_len: int) -> str:
    """Chuỗi nhiều dòng: bỏ ký tự điều khiển, cắt khoảng trắng, giới hạn độ dài."""
    if not isinstance(v, str):
        return ""
    return _CTRL.sub("", v).strip()[:max_len]


def clean1(v: object, max_len: int) -> str:
    """Chuỗi 1 dòng: gộp mọi khoảng trắng/xuống dòng thành 1 dấu cách."""
    return re.sub(r"\s+", " ", clean(v, max_len)).strip()


def pick_list(v: object, allowed: list[str]) -> list[str]:
    """Chỉ giữ giá trị nằm trong danh sách cho phép, theo thứ tự của danh sách."""
    if not isinstance(v, list):
        return []
    given = {str(x) for x in v}
    return [a for a in allowed if a in given]


def pick_industries(raw: dict) -> list[str]:
    """Ngành hàng chọn nhiều: nhận list (mới) hoặc chuỗi cách nhau dấu phẩy (bản cũ); bỏ trùng, giữ thứ tự."""
    v = raw.get("industries")
    if not isinstance(v, list):
        v = str(raw.get("industry") or "").split(",")
    out: list[str] = []
    for x in v:
        x = clean1(x, 60)
        if x and x.lower() not in {o.lower() for o in out}:
            out.append(x)
    return out[:MAX_INDUSTRIES]


def _valid_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and "." in (p.hostname or "") and " " not in url


def normalize(raw: dict) -> tuple[dict, dict[str, str]]:
    """Trả về (dữ liệu đã chuẩn hoá, lỗi theo trường)."""
    d = {
        "company_name": clean1(raw.get("company_name"), 150),
        "tax_code": re.sub(r"[^0-9\-]", "", clean(raw.get("tax_code"), 20)),
        "industries": pick_industries(raw),
        "company_size": clean1(raw.get("company_size"), 40),
        "province": clean1(raw.get("province"), 80),
        "address": clean1(raw.get("address"), 200),
        "website": clean1(raw.get("website"), 200),
        "contact_name": clean1(raw.get("contact_name"), 100),
        "position": clean1(raw.get("position"), 100),
        "email": clean1(raw.get("email"), 150).lower(),
        "phone": re.sub(r"[\s.\-()]", "", clean(raw.get("phone"), 20)),
        "offering": clean(raw.get("offering"), 1000),
        "target_customers": clean(raw.get("target_customers"), 1000),
        "target_regions": pick_list(raw.get("target_regions"), REGIONS),
        "opp_types": pick_list(raw.get("opp_types"), OPP_TYPES),
        "expected_tickets": raw.get("expected_tickets") if raw.get("expected_tickets") in TICKETS else "",
        "notes": clean(raw.get("notes"), 1000),
    }

    d["industry"] = ", ".join(d["industries"])[:300]

    # Form đăng ký chỉ còn thông tin cơ bản; tiêu chí tìm cơ hội nhập trong cổng thành viên.
    # offering/target_customers/... vẫn nhận nếu có (dữ liệu bản PHP cũ) nhưng không bắt buộc.
    errors: dict[str, str] = {}
    required = {
        "company_name": "Vui lòng nhập tên doanh nghiệp.",
        "province": "Vui lòng nhập tỉnh/thành.",
        "contact_name": "Vui lòng nhập họ tên người liên hệ.",
    }
    for field, msg in required.items():
        if d[field] == "":
            errors[field] = msg
    if not d["industries"]:
        errors["industries"] = "Vui lòng chọn ít nhất 1 ngành hàng."
    if d["company_size"] not in SIZES:
        errors["company_size"] = "Vui lòng chọn quy mô."
    if not re.fullmatch(r"\d{10}(-?\d{3})?", d["tax_code"]):
        errors["tax_code"] = "Mã số thuế gồm 10 hoặc 13 chữ số."
    if not _EMAIL.match(d["email"]):
        errors["email"] = "Email chưa đúng định dạng."
    if not re.fullmatch(r"(0|\+84)\d{9,10}", d["phone"]):
        errors["phone"] = "Số điện thoại chưa đúng định dạng."
    if d["website"]:
        w = d["website"] if re.match(r"^https?://", d["website"], re.I) else "https://" + d["website"]
        if _valid_url(w):
            d["website"] = w
        else:
            errors["website"] = "Website chưa đúng định dạng."
    if not raw.get("agree"):
        errors["agree"] = "Bạn cần đồng ý điều khoản để tiếp tục."

    return d, errors


def tax_key(tax_code: str) -> str:
    return re.sub(r"\D", "", tax_code)
