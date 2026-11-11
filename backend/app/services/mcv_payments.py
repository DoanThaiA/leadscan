"""Thanh toán đơn nạp tiền qua cổng MCV.

Luồng:
  1. Thành viên tạo đơn (PaymentOrder, mã LSP…) → start_payment() gọi POST /v1/payments với order_id = mã đơn.
     MCV trả payment_code + qr_data (chuỗi VietQR tới tài khoản công ty trên InfoCMS) + hạn QR.
  2. Trang nạp tiền vẽ QR từ qr_data (hoặc chuyển khách sang checkout_url), đếm ngược tới expires_at.
     Trình duyệt hỏi backend LeadScan; backend tra MCV (refresh) tối đa mỗi 5 giây — không gọi MCV từ trình duyệt.
  3. Khách chuyển khoản → MCV gửi webhook payment.paid (đã ký) tới /api/mcv/webhook → apply_paid() mở dịch vụ.
     API tra trạng thái trả "paid" cũng đi qua apply_paid() — 2 tín hiệu duy nhất được phép mở dịch vụ.
  4. QR hết hạn: khách bấm "Tạo mã QR mới" (cùng order_id → MCV cấp payment_code mới). QR cũ vẫn có thể thành paid.

Chống trùng: mcv_payments.payment_code unique + khoá dòng; processed_at đặt đúng 1 lần cho mỗi payment_code.
"""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import Activity, McvPayment, MemberUser, PaymentOrder
from app.services import payments
from app.services.mcv import McvClient, McvError, is_test_key, parse_dt

log = logging.getLogger("leadscan.mcv")

POLL_SECONDS = 5  # khoảng cách tối thiểu giữa 2 lần backend tra trạng thái 1 payment_code với MCV
OPEN_STATUSES = ("pending", "expired", "failed")  # còn có thể chuyển thành paid → đáng tra lại


def configured(cfg: Settings) -> bool:
    return bool(cfg.mcv_api_key and cfg.mcv_secret)


def can_simulate(cfg: Settings) -> bool:
    """Giả lập đã trả chỉ có ở môi trường chạy thử: cho phép test_mode + đang dùng khoá test."""
    return cfg.mcv_allow_test_mode and is_test_key(cfg.mcv_api_key)


def latest(db: Session, order: PaymentOrder) -> McvPayment | None:
    return db.scalar(select(McvPayment).where(McvPayment.order_id == order.id).order_by(McvPayment.id.desc()).limit(1))


def _iso(d: datetime | None) -> str | None:
    return d.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z") if d else None


def _sync(mp: McvPayment, data: dict) -> None:
    """Chép trạng thái MCV vào dòng mcv_payments (không bao giờ hạ "paid" về trạng thái khác)."""
    status = str(data.get("status") or mp.status or "pending")
    if mp.status != "paid":
        mp.status = status
    if data.get("amount") is not None:
        mp.amount = int(data["amount"])
    if data.get("paid_amount") is not None:
        mp.paid_amount = int(data["paid_amount"])
    if data.get("paid_at"):
        mp.paid_at = parse_dt(data["paid_at"])
    if data.get("expires_at"):
        mp.expires_at = parse_dt(data["expires_at"])
    if "test_mode" in data:
        mp.test_mode = bool(data["test_mode"])
    if data.get("checkout_url"):
        mp.checkout_url = str(data["checkout_url"])[:500]
    if "qr_data" in data:
        mp.qr_data = data["qr_data"]
    if isinstance(data.get("bank"), dict):
        mp.bank = {k: data["bank"].get(k) for k in ("bank_name", "account_no", "account_name", "transfer_content")}


def _get_or_create(db: Session, data: dict, order: PaymentOrder | None) -> McvPayment:
    code = str(data["payment_code"])
    mp = db.scalar(select(McvPayment).where(McvPayment.payment_code == code))
    if mp:
        return mp
    mp = McvPayment(
        payment_code=code,
        order_id=order.id if order else None,
        mcv_order_id=str(data.get("order_id") or (order.code if order else "")),
        status="pending",
        amount=int(data.get("amount") or (order.amount if order else 0)),
        test_mode=bool(data.get("test_mode")),
        checkout_url="",
        result="",
        last_event_id="",
    )
    _sync(mp, data)
    db.add(mp)
    try:
        db.commit()
    except IntegrityError:  # webhook/poll khác vừa tạo cùng payment_code
        db.rollback()
        mp = db.scalar(select(McvPayment).where(McvPayment.payment_code == code))
    return mp


