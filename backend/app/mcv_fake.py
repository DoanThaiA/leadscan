"""Cổng MCV giả lập — để chạy thử luồng thanh toán khi chưa có khoá MCV (và dùng trong pytest).

Làm đúng như đặc tả MCV: kiểm chữ ký request, POST/GET /v1/payments, cùng order_id trả lại QR cũ / 409 khác tiền /
cấp payment_code mới khi QR hết hạn, simulate-paid gửi webhook đã ký về LeadScan. Khoá test → qr_data null.

Chạy dev (cửa sổ riêng):
    cd backend
    set MCV_API_KEY=mcvpk_test_local & set MCV_SECRET=mcvsk_local
    set MCV_FAKE_WEBHOOK_URL=http://localhost:8000/api/mcv/webhook
    uv run uvicorn app.mcv_fake:app --port 8099
rồi cho backend LeadScan dùng: MCV_BASE_URL=http://localhost:8099, cùng MCV_API_KEY/MCV_SECRET,
LEADSCAN_MCV_ALLOW_TEST_MODE=true. Đặt MCV_FAKE_QR=1 để giả lập có chuỗi QR (xem giao diện vẽ QR).
KHÔNG dùng trên production.
"""

import json
import os
import re
import secrets
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.services.mcv import dumps, sign, timestamp_fresh
from app.services.vietqr import build_payload

VN = ZoneInfo("Asia/Ho_Chi_Minh")
ORDER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def _err(status: int, code: str, message: str, **extra) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": message, **extra}})


