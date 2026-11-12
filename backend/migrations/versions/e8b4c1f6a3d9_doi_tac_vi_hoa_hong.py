"""Đối tác LeadScan (Mốc 3): ví hoa hồng (khoản ghi có), cấu hình thưởng, thoả thuận riêng theo đối tác

Revision ID: e8b4c1f6a3d9
Revises: d5a9e3c7b2f1
Create Date: 2026-11-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8b4c1f6a3d9'
down_revision: Union[str, Sequence[str], None] = 'd5a9e3c7b2f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('partner_users') as b:
        b.add_column(sa.Column('custom_rate', sa.Integer(), nullable=True))
        b.add_column(sa.Column('custom_cafe_quota', sa.Integer(), nullable=True))

    op.create_table(
        'partner_credits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('submission_id', sa.Integer(), sa.ForeignKey('partner_submissions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('purchase_id', sa.Integer(), sa.ForeignKey('purchases.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('state', sa.String(length=10), nullable=False, server_default='pending'),
        sa.Column('available_at', sa.DateTime(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.Column('note', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('calc', sa.JSON(), nullable=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    for col in ('partner_id', 'submission_id', 'purchase_id', 'state', 'available_at', 'created_at'):
        op.create_index(f'ix_partner_credits_{col}', 'partner_credits', [col])

    op.create_table(
        'partner_settings',
        sa.Column('key', sa.String(length=40), primary_key=True),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'partner_setting_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('old_value', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('new_value', sa.String(length=100), nullable=False),
        sa.Column('reason', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_partner_setting_logs_created_at', 'partner_setting_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('partner_setting_logs')
    op.drop_table('partner_settings')
    op.drop_table('partner_credits')
    with op.batch_alter_table('partner_users') as b:
        b.drop_column('custom_cafe_quota')
        b.drop_column('custom_rate')
