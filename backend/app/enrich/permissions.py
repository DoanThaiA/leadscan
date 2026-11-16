"""Vai trò → quyền trong phân hệ làm giàu dữ liệu (tài liệu yêu cầu, mục 3; N04: kiểm soát tới từng trường).

Quyền (cap):
  a.read        xem hồ sơ doanh nghiệp (kho A)
  a.evidence    xem nguồn gốc từng trường của doanh nghiệp
  batch.read    xem danh sách lô MST
  batch.import  nhập lô MST
  b.read        xem tên, chức danh, liên hệ công việc của người — chỉ trong ngữ cảnh hồ sơ doanh nghiệp
  b.personal    xem MST cá nhân, năm sinh
  b.evidence    xem nguồn gốc trường của người
  b.list        truy vấn trực tiếp kho B (tìm, liệt kê người)
  run.read      xem vòng thu thập, tiến trình
  run.manage    tạo / tạm dừng / huỷ vòng thu thập
  source.manage cấu hình nguồn (bật tắt, độ tin cậy, tốc độ), dừng khẩn cấp, khung giờ chạy
  manual.work   xử lý hàng đợi thủ công
  data.import   nhập file nguồn chính thức (dữ liệu mua ĐKKD, nợ thuế, đấu thầu)
  docs.manage   nạp tài liệu công bố thông tin, duyệt kết quả bóc tách người + chức danh
  people.manage gộp / tách hồ sơ người, nhập MST cá nhân nội bộ, chạy suy luận email
  a.export      xuất danh sách doanh nghiệp theo bộ lọc (kho A)
  b.export      xuất kèm cột kho B (người ra quyết định, email công việc)
  compliance.*  danh sách từ chối, yêu cầu chủ thể dữ liệu, rà soát lưu trữ, DPIA, nhật ký truy cập / xuất

Không có vai trò → không vào được phân hệ (kho B mặc định ẩn).
"""

from fastapi import Depends, HTTPException

from app.auth import current_user
from app.models import AdminUser

_ALL_B = {"b.read", "b.personal", "b.evidence", "b.list"}
_BASE = {"a.read", "a.evidence", "batch.read"}

_OPS = {"run.read", "manual.work", "data.import", "docs.manage", "people.manage"}
_COMPLIANCE = {"compliance.read", "compliance.manage"}

ROLE_CAPS: dict[str, frozenset[str]] = {
    # source.manage: cấu hình nguồn, dừng khẩn cấp, khung giờ · run.manage: tạo / dừng vòng thu thập
    "quan_tri": frozenset(_BASE | {"batch.import", "source.manage", "run.manage", "a.export", "b.export"} | _COMPLIANCE | _OPS | _ALL_B),
    # biên tập: không xuất hàng loạt kho B (mục 3)
    "bien_tap": frozenset(_BASE | {"batch.import", "a.export"} | _OPS | _ALL_B),
    # kinh doanh: xuất kho A được, không xuất kho B / không thấy MST cá nhân
    "kinh_doanh": frozenset(_BASE | {"b.read", "a.export"}),
    "tham_dinh": frozenset(_BASE | {"run.read", "a.export", "b.export"} | _COMPLIANCE | _ALL_B),
    "phan_tich": frozenset(_BASE),
}

# Trường của người → quyền cần để thấy trường đó. Trường không có ở đây thì không bao giờ trả ra.
PERSON_FIELD_CAPS = {
    "id": "b.read",
    "ho_ten": "b.read",
    "chuc_danh": "b.read",
    "chuc_danh_chuan": "b.read",
    "la_nguoi_quyet_dinh": "b.read",
    "tu_ngay": "b.read",
    "den_ngay": "b.read",
    "lien_he": "b.read",  # email / điện thoại công việc
    "nam_sinh": "b.personal",
    "mst_ca_nhan": "b.personal",
    "bang_chung": "b.evidence",
}

FORBIDDEN = "Vai trò của bạn không được phép xem dữ liệu này."


def caps_of(user: AdminUser) -> frozenset[str]:
    return ROLE_CAPS.get(user.enrich_access or "", frozenset())


def has(user: AdminUser, cap: str) -> bool:
    return cap in caps_of(user)


def require(cap: str):
    """Dependency FastAPI: người dùng phải có quyền `cap`."""

    def dep(user: AdminUser = Depends(current_user)) -> AdminUser:
        if not user.enrich_access:
            raise HTTPException(403, "Tài khoản chưa được cấp vai trò trong phân hệ làm giàu dữ liệu.")
        if cap not in caps_of(user):
            raise HTTPException(403, FORBIDDEN)
        return user

    return dep


def filter_person(user: AdminUser, row: dict) -> dict:
    """Bỏ các trường người dùng không được xem (N04)."""
    caps = caps_of(user)
    return {k: v for k, v in row.items() if PERSON_FIELD_CAPS.get(k) in caps}
