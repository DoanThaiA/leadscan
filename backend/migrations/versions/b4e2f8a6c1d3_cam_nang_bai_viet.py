"""Cẩm nang (blog SEO): bảng articles

Revision ID: b4e2f8a6c1d3
Revises: a9d3e7c1b5f2
Create Date: 2026-11-17 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4e2f8a6c1d3'
down_revision: Union[str, Sequence[str], None] = 'a9d3e7c1b5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(length=160), nullable=False, unique=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='draft'),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('seo_title', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('excerpt', sa.String(length=400), nullable=False, server_default=''),
        sa.Column('category', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('cover_image', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('author_name', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('admin_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_articles_status', 'articles', ['status'])
    op.create_index('ix_articles_category', 'articles', ['category'])
    op.create_index('ix_articles_published_at', 'articles', ['published_at'])


def downgrade() -> None:
    op.drop_index('ix_articles_published_at', table_name='articles')
    op.drop_index('ix_articles_category', table_name='articles')
    op.drop_index('ix_articles_status', table_name='articles')
    op.drop_table('articles')
