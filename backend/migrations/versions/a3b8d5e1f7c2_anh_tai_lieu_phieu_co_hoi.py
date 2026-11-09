"""Ảnh & tài liệu của phiếu cơ hội (Cloudflare R2)

Bảng opportunity_attachments: tệp admin gắn vào phiếu cơ hội, hiện ở phần mở khoá sau khi mua.

Revision ID: a3b8d5e1f7c2
Revises: f2a9c4e6b8d1
Create Date: 2026-11-10 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3b8d5e1f7c2'
down_revision: Union[str, Sequence[str], None] = 'f2a9c4e6b8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'opportunity_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_by_id', sa.Integer(), nullable=True),
        sa.Column('key', sa.String(length=400), nullable=False),
        sa.Column('thumb_key', sa.String(length=400), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=120), nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('caption', sa.String(length=300), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['admin_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    for col in ('opportunity_id', 'status', 'created_at'):
        op.create_index(op.f(f'ix_opportunity_attachments_{col}'), 'opportunity_attachments', [col], unique=False)


def downgrade() -> None:
    for col in ('opportunity_id', 'status', 'created_at'):
        op.drop_index(op.f(f'ix_opportunity_attachments_{col}'), table_name='opportunity_attachments')
    op.drop_table('opportunity_attachments')
