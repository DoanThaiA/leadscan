"""Chuẩn hoá chức danh về danh mục cố định (B03) và cờ "người ra quyết định".

Người ra quyết định (mục 3): người đại diện pháp luật, HĐQT, ban điều hành, giám đốc khối.
"""

import re

from app.enrich.normalize import bo_dau

# mã → (tên hiển thị, là người ra quyết định)
TITLES: dict[str, tuple[str, bool]] = {
    "dai_dien_phap_luat": ("Người đại diện theo pháp luật", True),
    "chu_tich_hdqt": ("Chủ tịch HĐQT", True),
    "pho_chu_tich_hdqt": ("Phó Chủ tịch HĐQT", True),
    "thanh_vien_hdqt": ("Thành viên HĐQT", True),
    "chu_tich_hdtv": ("Chủ tịch HĐTV / Chủ tịch công ty", True),
    "tong_giam_doc": ("Tổng Giám đốc", True),
    "pho_tong_giam_doc": ("Phó Tổng Giám đốc", True),
    "giam_doc": ("Giám đốc", True),
    "pho_giam_doc": ("Phó Giám đốc", True),
    "giam_doc_khoi": ("Giám đốc khối / chức năng", True),
    "ke_toan_truong": ("Kế toán trưởng", False),
    "truong_ban_kiem_soat": ("Trưởng Ban kiểm soát", False),
    "truong_phong": ("Trưởng phòng", False),
    "thanh_vien_bdh": ("Thành viên Ban điều hành", True),
    "thanh_vien_bks": ("Thành viên Ban kiểm soát / Uỷ ban kiểm toán", False),
    "phu_trach_quan_tri": ("Người phụ trách quản trị công ty / Thư ký công ty", False),
    "chu_doanh_nghiep": ("Chủ doanh nghiệp tư nhân", True),
    "khac": ("Khác", False),
}

# thứ tự quan trọng: cụm cụ thể trước cụm chung
_RULES: list[tuple[str, str]] = [
    (r"dai dien (theo )?phap luat|nguoi dai dien", "dai_dien_phap_luat"),
    (r"pho chu tich (hoi dong quan tri|hdqt)", "pho_chu_tich_hdqt"),
    (r"chu tich (hoi dong quan tri|hdqt)", "chu_tich_hdqt"),
    (r"(thanh vien|uy vien) (hoi dong quan tri|hdqt)|thanh vien hdqt doc lap", "thanh_vien_hdqt"),
    (r"chu tich (hoi dong thanh vien|hdtv|cong ty)", "chu_tich_hdtv"),
    (r"(thanh vien|uy vien) (ban kiem soat|bks|uy ban kiem toan|ubkt)|kiem soat vien|chu tich uy ban kiem toan", "thanh_vien_bks"),
    (r"thanh vien ban (dieu hanh|giam doc|tong giam doc)", "thanh_vien_bdh"),
    (r"pho tong giam doc|pho tgd", "pho_tong_giam_doc"),
    (r"tong giam doc|\btgd\b|\bceo\b", "tong_giam_doc"),
    (r"giam doc (tai chinh|kinh doanh|san xuat|marketing|nhan su|cong nghe|van hanh|khoi|dieu hanh)|\b(cfo|cto|coo|cmo|chro)\b", "giam_doc_khoi"),
    (r"pho giam doc", "pho_giam_doc"),
    (r"giam doc|\bgd\b|director", "giam_doc"),
    (r"ke toan truong", "ke_toan_truong"),
    (r"phu trach quan tri|thu ky (cong ty|hdqt|hoi dong quan tri)", "phu_trach_quan_tri"),
    (r"truong ban kiem soat", "truong_ban_kiem_soat"),
    (r"chu doanh nghiep", "chu_doanh_nghiep"),
    (r"truong phong", "truong_phong"),
]


def normalize_title(raw: str | None) -> tuple[str, bool]:
    """'Tổng Giám Đốc' → ('tong_giam_doc', True). Không nhận ra → ('khac', False)."""
    key = bo_dau(raw)
    for pattern, code in _RULES:
        if re.search(pattern, key):
            return code, TITLES[code][1]
    return "khac", False
