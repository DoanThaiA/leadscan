"""Đối tác: khoá kết nối AI (MCP) để đăng cơ hội qua Claude / ChatGPT

Revision ID: a9d3e7c1b5f2
Revises: c4e1f7a9b3d2
Create Date: 2026-11-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9d3e7c1b5f2'
down_revision: Union[str, Sequence[str], None] = 'c4e1f7a9b3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'partner_mcp_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('hint', sa.String(length=16), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('last_client', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_partner_mcp_tokens_partner_id', 'partner_mcp_tokens', ['partner_id'])
    op.create_index('ix_partner_mcp_tokens_revoked_at', 'partner_mcp_tokens', ['revoked_at'])


def downgrade() -> None:
    op.drop_index('ix_partner_mcp_tokens_revoked_at', table_name='partner_mcp_tokens')
    op.drop_index('ix_partner_mcp_tokens_partner_id', table_name='partner_mcp_tokens')
    op.drop_table('partner_mcp_tokens')
