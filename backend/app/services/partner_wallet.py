"""Ví hoa hồng đối tác: ly cafe, hoa hồng lượt bán, thu hồi, giải phóng sau thời gian giữ, số dư.

Quy tắc (brief mục 5):
  - Ly cafe: cơ hội Đạt xác minh (trong hạn mức ly cafe/tháng theo hạng) → Chờ duyệt; phiếu xuất bản → Khả dụng.
    Vượt hạn mức: không có ly cafe trả trước, vẫn chia doanh thu khi bán. Đóng góp bổ sung: 1 ly cafe, Khả dụng ngay.
  - Hoa hồng mỗi lượt bán trong N tháng kể từ ngày xuất bản:
      PA2 (mode "max", mặc định): ghi thêm = max(0; tỷ lệ × doanh thu thuần lũy kế − tổng đã ghi cho cơ hội, KỂ CẢ ly cafe)
      PA1 (mode "sum"):           ghi thêm = max(0; tỷ lệ × doanh thu thuần lũy kế − tổng hoa hồng đã ghi)  (ly cafe cộng riêng)
    Hoa hồng ở Chờ duyệt N ngày rồi sang Khả dụng.
  - Doanh thu thuần = điểm thành viên thực trả cho phiếu (trừ phần đã hoàn), CHƯA gồm thuế GTGT (tách theo LEADSCAN_IAM_VAT_RATE).
  - Mỗi lượt bán được tính đều có 1 dòng hoa hồng (kể cả 0đ khi chưa vượt ly cafe) — dòng đó đánh dấu lượt bán "được tính"
    để lũy kế doanh thu. Lượt bán bị loại (tài khoản liên quan, hết hạn chia sẻ) không có dòng nào, chỉ có nhật ký.
  - Hoàn phiếu: tính lại lũy kế không có lượt đó → thu hồi phần đã ghi vượt (không thu hồi ly cafe bảo đảm).
  - Gian lận: huỷ khoản Chờ duyệt + thu hồi khoản Khả dụng của cơ hội, khoá tài khoản.

Tham số chỉnh trên trang quản trị (bảng partner_settings), mặc định ở SETTINGS.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.models import (
    AdminUser,
    Contact,
    MemberUser,
    Opportunity,
    PartnerCredit,
    PartnerEvent,
    PartnerSetting,
    PartnerSettingLog,
    PartnerSubmission,
    PartnerUser,
    PartnerWithdrawal,
    Purchase,
)
from app.models import WITHDRAWAL_OPEN

log = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# key: (kiểu, mặc định, nhãn, min, max)
SETTINGS: dict[str, tuple] = {
    "cafe_amount": (int, 30_000, "Giá trị 1 ly cafe (đ)", 0, 1_000_000),
    "reward_mode": (str, "max", "Cách cộng ly cafe & hoa hồng", ("max", "sum"), None),
    "rate_new": (int, 20, "Hoa hồng phiếu thường — hạng Mới (%)", 0, 50),
    "rate_silver": (int, 25, "Hoa hồng phiếu thường — hạng Bạc (%)", 0, 50),
    "rate_strategic": (int, 25, "Hoa hồng mặc định — hạng Chiến lược (%)", 0, 50),
    "rate_max": (int, 30, "Trần hoa hồng thoả thuận riêng (%)", 0, 50),
    "rate_large": (int, 10, "Hoa hồng cơ hội lớn (%)", 0, 50),
    "cafe_quota_new": (int, 10, "Hạn mức ly cafe/tháng — hạng Mới", 0, 10_000),
    "cafe_quota_silver": (int, 30, "Hạn mức ly cafe/tháng — hạng Bạc", 0, 10_000),
    "cafe_quota_strategic": (int, 100, "Hạn mức ly cafe/tháng — hạng Chiến lược (mặc định)", 0, 10_000),
    "hold_days": (int, 7, "Số ngày giữ hoa hồng trước khi Khả dụng", 0, 90),
    "share_months": (int, 12, "Thời hạn chia sẻ doanh thu (tháng từ ngày xuất bản)", 1, 60),
    # Rút tiền (Mốc 4)
    "min_withdraw": (int, 100_000, "Số tiền rút tối thiểu (đ)", 10_000, 100_000_000),
    "max_withdrawals_month": (int, 2, "Số lệnh rút tối đa mỗi tháng", 1, 31),
    "payout_days": (str, "5,20", "Ngày chi trong tháng (cách nhau dấu phẩy)", None, None),
    "tax_threshold": (int, 5_000_000, "Ngưỡng khấu trừ thuế TNCN mỗi lần chi (đ) — cá nhân", 0, 1_000_000_000),
    "tax_rate": (int, 10, "Thuế TNCN khấu trừ (%)", 0, 50),
}


def _valid_days(v: str) -> bool:
    try:
        days = [int(x) for x in v.split(",") if x.strip()]
    except ValueError:
        return False
    return bool(days) and all(1 <= d <= 28 for d in days) and len(days) == len(set(days))
MODES = {"max": "Lấy mức cao hơn (PA2 — ít nhất 1 ly cafe)", "sum": "Cộng dồn (PA1 — 1 ly cafe + hoa hồng)"}


# ================================================================== cấu hình


def settings(db: Session) -> dict:
    out = {k: v[1] for k, v in SETTINGS.items()}
    for row in db.scalars(select(PartnerSetting)):
        spec = SETTINGS.get(row.key)
        if spec:
            try:
                out[row.key] = spec[0](row.value)
            except ValueError:
                log.warning("Cấu hình đối tác %s không hợp lệ: %r", row.key, row.value)
    return out


def update_settings(db: Session, changes: dict, actor: AdminUser, reason: str) -> dict:
    cur = settings(db)
    for k, v in changes.items():
        spec = SETTINGS.get(k)
        if not spec:
            raise HTTPException(422, f"Tham số không hợp lệ: {k}")
        typ, _, label, lo, hi = spec
        if typ is int:
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise HTTPException(422, f"{label}: phải là số nguyên.") from None
            if v < lo or v > hi:
                raise HTTPException(422, f"{label}: từ {lo} đến {hi}.")
        elif lo is None:  # chuỗi tự do — hiện chỉ có ngày chi
            if not _valid_days(str(v)):
                raise HTTPException(422, f"{label}: các ngày 1–28, cách nhau dấu phẩy (vd 5,20).")
            v = ",".join(str(d) for d in sorted(int(x) for x in str(v).split(",") if x.strip()))
        elif v not in lo:
            raise HTTPException(422, f"{label}: giá trị không hợp lệ.")
        if v == cur[k]:
            continue
        row = db.get(PartnerSetting, k) or PartnerSetting(key=k)
        row.value, row.updated_by_id = str(v), actor.id
        db.add(row)
        db.add(PartnerSettingLog(key=k, old_value=str(cur[k]), new_value=str(v), reason=reason[:300], actor_id=actor.id))
    db.commit()
    return settings(db)


def rate_for(p: PartnerUser, s: PartnerSubmission, st: dict) -> int:
    if s.is_large:
        return st["rate_large"]
    if p.custom_rate is not None:
        return min(p.custom_rate, st["rate_max"])
    return st.get(f"rate_{p.tier}", st["rate_new"])


def quota_for(p: PartnerUser, st: dict) -> int:
    if p.custom_cafe_quota is not None:
        return p.custom_cafe_quota
    return st.get(f"cafe_quota_{p.tier}", st["cafe_quota_new"])


def month_start_utc(now: datetime | None = None) -> datetime:
    """Đầu tháng theo giờ Việt Nam, đổi về UTC (naive) như các cột DateTime khác."""
    local = (now or utcnow()).replace(tzinfo=ZoneInfo("UTC")).astimezone(VN_TZ)
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def add_months(dt: datetime, months: int) -> datetime:
    y, m = divmod(dt.month - 1 + months, 12)
    year, month = dt.year + y, m + 1
    for day in (dt.day, 30, 29, 28):
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    return dt


def share_until(s: PartnerSubmission, st: dict) -> datetime | None:
    return add_months(s.published_at, st["share_months"]) if s.published_at else None


def cafe_used(db: Session, partner_id: int, since: datetime | None = None) -> int:
    return db.scalar(
        select(func.count()).select_from(PartnerCredit).where(
            PartnerCredit.partner_id == partner_id, PartnerCredit.kind.in_(("cafe", "supplement")),
            PartnerCredit.amount > 0, PartnerCredit.state != "void", PartnerCredit.created_at >= (since or month_start_utc()),
        )
    ) or 0


# ================================================================== tiện ích


def _event(db: Session, s: PartnerSubmission, kind: str, content: str, actor_id: int | None = None) -> None:
    db.add(PartnerEvent(partner_id=s.partner_id, submission_id=s.id, kind=kind, content=content[:500], actor_id=actor_id))


def _vnd(n: int) -> str:
    return f"{n:,}đ".replace(",", ".")


def net_of(amount: int) -> int:
    """Tiền trước thuế GTGT của số tiền thành viên đã trả (điểm đã gồm thuế)."""
    from app.services.einvoice import NO_TAX_RATES, split_vat

    rate = get_settings().iam_vat_rate.strip()
    return split_vat(max(0, amount), rate.upper() if rate.upper() in NO_TAX_RATES else rate)[0]


def _credits(db: Session, s: PartnerSubmission) -> list[PartnerCredit]:
    return list(db.scalars(select(PartnerCredit).where(PartnerCredit.submission_id == s.id, PartnerCredit.state != "void")).unique())


def _lock(db: Session, sub_id: int) -> PartnerSubmission:
    """Khoá dòng cơ hội đối tác (PostgreSQL: FOR UPDATE) — 2 lượt mua cùng lúc không ghi hoa hồng trùng."""
    return db.scalar(select(PartnerSubmission).where(PartnerSubmission.id == sub_id).with_for_update(of=PartnerSubmission).execution_options(populate_existing=True))


# ================================================================== ly cafe


def grant_cafe(db: Session, s: PartnerSubmission, actor_id: int | None, kind: str = "cafe") -> PartnerCredit | None:
    """Ghi ly cafe khi Đạt xác minh (Chờ duyệt tới khi phiếu xuất bản) hoặc Đóng góp bổ sung (Khả dụng ngay)."""
    if any(c.kind in ("cafe", "supplement") and c.amount > 0 for c in _credits(db, s)):
        return None
    st = settings(db)
    p = s.partner
    quota = quota_for(p, st)
    if cafe_used(db, p.id) >= quota:
        _event(db, s, "cafe_quota", f"Vượt hạn mức {quota} ly cafe/tháng — không ghi ly cafe trả trước (vẫn chia doanh thu khi bán)", actor_id)
        return None
    if st["cafe_amount"] <= 0:
        return None
    now = utcnow()
    c = PartnerCredit(partner_id=p.id, submission_id=s.id, kind=kind, amount=st["cafe_amount"], actor_id=actor_id, created_at=now)
    if kind == "supplement":
        c.state, c.available_at, c.released_at = "available", now, now
        c.note = f"Đóng góp bổ sung {s.code}"
    else:
        c.state, c.note = "pending", f"Ly cafe — {s.code} đạt xác minh (khả dụng khi phiếu xuất bản)"
    db.add(c)
    _event(db, s, "credit", f"+{_vnd(c.amount)} {'đóng góp bổ sung' if kind == 'supplement' else 'ly cafe (Chờ duyệt)'}", actor_id)
    return c


def revoke_cafe(db: Session, s: PartnerSubmission, actor_id: int | None, reason: str) -> None:
    """Quyết định Đạt / Đóng góp bổ sung bị đổi (trước khi có phiếu): huỷ ly cafe."""
    for c in _credits(db, s):
        if c.kind not in ("cafe", "supplement") or c.amount <= 0:
            continue
        if c.state == "pending":
            c.state, c.voided_at = "void", utcnow()
            c.note = (c.note + f" — huỷ: {reason}")[:300]
        else:
            db.add(PartnerCredit(partner_id=s.partner_id, submission_id=s.id, kind="adjust", amount=-c.amount, state="available",
                                 available_at=utcnow(), released_at=utcnow(), note=f"Huỷ {c.note[:120]}: {reason}"[:300], actor_id=actor_id))
        _event(db, s, "credit", f"Huỷ ly cafe {_vnd(c.amount)}: {reason}", actor_id)


def release_cafe_on_publish(session: Session, s: PartnerSubmission) -> None:
    """Phiếu xuất bản → ly cafe Chờ duyệt sang Khả dụng. Gọi trong before_flush (models.py)."""
    now = utcnow()
    with session.no_autoflush:
        rows = session.scalars(select(PartnerCredit).where(PartnerCredit.submission_id == s.id, PartnerCredit.kind == "cafe",
                                                          PartnerCredit.state == "pending")).all()
    for c in rows:
        c.state, c.available_at, c.released_at = "available", now, now


def release_due(db: Session, partner_id: int | None = None) -> int:
    """Hoa hồng hết thời gian giữ → Khả dụng. Chạy định kỳ (Celery beat) và khi đối tác mở ví."""
    q = select(PartnerCredit).where(PartnerCredit.state == "pending", PartnerCredit.available_at.is_not(None), PartnerCredit.available_at <= utcnow())
    if partner_id:
        q = q.where(PartnerCredit.partner_id == partner_id)
    rows = db.scalars(q).unique().all()
    for c in rows:
        c.state, c.released_at = "available", utcnow()
    if rows:
        db.commit()
    return len(rows)


# ================================================================== hoa hồng lượt bán


def related_reason(db: Session, p: PartnerUser, purchase: Purchase) -> str:
    """Tài khoản thành viên mua phiếu có liên quan tới đối tác? (trùng SĐT, email, MST). Ngân hàng: kiểm tra ở Mốc 4."""
    c = purchase.company
    emails = {e.lower() for e in db.scalars(select(MemberUser.email).where(MemberUser.company_id == c.id))}
    contacts = db.scalars(select(Contact).where(Contact.company_id == c.id)).all()
    emails |= {x.email.lower() for x in contacts if x.email}
    phones = {_digits(x.phone) for x in contacts if x.phone}
    if p.email.lower() in emails:
        return "trùng email"
    if _digits(p.phone) in phones:
        return "trùng số điện thoại"
    if p.org_tax_code and _digits(p.org_tax_code)[:10] == (c.tax_key or "")[:10]:
        return "trùng mã số thuế"
    return ""


def _digits(s: str) -> str:
    d = "".join(ch for ch in s or "" if ch.isdigit())
    return "0" + d[2:] if d.startswith("84") and len(d) >= 11 else d


def _counted_net(db: Session, s: PartnerSubmission) -> tuple[int, int]:
    """(doanh thu thuần lũy kế, số lượt) của các lượt bán được tính cho cơ hội (có dòng hoa hồng)."""
    rows = db.execute(
        select(Purchase.price, Purchase.refund_amount).where(
            Purchase.id.in_(select(PartnerCredit.purchase_id).where(PartnerCredit.submission_id == s.id, PartnerCredit.kind == "commission", PartnerCredit.state != "void"))
        )
    ).all()
    net = sum(net_of(price - refund) for price, refund in rows)
    sold = sum(1 for price, refund in rows if refund < price)
    return net, sold


def _target(db: Session, s: PartnerSubmission, st: dict) -> tuple[int, int, int]:
    rate = rate_for(s.partner, s, st)
    cum, _ = _counted_net(db, s)
    return rate * cum // 100, rate, cum


def on_purchase(db: Session, purchase: Purchase) -> PartnerCredit | None:
    """Gọi trong catalog.buy (cùng transaction) sau khi đã ghi Purchase."""
    opp: Opportunity = purchase.opportunity
    if not opp.source_submission_id:
        return None
    s = _lock(db, opp.source_submission_id)
    if not s or s.status != "published":
        return None
    st = settings(db)
    p = s.partner
    until = share_until(s, st)
    when = purchase.created_at or utcnow()
    if until and when > until:
        _event(db, s, "sale_skip", f"Lượt bán phiếu {opp.code} sau hạn chia sẻ ({until:%d/%m/%Y}) — không tính hoa hồng")
        return None
    why = related_reason(db, p, purchase)
    if why:
        _event(db, s, "sale_skip", f"Lượt bán phiếu {opp.code}: tài khoản mua có liên quan tới đối tác ({why}) — không tính hoa hồng")
        log.warning("Đối tác %s: lượt mua #%s có liên quan (%s)", p.code, purchase.id, why)
        return None
    # Ghi dòng hoa hồng 0đ trước để lượt này vào lũy kế, rồi tính phần ghi thêm
    c = PartnerCredit(partner_id=p.id, submission_id=s.id, purchase_id=purchase.id, kind="commission", amount=0, state="available")
    db.add(c)
    db.flush()
    target, rate, cum = _target(db, s, st)
    credits = _credits(db, s)
    if st["reward_mode"] == "sum":
        done = sum(x.amount for x in credits if x.kind in ("commission", "clawback"))
    else:
        done = sum(x.amount for x in credits if x.kind != "adjust" and x.kind != "fraud")
    add = max(0, target - done)
    now = utcnow()
    c.amount = add
    c.calc = {"rate": rate, "net": net_of(purchase.price), "cum_net": cum, "target": target, "credited_before": done, "mode": st["reward_mode"]}
    if add > 0:
        c.state, c.available_at = "pending", now + timedelta(days=st["hold_days"])
        c.note = f"{rate}% lượt bán phiếu {opp.code}"
        _event(db, s, "credit", f"Bán 1 lượt phiếu {opp.code}: +{_vnd(add)} hoa hồng (Chờ duyệt {st['hold_days']} ngày)")
    else:
        c.released_at = c.available_at = now
        c.note = f"Lượt bán phiếu {opp.code} — {rate}% doanh thu lũy kế chưa vượt phần đã nhận"
        _event(db, s, "credit", f"Bán 1 lượt phiếu {opp.code} — chưa vượt mức đã nhận, chưa ghi thêm")
    return c


def on_refund(db: Session, purchase: Purchase, actor_id: int | None = None) -> PartnerCredit | None:
    """Gọi trong catalog.refund (sau khi đặt refund_amount): thu hồi phần hoa hồng đã ghi vượt."""
    opp: Opportunity = purchase.opportunity
    if not opp.source_submission_id:
        return None
    s = _lock(db, opp.source_submission_id)
    if not s:
        return None
    credits = _credits(db, s)
    if not any(x.purchase_id == purchase.id and x.kind == "commission" for x in credits):
        return None  # lượt này không được tính hoa hồng
    db.flush()
    st = settings(db)
    target, rate, cum = _target(db, s, st)
    if st["reward_mode"] == "sum":
        excess = sum(x.amount for x in credits if x.kind in ("commission", "clawback")) - target
    else:
        cafe = sum(x.amount for x in credits if x.kind in ("cafe", "supplement"))
        total = sum(x.amount for x in credits if x.kind not in ("adjust", "fraud"))
        excess = total - max(target, cafe)
    if excess <= 0:
        _event(db, s, "credit", f"Hoàn phiếu {opp.code} — không phải thu hồi", actor_id)
        return None
    pending = [x for x in credits if x.state == "pending" and x.amount > 0 and x.available_at]
    now = utcnow()
    c = PartnerCredit(partner_id=s.partner_id, submission_id=s.id, purchase_id=purchase.id, kind="clawback", amount=-excess,
                      note=f"Thu hồi hoa hồng — thành viên được hoàn phiếu {opp.code}", actor_id=actor_id,
                      calc={"rate": rate, "cum_net": cum, "target": target, "mode": st["reward_mode"]})
    if pending:  # trừ vào khoản còn đang giữ để không làm Khả dụng âm tạm thời
        c.state, c.available_at = "pending", max(x.available_at for x in pending)
    else:
        c.state, c.available_at, c.released_at = "available", now, now
    db.add(c)
    _event(db, s, "credit", f"Hoàn phiếu {opp.code}: thu hồi {_vnd(excess)}", actor_id)
    return c


def safe(fn, db: Session, purchase: Purchase, *args) -> None:
    """Tính thưởng đối tác không được làm hỏng giao dịch mua / hoàn của thành viên: lỗi → ghi log + nhật ký để kiểm tra tay."""
    try:
        with db.begin_nested():
            fn(db, purchase, *args)
    except Exception:  # noqa: BLE001
        log.exception("Lỗi tính thưởng đối tác cho lượt mua #%s", purchase.id)
        sub_id = purchase.opportunity.source_submission_id if purchase.opportunity else None
        s = db.get(PartnerSubmission, sub_id) if sub_id else None
        if s:
            _event(db, s, "credit_error", f"LỖI tính thưởng cho lượt mua #{purchase.id} — cần kiểm tra và điều chỉnh tay")


# ================================================================== gian lận, điều chỉnh


def mark_fraud(db: Session, s: PartnerSubmission, actor: AdminUser, reason: str, lock_partner: bool = True) -> None:
    from app.partner_auth import end_all_sessions

    now = utcnow()
    clawed = 0
    for c in _credits(db, s):
        if c.state == "pending":
            c.state, c.voided_at = "void", now
            c.note = (c.note + " — huỷ: gian lận")[:300]
        else:
            clawed += c.amount
    if clawed > 0:
        db.add(PartnerCredit(partner_id=s.partner_id, submission_id=s.id, kind="fraud", amount=-clawed, state="available",
                             available_at=now, released_at=now, note=f"Thu hồi do gian lận {s.code}: {reason}"[:300], actor_id=actor.id))
    s.status, s.reject_reason = "rejected", "fraud"
    s.internal_note = (s.internal_note + f"\n[Gian lận] {reason}").strip()[:5000]
    s.decided_at, s.decided_by_id = now, actor.id
    _event(db, s, "sub_decided", f"Gian lận: {reason} — thu hồi thưởng{' và khoá tài khoản' if lock_partner else ''}", actor.id)
    if lock_partner and s.partner.status != "locked":
        s.partner.status = "locked"
        end_all_sessions(db, s.partner_id)
        db.add(PartnerEvent(partner_id=s.partner_id, kind="status", actor_id=actor.id, content=f"Khoá tài khoản — gian lận ở {s.code}: {reason}"[:500]))
    db.commit()


def adjust(db: Session, p: PartnerUser, amount: int, reason: str, actor: AdminUser) -> PartnerCredit:
    if amount == 0:
        raise HTTPException(422, "Số tiền điều chỉnh phải khác 0.")
    now = utcnow()
    c = PartnerCredit(partner_id=p.id, kind="adjust", amount=amount, state="available", available_at=now, released_at=now,
                      note=reason[:300], actor_id=actor.id)
    db.add(c)
    db.add(PartnerEvent(partner_id=p.id, kind="credit", actor_id=actor.id, content=f"Điều chỉnh ví {'+' if amount > 0 else ''}{_vnd(amount)}: {reason}"[:500]))
    db.commit()
    return c


# ================================================================== số dư & hiển thị


def balances(db: Session, partner_id: int) -> dict:
    rows = dict(db.execute(select(PartnerCredit.state, func.coalesce(func.sum(PartnerCredit.amount), 0))
                           .where(PartnerCredit.partner_id == partner_id, PartnerCredit.state != "void").group_by(PartnerCredit.state)).all())
    month = db.scalar(select(func.coalesce(func.sum(PartnerCredit.amount), 0)).where(
        PartnerCredit.partner_id == partner_id, PartnerCredit.state != "void", PartnerCredit.created_at >= month_start_utc())) or 0
    pending, credited = int(rows.get("pending", 0)), int(rows.get("available", 0))
    w = dict(db.execute(select(PartnerWithdrawal.status, func.coalesce(func.sum(PartnerWithdrawal.amount), 0))
                        .where(PartnerWithdrawal.partner_id == partner_id).group_by(PartnerWithdrawal.status)).all())
    withdrawing = int(sum(w.get(k, 0) for k in WITHDRAWAL_OPEN))
    paid = int(w.get("paid", 0))
    available = credited - withdrawing - paid  # Khả dụng = đã ghi khả dụng − đang rút − đã rút
    return {"pending": pending, "available": available, "withdrawing": withdrawing, "paid": paid,
            "total": pending + available, "earned": pending + credited, "month": int(month)}


def wallet_summary(db: Session, p: PartnerUser) -> dict:
    st = settings(db)
    quota = quota_for(p, st)
    used = cafe_used(db, p.id)
    return {**balances(db, p.id), "cafe_quota": quota, "cafe_used": used, "cafe_left": max(0, quota - used),
            "rate": p.custom_rate if p.custom_rate is not None else st.get(f"rate_{p.tier}", st["rate_new"])}


def credit_out(c: PartnerCredit, admin: bool = False) -> dict:
    from app.models import CREDIT_KINDS, CREDIT_STATES

    out = {
        "id": c.id, "kind": c.kind, "kind_label": CREDIT_KINDS.get(c.kind, c.kind), "amount": c.amount, "state": c.state,
        "state_label": CREDIT_STATES.get(c.state, c.state), "note": c.note,
        "submission": {"id": c.submission.id, "code": c.submission.code, "company_name": c.submission.company_name} if c.submission else None,
        "available_at": c.available_at.isoformat() + "Z" if c.available_at else None,
        "created_at": c.created_at.isoformat() + "Z" if c.created_at else None,
    }
    if admin:
        out.update(calc=c.calc, purchase_id=c.purchase_id, actor=c.actor.full_name if c.actor else None)
    return out


def submission_money(db: Session, sub_ids: list[int]) -> dict[int, dict]:
    """{submission_id: {"sold": số lượt bán được tính (chưa hoàn), "earned": tổng đã ghi (không tính khoản huỷ)}}"""
    if not sub_ids:
        return {}
    earned = dict(db.execute(select(PartnerCredit.submission_id, func.sum(PartnerCredit.amount))
                             .where(PartnerCredit.submission_id.in_(sub_ids), PartnerCredit.state != "void").group_by(PartnerCredit.submission_id)).all())
    sold = dict(db.execute(
        select(PartnerCredit.submission_id, func.count())
        .join(Purchase, Purchase.id == PartnerCredit.purchase_id)
        .where(PartnerCredit.submission_id.in_(sub_ids), PartnerCredit.kind == "commission", PartnerCredit.state != "void", Purchase.refund_amount < Purchase.price)
        .group_by(PartnerCredit.submission_id)
    ).all())
    return {i: {"sold": int(sold.get(i, 0)), "earned": int(earned.get(i, 0) or 0)} for i in sub_ids}
