"""Cổng thanh toán MCV: bảng mcv_payments (mỗi payment_code MCV cấp cho 1 đơn nạp tiền)

payment_code unique → mỗi payment_code chỉ mở dịch vụ 1 lần (processed_at).

Revision ID: d1f5a7c3e9b2
Revises: c4e8a1f9d2b6
Create Date: 2026-11-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1f5a7c3e9b2'
down_revision: Union[str, Sequence[str], None] = 'c4e8a1f9d2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mcv_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_code', sa.String(length=100), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('mcv_order_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('paid_amount', sa.BigInteger(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('test_mode', sa.Boolean(), nullable=False),
        sa.Column('checkout_url', sa.String(length=500), nullable=False),
        sa.Column('qr_data', sa.Text(), nullable=True),
        sa.Column('bank', sa.JSON(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.String(length=300), nullable=False),
        sa.Column('last_event_id', sa.String(length=100), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['payment_orders.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_code'),
    )
    op.create_index(op.f('ix_mcv_payments_order_id'), 'mcv_payments', ['order_id'], unique=False)
    op.create_index(op.f('ix_mcv_payments_mcv_order_id'), 'mcv_payments', ['mcv_order_id'], unique=False)
    op.create_index(op.f('ix_mcv_payments_status'), 'mcv_payments', ['status'], unique=False)
    op.create_index(op.f('ix_mcv_payments_created_at'), 'mcv_payments', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mcv_payments_created_at'), table_name='mcv_payments')
    op.drop_index(op.f('ix_mcv_payments_status'), table_name='mcv_payments')
    op.drop_index(op.f('ix_mcv_payments_mcv_order_id'), table_name='mcv_payments')
    op.drop_index(op.f('ix_mcv_payments_order_id'), table_name='mcv_payments')
    op.drop_table('mcv_payments')
