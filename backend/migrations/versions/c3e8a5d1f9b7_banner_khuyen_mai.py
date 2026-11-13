"""Banner khuyến mãi: ảnh + tiêu đề + nội dung, hiện popup trên trang chủ

Revision ID: c3e8a5d1f9b7
Revises: b9e4f2a7c1d6
Create Date: 2026-11-13 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e8a5d1f9b7'
down_revision: Union[str, Sequence[str], None] = 'b9e4f2a7c1d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('promo_codes') as b:
        b.add_column(sa.Column('show_banner', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('banner_image', sa.String(length=500), nullable=False, server_default=''))
        b.add_column(sa.Column('banner_title', sa.String(length=150), nullable=False, server_default=''))
        b.add_column(sa.Column('banner_text', sa.String(length=500), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('promo_codes') as b:
        b.drop_column('banner_text')
        b.drop_column('banner_title')
        b.drop_column('banner_image')
        b.drop_column('show_banner')
