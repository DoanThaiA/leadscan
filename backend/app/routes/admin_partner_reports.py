"""API quản trị — báo cáo Đối tác: /api/admin/partner-reports/*

KPI thí điểm, công nợ đối tác, hiệu quả theo đối tác / ngành / tỉnh (kèm chi phí / doanh thu), cờ gian lận, nhật ký chung.
Thuế TNCN theo kỳ: /api/admin/partner-withdrawals/tax-report.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models import AdminUser
from app.services import partner_reports as rep

router = APIRouter(prefix="/api/admin/partner-reports")


def _csv(name: str, data: bytes) -> Response:
    return Response(data, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}.csv"', "Cache-Control": "no-store"})


@router.get("/kpi")
def kpi(d_from: date | None = Query(None, alias="from"), d_to: date | None = Query(None, alias="to"),
        _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return rep.kpi(db, d_from, d_to)


@router.get("/liabilities")
def liabilities(format: Literal["json", "csv"] = "json", _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    data = rep.liabilities(db)
    if format == "csv":
        rows = [[r["partner"]["code"], r["partner"]["full_name"], r["partner"]["tier"], r["pending"], r["available"], r["withdrawing"], r["owed"], r["paid"]] for r in data["items"]]
        return _csv("cong-no-doi-tac", rep.to_csv(["Mã đối tác", "Đối tác", "Hạng", "Chờ duyệt", "Khả dụng", "Đang rút", "LeadScan đang nợ", "Đã chi"], rows))
    return data


@router.get("/performance")
def performance(group: Literal["partner", "industry", "province"] = "partner", d_from: date | None = Query(None, alias="from"),
                d_to: date | None = Query(None, alias="to"), format: Literal["json", "csv"] = "json",
                _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    data = rep.performance(db, group, d_from, d_to)
    if format == "csv":
        head = {"partner": "Đối tác", "industry": "Ngành", "province": "Tỉnh/thành"}[group]
        rows = [[r["label"], r["sent"], r["ok"], r["pass_rate"], r["sold"], r["revenue"], r["cost"], r["cost_ratio"]] for r in data["items"]]
        return _csv(f"hieu-qua-theo-{group}", rep.to_csv([head, "Đã gửi", "Đạt", "Tỷ lệ đạt (%)", "Bán được", "Doanh thu thuần (đ)", "Chi phí đối tác (đ)", "Chi phí/doanh thu (%)"], rows))
    return data


@router.get("/fraud")
def fraud(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return {"items": rep.fraud_flags(db)}


@router.get("/events")
def events(kind: str = "", partner_id: int | None = None, q: str = Query("", max_length=100), page: int = Query(1, ge=1),
           page_size: int = Query(50, ge=1, le=200), d_from: date | None = Query(None, alias="from"), d_to: date | None = Query(None, alias="to"),
           _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return rep.events(db, kind, partner_id, q, page, page_size, d_from, d_to)
