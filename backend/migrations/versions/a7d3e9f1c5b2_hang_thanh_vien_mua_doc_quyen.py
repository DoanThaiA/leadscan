"""Hạng thành viên: tổng nạp của doanh nghiệp (Vàng ≥ 10 triệu) + lượt mua độc quyền phiếu cơ hội

Revision ID: a7d3e9f1c5b2
Revises: e4a7c9b2d6f8
Create Date: 2026-11-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3e9f1c5b2'
down_revision: Union[str, Sequence[str], None] = 'e4a7c9b2d6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('companies') as b:
        b.add_column(sa.Column('topup_total', sa.BigInteger(), nullable=False, server_default='0'))
    with op.batch_alter_table('purchases') as b:
        b.add_column(sa.Column('exclusive', sa.Boolean(), nullable=False, server_default=sa.false()))
    # tổng nạp = các đơn phí thành viên / nạp điểm đã thanh toán trước khi có cột này
    op.execute(
        "UPDATE companies SET topup_total = COALESCE((SELECT SUM(o.amount) FROM payment_orders o "
        "WHERE o.company_id = companies.id AND o.status = 'paid'), 0)"
    )


def downgrade() -> None:
    with op.batch_alter_table('purchases') as b:
        b.drop_column('exclusive')
    with op.batch_alter_table('companies') as b:
        b.drop_column('topup_total')
