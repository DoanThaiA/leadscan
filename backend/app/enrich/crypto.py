"""Mã hoá dữ liệu kho B khi lưu (N05).

• MST cá nhân: AES-SIV (mã hoá TẤT ĐỊNH) — cùng giá trị cho cùng bản mã nên vẫn tìm bằng `==` và giữ ràng buộc duy nhất,
  nhưng CSDL / bản sao lưu không chứa giá trị thật.
• Bản gốc (HTML, PDF — có thể chứa danh sách người nội bộ): Fernet trước khi ghi lên R2 / đĩa.
• Khoá băm (HMAC) cho danh sách từ chối theo MST cá nhân / tên + doanh nghiệp: không lưu giá trị gốc.

Khoá: LEADSCAN_ENRICH_DATA_KEY (base64, 64 byte — tạo bằng `python -m app.cli gen-data-key`). Thiếu khoá thì dùng khoá
phát triển cố định và ghi cảnh báo — KHÔNG dùng trên máy chủ thật. Mất khoá = mất MST cá nhân và bản gốc đã mã hoá.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from functools import lru_cache

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

log = logging.getLogger("leadscan.enrich.crypto")

PREFIX = "e1:"
RAW_MAGIC = b"LSE1"


@lru_cache
def master_key() -> bytes:
    from app.config import get_settings

    raw = get_settings().enrich_data_key
    if raw:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(key) != 64:
            raise RuntimeError("LEADSCAN_ENRICH_DATA_KEY phải là 64 byte (base64).")
        return key
    log.warning("Chưa đặt LEADSCAN_ENRICH_DATA_KEY — đang dùng khoá phát triển, KHÔNG dùng cho dữ liệu thật.")
    return hashlib.sha512(b"leadscan-dev-only-key").digest()


def _sub(label: bytes) -> bytes:
    return hmac.new(master_key(), label, hashlib.sha512).digest()


def encrypt_det(value: str, context: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV

    ct = AESSIV(_sub(b"siv")[:64]).encrypt(value.encode("utf-8"), [context])
    return PREFIX + base64.urlsafe_b64encode(ct).decode().rstrip("=")


def decrypt_det(token: str, context: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV

    data = token[len(PREFIX):]
    ct = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return AESSIV(_sub(b"siv")[:64]).decrypt(ct, [context]).decode("utf-8")


def blind_index(value: str, purpose: str) -> str:
    """HMAC — dùng cho danh sách từ chối: so khớp được mà không lưu giá trị gốc."""
    return hmac.new(_sub(b"idx"), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


class EncryptedMst(TypeDecorator):
    """Cột MST cá nhân: lưu bản mã AES-SIV, đọc ra giá trị thật; so sánh `==` vẫn đúng vì mã hoá tất định."""

    impl = String(120)
    cache_ok = True
    CONTEXT = b"enrich_persons.mst_ca_nhan"

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return None
        if isinstance(value, str) and value.startswith(PREFIX):
            return value
        return encrypt_det(str(value), self.CONTEXT)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_det(value, self.CONTEXT) if value.startswith(PREFIX) else value


@lru_cache
def _fernet():
    from cryptography.fernet import Fernet

    return Fernet(base64.urlsafe_b64encode(_sub(b"raw")[:32]))


def encrypt_blob(data: bytes) -> bytes:
    return RAW_MAGIC + _fernet().encrypt(data)


def decrypt_blob(data: bytes) -> bytes:
    if data.startswith(RAW_MAGIC):
        return _fernet().decrypt(data[len(RAW_MAGIC):])
    return data  # bản gốc lưu trước khi bật mã hoá


def generate_key() -> str:
    import os

    return base64.urlsafe_b64encode(os.urandom(64)).decode()
