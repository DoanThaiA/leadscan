"""API quản trị phần thương mại: cơ hội, đơn thanh toán, hoá đơn, enrich, ví & tài khoản thành viên."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import accounts
from app.auth import current_user, require_admin
from app.config import get_settings
from app.db import get_db, utcnow
from app.models import (
    ENRICH_STATUSES,
    INVOICE_STATUSES,
    OPP_SOURCES,
    OPP_STATUSES,
    ORDER_KINDS,
    ORDER_STATUSES,
    SEARCH_STATUSES,
    TX_KINDS,
    Activity,
    AdminUser,
    Company,
    EnrichRequest,
    InvoiceRequest,
    MemberSession,
    MemberUser,
    Opportunity,
    OpportunityAttachment,
    OpportunityContact,
    PaymentOrder,
    Purchase,
    SearchRequest,
    SearchRequestMatch,
    UserOpportunity,
    WalletTransaction,
)
from app.schemas_commerce import (
    AdjustIn,
    ConfirmOrderIn,
    EnrichAdminIn,
    EnrichOut,
    InvoiceAdminIn,
    InvoiceOut,
    MemberCreateIn,
    MemberUpdateIn,
    OppAdminOut,
    OppIn,
    OrderOut,
    TxOut,
)
from app.security import hash_password
from app.services import attachments, catalog, payments, tiers, usage, wallet
from app.worker import (
    enqueue,
    run_einvoice,
    match_opportunity_task,
    match_request_task,
    purge_files_task,
    send_invoice_request_task,
    send_search_request_task,
)

router = APIRouter(prefix="/api/admin")


def _queue(task, *args) -> bool:
    """Đưa việc so khớp vào Celery; Redis lỗi thì chạy luôn tại chỗ để dữ liệu không bị treo ở "đang so khớp"."""
    if enqueue(task, *args):
        return True
    task.apply(args=list(args))
    return False


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _company_ref(c: Company) -> dict:
    return {"id": c.id, "code": c.code, "name": c.name}


@router.get("/commerce-meta")
def commerce_meta(_: AdminUser = Depends(current_user)):
    cfg = get_settings()
    return {
        "opp_statuses": OPP_STATUSES,
        "opp_sources": OPP_SOURCES,
        "order_kinds": ORDER_KINDS,
        "order_statuses": ORDER_STATUSES,
        "invoice_statuses": INVOICE_STATUSES,
        "enrich_statuses": ENRICH_STATUSES,
        "search_statuses": SEARCH_STATUSES,
        "tx_kinds": TX_KINDS,
        "payment_provider": cfg.payment_provider,
        "invoice_email": cfg.invoice_email,
        "einvoice": {
            "enabled": cfg.iam_enabled,
            "provider": "IAM Invoice",
            "serial": f"{cfg.iam_invoice_form}{cfg.iam_invoice_serial}" if cfg.iam_invoice_serial else "",
            "sign": cfg.iam_sign,
            "on_payment": cfg.iam_issue_on_payment,
            "portal": cfg.iam_base_url,
        },
    }


@router.get("/commerce-stats")
def commerce_stats(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=30)
    revenue = db.scalar(select(func.coalesce(func.sum(PaymentOrder.paid_amount), 0)).where(PaymentOrder.status == "paid", PaymentOrder.paid_at >= since))
    sold = db.scalar(select(func.count()).select_from(Purchase).where(Purchase.created_at >= since))
    return {
        "revenue_30d": int(revenue or 0),
        "tickets_sold_30d": int(sold or 0),
        "pending_orders": db.scalar(select(func.count()).select_from(PaymentOrder).where(PaymentOrder.status == "pending", PaymentOrder.expires_at > utcnow())) or 0,
        "pending_invoices": db.scalar(select(func.count()).select_from(InvoiceRequest).where(InvoiceRequest.status == "pending")) or 0,
        "open_enrich": db.scalar(select(func.count()).select_from(EnrichRequest).where(EnrichRequest.status == "open")) or 0,
        "open_search": db.scalar(select(func.count()).select_from(SearchRequest).where(SearchRequest.status == "open")) or 0,
        "published_opportunities": db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.status == "published")) or 0,
        # Lượt gọi Cohere trong tháng (khoá Trial miễn phí: tối đa 1.000 lần/tháng)
        "cohere": {
            "configured": bool(get_settings().cohere_api_key),
            "calls_month": usage.calls_this_month("cohere"),
            "monthly_limit": get_settings().cohere_monthly_limit,
        },
    }


# ================================================================== cơ hội


def _opp_out(o: Opportunity, match_count: int = 0) -> dict:
    out = OppAdminOut.model_validate(o)
    out.contact_count = len(o.contacts)
    out.match_count = match_count
    out.sold_out = o.sold_count >= o.max_buyers or o.status == "closed"
    return out.model_dump(mode="json")


def _match_counts(db: Session, opp_ids: list[int]) -> dict[int, int]:
    """Số doanh nghiệp được mỗi cơ hội khớp (điểm riêng từng doanh nghiệp nằm ở UserOpportunity)."""
    if not opp_ids:
        return {}
    return dict(db.execute(select(UserOpportunity.opportunity_id, func.count()).where(UserOpportunity.opportunity_id.in_(opp_ids)).group_by(UserOpportunity.opportunity_id)).all())


def _next_opp_code(db: Session) -> str:
    n = (db.scalar(select(func.max(Opportunity.id))) or 0) + 1
    while db.scalar(select(Opportunity.id).where(Opportunity.code == f"CH-{n:06d}")):
        n += 1
    return f"CH-{n:06d}"


def _apply_opp(o: Opportunity, body: OppIn) -> None:
    data = body.model_dump(exclude={"contacts", "attachment_ids"})
    if data["status"] == "published" and not o.published_at:
        o.published_at = utcnow()
    for k, v in data.items():
        setattr(o, k, v)
    o.contacts = [OpportunityContact(position_order=i, **c.model_dump()) for i, c in enumerate(body.contacts) if any(c.model_dump().values())]


@router.get("/opportunities")
def list_opps(
    q: str = Query("", max_length=100),
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Opportunity)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Opportunity.title.ilike(like), Opportunity.code.ilike(like), Opportunity.buyer_name.ilike(like)))
    if status:
        stmt = stmt.where(Opportunity.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.options(selectinload(Opportunity.contacts)).order_by(Opportunity.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    counts = dict(db.execute(select(Opportunity.status, func.count()).group_by(Opportunity.status)).all())
    matches = _match_counts(db, [o.id for o in rows])
    return {"total": total, "page": page, "page_size": page_size, "items": [_opp_out(o, matches.get(o.id, 0)) for o in rows], "counts": counts}


def _purge(keys: list[str]) -> None:
    """Xoá tệp trên R2 ở việc nền (Redis lỗi thì xoá luôn)."""
    if keys:
        _queue(purge_files_task, keys)


def _opp_detail(db: Session, o: Opportunity) -> dict:
    d = _opp_out(o, _match_counts(db, [o.id]).get(o.id, 0))
    d["attachments"] = [attachments.out(a) for a in attachments.for_opportunity(db, o.id)]
    return d


@router.post("/opportunities", status_code=201)
def create_opp(body: OppIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    o = Opportunity(code=_next_opp_code(db), title=body.title, created_by_id=user.id)
    _apply_opp(o, body)
    db.add(o)
    db.flush()
    purge = attachments.link(db, o, body.attachment_ids, user, body.attachment_captions) if body.attachment_ids is not None else []
    db.commit()
    _purge(purge)
    _queue(match_opportunity_task, o.id)  # phiếu không mang điểm; việc nền chấm điểm riêng cho từng doanh nghiệp phù hợp
    db.refresh(o)
    return _opp_detail(db, o)


def _get_opp(db: Session, opp_id: int) -> Opportunity:
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    return o


@router.get("/opportunities/{opp_id}")
def get_opp(opp_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    o = _get_opp(db, opp_id)
    buyers = db.scalars(select(Purchase).where(Purchase.opportunity_id == o.id).order_by(Purchase.id.desc())).unique().all()
    return {
        "opportunity": _opp_detail(db, o),
        "purchases": [_purchase_admin_out(db, p) for p in buyers],
    }


def _purchase_admin_out(db: Session, p: Purchase) -> dict:
    """Người mua của 1 cơ hội: điểm lúc mua vs điểm hiện tại, các mục đã sửa sau khi mua, trạng thái hoàn điểm."""
    now = catalog.user_match(db, p.company_id, p.opportunity_id)
    return {
        "id": p.id,
        "price": p.price,
        "exclusive": p.exclusive,
        "created_at": _iso(p.created_at),
        "company": _company_ref(p.company),
        "score_at_purchase": (p.snapshot or {}).get("score"),
        "score_now": now.score if now else None,
        "changed_fields": catalog.changed_fields(p),
        "refund_amount": p.refund_amount,
        "refund_note": p.refund_note,
        "refunded_at": _iso(p.refunded_at),
    }


class RefundIn(BaseModel):
    note: str = Field(min_length=5, max_length=300)


@router.post("/purchases/{purchase_id}/refund")
def refund_purchase(purchase_id: int, body: RefundIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Duyệt hoàn điểm cho phiếu đã mua (vd. cơ hội bị sửa không còn phù hợp). Lịch sử mua giữ nguyên, ghi bút toán "Hoàn điểm"."""
    p = db.get(Purchase, purchase_id)
    if not p:
        raise HTTPException(404, "Không tìm thấy giao dịch mua.")
    catalog.refund(db, p, body.note.strip(), user.id)
    db.commit()
    return _purchase_admin_out(db, p)


