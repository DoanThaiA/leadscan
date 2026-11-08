"""yeu cau enrich tim kiem co hoi (search_requests)

Revision ID: c5d2a8e41f63
Revises: b81f4c2d9e07
Create Date: 2026-11-08 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5d2a8e41f63'
down_revision: Union[str, Sequence[str], None] = 'b81f4c2d9e07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXED = ("company_id", "status", "created_at")


def upgrade() -> None:
    op.create_table(
        "search_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("member_user_id", sa.Integer(), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("email_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_user_id"], ["member_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("search_requests", schema=None) as batch_op:
        for col in INDEXED:
            batch_op.create_index(batch_op.f(f"ix_search_requests_{col}"), [col], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("search_requests", schema=None) as batch_op:
        for col in INDEXED:
            batch_op.drop_index(batch_op.f(f"ix_search_requests_{col}"))
    op.drop_table("search_requests")
