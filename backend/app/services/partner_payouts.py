"""Rút tiền đối tác: hồ sơ thanh toán (mã hoá), lệnh rút, thuế TNCN, lô chi, file chi cho ngân hàng.

Quy tắc (brief mục 6.2–6.3, tham số chỉnh ở Cấu hình thưởng):
  - Rút từ `min_withdraw` (100.000đ) Khả dụng, tối đa `max_withdrawals_month` lệnh/tháng, mỗi lúc 1 lệnh đang mở.
  - Lần đầu cần hồ sơ: họ tên, số định danh, MST, tài khoản ngân hàng CHÍNH CHỦ — tên chủ tài khoản phải khớp tên hồ sơ
    (so sau khi bỏ dấu). Không thu ảnh CCCD. Số định danh / số tài khoản mã hoá khi lưu.
  - Thuế TNCN (đối tác cá nhân): lệnh từ `tax_threshold` (5.000.000đ) trở lên khấu trừ `tax_rate` (10%).
    Mỗi lúc chỉ 1 lệnh mở + giới hạn lệnh/tháng → hạn chế chia nhỏ để né ngưỡng. Kế toán cần xác nhận cách tính "lần chi trả".
  - Đối tác tổ chức: không khấu trừ; phải có số hoá đơn trước khi đưa vào lô chi.
  - Admin duyệt lệnh → lập lô theo ngày chi → xuất file CSV → chuyển khoản → đánh dấu đã chi.
"""

import csv
import hashlib
import io
import re
from datetime import date, timedelta

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.models import (
    WITHDRAWAL_OPEN,
    WITHDRAWAL_STATUSES,
    AdminUser,
    PartnerEvent,
    PartnerPayoutBatch,
    PartnerPayoutProfile,
    PartnerUser,
    PartnerWithdrawal,
)
from app.services import partner_wallet
from app.services.embedding import fold

# Ngân hàng phổ biến (mã BIN NAPAS). Ngân hàng khác: chọn "Khác" và ghi tên.
BANKS = {
    "970436": "Vietcombank", "970415": "VietinBank", "970418": "BIDV", "970405": "Agribank", "970422": "MB Bank",
    "970407": "Techcombank", "970416": "ACB", "970432": "VPBank", "970423": "TPBank", "970403": "Sacombank",
    "970437": "HDBank", "970441": "VIB", "970443": "SHB", "970431": "Eximbank", "970426": "MSB", "970448": "OCB",
    "970440": "SeABank", "970428": "Nam A Bank", "970454": "Bản Việt (BVBank)", "970449": "LPBank", "970409": "Bac A Bank",
    "970412": "PVcomBank", "970425": "ABBANK", "970433": "VietBank", "970452": "KienlongBank", "970400": "Saigonbank",
}


class FieldsError(Exception):
    """Lỗi theo từng ô của form — route trả {"detail", "fields"} như các form khác."""

    def __init__(self, message: str, fields: dict[str, str]):
        super().__init__(message)
        self.message, self.fields = message, fields


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _vnd(n: int) -> str:
    return f"{n:,}đ".replace(",", ".")


# ================================================================== mã hoá


def _fernet() -> Fernet:
    key = get_settings().partner_secret_key.strip()
    if not key:
        raise HTTPException(503, "Rút tiền chưa được mở (thiếu khoá mã hoá hồ sơ thanh toán). Vui lòng liên hệ LeadScan.")
    try:
        return Fernet(key.encode())
    except ValueError:
        raise HTTPException(503, "Khoá mã hoá hồ sơ thanh toán không hợp lệ.") from None


def encrypt(v: str) -> str:
    return _fernet().encrypt(v.encode()).decode() if v else ""


def decrypt(v: str) -> str:
    if not v:
        return ""
    try:
        return _fernet().decrypt(v.encode()).decode()
    except InvalidToken:
        raise HTTPException(500, "Không giải mã được hồ sơ thanh toán (sai khoá mã hoá?).") from None


def account_hash(bank_bin: str, account_no: str) -> str:
    return hashlib.sha256(f"{bank_bin}:{account_no}".encode()).hexdigest()


def names_match(a: str, b: str) -> bool:
    return fold(a).split() == fold(b).split()


# ================================================================== hồ sơ thanh toán