# ------------------------------------------------------------------ tạo / tra thanh toán


def start_payment(db: Session, cfg: Settings, order: PaymentOrder, client: McvClient | None = None) -> McvPayment:
    """Xin MCV mã QR cho đơn. Gọi lại khi QR cũ hết hạn → MCV cấp payment_code mới (cùng order_id). Lỗi → McvError."""
    client = client or McvClient(cfg)
    label = "Phí thành viên" if order.kind == "membership" else "Nạp điểm"
    user = db.get(MemberUser, order.created_by_id) if order.created_by_id else None
    fields = {
        "order_id": order.code,
        "amount": order.amount,
        "description": f"LeadScan — {label} — đơn {order.code}"[:255],
        "customer_name": (order.company.name if order.company else "")[:120],
        "customer_email": user.email if user else None,
        "expires_in_minutes": max(5, min(60, cfg.mcv_expires_minutes)),
        "metadata": {"company_id": order.company_id, "kind": order.kind, "points": order.points},
    }
    if cfg.mcv_return_url.startswith("https://"):  # MCV chỉ nhận https thuộc tên miền đã đăng ký
        fields["return_url"] = cfg.mcv_return_url
    _, data = client.create_payment(**fields)
    mp = _get_or_create(db, data, order)
    if mp.order_id is None:
        mp.order_id = order.id
    _sync(mp, data)
    mp.checked_at = utcnow()
    db.commit()
    if data.get("status") == "paid":  # đơn đã trả từ trước (vd webhook chưa tới)
        apply_paid(db, cfg, data, source="create")
    return mp


def refresh(db: Session, cfg: Settings, mp: McvPayment, *, force: bool = False, client: McvClient | None = None) -> McvPayment:
    """Tra trạng thái với MCV (tối đa 1 lần/5 giây cho mỗi payment_code). Lỗi mạng chỉ ghi log."""
    if mp.status not in OPEN_STATUSES and not (mp.status == "paid" and mp.processed_at is None):
        return mp
    if not force and mp.checked_at and (utcnow() - mp.checked_at).total_seconds() < POLL_SECONDS:
        return mp
    try:
        data = (client or McvClient(cfg)).get_payment(mp.payment_code)
    except McvError as e:
        log.warning("Tra trạng thái MCV %s lỗi: %s", mp.payment_code, e)
        mp.checked_at = utcnow()
        db.commit()
        return mp
    if str(data.get("order_id") or mp.mcv_order_id) != mp.mcv_order_id:
        log.error("MCV trả payment %s thuộc đơn %s, khác đơn đã lưu %s", mp.payment_code, data.get("order_id"), mp.mcv_order_id)
        return mp
    _sync(mp, data)
    mp.checked_at = utcnow()
    db.commit()
    if data.get("status") == "paid":
        apply_paid(db, cfg, data, source="status")
    db.refresh(mp)
    return mp


def lookup_for_order(db: Session, cfg: Settings, order: PaymentOrder, payment_code: str) -> McvPayment | None:
    """Trang kết quả (return_url): tra payment_code trên URL — chỉ nhận nếu MCV xác nhận nó thuộc đúng đơn này."""
    mp = db.scalar(select(McvPayment).where(McvPayment.payment_code == payment_code))
    if mp:
        return refresh(db, cfg, mp) if mp.order_id == order.id else None
    try:
        data = McvClient(cfg).get_payment(payment_code)
    except McvError as e:
        log.warning("Tra payment_code %s từ return_url lỗi: %s", payment_code, e)
        return None
    if str(data.get("order_id")) != order.code:
        return None
    mp = _get_or_create(db, data, order)
    mp.checked_at = utcnow()
    db.commit()
    if data.get("status") == "paid":
        apply_paid(db, cfg, data, source="status")
        db.refresh(mp)
    return mp


# ------------------------------------------------------------------ mở dịch vụ


