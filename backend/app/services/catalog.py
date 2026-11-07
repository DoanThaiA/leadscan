"""Kho cơ hội & mua phiếu."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Activity, Company, MemberUser, Opportunity, Purchase
from app.schemas_commerce import OppFull, OppPreview
from app.services import wallet


def membership_active(c: Company) -> bool:
    return bool(c.membership_expires_at and c.membership_expires_at > utcnow())


def preview(o: Opportunity, purchased: bool = False) -> dict:
    p = OppPreview.model_validate(o)
    p.contact_count = len(o.contacts)
    p.purchased = purchased
    p.sold_out = o.sold_count >= o.max_buyers or o.status == "closed"
    return p.model_dump(mode="json")


def full(o: Opportunity) -> dict:
    f = OppFull.model_validate(o)
    f.contact_count = len(o.contacts)
    f.purchased = True
    f.sold_out = o.sold_count >= o.max_buyers or o.status == "closed"
    return f.model_dump(mode="json")


def purchased_ids(db: Session, company_id: int, opp_ids: list[int]) -> set[int]:
    if not opp_ids:
        return set()
    return set(
        db.scalars(select(Purchase.opportunity_id).where(Purchase.company_id == company_id, Purchase.opportunity_id.in_(opp_ids))).all()
    )


def buy(db: Session, member: MemberUser, opp_id: int) -> Purchase:
    company = wallet.lock_company(db, member.company_id)
    if not membership_active(company):
        raise HTTPException(402, "Bạn cần thanh toán phí thành viên (hoặc gia hạn) trước khi mua phiếu.")
    opp = db.scalar(select(Opportunity).where(Opportunity.id == opp_id).with_for_update(of=Opportunity).execution_options(populate_existing=True))
    if not opp or opp.status == "draft":
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    if db.scalar(select(Purchase.id).where(Purchase.company_id == company.id, Purchase.opportunity_id == opp.id)):
        raise HTTPException(409, "Bạn đã mua phiếu này rồi.")
    if opp.status != "published" or opp.sold_count >= opp.max_buyers:
        raise HTTPException(409, "Phiếu cơ hội này đã hết lượt mua.")
    if company.points_balance < opp.price:
        raise HTTPException(402, f"Số dư không đủ: cần {opp.price:,} điểm, hiện có {company.points_balance:,} điểm.".replace(",", "."))

    purchase = Purchase(company_id=company.id, opportunity_id=opp.id, member_user_id=member.id, price=opp.price)
    db.add(purchase)
    db.flush()
    wallet.post(db, company, -opp.price, "purchase", f"Mua phiếu {opp.code}: {opp.title[:120]}", purchase_id=purchase.id)
    opp.sold_count += 1
    db.add(Activity(company_id=company.id, kind="update", content=f"{member.full_name} mua phiếu {opp.code} ({opp.price:,} điểm)".replace(",", ".")))
    try:
        db.commit()
    except IntegrityError:  # 2 lần bấm mua cùng lúc
        db.rollback()
        raise HTTPException(409, "Bạn đã mua phiếu này rồi.") from None
    db.refresh(purchase)
    return purchase
