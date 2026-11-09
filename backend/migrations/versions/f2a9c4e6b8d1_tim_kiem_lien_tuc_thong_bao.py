"""Phiếu tìm cơ hội "Tìm kiếm liên tục" + thông báo cơ hội mới phù hợp

- search_requests: bỏ trạng thái "done" (Đã có kết quả) — phiếu chỉ còn "open" (Tìm kiếm liên tục) hoặc
  "rejected" (Từ chối). Phiếu "done" cũ chuyển về "open".
- member_notifications: thông báo trong cổng thành viên khi cơ hội mới mở bán khớp phiếu tìm (email gộp).

Revision ID: f2a9c4e6b8d1
Revises: e7f1a2b3c4d5
Create Date: 2026-11-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2a9c4e6b8d1'
down_revision: Union[str, Sequence[str], None] = 'e7f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE search_requests SET status = 'open', resolved_at = NULL WHERE status = 'done'")
    op.create_table(
        'member_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=True),
        sa.Column('opportunity_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=24), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('emailed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['request_id'], ['search_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id', 'opportunity_id', name='uq_notify_request_opp_once'),
    )
    for col in ('company_id', 'request_id', 'opportunity_id', 'read_at', 'emailed_at', 'created_at'):
        op.create_index(op.f(f'ix_member_notifications_{col}'), 'member_notifications', [col], unique=False)


def downgrade() -> None:
    for col in ('company_id', 'request_id', 'opportunity_id', 'read_at', 'emailed_at', 'created_at'):
        op.drop_index(op.f(f'ix_member_notifications_{col}'), table_name='member_notifications')
    op.drop_table('member_notifications')
