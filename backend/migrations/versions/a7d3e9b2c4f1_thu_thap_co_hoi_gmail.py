"""Thu thập cơ hội từ Gmail: bảng inbound_emails (thư nhận qua webhook Apps Script) và inbound_email_blocks

Revision ID: a7d3e9b2c4f1
Revises: f4b8d2a6c9e3
Create Date: 2026-11-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3e9b2c4f1'
down_revision: Union[str, Sequence[str], None] = 'f4b8d2a6c9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXED = ('thread_id', 'from_email', 'received_at', 'status', 'opportunity_id', 'created_at')


def upgrade() -> None:
    op.create_table(
        'inbound_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmail_message_id', sa.String(length=100), nullable=False),
        sa.Column('thread_id', sa.String(length=100), nullable=False),
        sa.Column('from_email', sa.String(length=200), nullable=False),
        sa.Column('from_name', sa.String(length=200), nullable=False),
        sa.Column('to', sa.String(length=500), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('attachment_names', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('error', sa.String(length=500), nullable=False),
        sa.Column('ai_json', sa.JSON(), nullable=True),
        sa.Column('ai_model', sa.String(length=60), nullable=False),
        sa.Column('ai_input_tokens', sa.Integer(), nullable=False),
        sa.Column('ai_output_tokens', sa.Integer(), nullable=False),
        sa.Column('ai_cost_usd', sa.Float(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=True),
        sa.Column('decided_by_id', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('purged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['decided_by_id'], ['admin_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gmail_message_id'),
    )
    for col in INDEXED:
        op.create_index(op.f(f'ix_inbound_emails_{col}'), 'inbound_emails', [col], unique=False)
    op.create_table(
        'inbound_email_blocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pattern', sa.String(length=200), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['admin_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pattern'),
    )


def downgrade() -> None:
    op.drop_table('inbound_email_blocks')
    for col in INDEXED:
        op.drop_index(op.f(f'ix_inbound_emails_{col}'), table_name='inbound_emails')
    op.drop_table('inbound_emails')
