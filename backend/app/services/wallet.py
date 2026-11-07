"""Cộng/trừ điểm. Mọi thay đổi số dư đi qua đây để sổ cái luôn khớp số dư."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, WalletTransaction


def lock_company(db: Session, company_id: int) -> Company:
    """Khoá dòng doanh nghiệp tới hết transaction (PostgreSQL: SELECT … FOR UPDATE) để 2 giao dịch không giẫm nhau."""
    c = db.scalar(select(Company).where(Company.id == company_id).with_for_update(of=Company).execution_options(populate_existing=True))
    if not c:
        raise HTTPException(404, "Không tìm thấy khách hàng.")
    return c


def post(db: Session, company: Company, amount: int, kind: str, note: str = "", **refs) -> WalletTransaction:
    """Ghi 1 bút toán. Gọi sau lock_company; transaction do người gọi commit."""
    new_balance = company.points_balance + amount
    if new_balance < 0:
        raise HTTPException(400, "Số dư điểm không đủ.")
    company.points_balance = new_balance
    tx = WalletTransaction(company_id=company.id, kind=kind, amount=amount, balance_after=new_balance, note=note[:300], **refs)
    db.add(tx)
    return tx
