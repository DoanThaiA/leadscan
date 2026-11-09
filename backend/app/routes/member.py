"""API cổng thành viên: /api/member/*"""

import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import get_db, utcnow
from app.member_auth import create_session, current_member, destroy_session
from app.models import (
    OPP_SOURCES,
    Activity,
    EnrichRequest,
    InvoiceRequest,
    MemberNotification,
    MemberSession,
    MemberUser,
    Opportunity,
    PasswordReset,
    PaymentOrder,
    Profile,
    Purchase,
    SavedOpportunity,
    SearchRequest,
    SearchRequestMatch,
    UserOpportunity,
    WalletTransaction,
)
from app.registration_form import AREAS, CUSTOMER_SIZES, INDUSTRIES, REGIONS
from app.schemas import LoginIn, PasswordChangeIn
from app.schemas_commerce import EnrichIn, EnrichOut, InvoiceIn, OrderCreateIn, OrderOut, TxOut
from app.security import DUMMY_HASH, add_hit, client_ip, hash_password, origin_allowed, rate_limited, sha256, verify_password
from app.services import attachments, catalog, payments
from app.worker import enqueue, match_request_now, send_invoice_request_task, send_password_reset_task, send_search_request_task

router = APIRouter(prefix="/api/member")


def _me(user: MemberUser) -> dict:
    c = user.company
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "company": {
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "tax_code": c.tax_code,
            "address": ", ".join(x for x in (c.address, c.province) if x),
            "status": c.status,
            "points_balance": c.points_balance,
            "membership_expires_at": _iso(c.membership_expires_at),
            "membership_active": catalog.membership_active(c),
        },
    }


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