def save_profile(db: Session, p: PartnerUser, raw: dict) -> PartnerPayoutProfile:
    org = p.kind == "org"
    legal = re.sub(r"\s+", " ", str(raw.get("legal_name") or (p.org_name if org else "")).strip())[:200]
    id_number = re.sub(r"\D", "", str(raw.get("id_number") or ""))
    tax_code = re.sub(r"[^0-9\-]", "", str(raw.get("tax_code") or (p.org_tax_code if org else "")))[:20]
    bank_bin = str(raw.get("bank_bin") or "").strip()
    bank_name = BANKS.get(bank_bin) or re.sub(r"\s+", " ", str(raw.get("bank_name") or "")).strip()[:100]
    account = re.sub(r"\D", "", str(raw.get("account_no") or ""))
    holder = re.sub(r"\s+", " ", str(raw.get("account_holder") or "")).strip().upper()[:200]
    e: dict[str, str] = {}
    if len(legal) < 3:
        e["legal_name"] = "Vui lòng nhập họ tên đúng như trên CCCD." if not org else "Vui lòng nhập tên tổ chức."
    if not org and not re.fullmatch(r"\d{12}", id_number):
        e["id_number"] = "Số định danh cá nhân (CCCD) gồm 12 chữ số."
    if org and not re.fullmatch(r"\d{10}(-?\d{3})?", tax_code):
        e["tax_code"] = "Mã số thuế tổ chức gồm 10 hoặc 13 chữ số."
    if not org and tax_code and not re.fullmatch(r"\d{10}|\d{12}", tax_code):
        e["tax_code"] = "MST cá nhân gồm 10 chữ số (hoặc để trống — dùng số định danh)."
    if bank_bin and bank_bin not in BANKS:
        e["bank_bin"] = "Ngân hàng không hợp lệ."
    if not bank_name:
        e["bank_bin"] = "Vui lòng chọn ngân hàng."
    if not re.fullmatch(r"\d{6,20}", account):
        e["account_no"] = "Số tài khoản gồm 6–20 chữ số."
    if len(holder) < 3:
        e["account_holder"] = "Vui lòng nhập tên chủ tài khoản đúng như trên ngân hàng."
    elif legal and not names_match(holder, legal):
        e["account_holder"] = "Tên chủ tài khoản phải trùng tên hồ sơ — LeadScan chỉ chi về tài khoản chính chủ."
    if e:
        raise FieldsError("Vui lòng kiểm tra lại hồ sơ thanh toán.", e)

    prof = db.scalar(select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == p.id))
    is_new = prof is None
    prof = prof or PartnerPayoutProfile(partner_id=p.id)
    h = account_hash(bank_bin or bank_name, account)
    changed_acc = prof.account_hash != h
    prof.legal_name, prof.tax_code, prof.bank_bin, prof.bank_name = legal, tax_code, bank_bin, bank_name
    prof.account_holder, prof.name_match, prof.account_hash = holder, True, h
    prof.account_enc, prof.account_last4 = encrypt(account), account[-4:]
    if not org:
        prof.id_number_enc, prof.id_last4 = encrypt(id_number), id_number[-4:]
    db.add(prof)
    db.add(PartnerEvent(partner_id=p.id, kind="payout_profile",
                        content=f"{'Tạo' if is_new else 'Cập nhật'} hồ sơ thanh toán: {bank_name} ••••{account[-4:]}"))
    if changed_acc:
        others = shared_account_partners(db, h, p.id)
        if others:
            db.add(PartnerEvent(partner_id=p.id, kind="fraud_flag",
                                content=f"Cờ gian lận: tài khoản ngân hàng trùng với đối tác {', '.join(others)}"[:500]))
    db.commit()
    db.refresh(prof)
    return prof


def shared_account_partners(db: Session, h: str, partner_id: int) -> list[str]:
    return list(db.scalars(select(PartnerUser.code).join(PartnerPayoutProfile, PartnerPayoutProfile.partner_id == PartnerUser.id)
                           .where(PartnerPayoutProfile.account_hash == h, PartnerPayoutProfile.partner_id != partner_id)))


def profile_out(prof: PartnerPayoutProfile | None) -> dict | None:
    if not prof:
        return None
    return {
        "legal_name": prof.legal_name, "id_masked": f"••••••••{prof.id_last4}" if prof.id_last4 else "", "tax_code": prof.tax_code,
        "bank_bin": prof.bank_bin, "bank_name": prof.bank_name, "account_masked": f"••••{prof.account_last4}",
        "account_holder": prof.account_holder, "name_match": prof.name_match, "updated_at": _iso(prof.updated_at),
    }


def get_profile(db: Session, partner_id: int) -> PartnerPayoutProfile | None:
    return db.scalar(select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner_id))


# ================================================================== lệnh rút


def pay_days(st: dict) -> list[int]:
    return sorted(int(x) for x in str(st["payout_days"]).split(",") if x.strip())


