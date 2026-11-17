"""Cẩm nang: gắn bài với khu vực (tỉnh / miền)

Revision ID: c7a3d9e1f5b2
Revises: b4e2f8a6c1d3
Create Date: 2026-11-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a3d9e1f5b2'
down_revision: Union[str, Sequence[str], None] = 'b4e2f8a6c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('articles') as b:
        b.add_column(sa.Column('area', sa.String(length=60), nullable=False, server_default=''))
        b.create_index('ix_articles_area', ['area'])


def downgrade() -> None:
    with op.batch_alter_table('articles') as b:
        b.drop_index('ix_articles_area')
        b.drop_column('area')
