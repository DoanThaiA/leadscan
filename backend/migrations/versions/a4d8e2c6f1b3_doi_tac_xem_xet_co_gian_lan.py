"""Đối tác LeadScan (Mốc 5): ghi nhận quản trị viên đã xem xét / bỏ qua cờ gian lận

Revision ID: a4d8e2c6f1b3
Revises: f3c7a9d2e5b8
Create Date: 2026-11-12 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4d8e2c6f1b3'
down_revision: Union[str, Sequence[str], None] = 'f3c7a9d2e5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'partner_flag_reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=255), nullable=False, unique=True),
        sa.Column('flag_type', sa.String(length=24), nullable=False),
        sa.Column('detail', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('note', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('partner_flag_reviews')
