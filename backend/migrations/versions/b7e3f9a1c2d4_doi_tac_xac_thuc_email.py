"""Đối tác: kích hoạt tài khoản bằng mã OTP gửi qua email (bỏ xác thực SĐT qua SMS)

Đối tác đã xác thực SĐT trước đây được giữ trạng thái kích hoạt (email_verified_at = phone_verified_at).

Revision ID: b7e3f9a1c2d4
Revises: a4d8e2c6f1b3
Create Date: 2026-11-12 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e3f9a1c2d4'
down_revision: Union[str, Sequence[str], None] = 'a4d8e2c6f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('partner_users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))
    op.create_index('ix_partner_users_email_verified_at', 'partner_users', ['email_verified_at'])
    op.execute("UPDATE partner_users SET email_verified_at = phone_verified_at WHERE phone_verified_at IS NOT NULL")
    op.add_column('partner_otps', sa.Column('email', sa.String(length=150), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('partner_otps', 'email')
    op.drop_index('ix_partner_users_email_verified_at', table_name='partner_users')
    op.drop_column('partner_users', 'email_verified_at')
