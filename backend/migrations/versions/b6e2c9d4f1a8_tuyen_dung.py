"""tuyen dung: bai tuyen dung (job_posts) + ho so ung tuyen (job_applications)

Revision ID: b6e2c9d4f1a8
Revises: a3b8d5e1f7c2
Create Date: 2026-11-10 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6e2c9d4f1a8'
down_revision: Union[str, Sequence[str], None] = 'a3b8d5e1f7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=False),
        sa.Column("employment_type", sa.String(length=20), nullable=False),
        sa.Column("salary", sa.String(length=150), nullable=False),
        sa.Column("work_time", sa.String(length=200), nullable=False),
        sa.Column("reports_to", sa.String(length=150), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("benefits", sa.Text(), nullable=False),
        sa.Column("how_to_apply", sa.Text(), nullable=False),
        sa.Column("apply_email", sa.String(length=200), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    with op.batch_alter_table("job_posts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_job_posts_status"), ["status"], unique=False)

    op.create_table(
        "job_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("job_title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("cv_url", sa.String(length=500), nullable=False),
        sa.Column("portfolio_url", sa.String(length=500), nullable=False),
        sa.Column("intro", sa.Text(), nullable=False),
        sa.Column("cv_key", sa.String(length=400), nullable=False),
        sa.Column("cv_filename", sa.String(length=200), nullable=False),
        sa.Column("cv_mime", sa.String(length=100), nullable=False),
        sa.Column("cv_size", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=300), nullable=False),
        sa.Column("email_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("job_applications", schema=None) as batch_op:
        for col in ("job_id", "status", "created_at"):
            batch_op.create_index(batch_op.f(f"ix_job_applications_{col}"), [col], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("job_applications", schema=None) as batch_op:
        for col in ("job_id", "status", "created_at"):
            batch_op.drop_index(batch_op.f(f"ix_job_applications_{col}"))
    op.drop_table("job_applications")
    with op.batch_alter_table("job_posts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_job_posts_status"))
    op.drop_table("job_posts")
