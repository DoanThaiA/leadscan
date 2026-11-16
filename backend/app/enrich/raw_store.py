"""Lưu bản gốc (A09, N07): nén gzip rồi mã hoá (N05), khoá theo mã băm nội dung → cùng nội dung chỉ lưu một lần.

Có cấu hình R2 thì lưu trên R2 (prefix enrich-raw/), không thì lưu đĩa cục bộ (LEADSCAN_ENRICH_RAW_DIR).
"""

import gzip
import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db import utcnow
from app.enrich import crypto
from app.models_enrich import SourcePage
from app.services import storage

PREFIX = "enrich-raw"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _local_dir() -> Path:
    d = get_settings().enrich_raw_dir
    return Path(d) if d else BACKEND_DIR / "data" / "enrich-raw"


def _use_r2() -> bool:
    return storage._override is not None or storage.configured()  # noqa: SLF001 — test đặt MemoryStorage


def put(source_code: str, content_hash: str, data: bytes, content_type: str) -> str:
    key = f"{PREFIX}/{source_code}/{content_hash[:2]}/{content_hash}.gz"
    packed = crypto.encrypt_blob(gzip.compress(data, compresslevel=6))  # N05: bản gốc có thể chứa dữ liệu cá nhân
    if _use_r2():
        storage.backend().put_bytes(key, packed, "application/gzip")
    else:
        path = _local_dir() / key
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(packed)
    return key


def get(key: str) -> bytes:
    if _use_r2():
        packed = storage.backend().get_bytes(key)
    else:
        packed = (_local_dir() / key).read_bytes()
    return gzip.decompress(crypto.decrypt_blob(packed))


def save_page(
    db: Session,
    source_code: str,
    url: str,
    data: bytes,
    content_type: str,
    http_status: int | None = 200,
    mst: str | None = None,
) -> tuple[SourcePage, bool]:
    """Lưu bản gốc. Trả về (trang, là nội dung mới?). Cùng URL + cùng mã băm đã có → dùng lại (B12)."""
    h = sha256(data)
    page = db.scalar(
        select(SourcePage).where(SourcePage.source_code == source_code, SourcePage.url == url[:1000], SourcePage.content_hash == h)
    )
    if page:
        return page, False
    key = put(source_code, h, data, content_type)
    page = SourcePage(
        source_code=source_code,
        mst=mst,
        url=url[:1000],
        content_hash=h,
        storage_key=key,
        content_type=content_type[:100],
        size=len(data),
        http_status=http_status,
        fetched_at=utcnow(),
    )
    db.add(page)
    db.flush()
    return page, True
