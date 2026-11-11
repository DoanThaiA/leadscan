"""Webhook cổng thanh toán MCV: POST /api/mcv/webhook (MCV gọi khi khoản chuyển khớp đơn).

Headers: X-MCV-Event (payment.paid), X-MCV-Timestamp, X-MCV-Signature = HMAC-SHA256(Secret, timestamp + "." + raw_body).
Phải trả 2xx trong 10 giây, nếu không MCV gửi lại sau 1, 2, 5, 10, 30, 60, 120, 360, 720 phút.

  1. Đọc raw body (chưa parse), tính lại chữ ký, so bằng hmac.compare_digest — sai → 401.
  2. Timestamp lệch > 5 phút → từ chối (401, không xử lý). MCV gửi lại với timestamp mới nên không mất tín hiệu thật;
     request bị chụp lại (replay) thì không bao giờ qua được.
  3–4. apply_paid(): tìm đơn theo data.order_id, kiểm tra số tiền + test_mode, mỗi payment_code chỉ mở dịch vụ 1 lần.
  5. Trả 200 ngay; email/thông báo đẩy sang worker (mark_paid → enqueue).
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services import mcv, mcv_payments

log = logging.getLogger("leadscan.mcv")
router = APIRouter(prefix="/api/mcv")


@router.post("/webhook")
async def mcv_webhook(request: Request, db: Session = Depends(get_db)):
    cfg = get_settings()
    if not cfg.mcv_secret:
        raise HTTPException(503, "Chưa cấu hình MCV_SECRET.")
    raw = await request.body()
    ts = request.headers.get("x-mcv-timestamp", "")
    if not mcv.verify(cfg.mcv_secret, ts, raw, request.headers.get("x-mcv-signature", "")):
        log.warning("Webhook MCV sai chữ ký (ts=%s, %d byte)", ts, len(raw))
        raise HTTPException(401, "Sai chữ ký.")
    if not mcv.timestamp_fresh(ts):
        log.warning("Webhook MCV bị bỏ: timestamp %s lệch quá 5 phút", ts)
        raise HTTPException(401, "Timestamp quá hạn.")
    try:
        body = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Body không phải JSON.") from None
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise HTTPException(400, "Thiếu data.")

    event = request.headers.get("x-mcv-event") or body.get("event")
    if event != "payment.paid" or body.get("event", event) != event:
        return {"ok": True, "ignored": f"sự kiện {event}"}
    result = mcv_payments.apply_paid(db, cfg, body["data"], source="webhook", event_id=str(body.get("id") or ""))
    return {"ok": True, "result": result}
