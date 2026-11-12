"""Báo cáo, cờ gian lận, nhật ký cho tính năng Đối tác (brief mục 2 — KPI thí điểm, mục 9 — back-office).

Số liệu tiền:
  - Doanh thu từ cơ hội đối tác = điểm thành viên thực trả cho phiếu có đối tác nguồn, trừ phần đã hoàn, CHƯA gồm thuế GTGT
    (cùng cách tính với ví hoa hồng — partner_wallet.net_of).
  - Chi phí đối tác = ly cafe + đóng góp bổ sung + hoa hồng − thu hồi (khoản ghi không bị huỷ). Điều chỉnh tay báo riêng.
Kỳ báo cáo lọc theo ngày phát sinh (giờ Việt Nam): cơ hội theo ngày gửi, doanh thu theo ngày mua, chi phí theo ngày ghi.
"""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import (
    PARTNER_TIERS,
    SUBMISSION_OPEN,
    Opportunity,
    PartnerCredit,
    PartnerEvent,
    PartnerPayoutProfile,
    PartnerSubmission,
    PartnerUser,
    PartnerWithdrawal,
    Purchase,
)
from app.services.partner_wallet import net_of

COST_KINDS = ("cafe", "supplement", "commission", "clawback", "fraud")
OK_STATUSES = ("verified", "published", "supplement")
# KPI thí điểm 90 ngày (brief mục 2) — mục tiêu đề xuất, hiệu chỉnh sau 30 ngày
KPI_TARGETS = {"partners": 200, "activation": 30, "pass_rate": 40, "sell_rate": 25, "cost_ratio": 35}


def _range(d_from: date | None, d_to: date | None) -> tuple[datetime | None, datetime | None]:
    """Ngày theo giờ VN → khoảng UTC [from, to) để so với cột DateTime (UTC naive)."""
    start = datetime.combine(d_from, datetime.min.time()) - timedelta(hours=7) if d_from else None
    end = datetime.combine(d_to + timedelta(days=1), datetime.min.time()) - timedelta(hours=7) if d_to else None
    return start, end


def _between(col, start, end):
    conds = []
    if start:
        conds.append(col >= start)
    if end:
        conds.append(col < end)
    return conds


def _pct(a: int, b: int) -> float | None:
    return round(a * 100 / b, 1) if b else None


# ================================================================== doanh thu & chi phí


def revenue_rows(db: Session, start=None, end=None) -> list[tuple[int, int]]:
    """[(submission_id, doanh thu thuần)] của từng lượt mua phiếu có đối tác nguồn trong kỳ."""
    rows = db.execute(
        select(Opportunity.source_submission_id, Purchase.price, Purchase.refund_amount)
        .join(Opportunity, Opportunity.id == Purchase.opportunity_id)
        .where(Opportunity.source_submission_id.is_not(None), *_between(Purchase.created_at, start, end))
    ).all()
    return [(sid, net_of(price - refund)) for sid, price, refund in rows if price > refund]


def cost_rows(db: Session, start=None, end=None) -> list[tuple[int | None, int, int, str]]:
    """[(submission_id, partner_id, số tiền, loại)] — khoản ghi ví (không huỷ) trong kỳ."""
    return db.execute(
        select(PartnerCredit.submission_id, PartnerCredit.partner_id, PartnerCredit.amount, PartnerCredit.kind)
        .where(PartnerCredit.state != "void", *_between(PartnerCredit.created_at, start, end))
    ).all()


# ================================================================== KPI thí điểm


