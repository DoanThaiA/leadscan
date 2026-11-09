"""pgvector + Cohere embedding, so khớp chạy nền, Tất cả cơ hội bắt đầu trống

- PostgreSQL: cột embedding của opportunities / search_requests đổi từ JSON sang pgvector vector(1024)
  (Cohere output_dimension = 1024). SQLite (test) giữ JSON.
- embedding_model rộng hơn (80), thêm embedding_sha (chỉ gọi lại Cohere khi văn bản đổi); xoá vector cũ để nhúng lại.
- search_requests: match_status (pending/running/done/error), match_error, matched_at — so khớp chạy bằng Celery.
- api_usage: đếm lượt gọi Cohere theo tháng (khoá Trial miễn phí tối đa 1.000 lần/tháng).
- "Tất cả cơ hội" của doanh nghiệp chỉ có cơ hội khớp phiếu tìm: xoá các dòng cũ không gắn phiếu tìm nào.
  Phiếu tìm cũ để "pending" → chạy `python -m app.cli rematch` sau khi deploy để so khớp lại.

Revision ID: e7f1a2b3c4d5
Revises: d9e3b7a1c0f4
Create Date: 2026-11-09 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd9e3b7a1c0f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIM = 1024
TABLES = ("opportunities", "search_requests")


def upgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"
    if pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column("embedding_model", existing_type=sa.String(length=60), type_=sa.String(length=80), existing_nullable=False)
            batch_op.add_column(sa.Column("embedding_sha", sa.String(length=40), nullable=False, server_default=""))
        if pg:
            op.execute(f"ALTER TABLE {table} DROP COLUMN embedding")
            op.execute(f"ALTER TABLE {table} ADD COLUMN embedding vector({DIM})")
        else:
            op.execute(f"UPDATE {table} SET embedding = NULL")
        op.execute(f"UPDATE {table} SET embedding_model = '', embedding_sha = ''")

    with op.batch_alter_table("search_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("match_status", sa.String(length=16), nullable=False, server_default="pending"))
        batch_op.add_column(sa.Column("match_error", sa.String(length=300), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("matched_at", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_search_requests_match_status"), ["match_status"], unique=False)

    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "month", name="uq_api_usage_month"),
    )

    op.execute("DELETE FROM user_opportunities WHERE best_request_id IS NULL")


def downgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"
    op.drop_table("api_usage")
    with op.batch_alter_table("search_requests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_search_requests_match_status"))
        batch_op.drop_column("matched_at")
        batch_op.drop_column("match_error")
        batch_op.drop_column("match_status")
    for table in TABLES:
        if pg:
            op.execute(f"ALTER TABLE {table} DROP COLUMN embedding")
            op.execute(f"ALTER TABLE {table} ADD COLUMN embedding JSON")
        op.execute(f"UPDATE {table} SET embedding_model = ''")
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("embedding_sha")
            batch_op.alter_column("embedding_model", existing_type=sa.String(length=80), type_=sa.String(length=60), existing_nullable=False)
