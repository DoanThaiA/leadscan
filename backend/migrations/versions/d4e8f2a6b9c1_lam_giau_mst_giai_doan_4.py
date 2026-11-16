"""lam giau du lieu theo MST — giai doan 4: gop / tach nguoi, nghi trung

Revision ID: d4e8f2a6b9c1
Revises: c9d5e3f7a2b4
Create Date: 2026-11-19 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e8f2a6b9c1'
down_revision: Union[str, Sequence[str], None] = 'c9d5e3f7a2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"
    B = "kho_b" if pg else None
    persons = "kho_b.enrich_persons.id" if pg else "enrich_persons.id"

    with op.batch_alter_table("enrich_persons", schema=B) as b:
        b.add_column(sa.Column("merged_into_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_enrich_persons_merged_into", "enrich_persons", ["merged_into_id"], ["id"], referent_schema=B, ondelete="SET NULL")
        b.create_index("ix_enrich_persons_merged_into_id", ["merged_into_id"])

    op.create_table(
        "enrich_merge_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_a_id", sa.Integer(), nullable=False),
        sa.Column("person_b_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("decided_by_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["person_a_id"], [persons], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_b_id"], [persons], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_a_id", "person_b_id", name="uq_enrich_merge_pair"),
        schema=B,
    )
    for col in ("person_a_id", "person_b_id", "status"):
        op.create_index(f"ix_enrich_merge_candidates_{col}", "enrich_merge_candidates", [col], schema=B)

    op.create_table(
        "enrich_entity_ops",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("op", sa.String(length=10), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("other_person_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("undone_at", sa.DateTime(), nullable=True),
        sa.Column("undone_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], [persons], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["other_person_id"], [persons], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["undone_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=B,
    )
    op.create_index("ix_enrich_entity_ops_person_id", "enrich_entity_ops", ["person_id"], schema=B)
    op.create_index("ix_enrich_entity_ops_other_person_id", "enrich_entity_ops", ["other_person_id"], schema=B)


def downgrade() -> None:
    B = "kho_b" if op.get_bind().dialect.name == "postgresql" else None
    op.drop_table("enrich_entity_ops", schema=B)
    op.drop_table("enrich_merge_candidates", schema=B)
    with op.batch_alter_table("enrich_persons", schema=B) as b:
        b.drop_index("ix_enrich_persons_merged_into_id")
        b.drop_constraint("fk_enrich_persons_merged_into", type_="foreignkey")
        b.drop_column("merged_into_id")
