"""lam giau du lieu theo MST — gop Kho doanh nghiep: ten tieng Anh, nam thanh lap, gioi thieu

Kho doanh nghiep (knowledge_companies) da bo khoi giao dien; crawler PROFIT500 ghi thang vao phan he lam giau.
Bang knowledge_companies CHUA xoa o day — chuyen du lieu bang `python -m app.cli enrich-from-knowledge`, kiem tra xong
moi xoa o migration sau.

Revision ID: b2c8d4e6f0a1
Revises: a7b3c9d1e5f2
Create Date: 2026-11-17 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c8d4e6f0a1'
down_revision: Union[str, Sequence[str], None] = 'a7b3c9d1e5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _schema() -> str | None:
    return "kho_a" if op.get_bind().dialect.name == "postgresql" else None


def upgrade() -> None:
    with op.batch_alter_table("enrich_companies", schema=_schema()) as b:
        b.add_column(sa.Column("ten_tieng_anh", sa.String(length=300), nullable=True))
        b.add_column(sa.Column("nam_thanh_lap", sa.Integer(), nullable=True))
        b.add_column(sa.Column("mo_ta", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("enrich_companies", schema=_schema()) as b:
        b.drop_column("mo_ta")
        b.drop_column("nam_thanh_lap")
        b.drop_column("ten_tieng_anh")
