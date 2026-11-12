"""Cơ hội công khai (mở từ link chia sẻ), ảnh đối tác gắn vào cơ hội gửi, vector mô tả để lọc trùng theo ngữ nghĩa

Revision ID: d2f6b8a4c9e1
Revises: c5d1e8f2a7b6
Create Date: 2026-11-12 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2f6b8a4c9e1'
down_revision: Union[str, Sequence[str], None] = 'c5d1e8f2a7b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIM = 1024


def upgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"
    with op.batch_alter_table('partner_submissions') as b:
        b.add_column(sa.Column('embedding_model', sa.String(length=80), nullable=False, server_default=''))
        b.add_column(sa.Column('embedding_sha', sa.String(length=40), nullable=False, server_default=''))
        if not pg:
            b.add_column(sa.Column('embedding', sa.JSON(), nullable=True))
    if pg:
        op.execute(f"ALTER TABLE partner_submissions ADD COLUMN embedding vector({DIM})")

    with op.batch_alter_table('user_opportunities') as b:
        b.add_column(sa.Column('via_share', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        'partner_attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('partner_id', sa.Integer(), sa.ForeignKey('partner_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('submission_id', sa.Integer(), sa.ForeignKey('partner_submissions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('key', sa.String(length=400), nullable=False, unique=True),
        sa.Column('thumb_key', sa.String(length=400), nullable=False, server_default=''),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=120), nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('kind', sa.String(length=10), nullable=False, server_default='image'),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('caption', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    for col in ('partner_id', 'submission_id', 'status', 'created_at'):
        op.create_index(f'ix_partner_attachments_{col}', 'partner_attachments', [col])


def downgrade() -> None:
    op.drop_table('partner_attachments')
    with op.batch_alter_table('user_opportunities') as b:
        b.drop_column('via_share')
    with op.batch_alter_table('partner_submissions') as b:
        b.drop_column('embedding')
        b.drop_column('embedding_sha')
        b.drop_column('embedding_model')
