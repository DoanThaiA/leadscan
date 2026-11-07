"""bat pgvector

Revision ID: 0eeeab3eccd3
Revises: e59d6edb3c5e
Create Date: 2026-11-07 15:55:14.944559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0eeeab3eccd3'
down_revision: Union[str, Sequence[str], None] = 'e59d6edb3c5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Bật pgvector (lưu embedding cơ hội/chân dung để matching ở giai đoạn sau). Chỉ PostgreSQL."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS vector")
