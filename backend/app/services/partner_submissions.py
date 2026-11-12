"""Cơ hội đối tác gửi: chuẩn hoá form, kiểm tra trùng, điểm chất lượng tự động, quyết định xác minh, tạo phiếu nháp.

Điểm chất lượng hiện là điểm THEO QUY TẮC (độ đủ thông tin, độ chắc chắn, nguồn, bằng chứng, nghi trùng) — gợi ý cho
người duyệt, người duyệt chốt điểm cuối (final_score). Ngưỡng "Đạt xác minh": cfg.partner_min_score (mặc định 60).
"""

import re
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import (
    REJECT_REASONS,
    SUBMISSION_CERTAINTY,
    SUBMISSION_KINDS,
    SUBMISSION_OPEN,
    SUBMISSION_SOURCES,
    SUBMISSION_STATUSES,
    AdminUser,
    Opportunity,
    OpportunityContact,
    PartnerCredit,
    PartnerEvent,
    PartnerSubmission,
    PartnerUser,
)
from app.registration_form import _EMAIL, INDUSTRIES, clean, clean1, tax_key
from app.services import partner_wallet
from app.services.embedding import fold

_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){9,10}(?!\d)")
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.I)
_URL_RE = re.compile(r"^https?://[^\s]+\.[^\s]+$", re.I)
# Từ chung trong tên doanh nghiệp — bỏ đi khi so tên để "Công ty TNHH ABC" khớp "ABC Co., Ltd"
_NAME_STOP = {
    "cong", "ty", "tnhh", "co", "phan", "cp", "jsc", "ltd", "limited", "company", "corp", "corporation", "tap", "doan",
    "mtv", "mot", "thanh", "vien", "hai", "chi", "nhanh", "vn", "viet", "nam", "vietnam", "inc", "group", "va", "and",
}
# Nhóm cơ hội đối tác → nguồn của phiếu (danh mục OPP_SOURCES)
KIND_TO_SOURCE = {
    "buy": "Kết nối giao thương",
    "tender": "Dự án & gói thầu",
    "new_plant": "Nhà máy / FDI mới",
    "expansion": "Kết nối giao thương",
    "replace_supplier": "Kết nối giao thương",
}


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def name_key(name: str) -> str:
    return " ".join(w for w in fold(name).split() if w not in _NAME_STOP)


# ================================================================== form gửi cơ hội (brief mục 8.3)


