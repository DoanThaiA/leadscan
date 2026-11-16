"""lam giau du lieu theo MST — giai doan 1: kho A, kho B, thu thap, vai tro

Revision ID: f6a1c2d3e4b5
Revises: c3e8a5d1f9b7
Create Date: 2026-11-16 10:00:00.000000

PostgreSQL: 3 schema kho_a / kho_b / thu_thap. SQLite (dev): không có schema → bảng nằm chung, tên đã có tiền tố enrich_.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models_enrich import ACCESS_LOG_PG_FUNC, ACCESS_LOG_PG_TRIGGER, ACCESS_LOG_SQLITE_TRIGGERS

# revision identifiers, used by Alembic.
revision: str = 'f6a1c2d3e4b5'
down_revision: Union[str, Sequence[str], None] = 'c3e8a5d1f9b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ("kho_a", "kho_b", "thu_thap")


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    pg = _pg()

    def S(name: str) -> str | None:
        return name if pg else None

    def ref(schema: str, target: str) -> str:
        return f"{schema}.{target}" if pg else target

    A, B, T = S("kho_a"), S("kho_b"), S("thu_thap")
    if pg:
        for s in SCHEMAS:
            op.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")

    with op.batch_alter_table("admin_users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("enrich_role", sa.String(length=16), nullable=True))

    # ---------------------------------------------------------------- thu_thap (bảng không phụ thuộc kho A)
    op.create_table(
        "enrich_sources",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("trust", sa.Float(), nullable=False),
        sa.Column("legal_basis", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
        schema=T,
    )
    op.create_table(
        "enrich_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("list_source", sa.String(length=300), nullable=False),
        sa.Column("purposes", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("mst_count", sa.Integer(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_batches_created_at", "enrich_batches", ["created_at"], schema=T)
    op.create_table(
        "enrich_source_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_code"], [ref("thu_thap", "enrich_sources.code")]),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_source_pages_source_code", "enrich_source_pages", ["source_code"], schema=T)
    op.create_index("ix_enrich_source_pages_content_hash", "enrich_source_pages", ["content_hash"], schema=T)

    # ---------------------------------------------------------------- kho A
    op.create_table(
        "enrich_companies",
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("ten", sa.String(length=400), nullable=True),
        sa.Column("ten_khong_dau", sa.String(length=400), nullable=False),
        sa.Column("dia_chi", sa.String(length=600), nullable=True),
        sa.Column("tinh", sa.String(length=80), nullable=True),
        sa.Column("nganh_nghe", sa.JSON(), nullable=True),
        sa.Column("ngay_thanh_lap", sa.Date(), nullable=True),
        sa.Column("von", sa.BigInteger(), nullable=True),
        sa.Column("trang_thai", sa.String(length=120), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("domain", sa.String(length=200), nullable=True),
        sa.Column("ma_ck", sa.String(length=20), nullable=True),
        sa.Column("niem_yet", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("mst"),
        schema=A,
    )
    for col in ("ten_khong_dau", "tinh", "trang_thai", "domain", "created_at"):
        op.create_index(f"ix_enrich_companies_{col}", "enrich_companies", [col], schema=A)

    op.create_table(
        "enrich_company_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("is_inferred", sa.Boolean(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("source_page_id", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_code"], [ref("thu_thap", "enrich_sources.code")]),
        sa.ForeignKeyConstraint(["batch_id"], [ref("thu_thap", "enrich_batches.id")], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_page_id"], [ref("thu_thap", "enrich_source_pages.id")], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=A,
    )
    op.create_index("ix_enrich_company_evidence_field", "enrich_company_evidence", ["mst", "field"], schema=A)
    op.create_index("ix_enrich_company_evidence_source_code", "enrich_company_evidence", ["source_code"], schema=A)

    op.create_table(
        "enrich_company_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=A,
    )
    op.create_index("ix_enrich_company_changes_mst", "enrich_company_changes", ["mst"], schema=A)
    op.create_index("ix_enrich_company_changes_detected_at", "enrich_company_changes", ["detected_at"], schema=A)

    op.create_table(
        "enrich_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("day", sa.Date(), nullable=True),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_code"], [ref("thu_thap", "enrich_sources.code")]),
        sa.PrimaryKeyConstraint("id"),
        schema=A,
    )
    op.create_index("ix_enrich_signals_mst", "enrich_signals", ["mst"], schema=A)
    op.create_index("ix_enrich_signals_kind", "enrich_signals", ["kind"], schema=A)

    # ---------------------------------------------------------------- thu_thap (phụ thuộc kho A)
    op.create_table(
        "enrich_batch_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], [ref("thu_thap", "enrich_batches.id")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "mst", name="uq_enrich_batch_item"),
        schema=T,
    )
    op.create_index("ix_enrich_batch_items_batch_id", "enrich_batch_items", ["batch_id"], schema=T)
    op.create_index("ix_enrich_batch_items_mst", "enrich_batch_items", ["mst"], schema=T)

    op.create_table(
        "enrich_crawl_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("connector", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connector"], [ref("thu_thap", "enrich_sources.code")]),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_crawl_jobs_mst", "enrich_crawl_jobs", ["mst"], schema=T)
    op.create_index("ix_enrich_crawl_jobs_queue", "enrich_crawl_jobs", ["connector", "status"], schema=T)

    # ---------------------------------------------------------------- kho B
    op.create_table(
        "enrich_persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mst_ca_nhan", sa.String(length=14), nullable=True),
        sa.Column("ho_ten", sa.String(length=200), nullable=False),
        sa.Column("ho_ten_khong_dau", sa.String(length=200), nullable=False),
        sa.Column("nam_sinh", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mst_ca_nhan"),
        schema=B,
    )
    op.create_index("ix_enrich_persons_ho_ten_khong_dau", "enrich_persons", ["ho_ten_khong_dau"], schema=B)

    op.create_table(
        "enrich_person_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("company_mst", sa.String(length=14), nullable=False),
        sa.Column("chuc_danh", sa.String(length=200), nullable=False),
        sa.Column("chuc_danh_chuan", sa.String(length=60), nullable=False),
        sa.Column("la_nguoi_quyet_dinh", sa.Boolean(), nullable=False),
        sa.Column("tu_ngay", sa.Date(), nullable=True),
        sa.Column("den_ngay", sa.Date(), nullable=True),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("trust", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], [ref("kho_b", "enrich_persons.id")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_code"], [ref("thu_thap", "enrich_sources.code")]),
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_person_roles_person_id", "enrich_person_roles", ["person_id"], schema=B)
    op.create_index("ix_enrich_person_roles_company_mst", "enrich_person_roles", ["company_mst"], schema=B)

    op.create_table(
        "enrich_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=10), nullable=False),
        sa.Column("owner_id", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("is_inferred", sa.Boolean(), nullable=False),
        sa.Column("verify_status", sa.String(length=16), nullable=False),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_code"], [ref("thu_thap", "enrich_sources.code")]),
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_contacts_owner_id", "enrich_contacts", ["owner_id"], schema=B)
    op.create_index("ix_enrich_contacts_value", "enrich_contacts", ["value"], schema=B)

    op.create_table(
        "enrich_person_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("is_inferred", sa.Boolean(), nullable=False),
        sa.Column("source_page_id", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], [ref("kho_b", "enrich_persons.id")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_code"], [ref("thu_thap", "enrich_sources.code")]),
        sa.ForeignKeyConstraint(["source_page_id"], [ref("thu_thap", "enrich_source_pages.id")], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_person_evidence_field", "enrich_person_evidence", ["person_id", "field"], schema=B)

    op.create_table(
        "enrich_person_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("source_code", sa.String(length=40), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], [ref("kho_b", "enrich_persons.id")], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_person_changes_person_id", "enrich_person_changes", ["person_id"], schema=B)

    op.create_table(
        "enrich_optouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_optouts_value", "enrich_optouts", ["value"], schema=B)

    op.create_table(
        "enrich_access_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"]),  # không SET NULL — nhật ký chỉ ghi thêm
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_access_logs_user_id", "enrich_access_logs", ["user_id"], schema=B)
    op.create_index("ix_enrich_access_logs_created_at", "enrich_access_logs", ["created_at"], schema=B)
    # T08: nhật ký chỉ ghi thêm — chặn UPDATE/DELETE ngay trong CSDL
    if pg:
        op.execute(ACCESS_LOG_PG_FUNC)
        op.execute(ACCESS_LOG_PG_TRIGGER)
    else:
        for sql in ACCESS_LOG_SQLITE_TRIGGERS:
            op.execute(sql)


def downgrade() -> None:
    pg = _pg()

    def S(name: str) -> str | None:
        return name if pg else None

    A, B, T = S("kho_a"), S("kho_b"), S("thu_thap")
    for name in (
        "enrich_access_logs", "enrich_optouts", "enrich_person_changes", "enrich_person_evidence",
        "enrich_contacts", "enrich_person_roles", "enrich_persons",
    ):
        op.drop_table(name, schema=B)
    for name in ("enrich_crawl_jobs", "enrich_batch_items"):
        op.drop_table(name, schema=T)
    for name in ("enrich_signals", "enrich_company_changes", "enrich_company_evidence", "enrich_companies"):
        op.drop_table(name, schema=A)
    for name in ("enrich_source_pages", "enrich_batches", "enrich_sources"):
        op.drop_table(name, schema=T)
    with op.batch_alter_table("admin_users", schema=None) as batch_op:
        batch_op.drop_column("enrich_role")
    if pg:
        op.execute("DROP FUNCTION IF EXISTS kho_b.enrich_access_logs_append_only()")
        for s in SCHEMAS:
            op.execute(f"DROP SCHEMA IF EXISTS {s}")
