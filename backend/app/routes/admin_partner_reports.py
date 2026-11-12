"""API quản trị — báo cáo Đối tác: /api/admin/partner-reports/*

KPI thí điểm, công nợ đối tác, hiệu quả theo đối tác / ngành / tỉnh (kèm chi phí / doanh thu), cờ gian lận, nhật ký chung.
Thuế TNCN theo kỳ: /api/admin/partner-withdrawals/tax-report.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
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
    items = rep.fraud_flags(db)
    return {"items": items, "open": sum(1 for f in items if f["status"] == "open")}


class FlagReviewIn(BaseModel):
    key: str = Field(min_length=3, max_length=255)
    note: str = Field("", max_length=300)


def _admin_only(user: AdminUser) -> None:
    if user.role != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được xử lý cờ gian lận.")


@router.post("/fraud/review")
def review_flag(body: FlagReviewIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Kết luận cờ không phải gian lận (bỏ qua). Cờ tự hiện lại khi có dấu hiệu mới."""
    _admin_only(user)
    if not body.note.strip():
        raise HTTPException(422, "Vui lòng ghi lý do bỏ qua cờ.")
    try:
        rep.review_flag(db, body.key, body.note.strip(), user)
    except rep.FlagError as e:
        raise HTTPException(409, str(e)) from None
    return {"ok": True}


@router.post("/fraud/reopen")
def reopen_flag(body: FlagReviewIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    _admin_only(user)
    try:
        rep.reopen_flag(db, body.key, user, body.note.strip())
    except rep.FlagError as e:
        raise HTTPException(409, str(e)) from None
    return {"ok": True}


@router.get("/events")
def events(kind: str = "", partner_id: int | None = None, q: str = Query("", max_length=100), page: int = Query(1, ge=1),
           page_size: int = Query(50, ge=1, le=200), d_from: date | None = Query(None, alias="from"), d_to: date | None = Query(None, alias="to"),
           format: Literal["json", "csv"] = "json", _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    if format == "csv":
        return _csv("nhat-ky-doi-tac", rep.events_csv(db, kind, partner_id, q, d_from, d_to))
    return rep.events(db, kind, partner_id, q, page, page_size, d_from, d_to)