def normalize(raw: dict) -> tuple[dict, dict[str, str]]:
    d = {
        "company_name": clean1(raw.get("company_name"), 200),
        "tax_code": re.sub(r"[^0-9\-]", "", clean1(raw.get("tax_code"), 20)),
        "province": clean1(raw.get("province"), 80),
        "industry": clean1(raw.get("industry"), 100),
        "kind": raw.get("kind") if raw.get("kind") in SUBMISSION_KINDS else "",
        "need": clean(raw.get("need"), 4000),
        "scale": clean1(raw.get("scale"), 200),
        "timing": clean1(raw.get("timing"), 200),
        "source_type": raw.get("source_type") if raw.get("source_type") in SUBMISSION_SOURCES else "",
        "source_url": clean1(raw.get("source_url"), 500),
        "certainty": raw.get("certainty") if raw.get("certainty") in SUBMISSION_CERTAINTY else "",
        "evidence": clean(raw.get("evidence"), 2000),
        "contact_name": clean1(raw.get("contact_name"), 100),
        "contact_title": clean1(raw.get("contact_title"), 100),
        "contact_phone": re.sub(r"[\s.\-()]", "", clean1(raw.get("contact_phone"), 30)),
        "contact_email": clean1(raw.get("contact_email"), 150).lower(),
        "contact_consent": raw.get("contact_consent") is True,
        "can_connect": raw.get("can_connect") if raw.get("can_connect") in ("yes", "no") else "",
    }
    lookup = raw.get("tax_lookup")
    d["tax_lookup"] = (
        {"name": clean1(lookup.get("name"), 200), "status": clean1(lookup.get("status"), 100), "active": lookup.get("active") is True}
        if isinstance(lookup, dict) else None
    )
    e: dict[str, str] = {}
    if len(d["company_name"]) < 3:
        e["company_name"] = "Vui lòng nhập tên doanh nghiệp có nhu cầu."
    if d["tax_code"] and not re.fullmatch(r"\d{10}(-?\d{3})?", d["tax_code"]):
        e["tax_code"] = "Mã số thuế gồm 10 hoặc 13 chữ số (để trống nếu chưa biết)."
    if not d["province"]:
        e["province"] = "Vui lòng nhập khu vực / tỉnh thành."
    if d["industry"] not in INDUSTRIES:
        e["industry"] = "Vui lòng chọn ngành hàng."
    if not d["kind"]:
        e["kind"] = "Vui lòng chọn loại cơ hội."
    if len(d["need"]) < 30:
        e["need"] = "Mô tả nhu cầu cụ thể hơn: mặt hàng/dịch vụ, quy mô, thời điểm cần (ít nhất 30 ký tự)."
    if not d["source_type"]:
        e["source_type"] = "Vui lòng chọn nguồn biết tin."
    elif d["source_type"] == "public" and not _URL_RE.match(d["source_url"]):
        e["source_url"] = "Nguồn công khai: vui lòng dán link (bắt đầu bằng http:// hoặc https://)."
    if d["source_url"] and not _URL_RE.match(d["source_url"]):
        e["source_url"] = "Link chưa đúng định dạng."
    if not d["certainty"]:
        e["certainty"] = "Vui lòng chọn mức độ chắc chắn."
    has_contact = any(d[k] for k in ("contact_name", "contact_title", "contact_phone", "contact_email"))
    if has_contact:
        if not d["contact_consent"]:
            e["contact_consent"] = "Chỉ điền người liên hệ khi người đó đồng ý được giới thiệu hoặc là liên hệ công khai — vui lòng tick xác nhận."
        if d["contact_phone"] and not re.fullmatch(r"(0|\+84)\d{8,10}", d["contact_phone"]):
            e["contact_phone"] = "Số điện thoại chưa đúng định dạng."
        if d["contact_email"] and not _EMAIL.match(d["contact_email"]):
            e["contact_email"] = "Email chưa đúng định dạng."
    else:
        d["contact_consent"] = False
    # Trả thưởng cho thông tin cơ hội, không cho dữ liệu cá nhân: chặn danh sách SĐT / email
    blob = "\n".join((d["need"], d["evidence"], d["scale"], d["timing"]))
    if len(_PHONE_RE.findall(blob)) >= 3 or len(_EMAIL_RE.findall(blob)) >= 3:
        e["need"] = "LeadScan không nhận danh sách số điện thoại / email. Hãy mô tả nhu cầu; người liên hệ (nếu được đồng ý) điền ở mục Người liên hệ."
    if raw.get("commitment") is not True:
        e["commitment"] = "Bạn cần cam kết thông tin hợp pháp, không vi phạm bảo mật nơi làm việc, không phải dữ liệu mua bán."
    d["tax_key"] = tax_key(d["tax_code"]) if d["tax_code"] else ""
    return d, e


# ================================================================== kiểm tra trùng


def find_duplicates(db: Session, cfg: Settings, d: dict, exclude_id: int | None = None) -> list[dict]:
    """Cơ hội trong CSDL (phiếu) hoặc cơ hội đối tác khác cùng doanh nghiệp trong N ngày.

    Khớp theo MST, hoặc theo tên doanh nghiệp (đã bỏ từ chung) khi không có MST. same_group = cùng ngành (nhóm nhu cầu).
    """
    since = utcnow() - timedelta(days=cfg.partner_dup_days)
    hints: list[dict] = []
    nk = name_key(d["company_name"])

    # Chỉ đọc vài cột (không tải đầu mối, embedding); so tên phải làm ở Python vì cần bỏ dấu + bỏ từ chung
    cols = (Opportunity.id, Opportunity.code, Opportunity.title, Opportunity.buyer_name, Opportunity.buyer_tax_key, Opportunity.industry, Opportunity.created_at)
    conds = []
    if d["tax_key"]:
        conds.append(Opportunity.buyer_tax_key == d["tax_key"])
    if nk:
        conds.append(Opportunity.buyer_name != "")
    rows = db.execute(select(*cols).where(Opportunity.created_at >= since, or_(*conds))).all() if conds else []
    for o in rows:
        by_tax = bool(d["tax_key"]) and o.buyer_tax_key == d["tax_key"]
        by_name = bool(nk) and nk == name_key(o.buyer_name)
        if by_tax or by_name:
            hints.append({
                "type": "opportunity", "id": o.id, "code": o.code, "title": o.title[:120], "match": "tax" if by_tax else "name",
                "same_group": o.industry == d["industry"], "created_at": _iso(o.created_at),
            })

    sub_q = select(PartnerSubmission).where(PartnerSubmission.created_at >= since, PartnerSubmission.status != "rejected")
    if exclude_id:
        sub_q = sub_q.where(PartnerSubmission.id != exclude_id)
    if d["tax_key"]:
        sub_q = sub_q.where(or_(PartnerSubmission.tax_key == d["tax_key"], PartnerSubmission.province == d["province"]))
    else:
        sub_q = sub_q.where(PartnerSubmission.province == d["province"])
    for s in db.scalars(sub_q).unique():
        by_tax = bool(d["tax_key"]) and s.tax_key == d["tax_key"]
        by_name = bool(nk) and nk == name_key(s.company_name) and s.province == d["province"]
        if by_tax or by_name:
            hints.append({
                "type": "submission", "id": s.id, "code": s.code, "title": s.need[:120], "match": "tax" if by_tax else "name",
                "same_group": s.industry == d["industry"], "created_at": _iso(s.created_at), "partner_id": s.partner_id,
                "status": s.status,
            })
    return hints


