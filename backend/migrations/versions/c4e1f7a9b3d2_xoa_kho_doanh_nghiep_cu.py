"""xoa bang kho doanh nghiep cu (knowledge_companies)

Du lieu da chuyen sang phan he lam giau theo MST bang `enrich-from-knowledge` (lo #4, #5 tren may chu, 501 DN).
Xoa luon: ten CEO, logo, trang thai AI, ghi chu noi bo, `extra` cua kho cu (khong chuyen sang theo quyet dinh).
Downgrade chi tao lai bang RONG — du lieu khong khoi phuc duoc (dung ban sao luu deploy/backup.sh neu can).

Revision ID: c4e1f7a9b3d2
Revises: b2c8d4e6f0a1
Create Date: 2026-11-17 18:00:00.000000
"""
import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4e1f7a9b3d2'
down_revision: Union[str, Sequence[str], None] = 'b2c8d4e6f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXED = ["name", "industry", "province", "source", "ai_status", "created_at"]


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("knowledge_companies"):
        return
    with op.batch_alter_table("knowledge_companies", schema=None) as batch_op:
        for col in INDEXED:
            batch_op.drop_index(batch_op.f(f"ix_knowledge_companies_{col}"))
    op.drop_table("knowledge_companies")


def downgrade() -> None:
    # tạo lại cấu trúc bảng (rỗng) đúng như migration gốc a7c3d91f2b10
    path = Path(__file__).with_name("a7c3d91f2b10_kho_doanh_nghiep.py")
    spec = importlib.util.spec_from_file_location("_kho_doanh_nghiep_goc", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.upgrade()
