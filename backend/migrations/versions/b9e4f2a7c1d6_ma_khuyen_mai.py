"""Mã khuyến mãi giảm tiền đơn thanh toán (phí thành viên / nạp điểm)

Revision ID: b9e4f2a7c1d6
Revises: a7d3e9f1c5b2
Create Date: 2026-11-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9e4f2a7c1d6'
down_revision: Union[str, Sequence[str], None] = 'a7d3e9f1c5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'promo_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('discount_type', sa.String(length=10), nullable=False, server_default='percent'),
        sa.Column('discount_value', sa.BigInteger(), nullable=False),
        sa.Column('max_discount', sa.BigInteger(), nullable=True),
        sa.Column('min_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('applies_to', sa.String(length=16), nullable=False, server_default='all'),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('per_company_limit', sa.Integer(), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=True),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['admin_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    with op.batch_alter_table('payment_orders') as b:
        b.add_column(sa.Column('promo_id', sa.Integer(), nullable=True))
        b.add_column(sa.Column('promo_code', sa.String(length=30), nullable=False, server_default=''))
        b.add_column(sa.Column('original_amount', sa.BigInteger(), nullable=True))
        b.add_column(sa.Column('discount', sa.BigInteger(), nullable=False, server_default='0'))
        b.create_foreign_key('fk_payment_orders_promo_id', 'promo_codes', ['promo_id'], ['id'], ondelete='SET NULL')
        b.create_index('ix_payment_orders_promo_id', ['promo_id'])


def downgrade() -> None:
    with op.batch_alter_table('payment_orders') as b:
        b.drop_index('ix_payment_orders_promo_id')
        b.drop_constraint('fk_payment_orders_promo_id', type_='foreignkey')
        b.drop_column('discount')
        b.drop_column('original_amount')
        b.drop_column('promo_code')
        b.drop_column('promo_id')
    op.drop_table('promo_codes')
