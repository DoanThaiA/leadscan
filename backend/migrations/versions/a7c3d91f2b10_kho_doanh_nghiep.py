"""kho doanh nghiep (knowledge_companies)

Revision ID: a7c3d91f2b10
Revises: e44adf5a214e
Create Date: 2026-11-07 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3d91f2b10'
down_revision: Union[str, Sequence[str], None] = 'e44adf5a214e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXED = ["name", "industry", "province", "source", "ai_status", "created_at"]


def upgrade() -> None:
    op.create_table(
        "knowledge_companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("name_en", sa.String(length=300), nullable=False),
        sa.Column("tax_code", sa.String(length=20), nullable=True),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("industry", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("province", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=100), nullable=False),
        sa.Column("fax", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("website", sa.String(length=300), nullable=False),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("ceo_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("rank_label", sa.String(length=100), nullable=False),
        sa.Column("rank_list", sa.String(length=200), nullable=False),
        sa.Column("rank_year", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("crawled_at", sa.DateTime(), nullable=True),
        sa.Column("ai_status", sa.String(length=16), nullable=False),
        sa.Column("ai_scanned_at", sa.DateTime(), nullable=True),
        sa.Column("ai_note", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tax_code"),
        sa.UniqueConstraint("source", "source_id", name="uq_knowledge_source"),
    )
    with op.batch_alter_table("knowledge_companies", schema=None) as batch_op:
        for col in INDEXED:
            batch_op.create_index(batch_op.f(f"ix_knowledge_companies_{col}"), [col], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("knowledge_companies", schema=None) as batch_op:
        for col in INDEXED:
            batch_op.drop_index(batch_op.f(f"ix_knowledge_companies_{col}"))
    op.drop_table("knowledge_companies")
