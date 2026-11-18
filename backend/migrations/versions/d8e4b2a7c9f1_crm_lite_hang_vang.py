"""CRM Lite cho thành viên hạng Vàng: lead (1 phiếu đã mua = 1 lead), ghi chú, việc cần làm, lịch sử

Revision ID: d8e4b2a7c9f1
Revises: c7a3d9e1f5b2
Create Date: 2026-11-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e4b2a7c9f1'
down_revision: Union[str, Sequence[str], None] = 'c7a3d9e1f5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = {
    'crm_leads': ('company_id', 'opportunity_id', 'stage', 'owner_id', 'updated_at'),
    'crm_notes': ('company_id', 'lead_id'),
    'crm_tasks': ('company_id', 'lead_id', 'due_date', 'assignee_id', 'done_at'),
    'crm_events': ('company_id', 'lead_id'),
}


def _company_lead(*extra):
    return [
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        *extra,
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['crm_leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    ]


def upgrade() -> None:
    op.create_table(
        'crm_leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('purchase_id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=False),
        sa.Column('stage', sa.String(length=16), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['member_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('purchase_id'),
    )
    op.create_table(
        'crm_notes',
        *_company_lead(
            sa.Column('author_id', sa.Integer(), nullable=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['author_id'], ['member_users.id'], ondelete='SET NULL'),
        ),
    )
    op.create_table(
        'crm_tasks',
        *_company_lead(
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('assignee_id', sa.Integer(), nullable=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('done_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignee_id'], ['member_users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['created_by_id'], ['member_users.id'], ondelete='SET NULL'),
        ),
    )
    op.create_table(
        'crm_events',
        *_company_lead(
            sa.Column('actor_id', sa.Integer(), nullable=True),
            sa.Column('kind', sa.String(length=16), nullable=False),
            sa.Column('content', sa.String(length=500), nullable=False),
            sa.ForeignKeyConstraint(['actor_id'], ['member_users.id'], ondelete='SET NULL'),
        ),
    )
    for table, cols in INDEXES.items():
        for col in cols:
            op.create_index(op.f(f'ix_{table}_{col}'), table, [col], unique=False)


def downgrade() -> None:
    for table, cols in INDEXES.items():
        for col in cols:
            op.drop_index(op.f(f'ix_{table}_{col}'), table_name=table)
    for table in ('crm_events', 'crm_tasks', 'crm_notes', 'crm_leads'):
        op.drop_table(table)
