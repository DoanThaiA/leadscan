"""Đối tác LeadScan (Mốc 2): cơ hội đối tác gửi, hàng đợi xác minh, phiếu gắn đối tác nguồn

Revision ID: d5a9e3c7b2f1
Revises: c8e2f4a1d7b3
Create Date: 2026-11-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5a9e3c7b2f1'
down_revision: Union[str, Sequence[str], None] = 'c8e2f4a1d7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'partner_submissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=20), nullable=False, unique=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='submitted'),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('tax_code', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('tax_key', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('tax_lookup', sa.JSON(), nullable=True),
        sa.Column('province', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('industry', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('need', sa.Text(), nullable=False),
        sa.Column('scale', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('timing', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('source_type', sa.String(length=16), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('certainty', sa.String(length=16), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('contact_name', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('contact_title', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('contact_phone', sa.String(length=30), nullable=False, server_default=''),
        sa.Column('contact_email', sa.String(length=150), nullable=False, server_default=''),
        sa.Column('contact_consent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('can_connect', sa.String(length=4), nullable=False, server_default=''),
        sa.Column('auto_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('score_detail', sa.JSON(), nullable=False),
        sa.Column('final_score', sa.Integer(), nullable=True),
        sa.Column('dup_hints', sa.JSON(), nullable=False),
        sa.Column('is_large', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('reject_reason', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('partner_note', sa.Text(), nullable=False, server_default=''),
        sa.Column('internal_note', sa.Text(), nullable=False, server_default=''),
        sa.Column('assigned_to_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sla_due_at', sa.DateTime(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    for col in ('partner_id', 'status', 'tax_key', 'assigned_to_id', 'sla_due_at', 'created_at'):
        op.create_index(f'ix_partner_submissions_{col}', 'partner_submissions', [col])

    with op.batch_alter_table('partner_events') as b:
        b.add_column(sa.Column('submission_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_partner_events_submission', 'partner_submissions', ['submission_id'], ['id'], ondelete='CASCADE')
        b.create_index('ix_partner_events_submission_id', ['submission_id'])

    with op.batch_alter_table('opportunities') as b:
        b.add_column(sa.Column('source_partner_id', sa.Integer(), nullable=True))
        b.add_column(sa.Column('source_submission_id', sa.Integer(), nullable=True))
        b.add_column(sa.Column('buyer_tax_key', sa.String(length=20), nullable=False, server_default=''))
        b.create_foreign_key('fk_opportunities_source_partner', 'partner_users', ['source_partner_id'], ['id'], ondelete='SET NULL')
        b.create_foreign_key('fk_opportunities_source_submission', 'partner_submissions', ['source_submission_id'], ['id'], ondelete='SET NULL')
        b.create_index('ix_opportunities_source_partner_id', ['source_partner_id'])
        b.create_index('ix_opportunities_source_submission_id', ['source_submission_id'])
        b.create_index('ix_opportunities_buyer_tax_key', ['buyer_tax_key'])


def downgrade() -> None:
    with op.batch_alter_table('opportunities') as b:
        b.drop_index('ix_opportunities_buyer_tax_key')
        b.drop_index('ix_opportunities_source_submission_id')
        b.drop_index('ix_opportunities_source_partner_id')
        b.drop_constraint('fk_opportunities_source_submission', type_='foreignkey')
        b.drop_constraint('fk_opportunities_source_partner', type_='foreignkey')
        for c in ('buyer_tax_key', 'source_submission_id', 'source_partner_id'):
            b.drop_column(c)
    with op.batch_alter_table('partner_events') as b:
        b.drop_index('ix_partner_events_submission_id')
        b.drop_constraint('fk_partner_events_submission', type_='foreignkey')
        b.drop_column('submission_id')
    op.drop_table('partner_submissions')
