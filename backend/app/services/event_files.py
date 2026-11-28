"""Tệp của đăng ký sự kiện trên Cloudflare R2, thư mục SUKIEN/ (cùng bucket riêng tư với CV và tệp phiếu cơ hội).

Người đăng ký là khách lạ nên KHÔNG cấp link upload thẳng lên R2: tệp đi qua backend, được kiểm tra
đuôi + chữ ký đầu file + dung lượng rồi mới đẩy lên.

  SUKIEN/profile/<năm-tháng>/<uuid>/<tên file>     profile doanh nghiệp (PDF)
  SUKIEN/thanh-toan/<năm-tháng>/<uuid>/<tên file>  ảnh chụp màn hình chuyển khoản
"""

import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services import storage

log = logging.getLogger("leadscan.events")

PROFILE_PREFIX = "SUKIEN/profile"
PROOF_PREFIX = "SUKIEN/thanh-toan"


def enabled() -> bool:
    """Đã cấu hình R2 → form cho đính kèm profile và nộp ảnh chuyển khoản."""
    return storage.configured()


def _key(prefix: str, filename: str) -> str:
    month = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m")
    return f"{prefix}/{month}/{uuid.uuid4().hex}/{filename}"


def _upload(prefix: str, filename: str, mime: str, data: bytes) -> str:
    key = _key(prefix, filename)
    try:
        storage.backend().put_bytes(key, data, mime)
    except storage.StorageError:
        raise
    except Exception as e:  # noqa: BLE001 — lỗi mạng / botocore
        raise storage.StorageError(f"Không tải được tệp lên R2: {e}") from e
    return key


def upload_profile(filename: str, mime: str, data: bytes) -> str:
    return _upload(PROFILE_PREFIX, filename, mime, data)


def upload_proof(filename: str, mime: str, data: bytes) -> str:
    return _upload(PROOF_PREFIX, filename, mime, data)


def fetch(key: str) -> bytes:
    """Nội dung tệp (để đính kèm email hoặc gửi cho OCR). Lỗi R2 → storage.StorageError."""
    try:
        return storage.backend().get_bytes(key)
    except storage.StorageError:
        raise
    except Exception as e:  # noqa: BLE001
        raise storage.StorageError(f"Không đọc được tệp trên R2: {e}") from e


def view_url(key: str, filename: str, inline: bool = True) -> str:
    """Link xem/tải ký sẵn, hết hạn sau LEADSCAN_ATTACH_URL_TTL giây."""
    return storage.backend().presign_get(key, filename, inline, get_settings().attach_url_ttl)


def purge(keys: list[str]) -> None:
    """Xoá tệp trên R2 (chạy nền, tự thử lại khi R2 lỗi tạm). Không có Redis thì xoá luôn."""
    keys = [k for k in keys if k]
    if not keys:
        return
    from app.worker import enqueue, purge_files_task

    if not enqueue(purge_files_task, keys):
        try:
            storage.backend().delete(keys)
        except Exception:  # noqa: BLE001
            log.exception("Không xoá được %s tệp sự kiện trên R2", len(keys))