def kpi(db: Session, d_from: date | None = None, d_to: date | None = None) -> dict:
    start, end = _range(d_from, d_to)
    partners = db.execute(select(PartnerUser.id, PartnerUser.created_at).where(PartnerUser.phone_verified_at.is_not(None), *_between(PartnerUser.created_at, start, end))).all()
    first = dict(db.execute(select(PartnerSubmission.partner_id, func.min(PartnerSubmission.created_at)).group_by(PartnerSubmission.partner_id)).all())
    now = utcnow()
    activated = sum(1 for pid, created in partners if first.get(pid) and first[pid] <= created + timedelta(days=30))
    # chưa đủ 30 ngày mà chưa gửi → chưa tính vào mẫu số
    eligible = sum(1 for pid, created in partners if created <= now - timedelta(days=30) or (first.get(pid) and first[pid] <= created + timedelta(days=30)))

    subs = db.execute(select(PartnerSubmission.id, PartnerSubmission.status).where(*_between(PartnerSubmission.created_at, start, end))).all()
    sent = len(subs)
    ok_ids = {sid for sid, st in subs if st in ("verified", "published")}  # cơ hội đạt (không tính đóng góp bổ sung — không bán phiếu riêng)
    ok_all = sum(1 for _, st in subs if st in OK_STATUSES)
    sold_ids = {sid for sid, _ in revenue_rows(db)} & ok_ids  # cơ hội đạt (gửi trong kỳ) có ≥ 1 lượt bán

    rev = sum(v for _, v in revenue_rows(db, start, end))
    costs = cost_rows(db, start, end)
    cost = sum(a for sid, pid, a, k in costs if k in COST_KINDS)
    adjust = sum(a for sid, pid, a, k in costs if k == "adjust")

    items = [
        {"key": "partners", "label": "Đối tác đăng ký", "value": len(partners), "unit": "", "target": KPI_TARGETS["partners"], "better": "higher",
         "note": "Tài khoản đã xác thực SĐT"},
        {"key": "activation", "label": "Tỷ lệ kích hoạt", "value": _pct(activated, eligible), "unit": "%", "target": KPI_TARGETS["activation"], "better": "higher",
         "note": f"{activated}/{eligible} đối tác gửi ≥ 1 cơ hội trong 30 ngày đầu"},
        {"key": "pass_rate", "label": "Tỷ lệ đạt xác minh", "value": _pct(ok_all, sent), "unit": "%", "target": KPI_TARGETS["pass_rate"], "better": "higher",
         "note": f"{ok_all}/{sent} cơ hội đạt / đã gửi"},
        {"key": "sell_rate", "label": "Tỷ lệ bán được", "value": _pct(len(sold_ids), len(ok_ids)), "unit": "%", "target": KPI_TARGETS["sell_rate"], "better": "higher",
         "note": f"{len(sold_ids)}/{len(ok_ids)} cơ hội đạt có ≥ 1 lượt bán"},
        {"key": "cost_ratio", "label": "Chi phí đối tác / doanh thu", "value": _pct(cost, rev), "unit": "%", "target": KPI_TARGETS["cost_ratio"], "better": "lower",
         "note": "(Ly cafe + hoa hồng) / doanh thu phiếu từ cơ hội đối tác"},
    ]
    for it in items:
        v, t = it["value"], it["target"]
        it["met"] = None if v is None else (v >= t if it["better"] == "higher" else v <= t)
    met = sum(1 for it in items if it["met"])
    cost_ok = next(it for it in items if it["key"] == "cost_ratio")["met"]
    return {
        "items": items, "met": met, "total": len(items),
        # Cổng chuyển giai đoạn (brief mục 11): đạt ≥ 3/5 KPI, bắt buộc chi phí / doanh thu ≤ 35%
        "gate_passed": met >= 3 and bool(cost_ok),
        "revenue": rev, "cost": cost, "adjust": adjust, "sent": sent, "ok": ok_all, "sold": len(sold_ids),
        "period": {"from": d_from.isoformat() if d_from else None, "to": d_to.isoformat() if d_to else None},
    }


# ================================================================== công nợ đối tác


def liabilities(db: Session) -> dict:
    """Số LeadScan đang nợ từng đối tác: Chờ duyệt + Khả dụng (chưa rút) + Đang rút. Đã rút để đối chiếu."""
    cred = defaultdict(lambda: {"pending": 0, "available": 0})
    for pid, state, amt in db.execute(select(PartnerCredit.partner_id, PartnerCredit.state, func.sum(PartnerCredit.amount))
                                      .where(PartnerCredit.state != "void").group_by(PartnerCredit.partner_id, PartnerCredit.state)).all():
        cred[pid][state] = int(amt or 0)
    wd = defaultdict(lambda: {"withdrawing": 0, "paid": 0})
    for pid, status, amt in db.execute(select(PartnerWithdrawal.partner_id, PartnerWithdrawal.status, func.sum(PartnerWithdrawal.amount))
                                       .group_by(PartnerWithdrawal.partner_id, PartnerWithdrawal.status)).all():
        if status in ("requested", "approved"):
            wd[pid]["withdrawing"] += int(amt or 0)
        elif status == "paid":
            wd[pid]["paid"] += int(amt or 0)
    ids = set(cred) | set(wd)
    people = {p.id: p for p in db.scalars(select(PartnerUser).where(PartnerUser.id.in_(ids)))} if ids else {}
    rows = []
    for pid in ids:
        p = people.get(pid)
        if not p:
            continue
        c, w = cred[pid], wd[pid]
        available = c["available"] - w["withdrawing"] - w["paid"]
        rows.append({
            "partner": {"id": p.id, "code": p.code, "full_name": p.full_name, "kind": p.kind, "tier": PARTNER_TIERS.get(p.tier, p.tier)},
            "pending": c["pending"], "available": available, "withdrawing": w["withdrawing"], "paid": w["paid"],
            "owed": c["pending"] + available + w["withdrawing"],
        })
    rows.sort(key=lambda r: -r["owed"])
    totals = {k: sum(r[k] for r in rows) for k in ("pending", "available", "withdrawing", "paid", "owed")}
    return {"items": rows, "totals": totals}