def apply_paid(db: Session, cfg: Settings, data: dict, *, source: str, event_id: str = "") -> str:
    """Xử lý tín hiệu "đã thanh toán" (webhook đã xác thực chữ ký, hoặc API tra trạng thái).

    Trả về chuỗi kết quả (để log / trả về webhook). Gọi nhiều lần cùng payment_code chỉ cộng điểm 1 lần.
    """
    code, order_code = data.get("payment_code"), data.get("order_id")
    if not code or not order_code:
        return "ignored: thiếu payment_code/order_id"
    if data.get("status") != "paid":
        return f"ignored: trạng thái {data.get('status')}"
    if data.get("test_mode") and not cfg.mcv_allow_test_mode:
        log.warning("MCV %s (%s): bỏ qua thanh toán test_mode trên môi trường thật", code, source)
        return "ignored: test_mode"

    order = db.scalar(select(PaymentOrder).where(PaymentOrder.code == str(order_code)))
    if not order:
        log.error("MCV %s (%s): không có đơn %s", code, source, order_code)
        return "ignored: không có đơn"

    mp = _get_or_create(db, data, order)
    if mp.mcv_order_id != order.code:
        log.error("MCV %s (%s): payment_code đã gắn với đơn khác (%s ≠ %s)", code, source, mp.mcv_order_id, order.code)
        return "ignored: payment_code thuộc đơn khác"
    # Khoá dòng tới hết transaction: 2 webhook trùng (hoặc webhook + poll) chạy song song → chỉ 1 bên xử lý
    mp = db.scalar(select(McvPayment).where(McvPayment.id == mp.id).with_for_update(of=McvPayment).execution_options(populate_existing=True))
    if mp.processed_at:
        db.rollback()
        return "duplicate"

    _sync(mp, data)
    mp.order_id = order.id
    mp.processed_at = utcnow()
    if event_id:
        mp.last_event_id = event_id[:100]
    amount = int(data.get("amount") or 0)
    paid_amount = int(data.get("paid_amount") or amount)

    def hold(reason: str, note: str) -> str:
        """Không mở dịch vụ — ghi lại để quản trị đối soát (xác nhận tay / hoàn tiền)."""
        mp.result = reason[:300]
        order.note = note[:300]
        db.add(Activity(company_id=order.company_id, kind="update", content=f"MCV {code}: {note}"[:2000]))
        db.commit()
        log.error("MCV %s đơn %s (%s): %s", code, order.code, source, note)
        return f"ignored: {reason}"

    if amount != order.amount or paid_amount < order.amount:
        return hold("amount_mismatch", f"Số tiền MCV báo ({amount:,}đ, đã nhận {paid_amount:,}đ) không khớp đơn ({order.amount:,}đ) — chưa cộng điểm, cần đối soát.".replace(",", "."))
    if order.status == "paid":
        return hold("order_already_paid", f"Đơn đã thanh toán trước đó; nhận thêm {paid_amount:,}đ — cần đối soát/hoàn tiền.".replace(",", "."))

    if order.status in ("expired", "cancelled"):  # QR/đơn hết hạn nhưng khách vẫn chuyển: vẫn ghi nhận
        order.status = "pending"
    mp.result = "credited"
    try:
        payments.mark_paid(
            db, cfg, order, paid_amount, str(code),
            note=f"MCV {code}" + (" (test)" if data.get("test_mode") else ""),
            raw=str(data)[:4000],
        )
    except HTTPException as e:
        db.rollback()
        mp = db.get(McvPayment, mp.id)
        mp.processed_at, mp.result = utcnow(), f"error: {e.detail}"[:300]
        db.commit()
        log.error("MCV %s đơn %s: không ghi nhận được: %s", code, order.code, e.detail)
        return f"error: {e.detail}"
    log.info("MCV %s đơn %s (%s): đã cộng %s điểm", code, order.code, source, order.points)
    return "credited"


# ------------------------------------------------------------------ hiển thị


def payment_info(db: Session, cfg: Settings, order: PaymentOrder, mp: McvPayment | None, error: str = "") -> dict:
    """Dữ liệu cho trang thanh toán. Cùng khung với payments.payment_info() (InfoCMS/mock) + phần riêng của MCV."""
    bank = (mp.bank if mp else None) or {}
    return {
        "provider": "mcv",
        "configured": configured(cfg),
        "bank_name": bank.get("bank_name") or "",
        "account_no": bank.get("account_no") or "",
        "account_name": bank.get("account_name") or "",
        "amount": mp.amount if mp else order.amount,
        "transfer_content": bank.get("transfer_content") or "",
        "qr_payload": mp.qr_data if mp else None,
        "payment_code": mp.payment_code if mp else None,
        "mcv_status": mp.status if mp else None,
        "checkout_url": mp.checkout_url if mp else None,
        "expires_at": _iso(mp.expires_at) if mp else None,
        "test_mode": bool(mp and mp.test_mode),
        "can_simulate": bool(mp and mp.test_mode and can_simulate(cfg)),
        "error": error,
    }