class FakeMcv:
    def __init__(
        self,
        api_key: str,
        secret: str,
        *,
        on_webhook: Callable[[dict[str, str], bytes], None] | None = None,
        with_qr: bool = False,
        base_url: str = "http://localhost:8099",
    ):
        self.api_key, self.secret = api_key, secret
        self.on_webhook = on_webhook
        self.with_qr = with_qr
        self.base_url = base_url.rstrip("/")
        self.payments: dict[str, dict] = {}
        self.requests: list[httpx.Request] = []
        self.webhooks: list[tuple[dict[str, str], bytes]] = []

    @property
    def test_mode(self) -> bool:
        return self.api_key.startswith("mcvpk_test_")

    # ------------------------------------------------------------ helpers

    def _now(self) -> datetime:
        return datetime.now(VN).replace(microsecond=0)

    def _expired(self, p: dict) -> bool:
        return p["status"] == "pending" and datetime.fromisoformat(p["expires_at"]) <= self._now()

    def _view(self, p: dict) -> dict:
        if self._expired(p):
            p["status"] = "expired"
        return {k: v for k, v in p.items() if not k.startswith("_")}

    def expire(self, payment_code: str) -> None:
        """Cho QR hết hạn ngay (test)."""
        self.payments[payment_code]["expires_at"] = (self._now() - timedelta(seconds=1)).isoformat()

    def webhook_request(self, payment_code: str, *, timestamp: int | None = None) -> tuple[dict[str, str], bytes]:
        p = self._view(self.payments[payment_code])
        body = {"id": "evt_" + secrets.token_hex(8), "event": "payment.paid", "created_at": self._now().isoformat(), "data": p}
        raw = dumps(body)
        ts = str(timestamp if timestamp is not None else int(time.time()))
        headers = {"Content-Type": "application/json", "X-MCV-Event": "payment.paid", "X-MCV-Timestamp": ts, "X-MCV-Signature": sign(self.secret, ts, raw)}
        return headers, raw

    def mark_paid(self, payment_code: str, paid_amount: int | None = None, *, send_webhook: bool = True) -> dict:
        """Khách đã chuyển khoản (đủ tiền) → paid + gửi webhook. Chuyển thiếu → needs_attention, không webhook."""
        p = self.payments[payment_code]
        paid = p["amount"] if paid_amount is None else paid_amount
        p["paid_amount"] = paid
        p["paid_at"] = self._now().isoformat()
        p["status"] = "paid" if paid >= p["amount"] else "needs_attention"
        if p["status"] == "paid" and send_webhook:
            hook = self.webhook_request(payment_code)
            self.webhooks.append(hook)
            if self.on_webhook:
                self.on_webhook(*hook)
        return self._view(p)

    # ------------------------------------------------------------ httpx transport handler

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        raw = request.read()
        h = request.headers
        if h.get("x-mcv-key") != self.api_key:
            return _err(401, "unauthorized", "Sai API key.")
        ts = h.get("x-mcv-timestamp", "")
        if not timestamp_fresh(ts):
            return _err(401, "unauthorized", "Timestamp lệch quá 5 phút.")
        if not secrets.compare_digest(sign(self.secret, ts, raw), h.get("x-mcv-signature", "")):
            return _err(401, "unauthorized", "Sai chữ ký.")

        path, method = request.url.path.rstrip("/"), request.method
        if method == "POST" and path == "/v1/payments":
            if h.get("content-type", "").split(";")[0] != "application/json":
                return _err(422, "validation_error", "Content-Type phải là application/json.", fields={})
            return self._create(json.loads(raw or b"{}"))
        if method == "GET" and path == "/v1/payments":
            oid = request.url.params.get("order_id", "")
            rows = sorted((p for p in self.payments.values() if p["order_id"] == oid), key=lambda p: p["_seq"], reverse=True)[:20]
            return httpx.Response(200, json={"data": [self._view(p) for p in rows]})
        m = re.fullmatch(r"/v1/payments/([^/]+)(/simulate-paid)?", path)
        if m and m.group(1) in self.payments:
            code = m.group(1)
            if method == "GET" and not m.group(2):
                return httpx.Response(200, json={"data": self._view(self.payments[code])})
            if method == "POST" and m.group(2):
                if not self.test_mode:
                    return _err(403, "forbidden", "Không giả lập được bằng khoá thật.")
                return httpx.Response(200, json={"data": self.mark_paid(code)})
        return _err(404, "not_found", "Không tìm thấy.")

    def _create(self, b: dict) -> httpx.Response:
        fields = {}
        oid, amount = b.get("order_id"), b.get("amount")
        if not isinstance(oid, str) or not ORDER_RE.match(oid):
            fields["order_id"] = "order_id không hợp lệ."
        if not isinstance(amount, int) or not 1_000 <= amount <= 500_000_000:
            fields["amount"] = "Số tiền phải là số nguyên từ 1.000 đến 500.000.000."
        exp = b.get("expires_in_minutes", 15)
        if not isinstance(exp, int) or not 5 <= exp <= 60:
            fields["expires_in_minutes"] = "Từ 5 đến 60 phút."
        if len(str(b.get("description", ""))) > 255:
            fields["description"] = "Tối đa 255 ký tự."
        if len(str(b.get("customer_name", ""))) > 120:
            fields["customer_name"] = "Tối đa 120 ký tự."
        meta = b.get("metadata", {})
        if not isinstance(meta, dict) or len(meta) > 20 or any(not isinstance(v, (str, int, float)) for v in meta.values()):
            fields["metadata"] = "Tối đa 20 cặp chuỗi/số."
        if fields:
            return _err(422, "validation_error", "Dữ liệu không hợp lệ.", fields=fields)
        ret = b.get("return_url")
        if ret is not None and not str(ret).startswith("https://"):
            return _err(422, "invalid_return_url", "return_url phải là https thuộc tên miền đã đăng ký.")

        same = sorted((p for p in self.payments.values() if p["order_id"] == oid), key=lambda p: p["_seq"], reverse=True)
        for p in same:
            if p["status"] == "paid":
                return httpx.Response(200, json={"data": self._view(p)})
        if same and not self._expired(same[0]) and same[0]["status"] == "pending":
            if same[0]["amount"] != amount:
                return _err(409, "order_amount_mismatch", "Đơn đang có mã QR còn hạn với số tiền khác — dùng order_id mới.")
            return httpx.Response(200, json={"data": self._view(same[0])})

        code = "PAY" + secrets.token_hex(6).upper()
        now = self._now()
        transfer = "MCV" + code[3:]
        p = {
            "payment_code": code,
            "order_id": oid,
            "status": "pending",
            "amount": amount,
            "currency": "VND",
            "description": b.get("description", ""),
            "paid_amount": None,
            "paid_at": None,
            "expires_at": (now + timedelta(minutes=exp)).isoformat(),
            "created_at": now.isoformat(),
            "checkout_url": f"{self.base_url}/checkout/{code}",
            "qr_data": build_payload("970436", "0011009999999", amount, transfer) if (self.with_qr or not self.test_mode) else None,
            "bank": {"bank_name": "Vietcombank", "account_no": "0011009999999", "account_name": "CONG TY MCV (GIA LAP)", "transfer_content": transfer},
            "test_mode": self.test_mode,
            "metadata": meta,
            "_seq": len(self.payments),
            "_return_url": ret,
        }
        self.payments[code] = p
        return httpx.Response(201, json={"data": self._view(p)})


