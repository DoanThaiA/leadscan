"""Kho cơ hội & mua phiếu."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Activity, Company, MemberUser, Opportunity, Purchase, SavedOpportunity, UserOpportunity
from app.schemas_commerce import OppFull, OppPreview
from app.services import wallet
from app.services.matching import price_for


def membership_active(c: Company) -> bool:
    return bool(c.membership_expires_at and c.membership_expires_at > utcnow())


def _personalize(d: OppPreview, o: Opportunity, u) -> None:
    """Điểm & giá là của riêng từng doanh nghiệp: điểm theo mức phù hợp, giá đồng biến với điểm."""
    d.score, d.score_fit, d.score_urgency, d.score_trust = (u.score, u.score_fit, u.score_urgency, u.score_trust) if u else (0, 0, 0, 0)
    d.reasons = list(u.reasons or []) if u else []
    d.price = price_for(o.price, d.score)


def preview(o: Opportunity, purchased: bool = False, saved: bool = False, match: UserOpportunity | None = None) -> dict:
    p = OppPreview.model_validate(o)
    p.contact_count = len(o.contacts)
    p.purchased = purchased
    p.saved = saved
    p.sold_out = o.sold_count >= o.max_buyers or o.status == "closed"
    _personalize(p, o, match)
    return p.model_dump(mode="json")


def full(o: Opportunity, match: UserOpportunity | None = None) -> dict:
    f = OppFull.model_validate(o)
    f.contact_count = len(o.contacts)
    f.purchased = True
    f.sold_out = o.sold_count >= o.max_buyers or o.status == "closed"
    _personalize(f, o, match)
    return f.model_dump(mode="json")


def user_match(db: Session, company_id: int, opp_id: int) -> UserOpportunity | None:
    return db.scalar(select(UserOpportunity).where(UserOpportunity.company_id == company_id, UserOpportunity.opportunity_id == opp_id))


def user_matches(db: Session, company_id: int, opp_ids: list[int]) -> dict[int, UserOpportunity]:
    if not opp_ids:
        return {}
    rows = db.scalars(select(UserOpportunity).where(UserOpportunity.company_id == company_id, UserOpportunity.opportunity_id.in_(opp_ids))).unique()
    return {u.opportunity_id: u for u in rows}


def purchased_ids(db: Session, company_id: int, opp_ids: list[int]) -> set[int]:
    if not opp_ids:
        return set()
    return set(
        db.scalars(select(Purchase.opportunity_id).where(Purchase.company_id == company_id, Purchase.opportunity_id.in_(opp_ids))).all()
    )


def saved_ids(db: Session, company_id: int, opp_ids: list[int]) -> set[int]:
    if not opp_ids:
        return set()
    return set(
        db.scalars(
            select(SavedOpportunity.opportunity_id).where(SavedOpportunity.company_id == company_id, SavedOpportunity.opportunity_id.in_(opp_ids))
        ).all()
    )


def previews(db: Session, company_id: int, rows: list[Opportunity], scores: dict | None = None) -> list[dict]:
    """Xem trước kèm cờ đã mua / đã lưu và điểm, giá riêng của doanh nghiệp.

    scores: {opp_id: dòng điểm} để dùng điểm khác (vd. điểm theo từng phiếu tìm cơ hội); mặc định lấy điểm tổng của doanh nghiệp.
    """
    ids = [o.id for o in rows]
    owned, saved = purchased_ids(db, company_id, ids), saved_ids(db, company_id, ids)
    mine = scores if scores is not None else user_matches(db, company_id, ids)
    return [preview(o, o.id in owned, o.id in saved, mine.get(o.id)) for o in rows]


def buy(db: Session, member: MemberUser, opp_id: int) -> Purchase:
    company = wallet.lock_company(db, member.company_id)
    if not membership_active(company):
        raise HTTPException(402, "Bạn cần thanh toán phí thành viên (hoặc gia hạn) trước khi mua phiếu.")
    opp = db.scalar(select(Opportunity).where(Opportunity.id == opp_id).with_for_update(of=Opportunity).execution_options(populate_existing=True))
    if not opp or opp.status == "draft":
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    if db.scalar(select(Purchase.id).where(Purchase.company_id == company.id, Purchase.opportunity_id == opp.id)):
        raise HTTPException(409, "Bạn đã mua phiếu này rồi.")
    mine = user_match(db, company.id, opp.id)
    if not mine:  # chỉ mua được cơ hội đã được so khớp với doanh nghiệp
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    if opp.status != "published" or opp.sold_count >= opp.max_buyers:
        raise HTTPException(409, "Phiếu cơ hội này đã hết lượt mua.")
    price = price_for(opp.price, mine.score)  # giá theo điểm của chính doanh nghiệp
    if company.points_balance < price:
        raise HTTPException(402, f"Số dư không đủ: cần {price:,} điểm, hiện có {company.points_balance:,} điểm.".replace(",", "."))

    purchase = Purchase(company_id=company.id, opportunity_id=opp.id, member_user_id=member.id, price=price)
    db.add(purchase)
    db.flush()
    wallet.post(db, company, -price, "purchase", f"Mua phiếu {opp.code}: {opp.title[:120]}", purchase_id=purchase.id)
    opp.sold_count += 1
    db.add(Activity(company_id=company.id, kind="update", content=f"{member.full_name} mua phiếu {opp.code} ({price:,} điểm)".replace(",", ".")))
    try:
        db.commit()
    except IntegrityError:  # 2 lần bấm mua cùng lúc
        db.rollback()
        raise HTTPException(409, "Bạn đã mua phiếu này rồi.") from None
    db.refresh(purchase)
    return purchase
