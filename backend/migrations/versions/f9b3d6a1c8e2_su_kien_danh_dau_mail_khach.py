"""su kien: danh dau da gui email cho khach (nhan dang ky / xac nhan thanh toan) de khong gui trung + check-in bang QR

Revision ID: f9b3d6a1c8e2
Revises: e1a7c4d9b63f
Create Date: 2026-11-28 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9b3d6a1c8e2'
down_revision: Union[str, Sequence[str], None] = 'e1a7c4d9b63f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("event_registrations") as b:
        b.add_column(sa.Column("receipt_sent_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("confirm_sent_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("checked_in_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("checked_in_by_id", sa.Integer(), nullable=True))
        b.create_foreign_key(
            "fk_event_registrations_checked_in_by_id_admin_users", "admin_users", ["checked_in_by_id"], ["id"], ondelete="SET NULL"
        )
    # Đăng ký cũ đã báo ban tổ chức thì coi như khách cũng đã nhận email (luồng cũ gửi khách trước) → không gửi lại
    op.execute("UPDATE event_registrations SET receipt_sent_at = email_sent_at WHERE email_sent_at IS NOT NULL")
    op.execute("UPDATE event_registrations SET confirm_sent_at = paid_at WHERE status = 'paid' AND paid_at IS NOT NULL")


def downgrade() -> None:
    with op.batch_alter_table("event_registrations") as b:
        b.drop_constraint("fk_event_registrations_checked_in_by_id_admin_users", type_="foreignkey")
        b.drop_column("checked_in_by_id")
        b.drop_column("checked_in_at")
        b.drop_column("confirm_sent_at")
        b.drop_column("receipt_sent_at")
