"""Webhook nhận thư Gmail từ Apps Script: POST /api/webhooks/gmail  (xem deploy/gmail-appscript/README.md)

Xác thực (khoá LEADSCAN_GMAIL_WEBHOOK_SECRET; trống = webhook tắt → 404):
  X-LeadScan-Timestamp: <giây Unix>           lệch quá 5 phút so với máy chủ → 401 (chống gửi lại gói cũ)
  X-LeadScan-Signature: <hex HMAC-SHA256(khoá, "<timestamp>." + body)>

Body JSON (1 thư / request):
  id, thread_id, from ("Tên <email>"), to, subject, date (ISO 8601), body (văn bản thuần),
  attachments [{name, type, size, data (base64, chỉ loại máy chủ đọc được), skipped ("too_large")}] — hoặc [tên tệp] (bản cũ)

Kết quả:
  201 {"ok": true, "id"}                    đã nhận, xếp hàng xử lý (lọc + AI + tạo phiếu nháp)
  200 {"ok": true, "duplicate": true, "id"}  thư đã nhận trước đó — Apps Script gửi lại an toàn
  401 sai chữ ký / quá hạn · 413 quá lớn · 422 thiếu trường · 429 sai chữ ký quá nhiều lần
"""

import hashlib
import hmac
import json
import time
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import new_session
from app.routes.public import fail
from app.security import add_hit, client_ip, rate_limited, sha256
from app.services import gmail_ingest
from app.worker import enqueue, gmail_process_task

router = APIRouter(prefix="/api/webhooks")

MAX_SKEW = 300  # giây


def signature(secret: str, ts: str, body: bytes) -> str:
    return hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()


def _verify(secret: str, ts: str, sig: str, body: bytes) -> bool:
    if not ts.isdigit() or abs(time.time() - int(ts)) > MAX_SKEW:
        return False
    return hmac.compare_digest(signature(secret, ts, body), sig.strip().lower())


def _gate(ip: str, ok: bool):
    """IP sai chữ ký quá 20 lần / 15 phút → 429 (kể cả khi lần này đúng)."""
    key = "gwh:" + sha256(ip)
    with new_session() as db:
        if rate_limited(db, key, 20, timedelta(minutes=15)):
            return fail(429, "Sai chữ ký quá nhiều lần. Vui lòng thử lại sau 15 phút.")
        if not ok:
            add_hit(db, key)
            db.commit()
            return fail(401, "Sai chữ ký hoặc thời gian gửi đã quá hạn.")
    return None


def _save(data: dict):
    d, errors = gmail_ingest.normalize_payload(data)
    if errors:
        return None, errors
    with new_session() as db:
        e, created = gmail_ingest.save_email(db, d)
        return (e.id, created), {}


@router.post("/gmail")
async def gmail_webhook(request: Request):
    cfg = get_settings()
    if not cfg.gmail_webhook_secret:
        return fail(404, "Webhook Gmail chưa được bật.")
    limit = cfg.gmail_webhook_max_kb * 1024
    if int(request.headers.get("content-length") or 0) > limit:
        return fail(413, "Thư gửi lên quá lớn.")
    body = await request.body()
    if len(body) > limit:
        return fail(413, "Thư gửi lên quá lớn.")
    ok = _verify(cfg.gmail_webhook_secret, request.headers.get("x-leadscan-timestamp", ""), request.headers.get("x-leadscan-signature", ""), body)
    denied = await run_in_threadpool(_gate, client_ip(request, cfg), ok)
    if denied:
        return denied
    try:
        data = json.loads(body or b"null")
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return fail(400, "Body phải là JSON object.")

    out, errors = await run_in_threadpool(_save, data)
    if errors:
        return fail(422, "Thiếu thông tin thư.", errors)
    email_id, created = out
    headers = {"Cache-Control": "no-store"}
    if not created:
        return JSONResponse({"ok": True, "duplicate": True, "id": email_id}, status_code=200, headers=headers)
    enqueue(gmail_process_task, email_id)  # Redis lỗi: lượt quét gmail-sweep (10 phút) sẽ xử lý
    return JSONResponse({"ok": True, "id": email_id}, status_code=201, headers=headers)
