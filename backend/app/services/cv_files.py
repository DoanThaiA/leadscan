"""File CV của ứng viên trên Cloudflare R2, thư mục CV/ (cùng bucket riêng tư với tệp phiếu cơ hội).

Khác tệp phiếu cơ hội (trình duyệt PUT thẳng lên R2 bằng link ký sẵn), CV đi qua backend: ứng viên là người lạ,
không cấp link upload cho họ — backend kiểm tra đúng PDF/DOC/DOCX rồi mới đẩy lên R2.

Key: CV/<năm-tháng>/<uuid>/<tên file>  → xem theo tháng trong Cloudflare dashboard, không trùng tên.
"""

import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services import storage

log = logging.getLogger("leadscan.cv")

PREFIX = "CV"


def enabled() -> bool:
    """Đã cấu hình R2 → form ứng tuyển cho tải file CV; chưa thì chỉ nhận link CV."""
    return storage.configured()


def new_key(filename: str) -> str:
    month = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m")
    return f"{PREFIX}/{month}/{uuid.uuid4().hex}/{filename}"


def upload(filename: str, mime: str, data: bytes) -> str:
    """Đẩy file lên R2, trả về key. Lỗi R2 → storage.StorageError."""
    key = new_key(filename)
    try:
        storage.backend().put_bytes(key, data, mime)
    except storage.StorageError:
        raise
    except Exception as e:  # noqa: BLE001 — lỗi mạng / botocore
        raise storage.StorageError(f"Không tải được CV lên R2: {e}") from e
    return key


def fetch(key: str) -> bytes:
    """Lấy nội dung file (để đính kèm email). Lỗi R2 → storage.StorageError."""
    try:
        return storage.backend().get_bytes(key)
    except storage.StorageError:
        raise
    except Exception as e:  # noqa: BLE001
        raise storage.StorageError(f"Không đọc được CV trên R2: {e}") from e


def download_url(key: str, filename: str) -> str:
    """Link tải ký sẵn, hết hạn sau LEADSCAN_ATTACH_URL_TTL giây."""
    return storage.backend().presign_get(key, filename, False, get_settings().attach_url_ttl)


def purge(keys: list[str]) -> None:
    """Xoá file trên R2 (chạy nền, tự thử lại khi R2 lỗi tạm). Không có Redis thì xoá luôn."""
    keys = [k for k in keys if k]
    if not keys:
        return
    from app.worker import enqueue, purge_files_task

    if not enqueue(purge_files_task, keys):
        try:
            storage.backend().delete(keys)
        except Exception:  # noqa: BLE001
            log.exception("Không xoá được %s file CV trên R2", len(keys))
