"""Công thức giá phiếu cơ hội chỉnh được trên trang quản trị (pricing_settings + lịch sử)

Revision ID: c5d1e8f2a7b6
Revises: b7e3f9a1c2d4
Create Date: 2026-11-12 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5d1e8f2a7b6'
down_revision: Union[str, Sequence[str], None] = 'b7e3f9a1c2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pricing_settings',
        sa.Column('key', sa.String(length=40), primary_key=True),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'pricing_setting_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('old_value', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('new_value', sa.String(length=100), nullable=False),
        sa.Column('reason', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_pricing_setting_logs_created_at', 'pricing_setting_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_pricing_setting_logs_created_at', table_name='pricing_setting_logs')
    op.drop_table('pricing_setting_logs')
    op.drop_table('pricing_settings')
