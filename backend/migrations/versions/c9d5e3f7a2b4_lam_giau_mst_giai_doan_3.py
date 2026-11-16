"""lam giau du lieu theo MST — giai doan 3: tai lieu cong bo thong tin, cache mo hinh ngon ngu

Revision ID: c9d5e3f7a2b4
Revises: b8c4d2e6f1a3
Create Date: 2026-11-18 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c9d5e3f7a2b4'
down_revision: Union[str, Sequence[str], None] = 'b8c4d2e6f1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"

    def ref(schema: str, target: str) -> str:
        return f"{schema}.{target}" if pg else target

    B = "kho_b" if pg else None

    op.create_table(
        "enrich_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("doc_type", sa.String(length=30), nullable=False),
        sa.Column("period", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_page_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("extracted", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_page_id"], [ref("thu_thap", "enrich_source_pages.id")], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_documents_mst", "enrich_documents", ["mst"], schema=B)
    op.create_index("ix_enrich_documents_status", "enrich_documents", ["status"], schema=B)
    op.create_index("ix_enrich_documents_created_at", "enrich_documents", ["created_at"], schema=B)

    op.create_table(
        "enrich_llm_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("task", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=60), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash", "task", "model", name="uq_enrich_llm_cache"),
        schema=B,
    )


def downgrade() -> None:
    B = "kho_b" if op.get_bind().dialect.name == "postgresql" else None
    op.drop_table("enrich_llm_cache", schema=B)
    op.drop_table("enrich_documents", schema=B)
