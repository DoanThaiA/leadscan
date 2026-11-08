"""co hoi phu hop + kho cua toi

- companies.industry: 100 -> 300 ký tự (chọn nhiều ngành)
- profiles.search: tiêu chí tìm cơ hội phù hợp
- saved_opportunities: cơ hội thành viên thêm vào kho

Revision ID: b81f4c2d9e07
Revises: a7c3d91f2b10
Create Date: 2026-11-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b81f4c2d9e07'
down_revision: Union[str, Sequence[str], None] = 'a7c3d91f2b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.alter_column("industry", existing_type=sa.String(length=100), type_=sa.String(length=300), existing_nullable=False)
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("search", sa.JSON(), nullable=False, server_default="{}"))

    op.create_table(
        "saved_opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("member_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_user_id"], ["member_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "opportunity_id", name="uq_saved_once"),
    )
    with op.batch_alter_table("saved_opportunities", schema=None) as batch_op:
        for col in ("company_id", "opportunity_id", "created_at"):
            batch_op.create_index(batch_op.f(f"ix_saved_opportunities_{col}"), [col], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("saved_opportunities", schema=None) as batch_op:
        for col in ("company_id", "opportunity_id", "created_at"):
            batch_op.drop_index(batch_op.f(f"ix_saved_opportunities_{col}"))
    op.drop_table("saved_opportunities")
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_column("search")
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.alter_column("industry", existing_type=sa.String(length=300), type_=sa.String(length=100), existing_nullable=False)
