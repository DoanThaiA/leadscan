"""Webhook cổng thanh toán. InfoCMS gọi khi tài khoản thu nhận được tiền."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import PaymentOrder
from app.services import payments

log = logging.getLogger("leadscan.payments")
router = APIRouter(prefix="/api/payments")


@router.post("/infocms/webhook")
async def infocms_webhook(request: Request, db: Session = Depends(get_db)):
    cfg = get_settings()
    raw = await request.body()
    info = payments.parse_infocms_webhook(raw, dict(request.headers), cfg)  # sai chữ ký → 401
    if not info["success"]:
        return {"ok": True, "ignored": "giao dịch chưa thành công"}

    # Đã xử lý giao dịch này rồi → trả OK để InfoCMS không gửi lại
    if db.scalar(select(PaymentOrder.id).where(PaymentOrder.provider_txn_id == info["txn_id"])):
        return {"ok": True, "duplicate": True}
    if not info["code"]:
        log.warning("Webhook InfoCMS: không thấy mã đơn trong nội dung chuyển khoản (txn %s, %sđ)", info["txn_id"], info["amount"])
        return {"ok": True, "ignored": "không có mã đơn"}

    order = db.scalar(select(PaymentOrder).where(PaymentOrder.code == info["code"]))
    if not order:
        log.warning("Webhook InfoCMS: mã đơn %s không tồn tại (txn %s)", info["code"], info["txn_id"])
        return {"ok": True, "ignored": "không có đơn"}
    try:
        # Đơn hết hạn/huỷ nhưng khách vẫn chuyển tiền: vẫn ghi nhận để không mất tiền của khách
        if order.status in ("expired", "cancelled"):
            order.status = "pending"
        payments.mark_paid(db, cfg, order, info["amount"], info["txn_id"], raw=raw.decode("utf-8", "replace")[:4000])
    except HTTPException as e:
        db.rollback()
        log.error("Webhook InfoCMS: không ghi nhận được đơn %s: %s", order.code, e.detail)
        order = db.get(PaymentOrder, order.id)
        order.note = f"Webhook: {e.detail}"[:300]
        db.commit()
        return {"ok": True, "ignored": e.detail}
    return {"ok": True}
