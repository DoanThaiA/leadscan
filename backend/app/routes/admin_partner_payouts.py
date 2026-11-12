"""API quản trị — rút tiền đối tác: /api/admin/partner-withdrawals/*, /api/admin/partner-payout-batches/*

Nhân viên xem; duyệt / từ chối lệnh, lập lô, xuất file chi (có số tài khoản đầy đủ), đánh dấu đã chi: chỉ quản trị viên.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app.db import get_db
from app.models import WITHDRAWAL_OPEN, WITHDRAWAL_STATUSES, AdminUser, PartnerPayoutBatch, PartnerUser, PartnerWithdrawal
from app.services import partner_payouts as pay
from app.services import partner_wallet
from app.worker import enqueue, send_partner_withdrawal_update_task

router = APIRouter(prefix="/api/admin/partner-withdrawals")
batches = APIRouter(prefix="/api/admin/partner-payout-batches")


def _get(db: Session, wid: int) -> PartnerWithdrawal:
    w = db.get(PartnerWithdrawal, wid)
    if not w:
        raise HTTPException(404, "Không tìm thấy lệnh rút.")
    return w


@router.get("")
def list_withdrawals(
    status: str = "open",  # open = Chờ duyệt + Đã duyệt · all · hoặc 1 trạng thái
    q: str = Query("", max_length=100),
    partner_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(PartnerWithdrawal)
    if status == "open":
        stmt = stmt.where(PartnerWithdrawal.status.in_(WITHDRAWAL_OPEN))
    elif status and status != "all":
        stmt = stmt.where(PartnerWithdrawal.status == status)
    if partner_id:
        stmt = stmt.where(PartnerWithdrawal.partner_id == partner_id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.join(PartnerUser, PartnerUser.id == PartnerWithdrawal.partner_id).where(
            or_(PartnerWithdrawal.code.ilike(like), PartnerUser.code.ilike(like), PartnerUser.full_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PartnerWithdrawal.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    counts = dict(db.execute(select(PartnerWithdrawal.status, func.count()).group_by(PartnerWithdrawal.status)).all())
    st = partner_wallet.settings(db)
    return {"total": total, "items": [pay.withdrawal_out(w, admin=True, db=db) for w in rows], "counts": counts,
            "statuses": WITHDRAWAL_STATUSES, "next_pay_date": pay.next_pay_date(st).isoformat()}


@router.post("/{wid}/approve")
def approve(wid: int, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    w = _get(db, wid)
    pay.approve(db, w, user)
    enqueue(send_partner_withdrawal_update_task, w.id)
    return pay.withdrawal_out(w, admin=True, db=db)


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/{wid}/reject")
def reject(wid: int, body: RejectIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    w = _get(db, wid)
    pay.reject(db, w, user, body.reason.strip())
    enqueue(send_partner_withdrawal_update_task, w.id)
    return pay.withdrawal_out(w, admin=True, db=db)


class WithdrawalPatchIn(BaseModel):
    invoice_no: str | None = Field(None, max_length=50)  # đối tác tổ chức: số hoá đơn cho khoản hoa hồng
    tax_cert_no: str | None = Field(None, max_length=50)  # số chứng từ khấu trừ thuế TNCN
    note: str | None = Field(None, max_length=300)


@router.patch("/{wid}")
def patch_withdrawal(wid: int, body: WithdrawalPatchIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    w = _get(db, wid)
    for k in ("invoice_no", "tax_cert_no", "note"):
        v = getattr(body, k)
        if v is not None:
            setattr(w, k, v.strip())
    db.commit()
    return pay.withdrawal_out(w, admin=True, db=db)


@router.get("/tax-report")
def tax_report(year: int = Query(..., ge=2026, le=2100), month: int | None = Query(None, ge=1, le=12), _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = pay.tax_report(db, year, month)
    return {"items": rows, "total_amount": sum(r["amount"] for r in rows), "total_tax": sum(r["tax"] for r in rows)}


# ================================================================== lô chi


@batches.get("")
def list_batches(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(PartnerPayoutBatch).order_by(PartnerPayoutBatch.id.desc()).limit(50)).all()
    ready = db.scalar(select(func.count()).select_from(PartnerWithdrawal).where(PartnerWithdrawal.status == "approved", PartnerWithdrawal.batch_id.is_(None))) or 0
    return {"items": [pay.batch_out(db, b) for b in rows], "approved_unbatched": ready,
            "next_pay_date": pay.next_pay_date(partner_wallet.settings(db)).isoformat()}


class BatchIn(BaseModel):
    pay_date: date | None = None


@batches.post("", status_code=201)
def create_batch(body: BatchIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    return pay.batch_out(db, pay.create_batch(db, user, body.pay_date), items=True)


def _batch(db: Session, bid: int) -> PartnerPayoutBatch:
    b = db.get(PartnerPayoutBatch, bid)
    if not b:
        raise HTTPException(404, "Không tìm thấy lô chi.")
    return b


@batches.get("/{bid}")
def get_batch(bid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return pay.batch_out(db, _batch(db, bid), items=True)


@batches.get("/{bid}/export")
def export_batch(bid: int, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    b = _batch(db, bid)
    data = pay.export_csv(db, b, user)
    return Response(data, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{b.code}.csv"', "Cache-Control": "no-store"})


class PaidIn(BaseModel):
    bank_ref: str = Field("", max_length=100)


@batches.post("/{bid}/paid")
def mark_paid(bid: int, body: PaidIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    b = _batch(db, bid)
    for w in pay.mark_paid(db, b, user, body.bank_ref.strip()):
        enqueue(send_partner_withdrawal_update_task, w.id)
    return pay.batch_out(db, b, items=True)
