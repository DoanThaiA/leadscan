"""Cơ hội đối tác: thêm tiêu đề (đối tác đặt) → dùng làm tiêu đề phiếu khi tạo phiếu

Revision ID: e4a7c9b2d6f8
Revises: d2f6b8a4c9e1
Create Date: 2026-11-12 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4a7c9b2d6f8'
down_revision: Union[str, Sequence[str], None] = 'd2f6b8a4c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('partner_submissions') as b:
        b.add_column(sa.Column('title', sa.String(length=150), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('partner_submissions') as b:
        b.drop_column('title')
