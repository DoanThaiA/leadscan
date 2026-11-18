"""Danh mục bài viết (Cẩm nang, Tuyển dụng, Tin tức…): bảng article_sections, articles.section_id

Bài cũ đều vào danh mục "Cẩm nang" (giữ nguyên link /cam-nang/<slug>).

Revision ID: f4b8d2a6c9e3
Revises: e3b7c5a9d1f4
Create Date: 2026-11-18 10:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4b8d2a6c9e3'
down_revision: Union[str, Sequence[str], None] = 'e3b7c5a9d1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED = [
    ("cam-nang", "Cẩm nang", "Hướng dẫn tìm khách hàng B2B, đọc nhu cầu mua hàng, kiếm thêm thu nhập khi giới thiệu cơ hội và dùng LeadScan hiệu quả.", 1),
    ("tuyen-dung", "Tuyển dụng", "Văn hoá làm việc, câu chuyện đội ngũ và kinh nghiệm ứng tuyển tại LeadScan.", 2),
    ("tin-tuc", "Tin tức", "Tin hoạt động, tính năng mới và thông báo từ LeadScan.", 3),
]


def upgrade() -> None:
    sections = op.create_table(
        'article_sections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=400), nullable=False, server_default=''),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_article_sections_slug'),
    )
    now = datetime.utcnow()
    op.bulk_insert(sections, [
        {"slug": s, "name": n, "description": d, "sort_order": o, "is_active": True, "created_at": now, "updated_at": now} for s, n, d, o in SEED
    ])
    with op.batch_alter_table('articles') as b:
        b.add_column(sa.Column('section_id', sa.Integer(), nullable=True))
        b.create_index('ix_articles_section_id', ['section_id'])
        b.create_foreign_key('fk_articles_section_id', 'article_sections', ['section_id'], ['id'], ondelete='RESTRICT')
    op.execute("UPDATE articles SET section_id = (SELECT id FROM article_sections WHERE slug = 'cam-nang')")


def downgrade() -> None:
    with op.batch_alter_table('articles') as b:
        b.drop_constraint('fk_articles_section_id', type_='foreignkey')
        b.drop_index('ix_articles_section_id')
        b.drop_column('section_id')
    op.drop_table('article_sections')
