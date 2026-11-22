"""Công cụ của trợ lý LeadScan — mỗi công cụ là 1 hàm đọc dữ liệu (KHÔNG có công cụ nào ghi / mua / gửi / rút).

Phạm vi theo đối tượng:
  guest   : số liệu công khai (giá, thưởng đối tác, cơ hội đang bán, danh mục)
  member  : + dữ liệu của chính doanh nghiệp đang đăng nhập (ví, đơn, phiếu tìm, phiếu đã mua, cơ hội phù hợp)
  partner : + dữ liệu của chính đối tác (tài khoản, cơ hội đã gửi, rút tiền) và nhu cầu thành viên đang tìm (ẩn danh)

Dữ liệu gửi cho mô hình AI bên ngoài nên KHÔNG trả dữ liệu cá nhân: không email / SĐT / tên người liên hệ, không số tài khoản,
không đầu mối của phiếu đã mua. Mọi truy vấn của thành viên lọc theo company_id, của đối tác lọc theo partner_id.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import utcnow
from app.models import (
    ORDER_KINDS,
    ORDER_STATUSES,
    PARTNER_KINDS,
    PARTNER_TIERS,
    SEARCH_STATUSES,
    SUBMISSION_STATUSES,
    TX_KINDS,
    MemberNotification,
    MemberUser,
    Opportunity,
    PartnerSubmission,
    PartnerUser,
    PartnerWithdrawal,
    PaymentOrder,
    Purchase,
    SavedOpportunity,
    SearchRequest,
    SearchRequestMatch,
    UserOpportunity,
    WalletTransaction,
)
from app.registration_form import AREAS, INDUSTRIES

AUDIENCES = ("guest", "member", "partner")


class ToolError(Exception):
    """Lỗi nghiệp vụ trả lại cho AI (vd. không tìm thấy mã) — AI tự diễn đạt cho người dùng."""


@dataclass
class Ctx:
    db: Session
    audience: str
    member: MemberUser | None = None
    partner: PartnerUser | None = None
    used: list[str] = field(default_factory=list)


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _d(dt):
    """Ngày giờ VN dạng dd/mm/yyyy HH:MM cho AI đọc thẳng."""
    return (dt + timedelta(hours=7)).strftime("%d/%m/%Y %H:%M") if dt else None


def _limit(args: dict, default: int, top: int) -> int:
    try:
        return max(1, min(top, int(args.get("limit") or default)))
    except (TypeError, ValueError):
        return default


def _site() -> str:
    return get_settings().site_url.rstrip("/")


# ================================================================== công khai


def get_pricing(ctx: Ctx, args: dict) -> dict:
    from app.services import pricing

    cfg = get_settings()
    c = pricing.current()
    return {
        "membership": {
            "fee_vnd": cfg.membership_fee, "points_received": cfg.membership_points, "valid_days": cfg.membership_days,
            "note": "1 điểm = 1đ. Gia hạn khi còn hạn thì cộng dồn thời hạn. Nạp thêm điểm chỉ khi đang là thành viên.",
        },
        "topup": {"packages_vnd": cfg.topup_packs, "custom_min_vnd": cfg.topup_min, "custom_max_vnd": cfg.topup_max},
        "tiers": {
            "standard": "Thường — mặc định",
            "gold": f"Vàng — tổng đã nạp (phí thành viên + nạp điểm đã thanh toán) từ {cfg.gold_topup_threshold:,}đ".replace(",", "."),
            "gold_threshold_vnd": cfg.gold_topup_threshold,
            "gold_benefits": ["Mua độc quyền phiếu cơ hội (phiếu nhiều lượt mua và chưa ai mua)", "Dùng CRM Lite"],
            "exclusive_price_multiplier": cfg.exclusive_price_multiplier,
        },
        "ticket_price": {
            "min_price_vnd": c["min_price"],
            "formula": "Giá thành viên trả = giá cơ bản của phiếu × hệ số điểm phù hợp × hệ số gấp (hạn chót) × hệ số đủ thông tin × "
                       "hệ số giá trị đơn, làm tròn, không thấp hơn giá cơ bản và giá tối thiểu. Mỗi thành viên thấy giá riêng theo điểm phù hợp.",
            "score_from": c["score_from"], "score_max_mult": c["score_max_mult"],
            "urgency_mult": {"<=3 ngày": c["urg_3"], "<=7 ngày": c["urg_7"], "<=14 ngày": c["urg_14"], "<=30 ngày": c["urg_30"]},
            "info_full_mult": c["info_full_mult"],
            "value_thresholds_vnd": [c["value_t1"], c["value_t2"], c["value_t3"], c["value_t4"]],
            "value_mult": [c["value_m0"], c["value_m1"], c["value_m2"], c["value_m3"], c["value_m4"]],
        },
    }


def get_partner_rewards(ctx: Ctx, args: dict) -> dict:
    from app.services import partner_wallet

    cfg = get_settings()
    st = partner_wallet.settings(ctx.db)
    return {
        "cafe_vnd": st["cafe_amount"],
        "mode": st["reward_mode"],
        "mode_label": partner_wallet.MODES.get(st["reward_mode"], st["reward_mode"]),
        "commission_rate_percent": {"Mới": st["rate_new"], "Bạc": st["rate_silver"], "cơ hội lớn": st["rate_large"], "trần thoả thuận": st["rate_max"]},
        "cafe_quota_per_month": {"Mới": st["cafe_quota_new"], "Bạc": st["cafe_quota_silver"]},
        "hold_days": st["hold_days"],
        "share_months": st["share_months"],
        "min_withdraw_vnd": st["min_withdraw"],
        "max_withdrawals_per_month": st.get("max_withdrawals_month"),
        "payout_days_of_month": st["payout_days"],
        "pit_threshold_vnd": st["tax_threshold"],
        "pit_rate_percent": st["tax_rate"],
        "verify_min_score": cfg.partner_min_score,
        "verify_sla_workdays": cfg.partner_sla_workdays,
        "submit_per_day": cfg.partner_submit_per_day,
        "duplicate_check_days": cfg.partner_dup_days,
        "max_images_per_submission": cfg.partner_attach_max,
        "note": "Doanh thu tính hoa hồng là doanh thu thuần đã tách thuế GTGT, trừ phần hoàn. Thuế TNCN chỉ khấu trừ với đối tác cá nhân.",
    }


def _opp_out(o: Opportunity) -> dict:
    from app.routes.public_opportunities import public_out

    d = public_out(o)
    keep = ("code", "title", "summary", "industry", "province", "region", "source_type", "scale", "estimated_value", "deadline",
            "days_left", "max_buyers", "sold_count", "remaining", "exclusive", "sold_out", "contact_count", "price_from", "trust", "urgency")
    out = {k: d[k] for k in keep}
    if len(out["summary"] or "") > 400:
        out["summary"] = out["summary"][:400] + "…"
    out["published"] = _d(o.published_at)
    out["url"] = f"/co-hoi/{o.code}"
    return out


def search_opportunities(ctx: Ctx, args: dict) -> dict:
    q = str(args.get("query") or "").strip()[:100]
    stmt = select(Opportunity).where(Opportunity.status == "published")
    for w in q.split()[:6]:
        like = f"%{w}%"
        stmt = stmt.where(or_(Opportunity.title.ilike(like), Opportunity.summary.ilike(like), Opportunity.code.ilike(like), Opportunity.industry.ilike(like)))
    if args.get("industry"):
        stmt = stmt.where(Opportunity.industry == str(args["industry"]))
    if args.get("region"):
        r = str(args["region"])
        stmt = stmt.where(or_(Opportunity.region == r, Opportunity.province.ilike(f"%{r}%")))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = ctx.db.scalars(
        stmt.options(selectinload(Opportunity.contacts)).order_by(Opportunity.published_at.desc().nullslast(), Opportunity.id.desc()).limit(_limit(args, 6, 10))
    ).unique().all()
    return {
        "total_matching": total,
        "shown": len(rows),
        "items": [_opp_out(o) for o in rows],
        "note": "Chỉ là phần xem trước công khai: tên bên có nhu cầu, chi tiết và đầu mối chỉ mở sau khi thành viên mua phiếu. "
                "price_from là giá thấp nhất; giá thật của mỗi thành viên tính theo điểm phù hợp riêng.",
        "list_url": "/co-hoi",
    }


def get_opportunity(ctx: Ctx, args: dict) -> dict:
    code = str(args.get("code") or "").strip().upper()
    if code.isdigit():
        code = f"CH-{int(code):06d}"
    o = ctx.db.scalar(select(Opportunity).options(selectinload(Opportunity.contacts)).where(Opportunity.code == code, Opportunity.status.in_(("published", "closed"))))
    if not o:
        raise ToolError(f"Không có cơ hội đang hiển thị với mã {code or '(trống)'}.")
    out = _opp_out(o)
    if ctx.audience == "member" and ctx.member:
        from app.services import catalog

        cid = ctx.member.company_id
        m = catalog.user_match(ctx.db, cid, o.id)
        prev = catalog.preview(o, o.id in catalog.purchased_ids(ctx.db, cid, [o.id]), match=m)
        out.update(my_score=prev["score"], my_price=prev["price"], my_reasons=prev.get("reasons") or [], purchased=prev["purchased"],
                   member_url=f"/thanh-vien/co-hoi/{o.id}")
    return out


def list_options(ctx: Ctx, args: dict) -> dict:
    from app.models import OPP_SOURCES
    from app.registration_form import CUSTOMER_SIZES

    return {"industries": INDUSTRIES, "regions": AREAS, "customer_sizes": CUSTOMER_SIZES, "opportunity_sources": OPP_SOURCES}


# ================================================================== thành viên (dữ liệu của chính doanh nghiệp)


def _member(ctx: Ctx) -> MemberUser:
    if ctx.audience != "member" or not ctx.member:
        raise ToolError("Công cụ này chỉ dùng khi đăng nhập cổng thành viên.")
    return ctx.member


def get_my_account(ctx: Ctx, args: dict) -> dict:
    from app import accounts
    from app.services import catalog, crm, tiers

    u = _member(ctx)
    c, db, cid = u.company, ctx.db, u.company_id
    count = lambda stmt: db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    t = tiers.tier_out(c)
    crm_ok, crm_reason = crm.access(c)
    return {
        "company": {"code": c.code, "name": c.name},
        "membership_active": catalog.membership_active(c),
        "membership_expires": _d(c.membership_expires_at),
        "points_balance": c.points_balance,
        "tier": t["label"], "topup_total_vnd": t["topup_total"], "to_gold_vnd": t["to_gold"], "can_buy_exclusive": t["can_exclusive"],
        "crm_lite": {"access": crm_ok, "reason": crm_reason},
        "purchased_tickets": count(select(Purchase.id).where(Purchase.company_id == cid)),
        "matched_opportunities": count(select(UserOpportunity.id).where(UserOpportunity.company_id == cid)),
        "saved_opportunities": count(select(SavedOpportunity.id).where(SavedOpportunity.company_id == cid)),
        "open_search_requests": count(select(SearchRequest.id).where(SearchRequest.company_id == cid, SearchRequest.status == "open")),
        "unread_new_matches": count(select(MemberNotification.id).where(MemberNotification.company_id == cid, MemberNotification.read_at.is_(None))),
        "pending_orders": count(select(PaymentOrder.id).where(PaymentOrder.company_id == cid, PaymentOrder.status == "pending", PaymentOrder.expires_at > utcnow())),
        "also_partner": bool(accounts.portals_of(u).get("partner")),
    }


def get_my_wallet(ctx: Ctx, args: dict) -> dict:
    u = _member(ctx)
    rows = ctx.db.scalars(
        select(WalletTransaction).where(WalletTransaction.company_id == u.company_id).order_by(WalletTransaction.id.desc()).limit(_limit(args, 10, 30))
    ).unique().all()
    return {
        "points_balance": u.company.points_balance,
        "transactions": [{"time": _d(t.created_at), "kind": TX_KINDS.get(t.kind, t.kind), "amount": t.amount, "balance_after": t.balance_after, "note": t.note} for t in rows],
        "page_url": "/thanh-vien/vi",
    }


def list_my_orders(ctx: Ctx, args: dict) -> dict:
    from app.services import payments

    u = _member(ctx)
    rows = ctx.db.scalars(select(PaymentOrder).where(PaymentOrder.company_id == u.company_id).order_by(PaymentOrder.id.desc()).limit(_limit(args, 8, 20))).unique().all()
    out = []
    for o in rows:
        payments.expire_if_due(o)
        inv = o.invoice
        out.append({
            "code": o.code, "kind": ORDER_KINDS.get(o.kind, o.kind), "amount_vnd": o.amount, "points": o.points,
            "status": ORDER_STATUSES.get(o.status, o.status), "created": _d(o.created_at), "paid": _d(o.paid_at),
            "expires": _d(o.expires_at) if o.status == "pending" else None,
            "promo_code": o.promo_code or None, "discount_vnd": o.discount or 0,
            "invoice": ({"status": "Đã xuất" if inv.status == "issued" else "Chờ xuất", "number": inv.invoice_number or None} if inv else "Chưa có thông tin xuất hoá đơn"),
            "url": f"/thanh-vien/nap-tien/{o.code}",
        })
    ctx.db.commit()
    return {"orders": out}


def list_my_search_requests(ctx: Ctx, args: dict) -> dict:
    u = _member(ctx)
    db = ctx.db
    rows = db.scalars(select(SearchRequest).where(SearchRequest.company_id == u.company_id).order_by(SearchRequest.id.desc()).limit(_limit(args, 8, 20))).unique().all()
    ids = [r.id for r in rows]
    counts = dict(db.execute(
        select(SearchRequestMatch.request_id, func.count()).join(Opportunity, Opportunity.id == SearchRequestMatch.opportunity_id)
        .where(SearchRequestMatch.request_id.in_(ids), Opportunity.status == "published").group_by(SearchRequestMatch.request_id)
    ).all()) if ids else {}
    new = dict(db.execute(
        select(MemberNotification.request_id, func.count()).where(MemberNotification.request_id.in_(ids), MemberNotification.read_at.is_(None))
        .group_by(MemberNotification.request_id)
    ).all()) if ids else {}
    return {
        "requests": [{
            "id": r.id, "created": _d(r.created_at), "status": SEARCH_STATUSES.get(r.status, r.status),
            "description": (r.note or "")[:300], "criteria": r.criteria or {}, "matched_opportunities": counts.get(r.id, 0),
            "new_unseen": new.get(r.id, 0), "leadscan_reply": r.reply or None, "match_status": r.match_status,
        } for r in rows],
        "page_url": "/thanh-vien/phu-hop",
    }


def list_my_purchases(ctx: Ctx, args: dict) -> dict:
    u = _member(ctx)
    rows = ctx.db.scalars(select(Purchase).where(Purchase.company_id == u.company_id).order_by(Purchase.id.desc()).limit(_limit(args, 8, 20))).unique().all()
    return {
        "purchases": [{
            "code": p.opportunity.code, "title": p.opportunity.title, "price_points": p.price, "exclusive": p.exclusive, "bought": _d(p.created_at),
            "refunded_points": p.refund_amount or 0, "refund_note": p.refund_note or None,
        } for p in rows],
        "note": "Chi tiết, tên bên có nhu cầu và đầu mối xem trong trang Phiếu đã mua (trợ lý không đọc đầu mối).",
        "page_url": "/thanh-vien/phieu",
    }


def list_my_matches(ctx: Ctx, args: dict) -> dict:
    from app.services import catalog

    u = _member(ctx)
    db, cid = ctx.db, u.company_id
    rows = db.scalars(
        select(Opportunity).options(selectinload(Opportunity.contacts))
        .join(UserOpportunity, (UserOpportunity.opportunity_id == Opportunity.id) & (UserOpportunity.company_id == cid))
        .where(Opportunity.status == "published")
        .order_by(UserOpportunity.score.desc(), UserOpportunity.created_at.desc())
        .limit(_limit(args, 6, 15))
    ).unique().all()
    items = catalog.previews(db, cid, rows)
    return {
        "items": [{
            "code": it["code"], "title": it["title"], "industry": it["industry"], "province": it["province"], "my_score": it["score"],
            "my_price": it["price"], "purchased": it["purchased"], "sold_out": it["sold_out"], "url": f"/thanh-vien/co-hoi/{it['id']}",
        } for it in items],
        "page_url": "/thanh-vien/co-hoi",
    }


# ================================================================== đối tác (dữ liệu của chính đối tác)


def _partner(ctx: Ctx) -> PartnerUser:
    if ctx.audience != "partner" or not ctx.partner:
        raise ToolError("Công cụ này chỉ dùng khi đăng nhập cổng đối tác.")
    return ctx.partner


def get_my_partner_account(ctx: Ctx, args: dict) -> dict:
    from app.models import PartnerMcpToken
    from app.services import partner_payouts, partner_wallet
    from app.services import partner_submissions as subs

    p = _partner(ctx)
    db = ctx.db
    partner_wallet.release_due(db, p.id)
    st = subs.partner_stats(db, p.id)
    today = db.scalar(select(func.count()).select_from(PartnerSubmission).where(
        PartnerSubmission.partner_id == p.id, PartnerSubmission.created_at > utcnow() - timedelta(hours=24))) or 0
    return {
        "code": p.code, "tier": PARTNER_TIERS.get(p.tier, p.tier), "kind": PARTNER_KINDS.get(p.kind, p.kind),
        "email_verified": bool(p.email_verified_at), "joined": _d(p.created_at),
        "wallet": partner_wallet.wallet_summary(db, p),
        "submissions_by_status": {SUBMISSION_STATUSES.get(k, k): v for k, v in st["by_status"].items()},
        "submitted_last_24h": today, "submit_limit_per_day": get_settings().partner_submit_per_day,
        "payout_profile_set": partner_payouts.get_profile(db, p.id) is not None,
        "ai_connection_active": db.scalar(select(PartnerMcpToken.id).where(PartnerMcpToken.partner_id == p.id, PartnerMcpToken.revoked_at.is_(None))) is not None,
        "wallet_note": "pending = Chờ duyệt, available = Khả dụng (rút được), withdrawing = Đang rút, paid = Đã rút; cafe_left = ly cafe còn trong tháng.",
    }


def list_my_submissions(ctx: Ctx, args: dict) -> dict:
    from app.routes.partner_mcp import ToolError as McpError
    from app.routes.partner_mcp import tool_list

    p = _partner(ctx)
    try:
        d = tool_list(ctx.db, p, {"status": args.get("status") or "", "limit": _limit(args, 10, 30)})
    except McpError as e:
        raise ToolError(str(e)) from e
    for it in d["items"]:
        it["created_at"], it["decided_at"], it["published_at"] = (_d_iso(it.get(k)) for k in ("created_at", "decided_at", "published_at"))
    d["page_url"] = "/doi-tac/co-hoi"
    return d


def _d_iso(s: str | None):
    if not s:
        return None
    from datetime import datetime

    return _d(datetime.fromisoformat(s.rstrip("Z")))


def get_my_submission(ctx: Ctx, args: dict) -> dict:
    from app.models import PartnerEvent
    from app.services import partner_submissions as subs

    p = _partner(ctx)
    code = str(args.get("code") or "").strip().upper()
    if code.isdigit():
        code = f"GT-{int(code):06d}"
    s = ctx.db.scalar(select(PartnerSubmission).where(PartnerSubmission.code == code, PartnerSubmission.partner_id == p.id))
    if not s:
        raise ToolError(f"Không tìm thấy cơ hội {code or '(trống)'} trong danh sách cơ hội bạn đã gửi.")
    events = ctx.db.scalars(select(PartnerEvent).where(PartnerEvent.submission_id == s.id).order_by(PartnerEvent.id)).unique().all()
    events = [e for e in events if e.kind in ("sub_created", "sub_edited", "sub_verifying", "sub_decided", "sub_published", "credit", "cafe_quota")]
    (_, money, until), = subs.with_money(ctx.db, [s])
    out = subs.partner_out(s, events, money=money, until=until)
    for k in ("id", "contact_name", "contact_title", "contact_phone", "contact_email", "evidence", "source_url", "tax_code"):
        out.pop(k, None)  # dữ liệu người liên hệ / bằng chứng không gửi ra AI bên ngoài
    out["need"] = (out.get("need") or "")[:500]
    for k in ("sla_due_at", "decided_at", "published_at", "created_at", "share_until"):
        out[k] = _d_iso(out.get(k))
    out["events"] = [{"time": _d_iso(e["created_at"]), "content": e["content"]} for e in out.get("events", [])]
    out["url"] = f"/doi-tac/co-hoi/{s.id}"
    return out


def list_my_withdrawals(ctx: Ctx, args: dict) -> dict:
    from app.models import WITHDRAWAL_STATUSES
    from app.services import partner_payouts, partner_wallet

    p = _partner(ctx)
    rows = ctx.db.scalars(select(PartnerWithdrawal).where(PartnerWithdrawal.partner_id == p.id).order_by(PartnerWithdrawal.id.desc()).limit(_limit(args, 8, 20))).unique().all()
    st = partner_wallet.settings(ctx.db)
    return {
        "withdrawals": [{
            "code": w.code, "status": WITHDRAWAL_STATUSES.get(w.status, w.status), "amount_vnd": w.amount, "tax_withheld_vnd": w.tax_withheld,
            "net_vnd": w.net_amount, "bank": w.payee.get("bank_name", ""), "reject_reason": w.reject_reason or None,
            "pay_date": w.batch.pay_date.strftime("%d/%m/%Y") if w.batch else None,
            "created": _d(w.created_at), "approved": _d(w.approved_at), "paid": _d(w.paid_at),
        } for w in rows],
        "next_pay_date": partner_payouts.next_pay_date(st).strftime("%d/%m/%Y"),
        "page_url": "/doi-tac/rut-tien",
    }


def list_open_needs(ctx: Ctx, args: dict) -> dict:
    from app.services import open_needs

    _partner(ctx)
    unmet = bool(args.get("unmet_only"))
    d = open_needs.list_needs(ctx.db, q=str(args.get("query") or "")[:100], industry=str(args.get("industry") or ""),
                              region=str(args.get("region") or ""), unmet=unmet, sort="unmet" if unmet else "new", page_size=_limit(args, 8, 20))
    for it in d["items"]:
        it["text"] = it["text"][:500]
    return {"total": d["total"], "stats": d["stats"], "items": d["items"], "page_url": "/doi-tac/nhu-cau",
            "note": "Ẩn danh: không có tên / liên hệ của thành viên. match_count = 0: chưa có cơ hội nào phù hợp — nên ưu tiên đi tìm."}


# ================================================================== khai báo cho mô hình (định dạng function calling)


def _schema(props: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props or {}, "required": required or [], "additionalProperties": False}


_LIMIT = {"type": "integer", "minimum": 1, "maximum": 20, "description": "Số dòng tối đa."}
_IND = {"type": "string", "description": "Ngành hàng, đúng tên trong danh mục (xem list_options). Bỏ trống = mọi ngành."}
_REG = {"type": "string", "description": "Khu vực / tỉnh thành (vd: Miền Bắc, Bắc Ninh). Bỏ trống = mọi nơi."}

# (tên, mô tả, schema, hàm, đối tượng được dùng)
TOOLS: list[tuple[str, str, dict, object, tuple[str, ...]]] = [
    ("get_pricing", "Bảng giá hiện hành: phí thành viên, số điểm nhận, thời hạn; gói nạp điểm; hạng Thường/Vàng và ngưỡng; hệ số mua độc quyền; "
     "công thức và tham số giá phiếu cơ hội. Gọi khi người dùng hỏi giá, phí, nạp tiền, hạng, độc quyền.",
     _schema(), get_pricing, AUDIENCES),
    ("get_partner_rewards", "Chính sách thưởng đối tác hiện hành: giá trị ly cafe, cách tính hoa hồng, tỷ lệ theo hạng, hạn mức ly cafe/tháng, "
     "số ngày giữ, số tháng chia sẻ, mức rút tối thiểu, ngày chi, thuế TNCN, điểm đạt xác minh, hạn xác minh, số cơ hội được gửi/ngày.",
     _schema(), get_partner_rewards, AUDIENCES),
    ("search_opportunities", "Tìm phiếu cơ hội đang bán trên sàn (phần xem trước công khai) theo từ khoá, ngành, khu vực. Trả tổng số khớp và vài cơ hội mới nhất.",
     _schema({"query": {"type": "string", "description": "Từ khoá mặt hàng / nhu cầu / mã CH-…"}, "industry": _IND, "region": _REG, "limit": _LIMIT}),
     search_opportunities, AUDIENCES),
    ("get_opportunity", "Xem phần công khai của 1 phiếu cơ hội theo mã CH-xxxxxx (với thành viên: kèm điểm phù hợp và giá riêng của họ).",
     _schema({"code": {"type": "string", "description": "Mã phiếu, vd CH-000123"}}, ["code"]), get_opportunity, AUDIENCES),
    ("list_options", "Danh mục ngành hàng, khu vực, quy mô khách hàng, loại nguồn cơ hội dùng trong hệ thống.", _schema(), list_options, AUDIENCES),
    ("get_my_account", "Tài khoản thành viên của người đang hỏi: hạn thành viên, số dư điểm, hạng, tổng đã nạp, quyền CRM, số phiếu đã mua, "
     "số cơ hội phù hợp, phiếu tìm đang chạy, đơn chờ thanh toán.", _schema(), get_my_account, ("member",)),
    ("get_my_wallet", "Số dư điểm và lịch sử cộng/trừ điểm gần nhất của doanh nghiệp người hỏi.", _schema({"limit": _LIMIT}), get_my_wallet, ("member",)),
    ("list_my_orders", "Đơn thanh toán (phí thành viên / nạp điểm) gần nhất: trạng thái, số tiền, mã đơn, hoá đơn điện tử.",
     _schema({"limit": _LIMIT}), list_my_orders, ("member",)),
    ("list_my_search_requests", "Các phiếu tìm cơ hội doanh nghiệp đã gửi: trạng thái, số cơ hội đã khớp, cơ hội mới chưa xem, phản hồi của LeadScan.",
     _schema({"limit": _LIMIT}), list_my_search_requests, ("member",)),
    ("list_my_purchases", "Phiếu cơ hội doanh nghiệp đã mua: mã, tiêu đề, giá, ngày mua, hoàn điểm (không có đầu mối).",
     _schema({"limit": _LIMIT}), list_my_purchases, ("member",)),
    ("list_my_matches", "Cơ hội đang bán phù hợp nhất với doanh nghiệp (điểm phù hợp, giá riêng, đã mua chưa).",
     _schema({"limit": _LIMIT}), list_my_matches, ("member",)),
    ("get_my_partner_account", "Tài khoản đối tác của người đang hỏi: mã, hạng, đã xác thực email chưa, số dư ví hoa hồng theo trạng thái, "
     "ly cafe còn lại tháng này, số cơ hội theo trạng thái, đã gửi bao nhiêu trong 24 giờ, đã có hồ sơ thanh toán chưa.",
     _schema(), get_my_partner_account, ("partner",)),
    ("list_my_submissions", "Cơ hội đối tác đã gửi, mới nhất trước: mã GT-…, trạng thái, điểm, lượt bán, tiền đã ghi.",
     _schema({"status": {"type": "string", "enum": ["", "open", *SUBMISSION_STATUSES],
                         "description": "open = đang chờ/đang xác minh; " + "; ".join(f"{k} = {v}" for k, v in SUBMISSION_STATUSES.items())},
              "limit": _LIMIT}), list_my_submissions, ("partner",)),
    ("get_my_submission", "Chi tiết 1 cơ hội đối tác đã gửi theo mã GT-xxxxxx: trạng thái, lý do không đạt, ghi chú của LeadScan, điểm, lịch sử, tiền thưởng.",
     _schema({"code": {"type": "string", "description": "Mã cơ hội, vd GT-000123"}}, ["code"]), get_my_submission, ("partner",)),
    ("list_my_withdrawals", "Lệnh rút tiền của đối tác: trạng thái, số tiền, thuế khấu trừ, thực nhận, ngày chi; và ngày chi kế tiếp.",
     _schema({"limit": _LIMIT}), list_my_withdrawals, ("partner",)),
    ("list_open_needs", "Nhu cầu thành viên đang tìm (ẩn danh): họ bán gì, cần tìm khách hàng / cơ hội nào, ngành, khu vực, đã có bao nhiêu cơ hội khớp. "
     "Dùng để gợi ý đối tác nên đi tìm doanh nghiệp có nhu cầu mua nào.",
     _schema({"query": {"type": "string", "description": "Từ khoá sản phẩm / khách hàng cần tìm"}, "industry": _IND, "region": _REG,
              "unmet_only": {"type": "boolean", "description": "Chỉ nhu cầu chưa có cơ hội phù hợp"}, "limit": _LIMIT}),
     list_open_needs, ("partner",)),
]
_BY_NAME = {t[0]: t for t in TOOLS}


def specs(audience: str) -> list[dict]:
    """Danh sách công cụ cho mô hình (định dạng OpenAI/Cohere v2 function calling)."""
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": s}} for n, d, s, _, aud in TOOLS if audience in aud]


def names(audience: str) -> list[str]:
    return [n for n, *_ , aud in TOOLS if audience in aud]


def run(ctx: Ctx, name: str, args: dict) -> dict:
    t = _BY_NAME.get(name)
    if not t or ctx.audience not in t[4]:
        return {"error": f"Không có công cụ {name}."}
    ctx.used.append(name)
    try:
        return t[3](ctx, args if isinstance(args, dict) else {})
    except ToolError as e:
        return {"error": str(e)}