# ------------------------------------------------------------------ máy chủ dev (uvicorn app.mcv_fake:app)


def _make_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, RedirectResponse, Response

    hook_url = os.environ.get("MCV_FAKE_WEBHOOK_URL", "http://localhost:8000/api/mcv/webhook")

    def send(headers: dict[str, str], raw: bytes) -> None:
        def go():
            time.sleep(0.5)  # để request simulate-paid trả về trước
            try:
                r = httpx.post(hook_url, content=raw, headers=headers, timeout=10)
                print(f"[mcv-fake] webhook -> {hook_url}: {r.status_code} {r.text[:200]}")
            except httpx.HTTPError as e:
                print(f"[mcv-fake] webhook -> {hook_url} lỗi: {e}")

        threading.Thread(target=go, daemon=True).start()

    fake = FakeMcv(
        os.environ.get("MCV_API_KEY", "mcvpk_test_local"),
        os.environ.get("MCV_SECRET", "mcvsk_local"),
        on_webhook=send,
        with_qr=os.environ.get("MCV_FAKE_QR") == "1",
        base_url=os.environ.get("MCV_FAKE_BASE_URL", "http://localhost:8099"),
    )
    app = FastAPI(title="MCV giả lập", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.fake = fake

    @app.api_route("/v1/{rest:path}", methods=["GET", "POST"])
    async def api(request: Request, rest: str):
        req = httpx.Request(request.method, str(request.url), headers=request.headers.raw, content=await request.body())
        r = fake.handle(req)
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    @app.get("/checkout/{code}", response_class=HTMLResponse)
    def checkout(code: str):
        p = fake.payments.get(code)
        if not p:
            return HTMLResponse("Không tìm thấy", 404)
        v = fake._view(p)
        back = ""
        if v["status"] == "paid" and p["_return_url"]:
            back = f'<meta http-equiv="refresh" content="5;url={p["_return_url"]}?payment_code={code}&order_id={v["order_id"]}&status=paid">'
        return (
            f"<!doctype html><meta charset=utf-8>{back}<title>MCV giả lập</title>"
            f"<body style='font-family:sans-serif;max-width:480px;margin:40px auto'>"
            f"<h2>MCV giả lập — {code}</h2><p>Đơn {v['order_id']} · {v['amount']:,}đ · <b>{v['status']}</b></p>"
            f"<p>Nội dung CK: <code>{v['bank']['transfer_content']}</code> · hết hạn {v['expires_at']}</p>"
            + (
                f"<form method=post action='/checkout/{code}/simulate'><button>Giả lập: đã thanh toán</button></form>"
                f"<form method=post action='/checkout/{code}/expire'><button>Cho mã QR hết hạn (chỉ có ở bản giả lập)</button></form>"
                if v["status"] != "paid"
                else "<p>Đã thanh toán — quay về sau 5 giây.</p>"
            )
        )

    @app.post("/checkout/{code}/simulate")
    def checkout_simulate(code: str):
        if code in fake.payments and fake.test_mode:
            fake.mark_paid(code)
        return RedirectResponse(f"/checkout/{code}", 303)

    @app.post("/checkout/{code}/expire")
    def checkout_expire(code: str):
        if code in fake.payments:
            fake.expire(code)
        return RedirectResponse(f"/checkout/{code}", 303)

    return app


app = _make_app()
