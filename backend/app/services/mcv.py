"""Client cổng thanh toán MCV (https://api.mcv.network) — chỉ chạy trên server, không bao giờ gọi từ trình duyệt.

Ký mọi request:
    X-MCV-Key        API Key (mcvpk_test_… / mcvpk_live_…)
    X-MCV-Timestamp  unix giây (lệch > 5 phút bị từ chối)
    X-MCV-Signature  hex chữ thường của HMAC-SHA256(key=Secret, message=timestamp + "." + raw_body)

raw_body là ĐÚNG chuỗi byte gửi đi: ta tự json.dumps rồi ký và gửi nguyên chuỗi đó qua `content=`
(không dùng `json=` để httpx không encode lại). GET ký với raw_body rỗng (`timestamp + "."`).
Webhook MCV gửi về cũng ký theo cùng công thức, cùng Secret → dùng chung sign()/verify().
"""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings

MAX_SKEW_SECONDS = 300  # lệch giờ tối đa cho phép (cả request đi lẫn webhook về)

# Tests / máy dev không có mạng gắn httpx.MockTransport vào đây (xem app/mcv_fake.py)
TRANSPORT: httpx.BaseTransport | None = None


def sign(secret: str, timestamp: str | int, raw_body: bytes) -> str:
    msg = str(timestamp).encode() + b"." + raw_body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str, raw_body: bytes, signature: str) -> bool:
    if not secret or not timestamp or not signature:
        return False
    return hmac.compare_digest(sign(secret, timestamp, raw_body), signature.strip().lower())


def timestamp_fresh(timestamp: str, now: float | None = None) -> bool:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    return abs((now if now is not None else time.time()) - ts) <= MAX_SKEW_SECONDS


def dumps(payload: Any) -> bytes:
    """JSON gọn, giữ nguyên tiếng Việt — đúng chuỗi byte được ký và gửi đi."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def parse_dt(value: str | None) -> datetime | None:
    """ISO 8601 (MCV trả giờ VN, vd 2026-11-11T10:15:00+07:00) → UTC naive như cách DB lưu."""
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:  # không có múi giờ → coi là giờ VN
        from zoneinfo import ZoneInfo

        d = d.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    return d.astimezone(UTC).replace(tzinfo=None)


def is_test_key(api_key: str) -> bool:
    return api_key.startswith("mcvpk_test_")


class McvError(Exception):
    """Lỗi MCV dạng {"error": {"code", "message", "fields"?}}. status = mã HTTP (0 = không kết nối được)."""

    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        super().__init__(f"MCV {status} {code}: {message}")
        self.status, self.code, self.message, self.fields = status, code, message, fields or {}


class McvClient:
    def __init__(self, cfg: Settings, transport: httpx.BaseTransport | None = None):
        if not (cfg.mcv_api_key and cfg.mcv_secret):
            raise McvError(0, "not_configured", "Chưa cấu hình MCV_API_KEY / MCV_SECRET.")
        self.cfg = cfg
        self.transport = transport or TRANSPORT

    def signed_headers(self, raw_body: bytes, timestamp: int | None = None) -> dict[str, str]:
        ts = str(timestamp if timestamp is not None else int(time.time()))
        h = {
            "X-MCV-Key": self.cfg.mcv_api_key,
            "X-MCV-Timestamp": ts,
            "X-MCV-Signature": sign(self.cfg.mcv_secret, ts, raw_body),
            "Accept": "application/json",
        }
        return h

    def request(self, method: str, path: str, payload: dict | None = None, params: dict | None = None) -> tuple[int, dict]:
        """Gửi request đã ký. Trả (status, data) với data = phần "data" của response. Lỗi → McvError."""
        raw = dumps(payload) if payload is not None else b""
        headers = self.signed_headers(raw)
        if method != "GET":
            headers["Content-Type"] = "application/json"
        try:
            with httpx.Client(base_url=self.cfg.mcv_base_url.rstrip("/"), timeout=self.cfg.mcv_timeout_seconds, transport=self.transport) as c:
                r = c.request(method, path, content=raw if method != "GET" else None, headers=headers, params=params)
        except httpx.HTTPError as e:
            raise McvError(0, "network_error", f"Không kết nối được cổng thanh toán MCV ({type(e).__name__}).") from e
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400:
            err = body.get("error") if isinstance(body, dict) else None
            err = err if isinstance(err, dict) else {}
            raise McvError(r.status_code, str(err.get("code") or "http_error"), str(err.get("message") or f"MCV trả lỗi {r.status_code}."), err.get("fields"))
        data = body.get("data") if isinstance(body, dict) else None
        if data is None:
            raise McvError(r.status_code, "bad_response", "Phản hồi MCV không có trường data.")
        return r.status_code, data

    # ------------------------------------------------------------------ API

    def create_payment(self, **fields) -> tuple[int, dict]:
        """POST /v1/payments. 201 = tạo mới, 200 = trả lại thanh toán đã có cùng order_id."""
        payload = {k: v for k, v in fields.items() if v not in (None, "", {})}
        return self.request("POST", "/v1/payments", payload)

    def get_payment(self, payment_code: str) -> dict:
        return self.request("GET", f"/v1/payments/{payment_code}")[1]

    def list_payments(self, order_id: str) -> list[dict]:
        """Tối đa 20 thanh toán của 1 đơn, mới nhất trước."""
        return self.request("GET", "/v1/payments", params={"order_id": order_id})[1]

    def simulate_paid(self, payment_code: str) -> dict:
        """Chỉ khoá test: MCV đánh dấu đã trả và gửi webhook thật với test_mode: true."""
        return self.request("POST", f"/v1/payments/{payment_code}/simulate-paid", None)[1]
