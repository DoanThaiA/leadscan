"""Gửi phiếu cơ hội cho khách qua email: bảng opportunity_emails (nhật ký gửi)

Revision ID: b8e4f1a6d2c7
Revises: a7d3e9b2c4f1
Create Date: 2026-11-19 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e4f1a6d2c7'
down_revision: Union[str, Sequence[str], None] = 'a7d3e9b2c4f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXED = ('opportunity_id', 'company_id', 'member_user_id', 'status', 'created_at')


def upgrade() -> None:
    op.create_table(
        'opportunity_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('member_user_id', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('recipient_name', sa.String(length=100), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('error', sa.String(length=300), nullable=False),
        sa.Column('sent_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['member_user_id'], ['member_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sent_by_id'], ['admin_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in INDEXED:
        op.create_index(op.f(f'ix_opportunity_emails_{col}'), 'opportunity_emails', [col], unique=False)


def downgrade() -> None:
    for col in INDEXED:
        op.drop_index(op.f(f'ix_opportunity_emails_{col}'), table_name='opportunity_emails')
    op.drop_table('opportunity_emails')