@router.put("/opportunities/{opp_id}")
def update_opp(opp_id: int, body: OppIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    o = _get_opp(db, opp_id)
    if body.max_buyers < o.sold_count:
        raise HTTPException(400, f"Đã bán {o.sold_count} phiếu, số lượt bán tối đa không được nhỏ hơn.")
    _apply_opp(o, body)
    purge = attachments.link(db, o, body.attachment_ids, user, body.attachment_captions) if body.attachment_ids is not None else []
    db.commit()
    _purge(purge)
    _queue(match_opportunity_task, o.id)  # nội dung/trạng thái đổi → so khớp lại (nhúng lại chỉ khi nội dung đổi)
    db.refresh(o)
    return _opp_detail(db, o)


@router.delete("/opportunities/{opp_id}", status_code=204)
def delete_opp(opp_id: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    o = _get_opp(db, opp_id)
    if o.sold_count:
        raise HTTPException(400, "Cơ hội đã có người mua — hãy chuyển sang “Đã đóng” thay vì xoá.")
    keys = attachments.keys_of(db, o.id)
    db.delete(o)
    db.commit()
    _purge(keys)


# ================================================================== ảnh & tài liệu của phiếu cơ hội (Cloudflare R2)


class AttachInitIn(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    size: int = Field(gt=0)


class AttachPatchIn(BaseModel):
    caption: str = Field("", max_length=300)


def _get_attachment(db: Session, att_id: int) -> OpportunityAttachment:
    a = db.get(OpportunityAttachment, att_id)
    if not a:
        raise HTTPException(404, "Không tìm thấy tệp.")
    return a


@router.get("/attachments/config")
def attachment_config(_: AdminUser = Depends(current_user)):
    return attachments.limits()


@router.post("/attachments/init", status_code=201)
def attachment_init(body: AttachInitIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Bước 1: khai báo tệp → link PUT ký sẵn để trình duyệt tải thẳng lên R2 (gửi kèm header Content-Type trả về)."""
    a, url = attachments.init_upload(db, user, body.filename, body.size)
    return {"attachment": attachments.out(a, signed=False), "upload_url": url, "content_type": a.content_type, "expires_in": 600}


@router.post("/attachments/{att_id}/complete")
def attachment_complete(att_id: int, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Bước 3: trình duyệt đã PUT xong → kiểm tra tệp trên R2, ảnh thì bỏ EXIF + tạo ảnh nhỏ."""
    a = _get_attachment(db, att_id)
    if a.opportunity_id is None and a.uploaded_by_id != user.id:
        raise HTTPException(404, "Không tìm thấy tệp.")
    return attachments.out(attachments.complete_upload(db, a))


@router.patch("/attachments/{att_id}")
def attachment_patch(att_id: int, body: AttachPatchIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    a = _get_attachment(db, att_id)
    attachments.update_caption(a, body.caption)
    db.commit()
    return attachments.out(a)


@router.delete("/attachments/{att_id}", status_code=204)
def attachment_delete(att_id: int, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Huỷ tệp vừa tải lên nhưng chưa lưu vào phiếu. Tệp đã thuộc phiếu thì bỏ khỏi danh sách rồi lưu phiếu."""
    a = _get_attachment(db, att_id)
    if a.opportunity_id is not None:
        raise HTTPException(400, "Tệp đã thuộc phiếu — hãy bỏ tệp trong form rồi bấm lưu phiếu.")
    if a.uploaded_by_id != user.id:
        raise HTTPException(404, "Không tìm thấy tệp.")
    keys = [k for k in (a.key, a.thumb_key) if k]
    db.delete(a)
    db.commit()
    _purge(keys)


# ================================================================== đơn thanh toán


def _order_out(o: PaymentOrder) -> dict:
    d = OrderOut.model_validate(o).model_dump(mode="json")
    d["company"] = _company_ref(o.company)
    d["confirmed_by"] = o.confirmed_by.full_name if o.confirmed_by else None
    d["provider_txn_id"] = o.provider_txn_id
    return d


@router.get("/orders")
def list_orders(
    q: str = Query("", max_length=100),
    status: str = "",
    promo: str = Query("", max_length=40),  # lọc đơn dùng mã khuyến mãi
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.query(PaymentOrder).filter(PaymentOrder.status == "pending", PaymentOrder.expires_at < utcnow()).update({"status": "expired"}, synchronize_session=False)
    db.commit()
    stmt = select(PaymentOrder).join(Company, Company.id == PaymentOrder.company_id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(PaymentOrder.code.ilike(like), Company.name.ilike(like), Company.code.ilike(like)))
    if status:
        stmt = stmt.where(PaymentOrder.status == status)
    if promo.strip():
        stmt = stmt.where(PaymentOrder.promo_code == promo.strip().upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PaymentOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_order_out(o) for o in rows]}


@router.post("/orders/{order_id}/confirm")
def confirm_order(order_id: int, body: ConfirmOrderIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Xác nhận tay (dự phòng khi webhook lỗi) — chỉ quản trị viên, phải ghi rõ đã đối soát thế nào."""
    o = db.get(PaymentOrder, order_id)
    if not o:
        raise HTTPException(404, "Không tìm thấy đơn.")
    if o.status == "paid":
        raise HTTPException(409, "Đơn đã được ghi nhận thanh toán.")
    if o.status in ("expired", "cancelled"):
        o.status = "pending"
    payments.mark_paid(db, get_settings(), o, body.paid_amount or o.amount, None, admin_id=user.id, note=body.note)
    db.refresh(o)
    return _order_out(o)


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    o = db.get(PaymentOrder, order_id)
    if not o:
        raise HTTPException(404, "Không tìm thấy đơn.")
    if o.status != "pending":
        raise HTTPException(409, "Chỉ huỷ được đơn đang chờ thanh toán.")
    o.status = "cancelled"
    db.commit()
    return _order_out(o)


# ================================================================== hoá đơn


def _inv_out(i: InvoiceRequest) -> dict:
    d = InvoiceOut.model_validate(i).model_dump(mode="json")
    d["order"] = {"id": i.order.id, "code": i.order.code, "kind": i.order.kind, "amount": i.order.paid_amount or i.order.amount, "paid_at": _iso(i.order.paid_at)}
    d["company"] = _company_ref(i.order.company)
    return d


@router.get("/invoices")
def list_invoices(
    status: str = "", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), _: AdminUser = Depends(current_user), db: Session = Depends(get_db)
):
    stmt = select(InvoiceRequest)
    if status:
        stmt = stmt.where(InvoiceRequest.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(InvoiceRequest.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_inv_out(i) for i in rows]}


@router.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: InvoiceAdminIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    i = db.get(InvoiceRequest, invoice_id)
    if not i:
        raise HTTPException(404, "Không tìm thấy yêu cầu hoá đơn.")
    if body.invoice_number is not None:
        i.invoice_number = body.invoice_number
    if body.status:
        if body.status == "issued" and not (body.invoice_number or i.invoice_number):
            raise HTTPException(400, "Nhập số hoá đơn trước khi đánh dấu đã xuất.")
        i.status = body.status
        i.issued_at = utcnow() if body.status == "issued" else None
    db.commit()
    db.refresh(i)
    return _inv_out(i)


@router.post("/invoices/{invoice_id}/einvoice")
def issue_einvoice(invoice_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """Phát hành (hoặc kiểm tra lại) hoá đơn điện tử IAM ngay — dùng khi lần tự xuất bị lỗi hoặc hoá đơn đang là nháp."""
    if not get_settings().iam_enabled:
        raise HTTPException(400, "Chưa bật hoá đơn điện tử IAM (LEADSCAN_IAM_ENABLED).")
    i = db.get(InvoiceRequest, invoice_id)
    if not i:
        raise HTTPException(404, "Không tìm thấy yêu cầu hoá đơn.")
    if i.status == "issued":
        raise HTTPException(409, "Hoá đơn này đã xuất.")
    result, error = run_einvoice(invoice_id)
    if result in ("retry", "error"):
        raise HTTPException(502, f"IAM: {error}")
    db.expire_all()
    return _inv_out(db.get(InvoiceRequest, invoice_id))


@router.post("/invoices/{invoice_id}/resend")
def resend_invoice(invoice_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    if not db.get(InvoiceRequest, invoice_id):
        raise HTTPException(404, "Không tìm thấy yêu cầu hoá đơn.")
    enqueue(send_invoice_request_task, invoice_id)
    return {"ok": True}


# ================================================================== yêu cầu enrich


def _enrich_out(e: EnrichRequest) -> dict:
    d = EnrichOut.model_validate(e).model_dump(mode="json")
    d["company"] = _company_ref(e.purchase.company)
    d["opportunity"] = {"id": e.purchase.opportunity.id, "code": e.purchase.opportunity.code, "title": e.purchase.opportunity.title}
    return d


@router.get("/enrich-requests")
def list_enrich(status: str = "", _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(EnrichRequest)
    if status:
        stmt = stmt.where(EnrichRequest.status == status)
    rows = db.scalars(stmt.order_by(EnrichRequest.id.desc()).limit(200)).unique().all()
    return {"items": [_enrich_out(e) for e in rows]}


@router.patch("/enrich-requests/{req_id}")
def update_enrich(req_id: int, body: EnrichAdminIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(EnrichRequest, req_id)
    if not e:
        raise HTTPException(404, "Không tìm thấy yêu cầu.")
    e.status, e.reply = body.status, body.reply.strip()
    e.resolved_at = utcnow() if body.status != "open" else None
    db.commit()
    db.refresh(e)
    return _enrich_out(e)


# ================================================================== yêu cầu enrich tìm kiếm cơ hội


class SearchAdminIn(BaseModel):
    status: str
    reply: str = Field("", max_length=4000)

    @field_validator("status")
    @classmethod
    def _st(cls, v: str) -> str:
        if v not in SEARCH_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v


def _search_admin_out(r: SearchRequest, match_count: int = 0) -> dict:
    return {
        "match_count": match_count,
        "match_status": r.match_status,
        "match_error": r.match_error,
        "id": r.id,
        "criteria": r.criteria or {},
        "note": r.note,
        "status": r.status,
        "reply": r.reply,
        "email_sent_at": _iso(r.email_sent_at),
        "created_at": _iso(r.created_at),
        "resolved_at": _iso(r.resolved_at),
        "company": _company_ref(r.company),
        "member": {"full_name": r.member_user.full_name, "email": r.member_user.email} if r.member_user else None,
    }


@router.get("/search-requests")
def list_search_requests(status: str = "", _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(SearchRequest)
    if status:
        stmt = stmt.where(SearchRequest.status == status)
    rows = db.scalars(stmt.order_by(SearchRequest.id.desc()).limit(200)).unique().all()
    counts = dict(
        db.execute(select(SearchRequestMatch.request_id, func.count()).where(SearchRequestMatch.request_id.in_([r.id for r in rows])).group_by(SearchRequestMatch.request_id)).all()
    ) if rows else {}
    return {"items": [_search_admin_out(r, counts.get(r.id, 0)) for r in rows]}


@router.patch("/search-requests/{req_id}")
def update_search_request(req_id: int, body: SearchAdminIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(SearchRequest, req_id)
    if not r:
        raise HTTPException(404, "Không tìm thấy yêu cầu.")
    r.status, r.reply = body.status, body.reply.strip()
    r.resolved_at = utcnow() if body.status != "open" else None
    db.add(Activity(company_id=r.company_id, kind="update", actor_id=user.id, content=f"Yêu cầu tìm cơ hội #{r.id}: {SEARCH_STATUSES[r.status]}"))
    r.match_status = "pending"
    db.commit()
    _queue(match_request_task, r.id)  # "Từ chối" gỡ cơ hội khỏi phiếu; mở lại thì so khớp lại
    db.refresh(r)
    return _search_admin_out(r, db.scalar(select(func.count()).select_from(SearchRequestMatch).where(SearchRequestMatch.request_id == r.id)) or 0)


@router.post("/search-requests/{req_id}/rematch")
def rematch_search_request(req_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    """So khớp lại phiếu tìm cơ hội với toàn bộ phiếu cơ hội đang bán (vd. sau khi nhập thêm cơ hội hàng loạt)."""
    r = db.get(SearchRequest, req_id)
    if not r:
        raise HTTPException(404, "Không tìm thấy yêu cầu.")
    r.match_status = "pending"
    db.commit()
    queued = _queue(match_request_task, r.id)
    db.refresh(r)
    count = db.scalar(select(func.count()).select_from(SearchRequestMatch).where(SearchRequestMatch.request_id == r.id)) or 0
    return {"ok": queued, "match_status": r.match_status, "match_count": count}


@router.post("/search-requests/{req_id}/resend-email")
def resend_search_email(req_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    if not db.get(SearchRequest, req_id):
        raise HTTPException(404, "Không tìm thấy yêu cầu.")
    enqueue(send_search_request_task, req_id)
    return {"ok": True}


# ================================================================== ví & tài khoản thành viên của 1 khách hàng


def _member_out(m: MemberUser) -> dict:
    return {"id": m.id, "email": m.email, "full_name": m.full_name, "is_active": m.is_active, "created_at": _iso(m.created_at), "last_login_at": _iso(m.last_login_at)}


@router.get("/companies/{company_id}/account")
def company_account(company_id: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Không tìm thấy khách hàng.")
    txs = db.scalars(select(WalletTransaction).where(WalletTransaction.company_id == c.id).order_by(WalletTransaction.id.desc()).limit(50)).unique().all()
    orders = db.scalars(select(PaymentOrder).where(PaymentOrder.company_id == c.id).order_by(PaymentOrder.id.desc()).limit(30)).unique().all()
    buys = db.scalars(select(Purchase).where(Purchase.company_id == c.id).order_by(Purchase.id.desc()).limit(50)).unique().all()
    members = db.scalars(select(MemberUser).where(MemberUser.company_id == c.id).order_by(MemberUser.id)).unique().all()
    return {
        "points_balance": c.points_balance,
        "membership_expires_at": _iso(c.membership_expires_at),
        "membership_active": catalog.membership_active(c),
        "tier": tiers.tier_out(c),
        "members": [_member_out(m) for m in members],
        "transactions": [TxOut.model_validate(t).model_dump(mode="json") for t in txs],
        "orders": [_order_out(o) for o in orders],
        "purchases": [
            {"id": p.id, "price": p.price, "exclusive": p.exclusive, "created_at": _iso(p.created_at), "opportunity": {"id": p.opportunity.id, "code": p.opportunity.code, "title": p.opportunity.title}}
            for p in buys
        ],
    }


@router.post("/companies/{company_id}/wallet/adjust")
def adjust_wallet(company_id: int, body: AdjustIn, user: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    c = wallet.lock_company(db, company_id)
    wallet.post(db, c, body.amount, "adjust", body.note, actor_id=user.id)
    db.add(Activity(company_id=c.id, kind="update", actor_id=user.id, content=f"Điều chỉnh {body.amount:+,} điểm: {body.note}".replace(",", ".")))
    db.commit()
    return {"ok": True, "points_balance": c.points_balance}


@router.post("/companies/{company_id}/members", status_code=201)
def create_member(company_id: int, body: MemberCreateIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Không tìm thấy khách hàng.")
    if db.scalar(select(MemberUser.id).where(MemberUser.email == body.email)):
        raise HTTPException(409, "Email này đã có tài khoản.")
    # Email đã là đối tác → cùng 1 tài khoản: dùng mật khẩu đối tác đang dùng (không đổi mật khẩu của người ta)
    partner = accounts.partner_by_email(db, body.email)
    m = MemberUser(company_id=c.id, email=body.email, full_name=body.full_name,
                   password_hash=partner.password_hash if partner else hash_password(body.password))
    db.add(m)
    note = " (dùng chung mật khẩu tài khoản đối tác)" if partner else ""
    db.add(Activity(company_id=c.id, kind="update", actor_id=user.id, content=f"Tạo tài khoản đăng nhập cho {body.email}{note}"))
    db.commit()
    db.refresh(m)
    return {**_member_out(m), "shared_with_partner": bool(partner)}


@router.patch("/members/{member_id}")
def update_member(member_id: int, body: MemberUpdateIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(MemberUser, member_id)
    if not m:
        raise HTTPException(404, "Không tìm thấy tài khoản.")
    if body.is_active is not None:
        m.is_active = body.is_active
    if body.password:  # cùng 1 tài khoản → đổi luôn mật khẩu cổng đối tác, đăng xuất mọi phiên
        accounts.sync_password(db, m.email, hash_password(body.password), end_sessions=True)
    if body.is_active is False:
        db.query(MemberSession).filter(MemberSession.user_id == m.id).delete()
    db.add(Activity(company_id=m.company_id, kind="update", actor_id=user.id, content=f"Cập nhật tài khoản đăng nhập {m.email}"))
    db.commit()
    db.refresh(m)
    return _member_out(m)
