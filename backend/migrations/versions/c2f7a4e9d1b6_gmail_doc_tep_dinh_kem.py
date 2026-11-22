"""Thu thập cơ hội từ Gmail: lưu chữ đọc từ tệp đính kèm (inbound_emails.attachments)

Revision ID: c2f7a4e9d1b6
Revises: b8e4f1a6d2c7
Create Date: 2026-11-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2f7a4e9d1b6'
down_revision: Union[str, Sequence[str], None] = 'b8e4f1a6d2c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('inbound_emails') as batch:
        batch.add_column(sa.Column('attachments', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    with op.batch_alter_table('inbound_emails') as batch:
        batch.drop_column('attachments')
