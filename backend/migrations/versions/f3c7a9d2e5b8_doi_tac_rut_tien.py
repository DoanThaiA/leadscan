"""Đối tác LeadScan (Mốc 4): hồ sơ thanh toán (mã hoá), lệnh rút, lô chi

Revision ID: f3c7a9d2e5b8
Revises: e8b4c1f6a3d9
Create Date: 2026-11-12 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3c7a9d2e5b8'
down_revision: Union[str, Sequence[str], None] = 'e8b4c1f6a3d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'partner_payout_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('legal_name', sa.String(length=200), nullable=False),
        sa.Column('id_number_enc', sa.Text(), nullable=False, server_default=''),
        sa.Column('id_last4', sa.String(length=4), nullable=False, server_default=''),
        sa.Column('tax_code', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('bank_bin', sa.String(length=10), nullable=False, server_default=''),
        sa.Column('bank_name', sa.String(length=100), nullable=False),
        sa.Column('account_enc', sa.Text(), nullable=False),
        sa.Column('account_last4', sa.String(length=4), nullable=False),
        sa.Column('account_hash', sa.String(length=64), nullable=False),
        sa.Column('account_holder', sa.String(length=200), nullable=False),
        sa.Column('name_match', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_partner_payout_profiles_account_hash', 'partner_payout_profiles', ['account_hash'])

    op.create_table(
        'partner_payout_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=30), nullable=False, unique=True),
        sa.Column('pay_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='draft'),
        sa.Column('note', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('exported_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('paid_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_partner_payout_batches_status', 'partner_payout_batches', ['status'])
    op.create_index('ix_partner_payout_batches_created_at', 'partner_payout_batches', ['created_at'])

    op.create_table(
        'partner_withdrawals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=20), nullable=False, unique=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='requested'),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('tax_withheld', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('net_amount', sa.BigInteger(), nullable=False),
        sa.Column('payee', sa.JSON(), nullable=False),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('partner_payout_batches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('invoice_no', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('tax_cert_no', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('bank_ref', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('reject_reason', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('note', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
    )
    for col in ('partner_id', 'status', 'batch_id', 'created_at'):
        op.create_index(f'ix_partner_withdrawals_{col}', 'partner_withdrawals', [col])


def downgrade() -> None:
    op.drop_table('partner_withdrawals')
    op.drop_table('partner_payout_batches')
    op.drop_table('partner_payout_profiles')
