"""su kien: tong so ve (doi ten capacity) + so ve da ban ngoai form

Revision ID: f3b8d1c6a2e4
Revises: e1a7c4d9b63f
Create Date: 2026-11-28 14:00:00.000000

events.capacity ("quy mô dự kiến") đổi thành events.ticket_total (tổng số vé) — giữ nguyên số đã nhập.
events.tickets_sold: vé ban tổ chức đã bán ngoài form (chuyển khoản riêng, bán tại CLB…), nhập tay.
Trang sự kiện hiện: đã đăng ký = tickets_sold + số đăng ký trên web chưa huỷ; còn lại = ticket_total − đã đăng ký.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3b8d1c6a2e4'
down_revision: Union[str, Sequence[str], None] = 'e1a7c4d9b63f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.alter_column("capacity", new_column_name="ticket_total", existing_type=sa.Integer(), existing_nullable=True)
        batch_op.add_column(sa.Column("tickets_sold", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_column("tickets_sold")
        batch_op.alter_column("ticket_total", new_column_name="capacity", existing_type=sa.Integer(), existing_nullable=True)
