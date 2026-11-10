"""Ảnh bìa (banner) cho bài tuyển dụng

Cột job_posts.cover_image: đường dẫn ảnh trên website (vd /careers/truong-phong-kinh-doanh.webp) hoặc URL https.

Revision ID: c4e8a1f9d2b6
Revises: b6e2c9d4f1a8
Create Date: 2026-11-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e8a1f9d2b6'
down_revision: Union[str, Sequence[str], None] = 'b6e2c9d4f1a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('job_posts') as batch:
        batch.add_column(sa.Column('cover_image', sa.String(length=500), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('job_posts') as batch:
        batch.drop_column('cover_image')