# ================================================================== điểm chất lượng tự động


def auto_score(d: dict, hints: list[dict]) -> tuple[int, list[dict]]:
    parts: list[tuple[str, int]] = []
    if d["tax_key"]:
        parts.append(("Có mã số thuế doanh nghiệp", 15))
        lk = d.get("tax_lookup") or {}
        if lk.get("active"):
            parts.append(("Tra MST: doanh nghiệp đang hoạt động", 5))
    need_len = len(d["need"])
    parts.append(("Nhu cầu mô tả chi tiết" if need_len >= 120 else "Nhu cầu mô tả ngắn", 15 if need_len >= 120 else 8))
    if d["scale"]:
        parts.append(("Có quy mô / số lượng", 10))
    if d["timing"]:
        parts.append(("Có thời điểm cần", 10))
    parts.append((f"Độ chắc chắn: {SUBMISSION_CERTAINTY[d['certainty']]}", {"confirmed": 20, "insider": 12, "public": 6}[d["certainty"]]))
    parts.append((f"Nguồn: {SUBMISSION_SOURCES[d['source_type']]}", {"direct": 10, "relationship": 8, "fair": 8, "public": 5}[d["source_type"]]))
    if d["evidence"] or d["source_url"]:
        parts.append(("Có link / tài liệu chứng minh", 5))
    if d["contact_consent"] and (d["contact_phone"] or d["contact_email"]):
        parts.append(("Có người liên hệ đồng ý được giới thiệu", 5))
    if any(h["same_group"] for h in hints):
        parts.append(("Nghi trùng cơ hội đã có (cùng doanh nghiệp, cùng nhóm nhu cầu)", -30))
    elif hints:
        parts.append(("Doanh nghiệp đã có cơ hội khác gần đây", -5))
    total = max(0, min(100, sum(p for _, p in parts)))
    return total, [{"label": label, "points": p} for label, p in parts]


# ================================================================== tạo


def _next_code(db: Session) -> str:
    n = (db.scalar(select(func.max(PartnerSubmission.id))) or 0) + 1
    while db.scalar(select(PartnerSubmission.id).where(PartnerSubmission.code == f"GT-{n:06d}")):
        n += 1
    return f"GT-{n:06d}"


def sla_due(start: datetime, workdays: int) -> datetime:
    """Cộng N ngày làm việc (bỏ T7, CN; chưa tính ngày lễ)."""
    d, left = start, workdays
    while left > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d


