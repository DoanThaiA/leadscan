"""Đối tác LeadScan (Mốc 1): tài khoản đối tác, phiên, đặt lại mật khẩu, OTP, nhật ký

Revision ID: c8e2f4a1d7b3
Revises: b4d8f2a6c1e3
Create Date: 2026-11-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8e2f4a1d7b3'
down_revision: Union[str, Sequence[str], None] = 'b4d8f2a6c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'partner_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=20), nullable=False, unique=True),
        sa.Column('email', sa.String(length=150), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False, unique=True),
        sa.Column('phone_verified_at', sa.DateTime(), nullable=True),
        sa.Column('phone_verified_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kind', sa.String(length=10), nullable=False, server_default='personal'),
        sa.Column('org_name', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('org_tax_code', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('industries', sa.JSON(), nullable=False),
        sa.Column('regions', sa.JSON(), nullable=False),
        sa.Column('tier', sa.String(length=12), nullable=False, server_default='new'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='active'),
        sa.Column('terms_version', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('terms_accepted_at', sa.DateTime(), nullable=True),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('signup_ip', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('signup_ua', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_partner_users_status', 'partner_users', ['status'])
    op.create_index('ix_partner_users_created_at', 'partner_users', ['created_at'])

    op.create_table(
        'partner_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('ip', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('user_agent', sa.String(length=300), nullable=False, server_default=''),
    )
    op.create_index('ix_partner_sessions_partner_id', 'partner_sessions', ['partner_id'])
    op.create_index('ix_partner_sessions_expires_at', 'partner_sessions', ['expires_at'])

    op.create_table(
        'partner_password_resets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_partner_password_resets_partner_id', 'partner_password_resets', ['partner_id'])

    op.create_table(
        'partner_otps',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_partner_otps_partner_id', 'partner_otps', ['partner_id'])
    op.create_index('ix_partner_otps_created_at', 'partner_otps', ['created_at'])

    op.create_table(
        'partner_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(length=24), nullable=False),
        sa.Column('content', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_partner_events_partner_id', 'partner_events', ['partner_id'])
    op.create_index('ix_partner_events_created_at', 'partner_events', ['created_at'])


def downgrade() -> None:
    for t in ('partner_events', 'partner_otps', 'partner_password_resets', 'partner_sessions', 'partner_users'):
        op.drop_table(t)
