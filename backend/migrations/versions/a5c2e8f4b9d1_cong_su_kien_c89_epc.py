"""cong su kien c89 / epc: cot site cho su kien, dang ky va tai khoan quan tri

Revision ID: a5c2e8f4b9d1
Revises: f3b8d1c6a2e4
Create Date: 2026-11-28 16:00:00.000000

- events.site, event_registrations.site: trang đăng (leadscan / c89 / epc). Dữ liệu cũ → "leadscan" (giữ nguyên
  link leadscan.net/su-kien/... đang chia sẻ). Chuyển 1 sự kiện sang cổng khác trong admin LeadScan, ô "Trang đăng".
- admin_users.site: NULL = nhân viên LeadScan (như cũ); "c89" / "epc" = tài khoản chỉ quản lý cổng sự kiện đó.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a5c2e8f4b9d1'
down_revision: Union[str, Sequence[str], None] = 'f3b8d1c6a2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("events", "event_registrations"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("site", sa.String(length=20), nullable=False, server_default="leadscan"))
            batch_op.create_index(batch_op.f(f"ix_{table}_site"), ["site"], unique=False)
    with op.batch_alter_table("admin_users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("site", sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f("ix_admin_users_site"), ["site"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("admin_users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_admin_users_site"))
        batch_op.drop_column("site")
    for table in ("event_registrations", "events"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f"ix_{table}_site"))
            batch_op.drop_column("site")
