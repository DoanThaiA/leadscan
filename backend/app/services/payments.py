"""Đơn nạp tiền / phí thành viên và thanh toán qua InfoCMS (Smart Collect, VietQR).

Luồng:
  1. Thành viên tạo đơn → mã đơn (vd LSP7K2QX9MA) đồng thời là NỘI DUNG CHUYỂN KHOẢN.
  2. Trang thanh toán hiện VietQR tới tài khoản thu InfoCMS cấp (đã điền sẵn số tiền + nội dung).
  3. InfoCMS đối soát giao dịch và gọi webhook /api/payments/infocms/webhook → mark_paid() cộng điểm.
  4. Dự phòng: admin xác nhận tay sau khi kiểm tra sao kê.

LƯU Ý: InfoCMS chưa công bố tài liệu API. parse_infocms_webhook() viết theo dạng webhook phổ biến
(HMAC-SHA256 trên body, JSON có mã giao dịch / số tiền / nội dung). Khi có tài liệu chính thức chỉ cần
chỉnh hàm đó (và cấu hình infocms_*), phần còn lại giữ nguyên.
"""

import hashlib
import hmac
import json
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import Activity, PaymentOrder, PromoCode
from app.services import tiers, wallet
from app.services.vietqr import build_payload

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_RE = re.compile(r"LSP[A-Z2-9]{8}")


def new_order_code() -> str:
    return "LSP" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def payment_info(order: PaymentOrder, cfg: Settings) -> dict:
    """Thông tin để trang thanh toán hiển thị (QR + số tài khoản)."""
    ready = bool(cfg.payment_bank_bin and cfg.payment_account_no) and order.amount > 0  # đơn 0đ (mã khuyến mãi) không cần QR
    return {
        "provider": order.provider,
        "configured": ready,
        "bank_name": cfg.payment_bank_name,
        "account_no": cfg.payment_account_no,
        "account_name": cfg.payment_account_name,
        "amount": order.amount,
        "transfer_content": order.code,
        "qr_payload": build_payload(cfg.payment_bank_bin, cfg.payment_account_no, order.amount, order.code) if ready else None,
    }


def expire_if_due(order: PaymentOrder) -> None:
    if order.status == "pending" and order.expires_at < utcnow():
        order.status = "expired"


