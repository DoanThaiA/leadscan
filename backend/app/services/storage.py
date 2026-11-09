"""Lưu trữ tệp trên Cloudflare R2 (S3-compatible) cho ảnh & tài liệu của phiếu cơ hội.

Bucket để RIÊNG TƯ (không bật r2.dev / tên miền công khai):
  - Upload: backend cấp link PUT ký sẵn (presigned, ~10 phút) → trình duyệt gửi thẳng tệp lên R2,
    không đi qua Nginx/API (Nginx đang giới hạn body 1 MB).
  - Xem/tải: backend kiểm tra quyền rồi cấp link GET ký sẵn ngắn hạn (cfg.attach_url_ttl).

Test dùng MemoryStorage (set_backend) — không cần R2 thật.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote

from app.config import Settings, get_settings

log = logging.getLogger("leadscan.storage")


class StorageError(RuntimeError):
    pass


@dataclass
class ObjectInfo:
    size: int
    content_type: str


def configured(cfg: Settings | None = None) -> bool:
    if _override is not None:
        return True
    cfg = cfg or get_settings()
    return bool(cfg.r2_account_id or cfg.r2_endpoint) and bool(cfg.r2_access_key_id and cfg.r2_secret_access_key and cfg.r2_bucket)


def content_disposition(filename: str, inline: bool) -> str:
    """Tên tệp tiếng Việt an toàn cho header (RFC 6266 / 5987)."""
    ascii_name = filename.encode("ascii", "ignore").decode() or "tep"
    ascii_name = ascii_name.replace('"', "").replace("\\", "")
    return f"{'inline' if inline else 'attachment'}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


class R2Storage:
    def __init__(self, cfg: Settings):
        import boto3
        from botocore.config import Config

        self.bucket = cfg.r2_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=cfg.r2_endpoint or f"https://{cfg.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=cfg.r2_access_key_id,
            aws_secret_access_key=cfg.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}, connect_timeout=5, read_timeout=30),
        )

    def presign_put(self, key: str, content_type: str, expires: int = 600) -> str:
        # Content-Type nằm trong chữ ký → trình duyệt phải gửi đúng loại đã khai báo
        return self.client.generate_presigned_url(
            "put_object", Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type}, ExpiresIn=expires
        )

    def presign_get(self, key: str, filename: str, inline: bool, expires: int) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key, "ResponseContentDisposition": content_disposition(filename, inline)},
            ExpiresIn=expires,
        )

    def head(self, key: str) -> ObjectInfo | None:
        from botocore.exceptions import ClientError

        try:
            r = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise StorageError(f"R2 lỗi khi kiểm tra tệp: {e}") from e
        return ObjectInfo(size=int(r.get("ContentLength") or 0), content_type=r.get("ContentType") or "")

    def get_bytes(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def delete(self, keys: list[str]) -> None:
        keys = [k for k in keys if k]
        for i in range(0, len(keys), 1000):
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": [{"Key": k} for k in keys[i : i + 1000]], "Quiet": True})


class MemoryStorage:
    """Giả lập R2 trong bộ nhớ (test / chạy thử). Link ký sẵn có dạng memory://..."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}

    def presign_put(self, key: str, content_type: str, expires: int = 600) -> str:
        return f"memory://put/{key}?ct={quote(content_type)}"

    def presign_get(self, key: str, filename: str, inline: bool, expires: int) -> str:
        return f"memory://get/{key}?disposition={quote(content_disposition(filename, inline))}"

    def head(self, key: str) -> ObjectInfo | None:
        o = self.objects.get(key)
        return ObjectInfo(size=len(o[0]), content_type=o[1]) if o else None

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key][0]

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def delete(self, keys: list[str]) -> None:
        for k in keys:
            self.objects.pop(k, None)


_override: MemoryStorage | R2Storage | None = None


def set_backend(backend: MemoryStorage | R2Storage | None) -> None:
    """Thay backend (test). None = dùng R2 theo cấu hình."""
    global _override
    _override = backend
    _r2.cache_clear()


@lru_cache
def _r2() -> R2Storage:
    return R2Storage(get_settings())


def backend() -> MemoryStorage | R2Storage:
    if _override is not None:
        return _override
    if not configured():
        raise StorageError("Chưa cấu hình lưu trữ tệp (Cloudflare R2).")
    return _r2()
