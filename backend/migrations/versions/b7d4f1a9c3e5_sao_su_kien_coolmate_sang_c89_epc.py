"""su kien: sao su kien CEO1989 x Coolmate cua LeadScan sang 2 cong c89, epc

Revision ID: b7d4f1a9c3e5
Revises: a5c2e8f4b9d1
Create Date: 2026-11-28 17:00:00.000000

Chép nguyên dòng sự kiện ĐANG CÓ trên máy chủ (gồm cả phần đã sửa trong trang quản trị: tài khoản nhận phí,
nội dung, ảnh, số vé) sang cổng c89 và epc. Đường dẫn là duy nhất trên mọi trang nên bản sao thêm đuôi "-c89" /
"-epc". Đăng ký đã nhận KHÔNG chép theo — mỗi trang nhận đăng ký và đếm vé riêng.

Không tìm thấy sự kiện gốc, hoặc cổng đã có bản này → bỏ qua cổng đó.
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7d4f1a9c3e5'
down_revision: Union[str, Sequence[str], None] = 'a5c2e8f4b9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOURCE_SLUG = "ceo1989-x-coolmate-tu-noi-luc-den-tang-truong"
PORTALS = ("c89", "epc")


def _events(bind) -> sa.Table:
    return sa.Table("events", sa.MetaData(), autoload_with=bind)


def upgrade() -> None:
    bind = op.get_bind()
    events = _events(bind)
    source = bind.execute(sa.select(events).where(events.c.slug == SOURCE_SLUG)).mappings().first()
    if source is None:
        return
    now = datetime.utcnow()
    for site in PORTALS:
        slug = f"{SOURCE_SLUG}-{site}"
        if source["site"] == site:  # sự kiện gốc đã được chuyển sang cổng này trong admin
            continue
        if bind.execute(sa.select(events.c.id).where(events.c.slug == slug)).first():
            continue
        row = {k: v for k, v in source.items() if k != "id"}
        row.update(site=site, slug=slug, created_at=now, updated_at=now)
        if row["status"] == "published":
            row["published_at"] = now
        bind.execute(events.insert().values(**row))


def downgrade() -> None:
    """Chỉ xoá bản sao chưa có ai đăng ký — không làm mất đăng ký đã nhận."""
    bind = op.get_bind()
    events = _events(bind)
    for site in PORTALS:
        bind.execute(
            sa.text(
                "DELETE FROM events WHERE slug = :slug AND site = :site "
                "AND NOT EXISTS (SELECT 1 FROM event_registrations r WHERE r.event_id = events.id)"
            ),
            {"slug": f"{SOURCE_SLUG}-{site}", "site": site},
        )