def create_order(
    db: Session,
    cfg: Settings,
    company_id: int,
    member_id: int,
    kind: str,
    amount: int,
    points: int,
    *,
    promo: PromoCode | None = None,
    discount: int = 0,
) -> PaymentOrder:
    """amount = giá gốc; có mã khuyến mãi thì số tiền phải trả = amount - discount (không âm).
    Đơn còn 0đ dùng provider "free" — không qua cổng thanh toán, gọi activate_free() để kích hoạt luôn."""
    pay = max(0, amount - discount)
    for _ in range(5):
        code = new_order_code()
        if not db.scalar(select(PaymentOrder.id).where(PaymentOrder.code == code)):
            break
    order = PaymentOrder(
        code=code,
        company_id=company_id,
        created_by_id=member_id,
        kind=kind,
        amount=pay,
        points=points,
        provider=cfg.payment_provider if pay > 0 else "free",
        expires_at=utcnow() + timedelta(hours=cfg.order_expire_hours),
        promo_id=promo.id if promo else None,
        promo_code=promo.code if promo else "",
        original_amount=amount if promo else None,
        discount=amount - pay if promo else 0,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def activate_free(db: Session, cfg: Settings, order: PaymentOrder) -> bool:
    """Đơn 0đ nhờ mã khuyến mãi: không cần thanh toán — ghi nhận đã thanh toán 0đ và mở dịch vụ / cộng điểm ngay."""
    if order.amount > 0:
        raise HTTPException(400, "Đơn còn số tiền phải thanh toán.")
    note = f"Miễn phí nhờ mã khuyến mãi {order.promo_code}" if order.promo_code else "Đơn 0đ"
    return mark_paid(db, cfg, order, 0, None, note=note)


def mark_paid(
    db: Session,
    cfg: Settings,
    order: PaymentOrder,
    paid_amount: int,
    txn_id: str | None,
    *,
    admin_id: int | None = None,
    note: str = "",
    raw: str | None = None,
) -> bool:
    """Ghi nhận đã thanh toán + cộng điểm. Gọi lại nhiều lần vẫn chỉ cộng 1 lần. Trả về True nếu lần này mới cộng."""
    company = wallet.lock_company(db, order.company_id)
    order = db.scalar(select(PaymentOrder).where(PaymentOrder.id == order.id).with_for_update(of=PaymentOrder).execution_options(populate_existing=True))
    if order.status == "paid":
        return False
    if order.status == "cancelled":
        raise HTTPException(409, "Đơn đã bị huỷ.")
    if paid_amount < order.amount:
        raise HTTPException(400, f"Số tiền nhận được ({paid_amount:,}đ) nhỏ hơn số tiền đơn ({order.amount:,}đ).".replace(",", "."))

    order.status, order.paid_amount, order.paid_at = "paid", paid_amount, utcnow()
    order.provider_txn_id = txn_id
    order.confirmed_by_id = admin_id
    order.note = note[:300]
    order.raw_callback = raw

    label = "Phí thành viên" if order.kind == "membership" else "Nạp điểm"
    wallet.post(db, company, order.points, order.kind, f"{label} — đơn {order.code}", order_id=order.id, actor_id=admin_id)
    was_gold = tiers.tier_key(company, cfg) == "gold"
    company.topup_total = (company.topup_total or 0) + order.amount  # tổng nạp → hạng thành viên
    if not was_gold and tiers.tier_key(company, cfg) == "gold":
        db.add(Activity(company_id=company.id, kind="update", actor_id=admin_id,
                        content=f"Lên hạng Vàng (tổng nạp {company.topup_total:,}đ) — được mua độc quyền phiếu cơ hội".replace(",", ".")))

    if order.kind == "membership":
        now = utcnow()
        start = company.membership_expires_at if company.membership_expires_at and company.membership_expires_at > now else now
        company.membership_expires_at = start + timedelta(days=cfg.membership_days)
        if company.status != "active":
            db.add(Activity(company_id=company.id, kind="status", content="Đã thanh toán phí thành viên → Thành viên", actor_id=admin_id))
            company.status = "active"
    db.add(
        Activity(
            company_id=company.id,
            kind="update",
            actor_id=admin_id,
            content=f"Thanh toán {order.code}: {paid_amount:,}đ, cộng {order.points:,} điểm".replace(",", ".")
            + (f" (mã khuyến mãi {order.promo_code}, giảm {order.discount:,}đ)".replace(",", ".") if order.promo_code else "")
            + (" (xác nhận thủ công)" if admin_id else ""),
        )
    )
    db.commit()
    from app.worker import einvoice_for_order_task, enqueue, notify_payment_task  # import muộn: tránh vòng import

    enqueue(notify_payment_task, order.id)  # email cho thành viên + báo quản trị (chạy nền)
    if cfg.iam_enabled and cfg.iam_issue_on_payment and order.amount > 0:  # đơn 0đ không xuất hoá đơn
        enqueue(einvoice_for_order_task, order.id)  # tự xuất hoá đơn điện tử IAM
    return True


def parse_infocms_webhook(raw: bytes, headers: dict, cfg: Settings) -> dict:
    """Xác thực chữ ký và đọc {txn_id, amount, code} từ webhook InfoCMS. Lỗi → HTTPException."""
    if not cfg.infocms_webhook_secret:
        raise HTTPException(503, "Chưa cấu hình infocms_webhook_secret.")
    sig = headers.get(cfg.infocms_signature_header.lower(), "")
    expected = hmac.new(cfg.infocms_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not sig or not hmac.compare_digest(sig.strip().lower(), expected):
        raise HTTPException(401, "Sai chữ ký webhook.")
    try:
        data = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Body không phải JSON.") from None
    if isinstance(data.get("data"), dict):  # nhiều cổng bọc trong "data"
        data = data["data"]

    def pick(*keys):
        return next((data[k] for k in keys if data.get(k) not in (None, "")), None)

    txn_id = pick("transactionId", "transaction_id", "txnId", "referenceCode", "id")
    amount = pick("amount", "transferAmount", "creditAmount")
    content = str(pick("content", "description", "remark", "addInfo", "transferContent") or "")
    status = str(pick("status", "transactionStatus") or "success").lower()
    m = CODE_RE.search(content.upper().replace(" ", ""))
    if not txn_id or amount is None:
        raise HTTPException(400, "Thiếu mã giao dịch hoặc số tiền.")
    return {
        "txn_id": str(txn_id),
        "amount": int(float(amount)),
        "code": m.group(0) if m else None,
        "success": status in ("success", "succeeded", "completed", "paid", "00", "1", "true"),
    }
