"""Phiếu đã mua: lưu bản cơ hội tại thời điểm mua + hoàn điểm khi cơ hội bị sửa không còn phù hợp

Revision ID: b4d8f2a6c1e3
Revises: a3c7e9f1b5d2
Create Date: 2026-11-11 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d8f2a6c1e3'
down_revision: Union[str, Sequence[str], None] = 'a3c7e9f1b5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('purchases') as b:
        b.add_column(sa.Column('snapshot', sa.JSON(), nullable=True))
        b.add_column(sa.Column('refund_amount', sa.BigInteger(), nullable=False, server_default='0'))
        b.add_column(sa.Column('refund_note', sa.String(length=300), nullable=False, server_default=''))
        b.add_column(sa.Column('refunded_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('purchases') as b:
        for c in ('refunded_at', 'refund_note', 'refund_amount', 'snapshot'):
            b.drop_column(c)
