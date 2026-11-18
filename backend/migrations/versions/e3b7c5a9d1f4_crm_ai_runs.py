"""CRM Lite tuần 2: nhật ký nút AI (kết quả nháp, token, chi phí) để giữ trần ngân sách AI theo tháng

Revision ID: e3b7c5a9d1f4
Revises: d8e4b2a7c9f1
Create Date: 2026-11-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3b7c5a9d1f4'
down_revision: Union[str, Sequence[str], None] = 'd8e4b2a7c9f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLS = ('company_id', 'lead_id', 'created_at')


def upgrade() -> None:
    op.create_table(
        'crm_ai_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('model', sa.String(length=60), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('result', sa.Text(), nullable=False),
        sa.Column('error', sa.String(length=300), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['crm_leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['member_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in COLS:
        op.create_index(op.f(f'ix_crm_ai_runs_{col}'), 'crm_ai_runs', [col], unique=False)


def downgrade() -> None:
    for col in COLS:
        op.drop_index(op.f(f'ix_crm_ai_runs_{col}'), table_name='crm_ai_runs')
    op.drop_table('crm_ai_runs')