def next_pay_date(st: dict, today: date | None = None) -> date:
    today = today or (utcnow() + timedelta(hours=7)).date()
    days = pay_days(st)
    for d in days:
        if d >= today.day:
            return today.replace(day=d)
    nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=days[0])
    return nxt


def tax_for(p: PartnerUser, amount: int, st: dict) -> int:
    if p.kind == "org" or amount < st["tax_threshold"]:
        return 0
    return amount * st["tax_rate"] // 100


def rules(db: Session, p: PartnerUser) -> dict:
    """Điều kiện rút hiện tại cho cổng đối tác (kèm lý do chưa rút được)."""
    st = partner_wallet.settings(db)
    w = partner_wallet.balances(db, p.id)
    prof = get_profile(db, p.id)
    month = month_count(db, p.id)
    open_w = db.scalar(select(PartnerWithdrawal.code).where(PartnerWithdrawal.partner_id == p.id, PartnerWithdrawal.status.in_(WITHDRAWAL_OPEN)))
    reason = ""
    if not get_settings().partner_secret_key.strip():
        reason = "Rút tiền chưa được mở. Vui lòng liên hệ LeadScan."
    elif not prof:
        reason = "Cần hồ sơ thanh toán trước khi rút lần đầu."
    elif open_w:
        reason = f"Bạn đang có lệnh rút {open_w} chờ xử lý."
    elif month >= st["max_withdrawals_month"]:
        reason = f"Đã đạt {st['max_withdrawals_month']} lệnh rút trong tháng."
    elif w["available"] < st["min_withdraw"]:
        reason = f"Cần tối thiểu {_vnd(st['min_withdraw'])} Khả dụng để rút."
    return {
        "min": st["min_withdraw"], "max": max(0, w["available"]), "tax_threshold": st["tax_threshold"], "tax_rate": st["tax_rate"],
        "withholds_tax": p.kind != "org", "needs_invoice": p.kind == "org", "next_pay_date": next_pay_date(st).isoformat(),
        "pay_days": pay_days(st), "month_count": month, "month_max": st["max_withdrawals_month"], "can_request": not reason, "reason": reason,
    }


def month_count(db: Session, partner_id: int) -> int:
    return db.scalar(select(func.count()).select_from(PartnerWithdrawal).where(
        PartnerWithdrawal.partner_id == partner_id, PartnerWithdrawal.status.not_in(("cancelled", "rejected")),
        PartnerWithdrawal.created_at >= partner_wallet.month_start_utc())) or 0


def _next_code(db: Session, prefix: str, model, width: int = 6) -> str:
    n = (db.scalar(select(func.max(model.id))) or 0) + 1
    while db.scalar(select(model.id).where(model.code == f"{prefix}-{n:0{width}d}")):
        n += 1
    return f"{prefix}-{n:0{width}d}"


def request(db: Session, p: PartnerUser, amount: int) -> PartnerWithdrawal:
    # Khoá dòng đối tác: 2 lệnh rút gửi cùng lúc không vượt số dư
    p = db.scalar(select(PartnerUser).where(PartnerUser.id == p.id).with_for_update(of=PartnerUser).execution_options(populate_existing=True))
    r = rules(db, p)
    if not r["can_request"]:
        raise HTTPException(409, r["reason"])
    if amount < r["min"]:
        raise HTTPException(422, f"Số tiền rút tối thiểu {_vnd(r['min'])}.")
    if amount > r["max"]:
        raise HTTPException(422, f"Vượt số dư Khả dụng ({_vnd(r['max'])}).")
    st = partner_wallet.settings(db)
    prof = get_profile(db, p.id)
    tax = tax_for(p, amount, st)
    w = PartnerWithdrawal(
        code=_next_code(db, "RT", PartnerWithdrawal), partner_id=p.id, status="requested", amount=amount, tax_withheld=tax,
        net_amount=amount - tax,
        payee={"legal_name": prof.legal_name, "bank_bin": prof.bank_bin, "bank_name": prof.bank_name, "account_enc": prof.account_enc,
               "account_last4": prof.account_last4, "holder": prof.account_holder, "kind": p.kind, "tax_code": prof.tax_code,
               "account_hash": prof.account_hash},
    )
    db.add(w)
    db.flush()
    db.add(PartnerEvent(partner_id=p.id, kind="withdraw", content=f"Tạo lệnh rút {w.code}: {_vnd(amount)}" + (f" (khấu trừ thuế {_vnd(tax)})" if tax else "")))
    db.commit()
    db.refresh(w)
    return w


