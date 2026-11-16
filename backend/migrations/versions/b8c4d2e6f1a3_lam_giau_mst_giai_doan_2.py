"""lam giau du lieu theo MST — giai doan 2: vong thu thap, nhat ky tai, cau hinh, nhap nguon chinh thuc

Revision ID: b8c4d2e6f1a3
Revises: f6a1c2d3e4b5
Create Date: 2026-11-17 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8c4d2e6f1a3'
down_revision: Union[str, Sequence[str], None] = 'f6a1c2d3e4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    pg = _pg()

    def S(name: str) -> str | None:
        return name if pg else None

    def ref(schema: str, target: str) -> str:
        return f"{schema}.{target}" if pg else target

    A, B, T = S("kho_a"), S("kho_b"), S("thu_thap")

    op.create_table(
        "enrich_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("connectors", sa.JSON(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("job_count", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], [ref("thu_thap", "enrich_batches.id")], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_runs_status", "enrich_runs", ["status"], schema=T)

    op.create_table(
        "enrich_fetch_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("domain", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_fetch_logs_source_code", "enrich_fetch_logs", ["source_code"], schema=T)
    op.create_index("ix_enrich_fetch_logs_domain_at", "enrich_fetch_logs", ["domain", "at"], schema=T)

    op.create_table(
        "enrich_domain_slots",
        sa.Column("domain", sa.String(length=200), nullable=False),
        sa.Column("next_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("domain"),
        schema=T,
    )
    op.create_table(
        "enrich_settings",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
        schema=T,
    )
    op.create_table(
        "enrich_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("source_page_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_code"], [ref("thu_thap", "enrich_sources.code")]),
        sa.ForeignKeyConstraint(["source_page_id"], [ref("thu_thap", "enrich_source_pages.id")], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_imports_source_code", "enrich_imports", ["source_code"], schema=T)

    with op.batch_alter_table("enrich_source_pages", schema=T) as b:
        b.add_column(sa.Column("mst", sa.String(length=14), nullable=True))
        b.create_index("ix_enrich_source_pages_mst", ["mst"])

    with op.batch_alter_table("enrich_sources", schema=T) as b:
        b.add_column(sa.Column("paused_reason", sa.Text(), nullable=False, server_default=""))
        b.add_column(sa.Column("paused_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("enrich_crawl_jobs", schema=T) as b:
        b.add_column(sa.Column("run_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("next_attempt_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("handled_by_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_enrich_crawl_jobs_run", "enrich_runs", ["run_id"], ["id"], referent_schema=T, ondelete="CASCADE")
        b.create_foreign_key("fk_enrich_crawl_jobs_handler", "admin_users", ["handled_by_id"], ["id"], ondelete="SET NULL")
        b.create_index("ix_enrich_crawl_jobs_run_id", ["run_id"])

    with op.batch_alter_table("enrich_companies", schema=A) as b:
        b.add_column(sa.Column("loai_hinh", sa.String(length=60), nullable=True))

    with op.batch_alter_table("enrich_company_evidence", schema=A) as b:
        b.add_column(sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""))

    with op.batch_alter_table("enrich_signals", schema=A) as b:
        b.add_column(sa.Column("dedupe_key", sa.String(length=64), nullable=False, server_default=""))
        b.add_column(sa.Column("source_page_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_enrich_signals_page", "enrich_source_pages", ["source_page_id"], ["id"], referent_schema=T, ondelete="SET NULL")
        b.create_index("ix_enrich_signals_dedupe_key", ["dedupe_key"])

    with op.batch_alter_table("enrich_person_evidence", schema=B) as b:
        b.add_column(sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""))


def downgrade() -> None:
    pg = _pg()

    def S(name: str) -> str | None:
        return name if pg else None

    A, B, T = S("kho_a"), S("kho_b"), S("thu_thap")
    with op.batch_alter_table("enrich_person_evidence", schema=B) as b:
        b.drop_column("content_hash")
    with op.batch_alter_table("enrich_signals", schema=A) as b:
        b.drop_index("ix_enrich_signals_dedupe_key")
        b.drop_constraint("fk_enrich_signals_page", type_="foreignkey")
        b.drop_column("source_page_id")
        b.drop_column("dedupe_key")
    with op.batch_alter_table("enrich_company_evidence", schema=A) as b:
        b.drop_column("content_hash")
    with op.batch_alter_table("enrich_companies", schema=A) as b:
        b.drop_column("loai_hinh")
    with op.batch_alter_table("enrich_crawl_jobs", schema=T) as b:
        b.drop_index("ix_enrich_crawl_jobs_run_id")
        b.drop_constraint("fk_enrich_crawl_jobs_handler", type_="foreignkey")
        b.drop_constraint("fk_enrich_crawl_jobs_run", type_="foreignkey")
        b.drop_column("handled_by_id")
        b.drop_column("next_attempt_at")
        b.drop_column("run_id")
    with op.batch_alter_table("enrich_source_pages", schema=T) as b:
        b.drop_index("ix_enrich_source_pages_mst")
        b.drop_column("mst")
    with op.batch_alter_table("enrich_sources", schema=T) as b:
        b.drop_column("paused_at")
        b.drop_column("paused_reason")
    for name in ("enrich_imports", "enrich_settings", "enrich_domain_slots", "enrich_fetch_logs", "enrich_runs"):
        op.drop_table(name, schema=T)