def create(db: Session, cfg: Settings, p: PartnerUser, d: dict) -> PartnerSubmission:
    day = db.scalar(
        select(func.count()).select_from(PartnerSubmission)
        .where(PartnerSubmission.partner_id == p.id, PartnerSubmission.created_at > utcnow() - timedelta(hours=24))
    )
    if (day or 0) >= cfg.partner_submit_per_day:
        raise HTTPException(429, f"Mỗi ngày gửi tối đa {cfg.partner_submit_per_day} cơ hội. Vui lòng gửi tiếp vào ngày mai.")
    hints = find_duplicates(db, cfg, d)
    own = next((h for h in hints if h["type"] == "submission" and h.get("partner_id") == p.id and h["same_group"] and h["status"] in (*SUBMISSION_OPEN, "verified", "published", "supplement")), None)
    if own:
        raise HTTPException(409, f"Bạn đã gửi cơ hội này rồi ({own['code']}). Theo dõi trạng thái trong mục Cơ hội của tôi.")
    score, detail = auto_score(d, hints)
    now = utcnow()
    s = PartnerSubmission(
        code=_next_code(db), partner_id=p.id, status="submitted", auto_score=score, score_detail=detail, dup_hints=hints,
        sla_due_at=sla_due(now, cfg.partner_sla_workdays), created_at=now, **d,
    )
    db.add(s)
    db.flush()
    db.add(PartnerEvent(partner_id=p.id, submission_id=s.id, kind="sub_created", content=f"Gửi cơ hội {s.code}: {s.company_name}"[:500]))
    db.commit()
    db.refresh(s)
    return s


# ================================================================== hiển thị


def _status_label(s: PartnerSubmission) -> str:
    return SUBMISSION_STATUSES.get(s.status, s.status)


def partner_out(s: PartnerSubmission, events: list[PartnerEvent] | None = None, money: dict | None = None, until: datetime | None = None) -> dict:
    """Cho đối tác: không có nghi trùng (có thể lộ cơ hội của người khác), ghi chú nội bộ, người duyệt."""
    out = {
        "id": s.id, "code": s.code, "status": s.status, "status_label": _status_label(s),
        "company_name": s.company_name, "tax_code": s.tax_code, "province": s.province, "industry": s.industry,
        "kind": s.kind, "kind_label": SUBMISSION_KINDS.get(s.kind, s.kind),
        "need": s.need, "scale": s.scale, "timing": s.timing,
        "source_type": s.source_type, "source_label": SUBMISSION_SOURCES.get(s.source_type, s.source_type), "source_url": s.source_url,
        "certainty": s.certainty, "certainty_label": SUBMISSION_CERTAINTY.get(s.certainty, s.certainty), "evidence": s.evidence,
        "contact_name": s.contact_name, "contact_title": s.contact_title, "contact_phone": s.contact_phone, "contact_email": s.contact_email,
        "can_connect": s.can_connect,
        "reject_reason": s.reject_reason, "reject_label": REJECT_REASONS.get(s.reject_reason, "") if s.reject_reason else "",
        "partner_note": s.partner_note,
        "score": s.final_score if s.decided_at else None,  # điểm chỉ hiện sau khi có quyết định
        "sla_due_at": _iso(s.sla_due_at), "decided_at": _iso(s.decided_at), "published_at": _iso(s.published_at),
        "created_at": _iso(s.created_at),
        "sold_count": (money or {}).get("sold", 0),  # số lượt bán được tính hoa hồng (chưa hoàn)
        "earned": (money or {}).get("earned", 0),  # tổng đã ghi vào ví cho cơ hội này
        "share_until": _iso(until),
        "share_expired": bool(until and until < utcnow()),
    }
    if events is not None:
        out["events"] = [{"kind": e.kind, "content": e.content, "created_at": _iso(e.created_at)} for e in events]
    return out


def with_money(db: Session, rows: list[PartnerSubmission]) -> list[tuple[PartnerSubmission, dict, datetime | None]]:
    st = partner_wallet.settings(db)
    money = partner_wallet.submission_money(db, [s.id for s in rows])
    return [(s, money.get(s.id, {}), partner_wallet.share_until(s, st)) for s in rows]