def cancel(db: Session, p: PartnerUser, w: PartnerWithdrawal) -> None:
    if w.partner_id != p.id:
        raise HTTPException(404, "Không tìm thấy lệnh rút.")
    if w.status != "requested":
        raise HTTPException(409, "Chỉ huỷ được lệnh đang chờ duyệt.")
    w.status = "cancelled"
    db.add(PartnerEvent(partner_id=p.id, kind="withdraw", content=f"Đối tác huỷ lệnh rút {w.code}"))
    db.commit()


def approve(db: Session, w: PartnerWithdrawal, actor: AdminUser) -> None:
    if w.status != "requested":
        raise HTTPException(409, "Lệnh rút không ở trạng thái chờ duyệt.")
    w.status, w.approved_at, w.approved_by_id = "approved", utcnow(), actor.id
    db.add(PartnerEvent(partner_id=w.partner_id, kind="withdraw", actor_id=actor.id, content=f"Duyệt lệnh rút {w.code} — chờ chi theo lô"))
    db.commit()


def reject(db: Session, w: PartnerWithdrawal, actor: AdminUser, reason: str) -> None:
    if w.status not in WITHDRAWAL_OPEN:
        raise HTTPException(409, "Lệnh rút đã kết thúc.")
    if w.batch and w.batch.status != "draft":
        raise HTTPException(409, f"Lệnh đã nằm trong lô {w.batch.code} đã xuất file — đánh dấu lại lô trước.")
    w.status, w.reject_reason, w.decided_by_id, w.batch_id = "rejected", reason[:300], actor.id, None
    db.add(PartnerEvent(partner_id=w.partner_id, kind="withdraw", actor_id=actor.id, content=f"Từ chối lệnh rút {w.code}: {reason}"[:500]))
    db.commit()


def withdrawal_out(w: PartnerWithdrawal, admin: bool = False, db: Session | None = None) -> dict:
    out = {
        "id": w.id, "code": w.code, "status": w.status, "status_label": WITHDRAWAL_STATUSES.get(w.status, w.status),
        "amount": w.amount, "tax_withheld": w.tax_withheld, "net_amount": w.net_amount,
        "bank_name": w.payee.get("bank_name", ""), "account_masked": f"••••{w.payee.get('account_last4', '')}", "holder": w.payee.get("holder", ""),
        "invoice_no": w.invoice_no, "tax_cert_no": w.tax_cert_no, "reject_reason": w.reject_reason,
        "batch": {"code": w.batch.code, "pay_date": w.batch.pay_date.isoformat()} if w.batch else None,
        "created_at": _iso(w.created_at), "approved_at": _iso(w.approved_at), "paid_at": _iso(w.paid_at),
    }
    if admin:
        p = w.partner
        prof = get_profile(db, p.id) if db else None
        out.update(
            partner={"id": p.id, "code": p.code, "full_name": p.full_name, "kind": p.kind, "status": p.status},
            legal_name=w.payee.get("legal_name", ""), tax_code=w.payee.get("tax_code", ""), bank_ref=w.bank_ref, note=w.note,
            name_match=names_match(w.payee.get("holder", ""), w.payee.get("legal_name", "")),
            shared_with=shared_account_partners(db, w.payee.get("account_hash", ""), p.id) if db else [],
            profile_changed=bool(prof and prof.account_hash != w.payee.get("account_hash")),
            needs_invoice=p.kind == "org" and not w.invoice_no,
        )
    return out


# ================================================================== lô chi


def create_batch(db: Session, actor: AdminUser, pay_date: date | None = None) -> PartnerPayoutBatch:
    st = partner_wallet.settings(db)
    pay_date = pay_date or next_pay_date(st)
    rows = db.scalars(select(PartnerWithdrawal).where(PartnerWithdrawal.status == "approved", PartnerWithdrawal.batch_id.is_(None))
                      .order_by(PartnerWithdrawal.id)).unique().all()
    ready = [w for w in rows if not (w.payee.get("kind") == "org" and not w.invoice_no)]  # tổ chức: cần hoá đơn trước khi chi
    if not ready:
        raise HTTPException(409, "Không có lệnh rút đã duyệt nào sẵn sàng chi (tổ chức cần số hoá đơn).")
    base = f"LO-{pay_date:%Y%m%d}"
    code, n = base, 2
    while db.scalar(select(PartnerPayoutBatch.id).where(PartnerPayoutBatch.code == code)):
        code, n = f"{base}-{n}", n + 1
    b = PartnerPayoutBatch(code=code, pay_date=pay_date, created_by_id=actor.id)
    db.add(b)
    db.flush()
    for w in ready:
        w.batch_id = b.id
    db.commit()
    db.refresh(b)
    return b


