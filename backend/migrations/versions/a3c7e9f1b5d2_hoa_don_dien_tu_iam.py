"""Hoá đơn điện tử IAM Invoice: thêm cột theo dõi HĐĐT vào invoice_requests

Revision ID: a3c7e9f1b5d2
Revises: d1f5a7c3e9b2
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3c7e9f1b5d2'
down_revision: Union[str, Sequence[str], None] = 'd1f5a7c3e9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('invoice_requests') as b:
        b.add_column(sa.Column('source', sa.String(length=16), nullable=False, server_default='member'))
        b.add_column(sa.Column('einvoice_id', sa.String(length=50), nullable=False, server_default=''))
        b.add_column(sa.Column('einvoice_serial', sa.String(length=20), nullable=False, server_default=''))
        b.add_column(sa.Column('einvoice_status', sa.String(length=40), nullable=False, server_default=''))
        b.add_column(sa.Column('einvoice_error', sa.String(length=500), nullable=False, server_default=''))
        b.add_column(sa.Column('einvoice_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('invoice_requests') as b:
        for c in ('einvoice_at', 'einvoice_error', 'einvoice_status', 'einvoice_serial', 'einvoice_id', 'source'):
            b.drop_column(c)