# ================================================================== hiệu quả theo đối tác / ngành / tỉnh


def performance(db: Session, group: str = "partner", d_from: date | None = None, d_to: date | None = None) -> dict:
    """Nhóm theo cơ hội GỬI trong kỳ: số gửi, đạt, bán được, doanh thu thuần, chi phí, chi phí/doanh thu (toàn bộ vòng đời)."""
    start, end = _range(d_from, d_to)
    subs = db.scalars(select(PartnerSubmission).where(*_between(PartnerSubmission.created_at, start, end))).unique().all()
    rev = defaultdict(int)
    sold = set()
    for sid, v in revenue_rows(db):
        rev[sid] += v
        sold.add(sid)
    cost = defaultdict(int)
    for sid, _pid, a, k in cost_rows(db):
        if sid and k in COST_KINDS:
            cost[sid] += a

    def key(s: PartnerSubmission):
        if group == "industry":
            return s.industry or "(chưa rõ)", s.industry or "(chưa rõ)"
        if group == "province":
            return s.province or "(chưa rõ)", s.province or "(chưa rõ)"
        return s.partner_id, f"{s.partner.code} · {s.partner.full_name}"

    agg: dict = {}
    for s in subs:
        k, label = key(s)
        a = agg.setdefault(k, {"key": k, "label": label, "sent": 0, "ok": 0, "sold": 0, "revenue": 0, "cost": 0, "open": 0})
        a["sent"] += 1
        a["ok"] += s.status in OK_STATUSES
        a["open"] += s.status in SUBMISSION_OPEN
        a["sold"] += s.id in sold
        a["revenue"] += rev[s.id]
        a["cost"] += cost[s.id]
    rows = list(agg.values())
    for r in rows:
        r["pass_rate"] = _pct(r["ok"], r["sent"])
        r["cost_ratio"] = _pct(r["cost"], r["revenue"])
    rows.sort(key=lambda r: (-r["revenue"], -r["ok"], -r["sent"]))
    totals = {k: sum(r[k] for r in rows) for k in ("sent", "ok", "sold", "revenue", "cost", "open")}
    totals["pass_rate"], totals["cost_ratio"] = _pct(totals["ok"], totals["sent"]), _pct(totals["cost"], totals["revenue"])
    return {"group": group, "items": rows, "totals": totals}