def batch_items(db: Session, b: PartnerPayoutBatch) -> list[PartnerWithdrawal]:
    return list(db.scalars(select(PartnerWithdrawal).where(PartnerWithdrawal.batch_id == b.id).order_by(PartnerWithdrawal.id)).unique())


def batch_out(db: Session, b: PartnerPayoutBatch, items: bool = False) -> dict:
    from app.models import BATCH_STATUSES

    rows = batch_items(db, b)
    out = {
        "id": b.id, "code": b.code, "pay_date": b.pay_date.isoformat(), "status": b.status, "status_label": BATCH_STATUSES.get(b.status, b.status),
        "count": len(rows), "gross": sum(w.amount for w in rows), "tax": sum(w.tax_withheld for w in rows), "net": sum(w.net_amount for w in rows),
        "exported_at": _iso(b.exported_at), "paid_at": _iso(b.paid_at), "created_at": _iso(b.created_at), "note": b.note,
    }
    if items:
        out["items"] = [withdrawal_out(w, admin=True, db=db) for w in rows]
    return out


def export_csv(db: Session, b: PartnerPayoutBatch, actor: AdminUser) -> bytes:
    """File chi cho ngân hàng (CSV UTF-8 có BOM, mở được bằng Excel). Chứa số tài khoản ĐẦY ĐỦ — chỉ quản trị viên, có ghi nhật ký.
    Mỗi ngân hàng có mẫu chi lương/chi hộ riêng: cột ở đây là cột chung, kế toán dán sang mẫu của ngân hàng nếu cần."""
    if b.status == "paid":
        raise HTTPException(409, "Lô đã chi.")
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["STT", "Mã lệnh", "Mã đối tác", "Tên người nhận", "Số tài khoản", "Ngân hàng", "Mã BIN", "Số tiền chi (đ)", "Thuế TNCN đã khấu trừ (đ)", "Nội dung"])
    for i, w in enumerate(batch_items(db, b), 1):
        wr.writerow([i, w.code, w.partner.code, w.payee.get("holder", ""), decrypt(w.payee.get("account_enc", "")), w.payee.get("bank_name", ""),
                     w.payee.get("bank_bin", ""), w.net_amount, w.tax_withheld, f"LeadScan chi hoa hong {w.code}"])
    if b.status == "draft":
        b.status, b.exported_at = "exported", utcnow()
    for w in batch_items(db, b):
        db.add(PartnerEvent(partner_id=w.partner_id, kind="withdraw", actor_id=actor.id, content=f"Xuất file chi lô {b.code} (lệnh {w.code})"))
    db.commit()
    return ("﻿" + buf.getvalue()).encode("utf-8")


def mark_paid(db: Session, b: PartnerPayoutBatch, actor: AdminUser, bank_ref: str = "") -> list[PartnerWithdrawal]:
    if b.status == "paid":
        raise HTTPException(409, "Lô đã được đánh dấu đã chi.")
    if b.status != "exported":
        raise HTTPException(409, "Xuất file chi trước khi đánh dấu đã chi.")
    now = utcnow()
    rows = batch_items(db, b)
    for w in rows:
        if w.status != "approved":
            continue
        w.status, w.paid_at, w.bank_ref = "paid", now, bank_ref[:100]
        db.add(PartnerEvent(partner_id=w.partner_id, kind="withdraw", actor_id=actor.id, content=f"Đã chi lệnh rút {w.code}: {_vnd(w.net_amount)} (lô {b.code})"))
    b.status, b.paid_at, b.paid_by_id = "paid", now, actor.id
    db.commit()
    return rows


def tax_report(db: Session, year: int, month: int | None = None) -> list[dict]:
    """Thuế TNCN đã khấu trừ theo kỳ (theo ngày chi) — cho kế toán kê khai và phát hành chứng từ."""
    from datetime import datetime

    start = datetime(year, month or 1, 1)
    end = datetime(year + (1 if not month or month == 12 else 0), (month % 12 + 1) if month else 1, 1)
    rows = db.scalars(select(PartnerWithdrawal).where(PartnerWithdrawal.status == "paid", PartnerWithdrawal.paid_at >= start - timedelta(hours=7),
                                                    PartnerWithdrawal.paid_at < end - timedelta(hours=7)).order_by(PartnerWithdrawal.paid_at)).unique().all()
    return [{"code": w.code, "partner": w.partner.code, "legal_name": w.payee.get("legal_name", ""), "tax_code": w.payee.get("tax_code", ""),
             "amount": w.amount, "tax": w.tax_withheld, "net": w.net_amount, "paid_at": _iso(w.paid_at), "tax_cert_no": w.tax_cert_no} for w in rows]