def admin_out(db: Session, s: PartnerSubmission, detail: bool = False) -> dict:
    (_, money, until), = with_money(db, [s])
    out = partner_out(s, money=money, until=until)
    p = s.partner
    out.update(
        partner={"id": p.id, "code": p.code, "full_name": p.full_name, "phone": p.phone, "tier": p.tier, "kind": p.kind, "org_name": p.org_name},
        auto_score=s.auto_score, final_score=s.final_score, score=s.final_score if s.final_score is not None else s.auto_score,
        dup_count=len(s.dup_hints or []), dup_strong=any(h.get("same_group") for h in s.dup_hints or []),
        is_large=s.is_large, assigned_to={"id": s.assigned_to.id, "full_name": s.assigned_to.full_name} if s.assigned_to else None,
        overdue=bool(s.status in SUBMISSION_OPEN and s.sla_due_at and s.sla_due_at < utcnow()),
        decided_by=s.decided_by.full_name if s.decided_by else None,
    )
    if detail:
        opp = linked_opportunity(db, s)
        events = db.scalars(select(PartnerEvent).where(PartnerEvent.submission_id == s.id).order_by(PartnerEvent.id.desc())).unique().all()
        out.update(
            contact_consent=s.contact_consent, tax_lookup=s.tax_lookup, score_detail=s.score_detail, internal_note=s.internal_note,
            dup_hints=s.dup_hints or [], dup_live=find_duplicates(db, _cfg(), _as_dict(s), exclude_id=s.id),
            opportunity={"id": opp.id, "code": opp.code, "status": opp.status, "title": opp.title} if opp else None,
            partner_stats=partner_stats(db, p.id),
            credits=[partner_wallet.credit_out(c, admin=True) for c in db.scalars(
                select(PartnerCredit).where(PartnerCredit.submission_id == s.id).order_by(PartnerCredit.id.desc())).unique()],
            events=[{"kind": e.kind, "content": e.content, "actor": e.actor.full_name if e.actor else None, "created_at": _iso(e.created_at)} for e in events],
        )
    return out


def _cfg() -> Settings:
    from app.config import get_settings

    return get_settings()


def _as_dict(s: PartnerSubmission) -> dict:
    return {"company_name": s.company_name, "tax_key": s.tax_key, "province": s.province, "industry": s.industry}


def partner_stats(db: Session, partner_id: int) -> dict:
    rows = dict(db.execute(select(PartnerSubmission.status, func.count()).where(PartnerSubmission.partner_id == partner_id).group_by(PartnerSubmission.status)).all())
    total = sum(rows.values())
    decided = sum(v for k, v in rows.items() if k not in SUBMISSION_OPEN)
    ok = rows.get("verified", 0) + rows.get("published", 0)
    return {"by_status": rows, "total": total, "ok": ok, "pass_rate": round(ok * 100 / decided) if decided else None}


def linked_opportunity(db: Session, s: PartnerSubmission) -> Opportunity | None:
    return db.scalar(select(Opportunity).where(Opportunity.source_submission_id == s.id).order_by(Opportunity.id).limit(1))


# ================================================================== xác minh (quản trị)

DECISIONS = {"verified", "duplicate", "rejected", "supplement"}


def assign(db: Session, s: PartnerSubmission, assignee: AdminUser | None, actor: AdminUser) -> None:
    s.assigned_to_id = assignee.id if assignee else None
    if s.status == "submitted":
        s.status = "verifying"
        db.add(PartnerEvent(partner_id=s.partner_id, submission_id=s.id, kind="sub_verifying", actor_id=actor.id, content="Bắt đầu xác minh"))
    if assignee:
        db.add(PartnerEvent(partner_id=s.partner_id, submission_id=s.id, kind="sub_assign", actor_id=actor.id, content=f"Giao {assignee.full_name} xác minh"))
    db.commit()
    db.refresh(s)  # nạp lại người phụ trách (quan hệ joined)