def to_csv(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")


# ================================================================== cờ gian lận


def fraud_flags(db: Session) -> list[dict]:
    """Dấu hiệu cần xem xét (brief mục 9 & 10). Chỉ là cờ — quyết định khoá / thu hồi do quản trị viên."""
    flags: list[dict] = []
    people = {p.id: p for p in db.scalars(select(PartnerUser))}

    def ref(pid):
        p = people.get(pid)
        return {"id": pid, "code": p.code, "full_name": p.full_name, "status": p.status} if p else {"id": pid, "code": "?", "full_name": "", "status": ""}

    # 1. Nhiều tài khoản đăng ký cùng IP (cùng IP + trình duyệt → mức nặng hơn)
    by_ip = defaultdict(list)
    for p in people.values():
        if p.signup_ip:
            by_ip[p.signup_ip].append(p)
    for ip, ps in by_ip.items():
        if len(ps) < 2:
            continue
        same_ua = len({p.signup_ua for p in ps}) == 1
        flags.append({"type": "same_device" if same_ua else "same_ip", "severity": "high" if same_ua else "medium",
                      "label": "Nhiều tài khoản cùng IP và trình duyệt đăng ký" if same_ua else "Nhiều tài khoản đăng ký cùng IP",
                      "detail": f"IP {ip} — {len(ps)} tài khoản", "partners": [ref(p.id) for p in ps]})

    # 2. Cùng tài khoản ngân hàng nhận tiền
    by_acc = defaultdict(list)
    for pid, h in db.execute(select(PartnerPayoutProfile.partner_id, PartnerPayoutProfile.account_hash)).all():
        by_acc[h].append(pid)
    for h, pids in by_acc.items():
        if len(pids) >= 2:
            flags.append({"type": "shared_bank", "severity": "high", "label": "Nhiều đối tác dùng chung tài khoản ngân hàng",
                          "detail": f"{len(pids)} đối tác cùng 1 tài khoản nhận tiền", "partners": [ref(i) for i in pids]})

    # 3. Tỷ lệ không đạt / trùng cao (≥ 5 cơ hội đã có kết quả, ≥ 70% không đạt hoặc trùng)
    stats = defaultdict(lambda: {"decided": 0, "bad": 0})
    for pid, st, n in db.execute(select(PartnerSubmission.partner_id, PartnerSubmission.status, func.count())
                                 .group_by(PartnerSubmission.partner_id, PartnerSubmission.status)).all():
        if st not in SUBMISSION_OPEN:
            stats[pid]["decided"] += n
            if st in ("rejected", "duplicate"):
                stats[pid]["bad"] += n
    for pid, s in stats.items():
        if s["decided"] >= 5 and s["bad"] * 100 >= 70 * s["decided"]:
            flags.append({"type": "high_reject", "severity": "medium", "label": "Tỷ lệ không đạt / trùng cao",
                          "detail": f"{s['bad']}/{s['decided']} cơ hội không đạt hoặc trùng", "partners": [ref(pid)]})

    # 4. Đối tác và người mua phiếu có liên quan (lượt bán bị loại khỏi hoa hồng)
    rel = defaultdict(list)
    for pid, content in db.execute(select(PartnerEvent.partner_id, PartnerEvent.content).where(PartnerEvent.kind == "sale_skip", PartnerEvent.content.like("%có liên quan%"))).all():
        rel[pid].append(content)
    for pid, items in rel.items():
        flags.append({"type": "related_buyer", "severity": "high", "label": "Tài khoản mua phiếu có liên quan tới đối tác",
                      "detail": f"{len(items)} lượt mua: {items[-1][:160]}", "partners": [ref(pid)]})

    # 5. Đã bị đánh dấu gian lận
    fr = defaultdict(list)
    for pid, code in db.execute(select(PartnerSubmission.partner_id, PartnerSubmission.code).where(PartnerSubmission.reject_reason == "fraud")).all():
        fr[pid].append(code)
    for pid, codes in fr.items():
        flags.append({"type": "fraud_marked", "severity": "high", "label": "Đã có cơ hội bị đánh dấu gian lận",
                      "detail": ", ".join(codes), "partners": [ref(pid)]})

    order = {"high": 0, "medium": 1}
    flags.sort(key=lambda f: (order.get(f["severity"], 2), f["type"]))
    return flags


def flags_by_partner(db: Session) -> dict[int, list[str]]:
    out: dict[int, list[str]] = defaultdict(list)
    for f in fraud_flags(db):
        for p in f["partners"]:
            out[p["id"]].append(f["label"])
    return out


# ================================================================== nhật ký chung


def events(db: Session, kind: str = "", partner_id: int | None = None, q: str = "", page: int = 1, page_size: int = 50,
           d_from: date | None = None, d_to: date | None = None) -> dict:
    start, end = _range(d_from, d_to)
    stmt = select(PartnerEvent).where(*_between(PartnerEvent.created_at, start, end))
    if kind:
        stmt = stmt.where(PartnerEvent.kind.in_(EVENT_GROUPS.get(kind, (kind,))))
    if partner_id:
        stmt = stmt.where(PartnerEvent.partner_id == partner_id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.join(PartnerUser, PartnerUser.id == PartnerEvent.partner_id).where(
            or_(PartnerEvent.content.ilike(like), PartnerUser.code.ilike(like), PartnerUser.full_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PartnerEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    people = {p.id: p for p in db.scalars(select(PartnerUser).where(PartnerUser.id.in_({e.partner_id for e in rows})))} if rows else {}
    subs = {s.id: s.code for s in db.scalars(select(PartnerSubmission).where(PartnerSubmission.id.in_({e.submission_id for e in rows if e.submission_id})))} if rows else {}
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [{
            "id": e.id, "kind": e.kind, "content": e.content, "actor": e.actor.full_name if e.actor else None,
            "partner": {"id": e.partner_id, "code": people[e.partner_id].code, "full_name": people[e.partner_id].full_name} if e.partner_id in people else None,
            "submission": {"id": e.submission_id, "code": subs.get(e.submission_id, "")} if e.submission_id else None,
            "created_at": e.created_at.isoformat() + "Z",
        } for e in rows],
    }


# Nhóm loại nhật ký cho bộ lọc
EVENT_GROUPS = {
    "account": ("created", "phone_verified", "password", "status", "tier", "note"),
    "submission": ("sub_created", "sub_verifying", "sub_assign", "sub_decided", "sub_opp", "sub_published"),
    "money": ("credit", "cafe_quota", "sale_skip", "credit_error"),
    "payout": ("withdraw", "payout_profile"),
    "fraud": ("fraud_flag",),
}
