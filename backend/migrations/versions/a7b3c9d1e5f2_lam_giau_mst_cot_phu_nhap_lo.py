"""lam giau du lieu theo MST — nhap lo nhan them cot phu: nhom nganh, nhom san pham, ma HS

Revision ID: a7b3c9d1e5f2
Revises: e5f9a3b7c2d8
Create Date: 2026-11-17 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7b3c9d1e5f2'
down_revision: Union[str, Sequence[str], None] = 'e5f9a3b7c2d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _schema() -> str | None:
    return "kho_a" if op.get_bind().dialect.name == "postgresql" else None


def upgrade() -> None:
    with op.batch_alter_table("enrich_companies", schema=_schema()) as b:
        b.add_column(sa.Column("nhom_nganh", sa.String(length=200), nullable=True))
        b.add_column(sa.Column("nhom_san_pham", sa.JSON(), nullable=True))
        b.add_column(sa.Column("ma_hs", sa.JSON(), nullable=True))
        b.create_index("ix_enrich_companies_nhom_nganh", ["nhom_nganh"])


def downgrade() -> None:
    with op.batch_alter_table("enrich_companies", schema=_schema()) as b:
        b.drop_index("ix_enrich_companies_nhom_nganh")
        b.drop_column("ma_hs")
        b.drop_column("nhom_san_pham")
        b.drop_column("nhom_nganh")