def decide(db: Session, cfg: Settings, s: PartnerSubmission, actor: AdminUser, decision: str, *, reason: str = "",
           partner_note: str = "", internal_note: str | None = None, final_score: int | None = None, is_large: bool = False) -> None:
    if decision not in DECISIONS:
        raise HTTPException(422, "Quyết định không hợp lệ.")
    if s.status == "published" or linked_opportunity(db, s):
        raise HTTPException(409, "Cơ hội đã có phiếu — không đổi quyết định được nữa.")
    if s.status not in SUBMISSION_OPEN and actor.role != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được đổi quyết định đã đưa ra.")
    score = s.auto_score if final_score is None else final_score
    if not 0 <= score <= 100:
        raise HTTPException(422, "Điểm chất lượng từ 0 đến 100.")
    if decision == "verified" and score < cfg.partner_min_score:
        raise HTTPException(422, f"Điểm {score} dưới ngưỡng {cfg.partner_min_score} — chưa thể Đạt xác minh. Chấm lại điểm hoặc chọn Không đạt.")
    if reason == "fraud":
        raise HTTPException(422, "Gian lận: dùng nút “Đánh dấu gian lận” để thu hồi thưởng và khoá tài khoản.")
    if decision == "rejected" and reason not in REJECT_REASONS:
        raise HTTPException(422, "Vui lòng chọn lý do không đạt.")
    if decision == "rejected" and reason == "other" and not partner_note.strip():
        raise HTTPException(422, "Lý do khác: vui lòng ghi rõ cho đối tác.")
    was = s.status
    if was in ("verified", "supplement") and decision != was:
        partner_wallet.revoke_cafe(db, s, actor.id, f"đổi quyết định {SUBMISSION_STATUSES[was]} → {SUBMISSION_STATUSES[decision]}")
    s.status = decision
    s.final_score = score
    s.reject_reason = reason if decision == "rejected" else ""
    s.partner_note = partner_note.strip()[:2000]
    if internal_note is not None:
        s.internal_note = internal_note[:5000]
    s.is_large = bool(is_large) and decision == "verified"
    s.decided_at, s.decided_by_id = utcnow(), actor.id
    if not s.assigned_to_id:
        s.assigned_to_id = actor.id
    label = SUBMISSION_STATUSES[decision]
    extra = f" — {REJECT_REASONS[reason]}" if decision == "rejected" else ""
    prefix = "Đổi quyết định" if was not in SUBMISSION_OPEN else "Kết quả xác minh"
    db.add(PartnerEvent(partner_id=s.partner_id, submission_id=s.id, kind="sub_decided", actor_id=actor.id, content=f"{prefix}: {label}{extra} (điểm {score})"[:500]))
    if decision in ("verified", "supplement") and decision != was:
        db.flush()
        partner_wallet.grant_cafe(db, s, actor.id, kind="cafe" if decision == "verified" else "supplement")
    db.commit()
    db.refresh(s)


def create_opportunity(db: Session, s: PartnerSubmission, actor: AdminUser) -> Opportunity:
    """Phiếu NHÁP từ cơ hội đạt xác minh, gắn đối tác nguồn. Admin hoàn thiện (tiêu đề, giá, tóm tắt) rồi mở bán."""
    if s.status != "verified":
        raise HTTPException(409, "Chỉ tạo phiếu từ cơ hội Đạt xác minh.")
    if linked_opportunity(db, s):
        raise HTTPException(409, "Cơ hội này đã có phiếu.")
    kind = SUBMISSION_KINDS.get(s.kind, s.kind)
    first = re.split(r"(?<=[.!?\n])\s", s.need.strip(), maxsplit=1)[0]
    title = f"{kind}: {first}"[:200]
    summary = " · ".join(x for x in (kind, s.industry, s.province, s.scale and f"Quy mô: {s.scale}", s.timing and f"Thời điểm: {s.timing}") if x)
    lines = [s.need]
    if s.scale:
        lines.append(f"Quy mô: {s.scale}")
    if s.timing:
        lines.append(f"Thời điểm cần: {s.timing}")
    lines.append(f"Mức độ chắc chắn: {SUBMISSION_CERTAINTY.get(s.certainty, s.certainty)}")
    if s.evidence:
        lines.append(f"Tài liệu / link: {s.evidence}")
    n = (db.scalar(select(func.max(Opportunity.id))) or 0) + 1
    while db.scalar(select(Opportunity.id).where(Opportunity.code == f"CH-{n:06d}")):
        n += 1
    o = Opportunity(
        code=f"CH-{n:06d}", status="draft", title=title, summary=summary, industry=s.industry, province=s.province,
        source_type=KIND_TO_SOURCE.get(s.kind, ""), scale=s.scale, buyer_name=s.company_name + (f" (MST {s.tax_code})" if s.tax_code else ""),
        detail="\n".join(lines), source_url=s.source_url, buyer_tax_key=s.tax_key, created_by_id=actor.id,
        source_partner_id=s.partner_id, source_submission_id=s.id,
    )
    if s.contact_consent and (s.contact_name or s.contact_phone or s.contact_email):
        o.contacts = [OpportunityContact(position_order=0, full_name=s.contact_name, title=s.contact_title, phone=s.contact_phone, email=s.contact_email, note="Đối tác giới thiệu, đã đồng ý")]
    db.add(o)
    db.flush()
    db.add(PartnerEvent(partner_id=s.partner_id, submission_id=s.id, kind="sub_opp", actor_id=actor.id, content=f"Tạo phiếu nháp {o.code}"))
    db.commit()
    db.refresh(o)
    return o
