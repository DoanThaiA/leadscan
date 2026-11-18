"""Xuất Excel danh sách lead CRM — CHỈ dữ liệu doanh nghiệp: không có cột tên/SĐT/email đầu mối (CRM không bán dữ liệu cá nhân)."""

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models_crm import CRM_STAGES, CrmLead
from app.services import crm

COLUMNS = [
    ("Mã phiếu", 14), ("Cơ hội", 48), ("Bên có nhu cầu", 34), ("MST bên có nhu cầu", 16), ("Ngành", 22), ("Tỉnh/thành", 16),
    ("Quy mô / số lượng", 26), ("Giá trị ước tính", 20), ("Hạn chót", 12), ("Điểm phù hợp", 10), ("Giai đoạn", 14),
    ("Phụ trách", 20), ("Việc chưa xong", 10), ("Hạn việc gần nhất", 14), ("Giá phiếu (điểm)", 14), ("Ngày mua", 12),
]
# Bảo vệ cấu trúc: test kiểm tra không cột nào mang dữ liệu cá nhân
PII_WORDS = ("đầu mối", "điện thoại", "sđt", "email", "người liên hệ")


FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe(v):
    """Chống chèn công thức (CSV/Excel injection — OWASP): tiêu đề, tên bên mua có thể do đối tác nhập; chuỗi bắt đầu bằng
    = + - @ sẽ bị Excel/openpyxl coi là công thức (vd. =HYPERLINK gửi dữ liệu ra ngoài khi người dùng bấm). Thêm ' ở đầu."""
    return "'" + v if isinstance(v, str) and v.startswith(FORMULA_START) else v


def _date(v) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def leads_xlsx(leads: list[CrmLead], stats: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Lead"
    ws.append([c for c, _ in COLUMNS])
    for i, (_, w) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    head = PatternFill("solid", fgColor="FFCD00")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="00305A")
        cell.fill = head
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"

    for lead in leads:
        s = crm.snapshot(lead)
        n_open, next_due = stats.get(lead.id, (0, None))
        ws.append([safe(v) for v in [
            s.get("code", ""), s.get("title", ""), s.get("buyer_name", ""), lead.purchase.opportunity.buyer_tax_key or "",
            s.get("industry", ""), s.get("province", ""), s.get("scale", ""), s.get("estimated_value", ""), _date(s.get("deadline")),
            s.get("score", 0), CRM_STAGES.get(lead.stage, lead.stage), lead.owner.full_name if lead.owner else "",
            n_open, next_due, lead.purchase.price, lead.purchase.created_at.date() if lead.purchase.created_at else None,
        ]])
    for row in ws.iter_rows(min_row=2):
        for idx in (8, 13, 15):  # cột ngày
            row[idx].number_format = "DD/MM/YYYY"
        row[14].number_format = "#,##0"
    if leads:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(leads) + 1}"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
