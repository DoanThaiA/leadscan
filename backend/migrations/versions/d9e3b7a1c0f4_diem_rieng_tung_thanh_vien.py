"""diem rieng tung thanh vien: user_opportunities, search_request_matches, embedding

- opportunities.embedding / embedding_model, search_requests.embedding / embedding_model
- user_opportunities: "Tất cả cơ hội" của từng doanh nghiệp + điểm riêng (mỗi cặp 1 dòng)
- search_request_matches: cơ hội phù hợp của từng phiếu tìm cơ hội
- Dữ liệu cũ: cơ hội đã mua / đã lưu được giữ lại trong "Tất cả cơ hội" của doanh nghiệp (điểm cũ của phiếu)

Revision ID: d9e3b7a1c0f4
Revises: c5d2a8e41f63
Create Date: 2026-11-09 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9e3b7a1c0f4'
down_revision: Union[str, Sequence[str], None] = 'c5d2a8e41f63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("opportunities", "search_requests"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("embedding", sa.JSON(), nullable=True))
            batch_op.add_column(sa.Column("embedding_model", sa.String(length=60), nullable=False, server_default=""))

    op.create_table(
        "user_opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_fit", sa.Integer(), nullable=False),
        sa.Column("score_urgency", sa.Integer(), nullable=False),
        sa.Column("score_trust", sa.Integer(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("best_request_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["best_request_id"], ["search_requests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "opportunity_id", name="uq_user_opp_once"),
    )
    with op.batch_alter_table("user_opportunities", schema=None) as batch_op:
        for col in ("company_id", "opportunity_id", "score", "created_at"):
            batch_op.create_index(batch_op.f(f"ix_user_opportunities_{col}"), [col], unique=False)

    op.create_table(
        "search_request_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_fit", sa.Integer(), nullable=False),
        sa.Column("score_urgency", sa.Integer(), nullable=False),
        sa.Column("score_trust", sa.Integer(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["search_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "opportunity_id", name="uq_request_opp_once"),
    )
    with op.batch_alter_table("search_request_matches", schema=None) as batch_op:
        for col in ("request_id", "opportunity_id"):
            batch_op.create_index(batch_op.f(f"ix_search_request_matches_{col}"), [col], unique=False)

    # Giữ lại cơ hội đã mua / đã lưu của từng doanh nghiệp (không gắn phiếu tìm → không bị dọn khi so khớp lại)
    op.execute(
        """
        INSERT INTO user_opportunities
            (company_id, opportunity_id, score, score_fit, score_urgency, score_trust, reasons, best_request_id, created_at, updated_at)
        SELECT x.company_id, x.opportunity_id, o.score, o.score_fit, o.score_urgency, o.score_trust, '[]', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM (
            SELECT company_id, opportunity_id FROM purchases
            UNION
            SELECT company_id, opportunity_id FROM saved_opportunities
        ) x
        JOIN opportunities o ON o.id = x.opportunity_id
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("search_request_matches", schema=None) as batch_op:
        for col in ("request_id", "opportunity_id"):
            batch_op.drop_index(batch_op.f(f"ix_search_request_matches_{col}"))
    op.drop_table("search_request_matches")
    with op.batch_alter_table("user_opportunities", schema=None) as batch_op:
        for col in ("company_id", "opportunity_id", "score", "created_at"):
            batch_op.drop_index(batch_op.f(f"ix_user_opportunities_{col}"))
    op.drop_table("user_opportunities")
    for table in ("search_requests", "opportunities"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("embedding_model")
            batch_op.drop_column("embedding")
