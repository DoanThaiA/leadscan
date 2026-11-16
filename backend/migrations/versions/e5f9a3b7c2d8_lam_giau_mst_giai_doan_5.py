"""lam giau du lieu theo MST — giai doan 5: theo doi + canh bao, bo loc da luu, nhat ky xuat, ma hoa MST ca nhan

Revision ID: e5f9a3b7c2d8
Revises: d4e8f2a6b9c1
Create Date: 2026-11-20 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f9a3b7c2d8'
down_revision: Union[str, Sequence[str], None] = 'd4e8f2a6b9c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.enrich.crypto import PREFIX, EncryptedMst, encrypt_det

    pg = op.get_bind().dialect.name == "postgresql"
    A, B, T = ("kho_a", "kho_b", "thu_thap") if pg else (None, None, None)

    def ref(schema: str, target: str) -> str:
        return f"{schema}.{target}" if pg else target

    op.create_table(
        "enrich_watchlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("shared", sa.Boolean(), nullable=False),
        sa.Column("kinds", sa.JSON(), nullable=False),
        sa.Column("email_digest", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_watchlists_owner_id", "enrich_watchlists", ["owner_id"], schema=T)
    op.create_table(
        "enrich_watch_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["watchlist_id"], [ref("thu_thap", "enrich_watchlists.id")], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mst"], [ref("kho_a", "enrich_companies.mst")], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watchlist_id", "mst", name="uq_enrich_watch_item"),
        schema=T,
    )
    op.create_index("ix_enrich_watch_items_watchlist_id", "enrich_watch_items", ["watchlist_id"], schema=T)
    op.create_index("ix_enrich_watch_items_mst", "enrich_watch_items", ["mst"], schema=T)
    op.create_table(
        "enrich_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=True),
        sa.Column("mst", sa.String(length=14), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("ref", sa.String(length=60), nullable=False),
        sa.Column("emailed_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["watchlist_id"], [ref("thu_thap", "enrich_watchlists.id")], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_alerts_user_unread", "enrich_alerts", ["user_id", "read_at"], schema=T)
    op.create_index("ix_enrich_alerts_mst", "enrich_alerts", ["mst"], schema=T)
    op.create_index("ix_enrich_alerts_created_at", "enrich_alerts", ["created_at"], schema=T)
    op.create_table(
        "enrich_saved_filters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("shared", sa.Boolean(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_saved_filters_owner_id", "enrich_saved_filters", ["owner_id"], schema=T)
    op.create_table(
        "enrich_exports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("filter", sa.JSON(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("blocked_count", sa.Integer(), nullable=False),
        sa.Column("optout_count", sa.Integer(), nullable=False),
        sa.Column("include_inferred", sa.Boolean(), nullable=False),
        sa.Column("includes_kho_b", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=T,
    )
    op.create_index("ix_enrich_exports_user_id", "enrich_exports", ["user_id"], schema=T)
    op.create_index("ix_enrich_exports_created_at", "enrich_exports", ["created_at"], schema=T)

    with op.batch_alter_table("enrich_optouts", schema=B) as b:
        b.add_column(sa.Column("created_by_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_enrich_optouts_user", "admin_users", ["created_by_id"], ["id"], ondelete="SET NULL")

    # N05: MST cá nhân → bản mã AES-SIV (cột dài hơn), mã hoá dữ liệu đang có
    with op.batch_alter_table("enrich_persons", schema=B) as b:
        b.alter_column("mst_ca_nhan", type_=sa.String(length=120), existing_type=sa.String(length=14), existing_nullable=True)
    persons = sa.table("enrich_persons", sa.column("id", sa.Integer), sa.column("mst_ca_nhan", sa.String), schema=B)
    conn = op.get_bind()
    for pid, val in conn.execute(sa.select(persons.c.id, persons.c.mst_ca_nhan).where(persons.c.mst_ca_nhan.is_not(None))).all():
        if not val.startswith(PREFIX):
            conn.execute(persons.update().where(persons.c.id == pid).values(mst_ca_nhan=encrypt_det(val, EncryptedMst.CONTEXT)))


def downgrade() -> None:
    from app.enrich.crypto import PREFIX, EncryptedMst, decrypt_det

    pg = op.get_bind().dialect.name == "postgresql"
    B, T = ("kho_b", "thu_thap") if pg else (None, None)
    persons = sa.table("enrich_persons", sa.column("id", sa.Integer), sa.column("mst_ca_nhan", sa.String), schema=B)
    conn = op.get_bind()
    for pid, val in conn.execute(sa.select(persons.c.id, persons.c.mst_ca_nhan).where(persons.c.mst_ca_nhan.is_not(None))).all():
        if val.startswith(PREFIX):
            conn.execute(persons.update().where(persons.c.id == pid).values(mst_ca_nhan=decrypt_det(val, EncryptedMst.CONTEXT)))
    with op.batch_alter_table("enrich_persons", schema=B) as b:
        b.alter_column("mst_ca_nhan", type_=sa.String(length=14), existing_type=sa.String(length=120), existing_nullable=True)
    with op.batch_alter_table("enrich_optouts", schema=B) as b:
        b.drop_constraint("fk_enrich_optouts_user", type_="foreignkey")
        b.drop_column("created_by_id")
    for name in ("enrich_exports", "enrich_saved_filters", "enrich_alerts", "enrich_watch_items", "enrich_watchlists"):
        op.drop_table(name, schema=T)
