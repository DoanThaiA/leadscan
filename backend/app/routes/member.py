"""API cổng thành viên: /api/member/*"""

import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import get_db, utcnow
from app import accounts
from app.member_auth import current_member
from app.models import (
    OPP_SOURCES,
    Activity,
    Contact,
    EnrichRequest,
    InvoiceRequest,
    MemberNotification,
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
from app.registration_form import AREAS, CUSTOMER_SIZES, INDUSTRIES, MAX_INDUSTRIES, REGIONS, SIZES, clean1, pick_industries
from app.registration_form import _valid_url as valid_url
from app.schemas import LoginIn, PasswordChangeIn
from app.schemas_commerce import EnrichIn, EnrichOut, InvoiceIn, OrderCreateIn, OrderOut, TxOut
from app.security import add_hit, client_ip, hash_password, origin_allowed, rate_limited, sha256, verify_password
from app.services import attachments, catalog, mcv_payments, payments, promos, tiers
from app.services import products as prod
from app.services.mcv import McvClient, McvError
from app.worker import enqueue, issue_einvoice_task, match_request_now, send_invoice_request_task, send_password_reset_task, send_search_request_task

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
            "tier": tiers.tier_out(c),
        },
        "portals": accounts.portals_of(user),  # cùng email dùng được cổng nào (hiện nút chuyển cổng)
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
    # 1 tài khoản cho cả 2 cổng: mở phiên thành viên + phiên đối tác (nếu email có hồ sơ đối tác)
    user, partner = accounts.authenticate(db, body.email, body.password)
    if not user and not partner:
        add_hit(db, key)
        db.commit()
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    if user and not accounts.member_usable(user):
        raise HTTPException(403, "Tài khoản đang bị khoá. Vui lòng liên hệ LeadScan.")
    if not user and not accounts.partner_usable(partner):
        raise HTTPException(403, "Tài khoản đối tác đang bị khoá. Vui lòng liên hệ LeadScan.")
    accounts.open_sessions(db, user, partner, request, response)
    if not user:  # chỉ có hồ sơ đối tác → trang đăng nhập cho chọn vào cổng đối tác hoặc đăng ký thành viên
        return {"portals": {"member": False, "partner": True}, "redirect": accounts.PARTNER_HOME if partner.email_verified_at else "/doi-tac/xac-thuc"}
    return _me(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    accounts.logout_all(db, request, response)  # đăng xuất cả cổng đối tác (cùng 1 tài khoản)


@router.get("/auth/me")
def me(user: MemberUser = Depends(current_member)):
    return _me(user)


@router.post("/auth/password", status_code=204)
def change_password(body: PasswordChangeIn, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")
    accounts.sync_password(db, user.email, hash_password(body.new_password), end_sessions=False)  # áp dụng cả cổng đối tác
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
    pr.used_at = utcnow()
    accounts.sync_password(db, user.email, hash_password(body.password), end_sessions=True)  # cả 2 cổng
    db.commit()


# ================================================================== thông tin tài khoản & doanh nghiệp

# Thành viên tự sửa được: tên người dùng, thông tin doanh nghiệp (trừ mã số thuế), người liên hệ chính.
# Mã số thuế và email đăng nhập gắn với định danh / hoá đơn / đăng nhập → đổi qua LeadScan.
PROFILE_LABELS = {
    "full_name": "Họ tên người dùng", "company_name": "Tên doanh nghiệp", "industries": "Ngành hàng", "company_size": "Quy mô",
    "province": "Tỉnh/thành", "address": "Địa chỉ", "website": "Website",
    "contact_name": "Người liên hệ", "contact_position": "Chức vụ", "contact_phone": "SĐT liên hệ",
}


def _primary_contact(db: Session, company_id: int) -> Contact | None:
    return db.scalar(select(Contact).where(Contact.company_id == company_id).order_by(Contact.is_primary.desc(), Contact.id).limit(1))


def _profile(db: Session, user: MemberUser) -> dict:
    c = user.company
    ct = _primary_contact(db, c.id)
    return {
        "full_name": user.full_name,
        "email": user.email,
        "company_name": c.name,
        "tax_code": c.tax_code,
        "industries": [x.strip() for x in (c.industry or "").split(",") if x.strip()],
        "company_size": c.company_size,
        "province": c.province,
        "address": c.address,
        "website": c.website,
        "contact_name": ct.full_name if ct else "",
        "contact_position": ct.position if ct else "",
        "contact_phone": ct.phone if ct else "",
        "options": {"industries": INDUSTRIES, "sizes": SIZES, "max_industries": MAX_INDUSTRIES},
    }


@router.get("/profile")
def get_profile(user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    return _profile(db, user)


@router.put("/profile")
def update_profile(raw: dict, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    """Lưu thông tin; lỗi → 422 {detail, fields}. Mỗi thay đổi ghi vào lịch sử khách hàng để LeadScan theo dõi."""
    d = {
        "full_name": clean1(raw.get("full_name"), 100),
        "company_name": clean1(raw.get("company_name"), 150),
        "industries": pick_industries(raw) if isinstance(raw.get("industries"), list) else [],
        "company_size": clean1(raw.get("company_size"), 40),
        "province": clean1(raw.get("province"), 80),
        "address": clean1(raw.get("address"), 200),
        "website": clean1(raw.get("website"), 200),
        "contact_name": clean1(raw.get("contact_name"), 100),
        "contact_position": clean1(raw.get("contact_position"), 100),
        "contact_phone": re.sub(r"[\s.\-()]", "", clean1(raw.get("contact_phone"), 20)),
    }
    errors: dict[str, str] = {}
    for k, msg in (("full_name", "Vui lòng nhập họ tên."), ("company_name", "Vui lòng nhập tên doanh nghiệp."),
                   ("province", "Vui lòng nhập tỉnh/thành."), ("contact_name", "Vui lòng nhập họ tên người liên hệ.")):
        if not d[k]:
            errors[k] = msg
    if not d["industries"]:
        errors["industries"] = "Vui lòng chọn ít nhất 1 ngành hàng."
    elif isinstance(raw.get("industries"), list) and len({str(x).strip().lower() for x in raw["industries"] if str(x).strip()}) > MAX_INDUSTRIES:
        errors["industries"] = f"Chọn tối đa {MAX_INDUSTRIES} ngành hàng."
    if d["company_size"] not in SIZES:
        errors["company_size"] = "Vui lòng chọn quy mô."
    if d["contact_phone"] and not re.fullmatch(r"(0|\+84)\d{9,10}", d["contact_phone"]):
        errors["contact_phone"] = "Số điện thoại chưa đúng định dạng."
    if d["website"]:
        w = d["website"] if re.match(r"^https?://", d["website"], re.I) else "https://" + d["website"]
        if valid_url(w):
            d["website"] = w
        else:
            errors["website"] = "Website chưa đúng định dạng."
    if errors:
        return JSONResponse({"detail": "Vui lòng kiểm tra lại thông tin.", "fields": errors}, status_code=422)

    c = user.company
    ct = _primary_contact(db, c.id)
    before = _profile(db, user)
    user.full_name = d["full_name"]
    c.name, c.industry, c.company_size = d["company_name"], ", ".join(d["industries"])[:300], d["company_size"]
    c.province, c.address, c.website = d["province"], d["address"], d["website"]
    if not ct:
        ct = Contact(company_id=c.id, email=user.email, is_primary=True)
        db.add(ct)
    ct.full_name, ct.position, ct.phone = d["contact_name"], d["contact_position"], d["contact_phone"]

    changes = []
    for k, label in PROFILE_LABELS.items():
        old, new = before[k], d[k]
        if old != new:
            fmt = (lambda v: ", ".join(v)) if k == "industries" else (lambda v: v or "(trống)")
            changes.append(f"{label}: {fmt(old)} → {fmt(new)}")
    if changes:
        db.add(Activity(company_id=c.id, kind="update", content=f"{user.full_name} tự cập nhật thông tin — " + "; ".join(changes)[:3800]))
    db.commit()
    return {"me": _me(user), "profile": _profile(db, user), "changed": len(changes)}


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
    mine = select(Purchase.opportunity_id).where(Purchase.company_id == cid)
    if only == "purchased":
        stmt = stmt.where(Opportunity.id.in_(mine))
    elif only == "available":
        stmt = stmt.where(Opportunity.status == "published", Opportunity.sold_count < Opportunity.max_buyers, Opportunity.id.not_in(mine))
    else:
        # phiếu đã đóng chỉ hiện nếu mình đã mua
        stmt = stmt.where(or_(Opportunity.status == "published", Opportunity.id.in_(mine)))
    stmt = stmt.options(selectinload(Opportunity.contacts))

    if max_price is not None or sort in ("price_asc", "price_desc"):
        # Giá phụ thuộc điểm, hạn chót, độ đủ thông tin, giá trị đơn hàng (catalog.price_of) — lọc/sắp xếp đúng giá hiển thị
        # bằng Python trên các cơ hội đã khớp của doanh nghiệp (số lượng nhỏ), rồi mới phân trang.
        items = catalog.previews(db, cid, db.scalars(stmt.order_by(Opportunity.id.desc())).unique().all())
        if max_price is not None:
            items = [it for it in items if it["price"] <= max_price]
        if sort in ("price_asc", "price_desc"):
            items.sort(key=lambda it: it["price"], reverse=sort == "price_desc")
        total, items = len(items), items[(page - 1) * page_size : page * page_size]
    else:
        order = {"score": (UserOpportunity.score.desc(), Opportunity.id.desc())}.get(sort, (Opportunity.published_at.desc(), Opportunity.id.desc()))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = catalog.previews(db, cid, db.scalars(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)).unique().all())
    industries = db.scalars(
        select(Opportunity.industry).join(UserOpportunity, mine_join).where(Opportunity.status == "published", Opportunity.industry != "").distinct().order_by(Opportunity.industry)
    ).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
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
        pv = catalog.preview(o, saved=saved, match=u)
        return {"opportunity": pv, "purchase": None, "attachment_counts": attachments.counts(db, o.id),
                "exclusive": tiers.exclusive_offer(user.company, o, pv["price"])}
    enrich = db.scalars(select(EnrichRequest).where(EnrichRequest.purchase_id == p.id).order_by(EnrichRequest.id.desc())).unique().all()
    return {
        "opportunity": catalog.full(o, u),
        "attachments": [attachments.out(a) for a in attachments.for_opportunity(db, o.id)],  # link ký ngắn hạn
        "purchase": {
            **{k: v for k, v in catalog.purchase_out(p).items() if k != "opportunity"},
            "enrich_requests": [EnrichOut.model_validate(e).model_dump(mode="json") for e in enrich],
        },
    }


@router.post("/opportunities/{opp_id}/open-shared")
def open_shared(opp_id: int, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    """Thành viên bấm "Mua" trên trang công khai /co-hoi/<mã>: cơ hội chưa so khớp với doanh nghiệp → thêm vào "Tất cả cơ hội"
    + Kho của tôi (đánh dấu via_share, so khớp lại không xoá) để xem & mua. Điểm phù hợp = 0 phần khớp yêu cầu → giá cơ bản."""
    from datetime import date as _date

    from app.services.matching import _trust, urgency_of

    o = db.get(Opportunity, opp_id)
    if not o or o.status != "published":
        raise HTTPException(404, "Cơ hội không còn mở bán.")
    cid = user.company_id
    if catalog.user_match(db, cid, o.id) is None and not db.scalar(select(Purchase.id).where(Purchase.company_id == cid, Purchase.opportunity_id == o.id)):
        urg, trust = urgency_of(o, _date.today()), _trust(o)
        db.add(UserOpportunity(company_id=cid, opportunity_id=o.id, score=0, score_fit=0,  # chưa so khớp với yêu cầu → điểm phù hợp 0 (giá cơ bản)
                               score_urgency=urg, score_trust=trust, via_share=True,
                               reasons=["Bạn mở cơ hội này từ liên kết chia sẻ — chưa so khớp với yêu cầu tìm cơ hội của bạn"]))
        if not catalog.saved_ids(db, cid, [o.id]):
            db.add(SavedOpportunity(company_id=cid, opportunity_id=o.id, member_user_id=user.id))
        db.commit()
    return {"id": o.id}


class PurchaseIn(BaseModel):
    exclusive: bool = False  # mua độc quyền (hạng Vàng)


@router.post("/opportunities/{opp_id}/purchase")
def purchase(opp_id: int, body: PurchaseIn | None = None, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    p = catalog.buy(db, user, opp_id, exclusive=bool(body and body.exclusive))
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
        "items": [catalog.purchase_out(p, mine.get(p.opportunity_id)) for p in rows],
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
    promo, discount = None, 0
    if body.promo_code.strip():  # khoá dòng mã tới khi tạo xong đơn → không vượt số lượt
        promo, discount = promos.check(db, body.promo_code, body.kind, amount, user.company_id, lock=True)
    order = payments.create_order(db, cfg, user.company_id, user.id, body.kind, amount, points, promo=promo, discount=discount)
    if order.amount <= 0:  # mã khuyến mãi giảm hết → không cần thanh toán, kích hoạt luôn
        payments.activate_free(db, cfg, order)
        db.refresh(order)
        db.refresh(user.company)
        return {"order": OrderOut.model_validate(order).model_dump(mode="json"), "payment": _payment_info(db, order), "me": _me(user)}
    error = ""
    if order.provider == "mcv":  # xin MCV mã QR ngay; lỗi thì đơn vẫn còn, trang thanh toán có nút "Tạo mã QR"
        try:
            mcv_payments.start_payment(db, cfg, order)
        except McvError as e:
            error = _mcv_error_text(e)
    return {"order": OrderOut.model_validate(order).model_dump(mode="json"), "payment": _payment_info(db, order, error=error)}


class PromoCheckIn(BaseModel):
    code: str = Field(max_length=40)
    kind: str
    amount: int | None = None  # chỉ dùng cho topup


@router.post("/promo/check")
def check_promo(body: PromoCheckIn, request: Request, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    """Xem trước mã khuyến mãi cho đơn sắp tạo: số tiền giảm và số tiền còn phải trả."""
    cfg = get_settings()
    key = "promo:" + str(user.company_id)
    if rate_limited(db, key, 30, timedelta(minutes=15)):  # chặn dò mã
        raise HTTPException(429, "Bạn thử mã quá nhiều lần. Vui lòng thử lại sau ít phút.")
    if body.kind == "membership":
        amount = cfg.membership_fee
    elif body.kind == "topup":
        amount = int(body.amount or 0)
    else:
        raise HTTPException(400, "Loại đơn không hợp lệ.")
    try:
        p, discount = promos.check(db, body.code, body.kind, amount, user.company_id)
    except HTTPException:
        add_hit(db, key)
        db.commit()
        raise
    return {
        "code": p.code,
        "name": p.name,
        "description": promos.describe(p),
        "amount": amount,
        "discount": discount,
        "pay": max(0, amount - discount),
    }


def _mcv_error_text(e: McvError) -> str:
    if e.status == 429:
        return "Cổng thanh toán đang bận, vui lòng thử lại sau ít phút."
    if e.code == "not_configured":
        return "Cổng thanh toán chưa được cấu hình. Vui lòng liên hệ LeadScan để được hỗ trợ thanh toán."
    return f"Chưa tạo được mã thanh toán: {e.message}"


def _payment_info(db: Session, o: PaymentOrder, *, refresh: bool = False, payment_code: str = "", error: str = "") -> dict:
    """Thông tin thanh toán của đơn. Đơn MCV: tra trạng thái với MCV (tối đa 1 lần/5 giây) — trình duyệt không gọi MCV."""
    cfg = get_settings()
    if o.provider != "mcv":
        return payments.payment_info(o, cfg)
    mp = None
    if payment_code:  # trang kết quả (return_url): tra đúng payment_code MCV gửi về, không tin status trên URL
        mp = mcv_payments.lookup_for_order(db, cfg, o, payment_code)
    latest = mcv_payments.latest(db, o)
    if refresh and latest and mcv_payments.configured(cfg):
        latest = mcv_payments.refresh(db, cfg, latest)
    db.refresh(o)
    return mcv_payments.payment_info(db, cfg, o, mp or latest, error=error)


def _my_order(db: Session, user: MemberUser, code: str) -> PaymentOrder:
    o = db.scalar(select(PaymentOrder).where(PaymentOrder.code == code.upper(), PaymentOrder.company_id == user.company_id))
    if not o:
        raise HTTPException(404, "Không tìm thấy đơn.")
    return o


@router.get("/orders/{code}")
def get_order(
    code: str,
    payment_code: str = Query("", max_length=100, pattern=r"^[A-Za-z0-9._:-]*$"),
    user: MemberUser = Depends(current_member),
    db: Session = Depends(get_db),
):
    o = _my_order(db, user, code)
    payments.expire_if_due(o)
    db.commit()
    payment = _payment_info(db, o, refresh=o.status in ("pending", "expired", "cancelled"), payment_code=payment_code)
    db.refresh(user.company)
    return {"order": OrderOut.model_validate(o).model_dump(mode="json"), "payment": payment, "me": _me(user)}


@router.post("/orders/{code}/mcv")
def renew_mcv_payment(code: str, user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    """Tạo (lại) mã QR MCV cho đơn đang chờ — dùng khi QR cũ hết hạn hoặc lần tạo trước bị lỗi."""
    cfg = get_settings()
    o = _my_order(db, user, code)
    payments.expire_if_due(o)
    db.commit()
    if o.provider != "mcv":
        raise HTTPException(404, "Không tồn tại.")
    if o.status != "pending":
        raise HTTPException(409, "Đơn không còn chờ thanh toán — vui lòng tạo đơn mới.")
    try:
        mcv_payments.start_payment(db, cfg, o)
    except McvError as e:
        raise HTTPException(429 if e.status == 429 else 502, _mcv_error_text(e)) from None
    return {"order": OrderOut.model_validate(o).model_dump(mode="json"), "payment": _payment_info(db, o)}


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
    """Chỉ cho môi trường chạy thử: provider mock (giả lập tại chỗ) hoặc MCV với khoá test + cho phép test_mode.
    Production dùng webhook MCV/InfoCMS."""
    cfg = get_settings()
    if cfg.payment_provider == "mcv" and mcv_payments.can_simulate(cfg):
        o = _my_order(db, user, code)
        mp = mcv_payments.latest(db, o) if o.provider == "mcv" else None
        if not mp or mp.status == "paid":
            raise HTTPException(409, "Đơn không có mã thanh toán MCV đang chờ.")
        try:
            # MCV gửi webhook thật (test_mode: true). Máy dev thường không nhận được webhook (localhost)
            # → tra trạng thái ngay để ghi nhận; webhook tới sau sẽ là "duplicate".
            McvClient(cfg).simulate_paid(mp.payment_code)
        except McvError as e:
            raise HTTPException(502, _mcv_error_text(e)) from None
        mcv_payments.refresh(db, cfg, mp, force=True)
        return {"ok": True}
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
    if o.amount <= 0:
        raise HTTPException(400, "Đơn miễn phí (0đ) không xuất hoá đơn.")
    if o.invoice:
        raise HTTPException(409, "Đơn này đã gửi thông tin xuất hoá đơn.")
    inv = InvoiceRequest(order_id=o.id, **body.model_dump())
    db.add(inv)
    try:
        db.commit()
    except IntegrityError:  # hệ thống vừa tự tạo yêu cầu hoá đơn cho đơn này
        db.rollback()
        raise HTTPException(409, "Đơn này đã có thông tin xuất hoá đơn.") from None
    db.refresh(inv)
    if get_settings().iam_enabled:
        enqueue(issue_einvoice_task, inv.id)  # tự xuất hoá đơn điện tử IAM (lỗi → email kế toán)
    else:
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


def _understood(note: str, regions: list[str]) -> dict:
    """Hệ thống hiểu mô tả của khách thế nào: sản phẩm cụ thể, địa điểm — và cảnh báo khi mâu thuẫn với ô tiêu chí."""
    products, places = prod.product_names(prod.find_products(note)), prod.find_places(note)
    warning = ""
    if places and regions:
        place_regions = set(places) | {prod.province_region(x) for x in places}
        if not place_regions & set(regions) and "Toàn quốc" not in regions:
            warning = (
                f"Bạn chọn khu vực {', '.join(regions)} nhưng mô tả ghi {', '.join(places)}. "
                "Hệ thống sẽ ƯU TIÊN địa điểm trong mô tả; nếu không đúng ý, hãy sửa ô Khu vực cho khớp."
            )
    return {"products": products, "places": places, "warning": warning}


def _search_out(r: SearchRequest, match_count: int = 0, new_count: int = 0) -> dict:
    return {
        "understood": _understood(r.note or "", (r.criteria or {}).get("regions") or []),
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


class UnderstandIn(BaseModel):
    note: str = Field("", max_length=3000)
    regions: list[str] = Field(default_factory=list, max_length=50)


@router.post("/search-requests/understand")
def understand_search_request(body: UnderstandIn, _: MemberUser = Depends(current_member)):
    """Xem trước (khi khách đang gõ): hệ thống nhận ra sản phẩm, địa điểm nào trong mô tả."""
    return _understood(body.note, _norm_list(body.regions))


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