# ================================================================== đăng nhập


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    cfg = get_settings()
    if not origin_allowed(request, cfg):
        raise HTTPException(403, "Yêu cầu không hợp lệ.")
    key = "mlogin:" + sha256(client_ip(request, cfg))
    if rate_limited(db, key, cfg.login_attempts_per_15min, timedelta(minutes=15)):
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.")
    user = db.scalar(select(MemberUser).where(MemberUser.email == body.email.strip().lower()))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        add_hit(db, key)
        db.commit()
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    if not user.is_active or user.company.status in ("suspended", "rejected"):
        raise HTTPException(403, "Tài khoản đang bị khoá. Vui lòng liên hệ LeadScan.")
    create_session(db, user, request, response)
    return _me(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    destroy_session(db, request, response)


@router.get("/auth/me")
def me(user: MemberUser = Depends(current_member)):
    return _me(user)


@router.post("/auth/password", status_code=204)
def change_password(body: PasswordChangeIn, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")
    user.password_hash = hash_password(body.new_password)
    db.commit()


class ForgotIn(BaseModel):
    email: str = Field(max_length=150)


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=200)


@router.post("/auth/forgot")
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Luôn trả cùng một thông báo để không lộ email nào có tài khoản."""
    cfg = get_settings()
    key = "forgot:" + sha256(client_ip(request, cfg))
    if rate_limited(db, key, 5, timedelta(hours=1)):
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau.")
    add_hit(db, key)
    user = db.scalar(select(MemberUser).where(MemberUser.email == body.email.strip().lower(), MemberUser.is_active))
    if user:
        token = secrets.token_urlsafe(32)
        db.add(PasswordReset(token_hash=sha256(token), user_id=user.id, expires_at=utcnow() + timedelta(hours=1)))
        db.commit()
        enqueue(send_password_reset_task, user.email, user.full_name, token)
    db.commit()
    return {"ok": True, "message": "Nếu email có tài khoản, chúng tôi đã gửi liên kết đặt lại mật khẩu (hiệu lực 60 phút)."}


@router.post("/auth/reset", status_code=204)
def reset(body: ResetIn, db: Session = Depends(get_db)):
    pr = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == sha256(body.token)))
    if not pr or pr.used_at or pr.expires_at < utcnow():
        raise HTTPException(400, "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")
    user = db.get(MemberUser, pr.user_id)
    user.password_hash = hash_password(body.password)
    pr.used_at = utcnow()
    db.execute(delete(MemberSession).where(MemberSession.user_id == user.id))
    db.commit()


# ================================================================== tổng quan


@router.get("/dashboard")
def dashboard(user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    cid = user.company_id
    bought = db.scalar(select(func.count()).select_from(Purchase).where(Purchase.company_id == cid)) or 0
    spent = -(db.scalar(select(func.sum(WalletTransaction.amount)).where(WalletTransaction.company_id == cid, WalletTransaction.kind == "purchase")) or 0)
    recent = db.scalars(select(Purchase).where(Purchase.company_id == cid).order_by(Purchase.id.desc()).limit(5)).unique().all()
    mine = catalog.user_matches(db, cid, [p.opportunity_id for p in recent])
    newest = db.scalars(
        select(Opportunity)
        .options(selectinload(Opportunity.contacts))
        .join(UserOpportunity, and_(UserOpportunity.opportunity_id == Opportunity.id, UserOpportunity.company_id == cid))
        .where(Opportunity.status == "published")
        .order_by(UserOpportunity.created_at.desc(), UserOpportunity.score.desc())
        .limit(6)
    ).unique().all()
    pending_orders = db.scalar(select(func.count()).select_from(PaymentOrder).where(PaymentOrder.company_id == cid, PaymentOrder.status == "pending", PaymentOrder.expires_at > utcnow())) or 0
    return {
        "me": _me(user),
        "purchased_count": bought,
        "points_spent": spent,
        "pending_orders": pending_orders,
        "recent_purchases": [{"id": p.id, "price": p.price, "created_at": _iso(p.created_at), "opportunity": catalog.preview(p.opportunity, True, match=mine.get(p.opportunity_id))} for p in recent],
        "new_opportunities": catalog.previews(db, cid, newest),
        "saved_count": db.scalar(select(func.count()).select_from(SavedOpportunity).where(SavedOpportunity.company_id == cid, _visible(cid, SavedOpportunity.opportunity_id))) or 0,
        "matched_count": db.scalar(select(func.count()).select_from(UserOpportunity).where(UserOpportunity.company_id == cid)) or 0,
    }


# ================================================================== kho cơ hội


@router.get("/opportunities")
def list_opportunities(
    q: str = Query("", max_length=100),
    industry: str = "",
    region: str = "",
    source: str = "",
    min_score: int = Query(0, ge=0, le=100),
    max_price: int | None = Query(None, ge=0),
    only: str = "",  # "available" = còn lượt, "purchased" = đã mua
    sort: str = "new",  # new | score | price_asc | price_desc
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    user: MemberUser = Depends(current_member),
    db: Session = Depends(get_db),
):
    # Chỉ hiện cơ hội đã được so khớp với doanh nghiệp (từ các phiếu tìm cơ hội), kèm điểm riêng của họ
    cid = user.company_id
    mine_join = and_(UserOpportunity.opportunity_id == Opportunity.id, UserOpportunity.company_id == cid)
    stmt = select(Opportunity).join(UserOpportunity, mine_join).where(Opportunity.status.in_(("published", "closed")))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Opportunity.title.ilike(like), Opportunity.summary.ilike(like), Opportunity.code.ilike(like), Opportunity.province.ilike(like)))
    if industry:
        stmt = stmt.where(Opportunity.industry == industry)
    if region:
        stmt = stmt.where(Opportunity.region == region)
    if source:
        stmt = stmt.where(Opportunity.source_type == source)
    if min_score:
        stmt = stmt.where(UserOpportunity.score >= min_score)
    price_expr = Opportunity.price * (50 + UserOpportunity.score) / 100  # xấp xỉ matching.price_for (bỏ làm tròn nghìn)
    if max_price is not None:
        stmt = stmt.where(price_expr <= max_price)
    mine = select(Purchase.opportunity_id).where(Purchase.company_id == cid)
    if only == "purchased":
        stmt = stmt.where(Opportunity.id.in_(mine))
    elif only == "available":
        stmt = stmt.where(Opportunity.status == "published", Opportunity.sold_count < Opportunity.max_buyers, Opportunity.id.not_in(mine))
    else:
        # phiếu đã đóng chỉ hiện nếu mình đã mua
        stmt = stmt.where(or_(Opportunity.status == "published", Opportunity.id.in_(mine)))
    order = {
        "score": (UserOpportunity.score.desc(), Opportunity.id.desc()),
        "price_asc": (price_expr.asc(), Opportunity.id.desc()),
        "price_desc": (price_expr.desc(), Opportunity.id.desc()),
    }.get(sort, (Opportunity.published_at.desc(), Opportunity.id.desc()))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.options(selectinload(Opportunity.contacts)).order_by(*order).offset((page - 1) * page_size).limit(page_size)).unique().all()
    industries = db.scalars(
        select(Opportunity.industry).join(UserOpportunity, mine_join).where(Opportunity.status == "published", Opportunity.industry != "").distinct().order_by(Opportunity.industry)
    ).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": catalog.previews(db, cid, rows),
        "facets": {"industries": industries, "regions": REGIONS, "sources": OPP_SOURCES},
    }


def _visible(company_id: int, opp_id_col):
    """Điều kiện SQL: cơ hội doanh nghiệp được thấy = đã khớp phiếu tìm của họ hoặc đã mua."""
    return or_(
        opp_id_col.in_(select(UserOpportunity.opportunity_id).where(UserOpportunity.company_id == company_id)),
        opp_id_col.in_(select(Purchase.opportunity_id).where(Purchase.company_id == company_id)),
    )


def _get_opp(db: Session, opp_id: int, company_id: int) -> tuple[Opportunity, Purchase | None, UserOpportunity | None]:
    """Cơ hội doanh nghiệp được xem: đã được so khớp với doanh nghiệp (hoặc đã mua)."""
    o = db.get(Opportunity, opp_id)
    p = db.scalar(select(Purchase).where(Purchase.company_id == company_id, Purchase.opportunity_id == opp_id)) if o else None
    u = catalog.user_match(db, company_id, opp_id) if o else None
    if not o or o.status == "draft" or (o.status == "closed" and not p) or not (p or u):
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    return o, p, u


@router.get("/opportunities/{opp_id}")
def get_opportunity(opp_id: int, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    o, p, u = _get_opp(db, opp_id, user.company_id)
    if not p:
        saved = bool(catalog.saved_ids(db, user.company_id, [o.id]))
        # chưa mua: chỉ cho biết có bao nhiêu ảnh / tài liệu (mở khoá sau khi mua)
        return {"opportunity": catalog.preview(o, saved=saved, match=u), "purchase": None, "attachment_counts": attachments.counts(db, o.id)}
    enrich = db.scalars(select(EnrichRequest).where(EnrichRequest.purchase_id == p.id).order_by(EnrichRequest.id.desc())).unique().all()
    return {
        "opportunity": catalog.full(o, u),
        "attachments": [attachments.out(a) for a in attachments.for_opportunity(db, o.id)],  # link ký ngắn hạn
        "purchase": {"id": p.id, "price": p.price, "created_at": _iso(p.created_at), "enrich_requests": [EnrichOut.model_validate(e).model_dump(mode="json") for e in enrich]},
    }


@router.post("/opportunities/{opp_id}/purchase")
def purchase(opp_id: int, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    p = catalog.buy(db, user, opp_id)
    db.refresh(user.company)
    return {"ok": True, "purchase_id": p.id, "points_balance": user.company.points_balance}


@router.get("/purchases")
def list_purchases(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50), user: MemberUser = Depends(current_member), db: Session = Depends(get_db)
):
    base = select(Purchase).where(Purchase.company_id == user.company_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Purchase.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    mine = catalog.user_matches(db, user.company_id, [p.opportunity_id for p in rows])
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{"id": p.id, "price": p.price, "created_at": _iso(p.created_at), "opportunity": catalog.full(p.opportunity, mine.get(p.opportunity_id))} for p in rows],
    }


@router.post("/purchases/{purchase_id}/enrich", response_model=EnrichOut, status_code=201)
def request_enrich(purchase_id: int, body: EnrichIn, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    p = db.get(Purchase, purchase_id)
    if not p or p.company_id != user.company_id:
        raise HTTPException(404, "Không tìm thấy phiếu.")
    if db.scalar(select(EnrichRequest.id).where(EnrichRequest.purchase_id == p.id, EnrichRequest.status == "open")):
        raise HTTPException(409, "Phiếu này đang có yêu cầu enrich chờ xử lý.")
    e = EnrichRequest(purchase_id=p.id, note=body.note.strip())
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ================================================================== ví & nạp tiền


@router.get("/wallet")
def get_wallet(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: MemberUser = Depends(current_member), db: Session = Depends(get_db)
):
    cid = user.company_id
    base = select(WalletTransaction).where(WalletTransaction.company_id == cid)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    txs = db.scalars(base.order_by(WalletTransaction.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    orders = db.scalars(select(PaymentOrder).where(PaymentOrder.company_id == cid).order_by(PaymentOrder.id.desc()).limit(30)).unique().all()
    for o in orders:
        payments.expire_if_due(o)
    db.commit()
    return {
        "me": _me(user),
        "transactions": {"total": total, "page": page, "page_size": page_size, "items": [TxOut.model_validate(t).model_dump(mode="json", exclude={"actor"}) for t in txs]},
        "orders": [OrderOut.model_validate(o).model_dump(mode="json") for o in orders],
    }


@router.get("/packages")
def packages(user: MemberUser = Depends(current_member)):
    cfg = get_settings()
    return {
        "membership_active": catalog.membership_active(user.company),
        "membership_expires_at": _iso(user.company.membership_expires_at),
        "membership": {"amount": cfg.membership_fee, "points": cfg.membership_points, "days": cfg.membership_days},
        "topup": {"packs": cfg.topup_packs, "min": cfg.topup_min, "max": cfg.topup_max},
        "provider": cfg.payment_provider,
    }


@router.post("/orders", status_code=201)
def create_order(body: OrderCreateIn, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    cfg = get_settings()
    if body.kind == "membership":
        amount, points = cfg.membership_fee, cfg.membership_points
    else:
        if not catalog.membership_active(user.company):
            raise HTTPException(400, "Vui lòng thanh toán phí thành viên trước khi nạp thêm điểm.")
        amount = int(body.amount or 0)
        if not cfg.topup_min <= amount <= cfg.topup_max:
            raise HTTPException(400, f"Số tiền nạp phải từ {cfg.topup_min:,}đ đến {cfg.topup_max:,}đ.".replace(",", "."))
        points = amount
    order = payments.create_order(db, cfg, user.company_id, user.id, body.kind, amount, points)
    return {"order": OrderOut.model_validate(order).model_dump(mode="json"), "payment": payments.payment_info(order, cfg)}


def _my_order(db: Session, user: MemberUser, code: str) -> PaymentOrder:
    o = db.scalar(select(PaymentOrder).where(PaymentOrder.code == code.upper(), PaymentOrder.company_id == user.company_id))
    if not o:
        raise HTTPException(404, "Không tìm thấy đơn.")
    return o


@router.get("/orders/{code}")
def get_order(code: str, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    o = _my_order(db, user, code)
    payments.expire_if_due(o)
    db.commit()
    return {"order": OrderOut.model_validate(o).model_dump(mode="json"), "payment": payments.payment_info(o, get_settings()), "me": _me(user)}


@router.post("/orders/{code}/cancel")
def cancel_order(code: str, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    o = _my_order(db, user, code)
    if o.status != "pending":
        raise HTTPException(409, "Chỉ huỷ được đơn đang chờ thanh toán.")
    o.status = "cancelled"
    db.commit()
    return {"ok": True}


@router.post("/orders/{code}/simulate-paid")
def simulate_paid(code: str, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    """Chỉ có khi payment_provider = mock (chạy thử). Production dùng webhook InfoCMS."""
    cfg = get_settings()
    if cfg.payment_provider != "mock":
        raise HTTPException(404, "Không tồn tại.")
    o = _my_order(db, user, code)
    payments.expire_if_due(o)
    if o.status != "pending":
        raise HTTPException(409, "Đơn không còn chờ thanh toán.")
    payments.mark_paid(db, cfg, o, o.amount, f"MOCK-{o.code}", note="Giả lập thanh toán")
    return {"ok": True}


@router.post("/orders/{code}/invoice", status_code=201)
def request_invoice(code: str, body: InvoiceIn, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    o = _my_order(db, user, code)
    if o.status != "paid":
        raise HTTPException(400, "Chỉ yêu cầu xuất hoá đơn cho đơn đã thanh toán.")
    if o.invoice:
        raise HTTPException(409, "Đơn này đã gửi thông tin xuất hoá đơn.")
    inv = InvoiceRequest(order_id=o.id, **body.model_dump())
    db.add(inv)
    db.commit()
    db.refresh(inv)
    enqueue(send_invoice_request_task, inv.id)
    return {"ok": True, "invoice_id": inv.id}


# ================================================================== cơ hội phù hợp


def _norm_list(v: list[str], allowed: list[str] | None = None, limit: int = 20, max_len: int = 60) -> list[str]:
    out: list[str] = []
    for x in v:
        x = " ".join(str(x).split())[:max_len]
        if x and x not in out and (allowed is None or x in allowed):
            out.append(x)
    return out[:limit]


class MatchCriteria(BaseModel):
    industries: list[str] = Field(default_factory=list, max_length=50)
    regions: list[str] = Field(default_factory=list, max_length=50)
    sizes: list[str] = Field(default_factory=list, max_length=10)
    sources: list[str] = Field(default_factory=list, max_length=20)
    min_score: int = Field(0, ge=0, le=100)

    def cleaned(self) -> dict:
        return {
            "industries": _norm_list(self.industries),  # cho phép ngành tự nhập
            "regions": _norm_list(self.regions),
            "sizes": _norm_list(self.sizes, CUSTOMER_SIZES),
            "sources": _norm_list(self.sources, OPP_SOURCES),
            "min_score": self.min_score,
        }


def _criteria(user: MemberUser) -> dict:
    raw = (user.company.profile.search if user.company.profile else None) or {}
    try:
        return MatchCriteria.model_validate(raw).cleaned()
    except ValueError:
        return MatchCriteria().cleaned()


def _configured(c: dict) -> bool:
    return bool(c["industries"] or c["regions"] or c["sources"])


def _merge(*lists: list[str]) -> list[str]:
    return list(dict.fromkeys(x for lst in lists for x in lst))


@router.get("/match")
def get_match(user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    c = _criteria(user)
    opp_industries = db.scalars(
        select(Opportunity.industry).where(Opportunity.status == "published", Opportunity.industry != "").distinct().order_by(Opportunity.industry)
    ).all()
    return {
        "criteria": c,
        "configured": _configured(c),
        "options": {
            "industries": _merge(c["industries"], INDUSTRIES, opp_industries),
            "regions": _merge(AREAS, c["regions"]),
            "sizes": CUSTOMER_SIZES,
            "sources": OPP_SOURCES,
            "min_scores": [0, 60, 70, 80, 90],
        },
    }


# ================================================================== yêu cầu enrich tìm kiếm cơ hội

SEARCH_REQUESTS_PER_DAY = 10


class SearchRequestIn(MatchCriteria):
    note: str = Field(max_length=3000)


def _search_out(r: SearchRequest, match_count: int = 0, new_count: int = 0) -> dict:
    return {
        "new_count": new_count,  # cơ hội mới phù hợp khách chưa xem (tìm kiếm liên tục)
        "match_status": r.match_status,  # pending | running | done | error — so khớp chạy nền
        "matched_at": _iso(r.matched_at),
        "id": r.id,
        "criteria": r.criteria or {},
        "note": r.note,
        "status": r.status,
        "reply": r.reply,
        "created_at": _iso(r.created_at),
        "resolved_at": _iso(r.resolved_at),
        "match_count": match_count,
    }


def _match_counts(db: Session, req_ids: list[int]) -> dict[int, int]:
    if not req_ids:
        return {}
    return dict(
        db.execute(
            select(SearchRequestMatch.request_id, func.count())
            .join(Opportunity, Opportunity.id == SearchRequestMatch.opportunity_id)
            .where(SearchRequestMatch.request_id.in_(req_ids), Opportunity.status == "published")
            .group_by(SearchRequestMatch.request_id)
        ).all()
    )


def _live_notifications(company_id: int):
    """Thông báo cơ hội mới của doanh nghiệp mà cơ hội vẫn đang bán và vẫn khớp phiếu tìm."""
    return (
        select(MemberNotification)
        .join(Opportunity, Opportunity.id == MemberNotification.opportunity_id)
        .join(
            SearchRequestMatch,
            (SearchRequestMatch.request_id == MemberNotification.request_id) & (SearchRequestMatch.opportunity_id == MemberNotification.opportunity_id),
        )
        .where(MemberNotification.company_id == company_id, Opportunity.status == "published")
    )


def _new_counts(db: Session, company_id: int, req_ids: list[int]) -> dict[int, int]:
    if not req_ids:
        return {}
    sub = _live_notifications(company_id).where(MemberNotification.read_at.is_(None), MemberNotification.request_id.in_(req_ids)).subquery()
    return dict(db.execute(select(sub.c.request_id, func.count()).group_by(sub.c.request_id)).all())


@router.get("/search-requests")
def list_search_requests(limit: int = Query(30, ge=1, le=100), user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SearchRequest).where(SearchRequest.company_id == user.company_id).order_by(SearchRequest.id.desc()).limit(limit)
    ).unique().all()
    ids = [r.id for r in rows]
    counts, new = _match_counts(db, ids), _new_counts(db, user.company_id, ids)
    return {"items": [_search_out(r, counts.get(r.id, 0), new.get(r.id, 0)) for r in rows]}


@router.get("/search-requests/{req_id}/opportunities")
def search_request_opportunities(
    req_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: MemberUser = Depends(current_member),
    db: Session = Depends(get_db),
):
    """Bấm vào một phiếu tìm cơ hội → các cơ hội phù hợp với phiếu đó (điểm tính theo chính phiếu này)."""
    r = db.get(SearchRequest, req_id)
    if not r or r.company_id != user.company_id:
        raise HTTPException(404, "Không tìm thấy yêu cầu.")
    base = (
        select(SearchRequestMatch)
        .join(Opportunity, Opportunity.id == SearchRequestMatch.opportunity_id)
        .where(SearchRequestMatch.request_id == r.id, Opportunity.status == "published")
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(SearchRequestMatch.score.desc(), SearchRequestMatch.id).offset((page - 1) * page_size).limit(page_size)).unique().all()
    opps = [m.opportunity for m in rows]
    items = catalog.previews(db, user.company_id, opps, scores={m.opportunity_id: m for m in rows})
    # cơ hội mới khách chưa xem → gắn nhãn "Mới" (cổng gọi POST .../seen sau khi hiển thị để đánh dấu đã xem)
    fresh = set(db.scalars(select(MemberNotification.opportunity_id).where(MemberNotification.request_id == r.id, MemberNotification.read_at.is_(None))))
    for it in items:
        it["is_new"] = it["id"] in fresh
    return {"request": _search_out(r, total), "total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/search-requests/{req_id}/seen", status_code=204)
def search_request_seen(req_id: int, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    """Khách đã mở phiếu → các cơ hội mới của phiếu tính là đã xem (chuông và số "mới" giảm)."""
    r = db.get(SearchRequest, req_id)
    if not r or r.company_id != user.company_id:
        raise HTTPException(404, "Không tìm thấy yêu cầu.")
    db.execute(update(MemberNotification).where(MemberNotification.request_id == r.id, MemberNotification.read_at.is_(None)).values(read_at=utcnow()))
    db.commit()


@router.post("/search-requests", status_code=201)
def create_search_request(
    body: SearchRequestIn, background: BackgroundTasks, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)
):
    note = body.note.strip()
    if len(note) < 10:
        raise HTTPException(422, "Vui lòng mô tả rõ yêu cầu (ít nhất 10 ký tự).")
    c = user.company
    recent = db.scalar(
        select(func.count()).select_from(SearchRequest).where(SearchRequest.company_id == c.id, SearchRequest.created_at > utcnow() - timedelta(days=1))
    )
    if (recent or 0) >= SEARCH_REQUESTS_PER_DAY:
        raise HTTPException(429, f"Mỗi ngày gửi tối đa {SEARCH_REQUESTS_PER_DAY} yêu cầu. Vui lòng thử lại sau.")
    criteria = body.cleaned()
    r = SearchRequest(company_id=c.id, member_user_id=user.id, criteria=criteria, note=note)
    db.add(r)
    # nhớ tiêu chí để điền sẵn cho lần sau
    if c.profile is None:
        c.profile = Profile()
    c.profile.search = criteria
    db.add(Activity(company_id=c.id, kind="update", content=f"{user.full_name} gửi yêu cầu tìm cơ hội: {note[:200]}"))
    db.commit()
    # So khớp NGAY trong lúc gửi: nhúng Cohere → ứng viên pgvector → chấm điểm hybrid riêng cho doanh nghiệp
    # → thêm cơ hội phù hợp vào Tất cả cơ hội + Kho. Khách thấy kết quả liền, không chờ quản trị duyệt.
    match_request_now(r.id)
    background.add_task(enqueue, send_search_request_task, r.id)  # email báo quản trị: gửi sau khi đã trả kết quả cho khách
    db.refresh(r)
    return _search_out(r, _match_counts(db, [r.id]).get(r.id, 0))


# ================================================================== thông báo (cơ hội mới phù hợp)


@router.get("/notifications")
def list_notifications(limit: int = Query(20, ge=1, le=50), user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    base = _live_notifications(user.company_id)
    unread = db.scalar(select(func.count()).select_from(base.where(MemberNotification.read_at.is_(None)).subquery())) or 0
    rows = db.scalars(base.order_by(MemberNotification.id.desc()).limit(limit)).unique().all()
    reqs = {r.id: r for r in db.scalars(select(SearchRequest).where(SearchRequest.id.in_({n.request_id for n in rows if n.request_id}))).unique()}
    items = []
    for n in rows:
        o, r = n.opportunity, reqs.get(n.request_id)
        items.append({
            "id": n.id,
            "kind": n.kind,
            "created_at": _iso(n.created_at),
            "read": n.read_at is not None,
            "score": n.score,
            "request": {"id": r.id, "note": (r.note or "")[:140]} if r else None,
            "opportunity": {"id": o.id, "code": o.code, "title": o.title, "industry": o.industry, "province": o.province},
        })
    return {"unread": unread, "items": items}


@router.post("/notifications/read-all", status_code=204)
def read_all_notifications(user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    db.execute(update(MemberNotification).where(MemberNotification.company_id == user.company_id, MemberNotification.read_at.is_(None)).values(read_at=utcnow()))
    db.commit()


@router.post("/notifications/{notif_id}/read", status_code=204)
def read_notification(notif_id: int, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    n = db.get(MemberNotification, notif_id)
    if not n or n.company_id != user.company_id:
        raise HTTPException(404, "Không tìm thấy thông báo.")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()


# ================================================================== kho của tôi (cơ hội đã lưu)


@router.get("/saved")
def list_saved(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50), user: MemberUser = Depends(current_member), db: Session = Depends(get_db)
):
    base = (
        select(SavedOpportunity)
        .join(Opportunity, Opportunity.id == SavedOpportunity.opportunity_id)
        .where(SavedOpportunity.company_id == user.company_id, Opportunity.status != "draft", _visible(user.company_id, Opportunity.id))
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(SavedOpportunity.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    items = catalog.previews(db, user.company_id, [r.opportunity for r in rows])
    for it, r in zip(items, rows):
        it["saved_at"] = _iso(r.created_at)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/saved/{opp_id}", status_code=201)
def save_opportunity(opp_id: int, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    o, _, _ = _get_opp(db, opp_id, user.company_id)
    exists = db.scalar(select(SavedOpportunity.id).where(SavedOpportunity.company_id == user.company_id, SavedOpportunity.opportunity_id == o.id))
    if not exists:
        db.add(SavedOpportunity(company_id=user.company_id, opportunity_id=o.id, member_user_id=user.id))
        try:
            db.commit()
        except IntegrityError:  # bấm 2 lần cùng lúc
            db.rollback()
    return {"ok": True, "saved": True}


@router.delete("/saved/{opp_id}", status_code=204)
def unsave_opportunity(opp_id: int, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    db.execute(delete(SavedOpportunity).where(SavedOpportunity.company_id == user.company_id, SavedOpportunity.opportunity_id == opp_id))
    db.commit()
