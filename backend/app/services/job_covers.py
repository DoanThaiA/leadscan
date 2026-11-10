"""Ảnh bìa (banner) bài tuyển dụng, lưu trên Cloudflare R2, thư mục job-covers/.

Luồng (admin soạn bài):
  1. init     : khai báo tên + dung lượng → trả link PUT ký sẵn lên R2 (trình duyệt gửi thẳng, không qua Nginx)
  2. (trình duyệt PUT tệp lên R2)
  3. complete : kiểm tra đúng là ảnh → xoay theo EXIF, XOÁ EXIF, thu về rộng tối đa 1920px, lưu WebP
               → trả đường dẫn công khai /api/jobs/covers/<id>.webp để lưu vào job_posts.cover_image
  4. công khai: GET /api/jobs/covers/<id>.webp đọc ảnh từ R2 (bucket riêng tư), cache 1 năm (tên tệp là duy nhất)
"""

from __future__ import annotations

import io
import re
import uuid

from fastapi import HTTPException

from app.config import get_settings
from app.services import storage
from app.services.attachments import _require_storage

COVER_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
MAX_WIDTH = 1920
PREFIX = "job-covers"
PUBLIC_PATH = "/api/jobs/covers"
NAME_RE = re.compile(r"^[0-9a-f]{32}\.webp$")


def _ext(filename: str) -> str:
    return filename.rpartition(".")[2].lower() if "." in filename else ""


def init_upload(filename: str, size: int) -> dict:
    """→ {upload_id, upload_url, content_type}. Sai loại / quá dung lượng → 400; chưa cấu hình R2 → 503."""
    _require_storage()
    ext = _ext(filename)
    if ext not in COVER_TYPES:
        raise HTTPException(400, "Ảnh bìa chỉ nhận JPG, PNG hoặc WebP.")
    max_mb = get_settings().attach_image_max_mb
    if size <= 0:
        raise HTTPException(400, "Tệp rỗng.")
    if size > max_mb * 1024 * 1024:
        raise HTTPException(400, f"Ảnh bìa tối đa {max_mb} MB.")
    uid = uuid.uuid4().hex
    ctype = COVER_TYPES[ext]
    key = f"{PREFIX}/upload/{uid}.{ext}"
    return {"upload_id": f"{uid}.{ext}", "upload_url": storage.backend().presign_put(key, ctype), "content_type": ctype, "expires_in": 600}


def complete_upload(upload_id: str) -> dict:
    """Ảnh đã lên R2 → chuẩn hoá thành WebP → {url, width, height}."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    _require_storage()
    m = re.fullmatch(r"([0-9a-f]{32})\.(jpg|jpeg|png|webp)", upload_id or "")
    if not m:
        raise HTTPException(400, "Mã tải lên không hợp lệ.")
    uid, ext = m.groups()
    st = storage.backend()
    src = f"{PREFIX}/upload/{upload_id}"
    info = st.head(src)
    if info is None:
        raise HTTPException(400, "Chưa thấy ảnh trên kho lưu trữ — vui lòng tải lên lại.")
    max_mb = get_settings().attach_image_max_mb
    if info.size > max_mb * 1024 * 1024 or (info.content_type and info.content_type.split(";")[0] != COVER_TYPES[ext]):
        st.delete([src])
        raise HTTPException(400, "Ảnh tải lên không khớp loại hoặc vượt dung lượng cho phép.")

    Image.MAX_IMAGE_PIXELS = 60_000_000  # chặn ảnh "bom giải nén"
    try:
        img = Image.open(io.BytesIO(st.get_bytes(src)))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        st.delete([src])
        raise HTTPException(400, "Tệp không phải ảnh hợp lệ.") from None
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "transparency" in img.info or img.mode in ("LA", "P") else "RGB")
    if img.width > MAX_WIDTH:
        img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=85, method=6)  # bản lưu không còn EXIF (có thể lộ toạ độ GPS)
    name = f"{uid}.webp"
    st.put_bytes(f"{PREFIX}/{name}", buf.getvalue(), "image/webp")
    st.delete([src])
    return {"url": f"{PUBLIC_PATH}/{name}", "width": img.width, "height": img.height}


def read_cover(name: str) -> bytes:
    """Ảnh bìa công khai theo tên tệp. Không có / sai tên → 404."""
    if not NAME_RE.fullmatch(name) or not storage.configured():
        raise HTTPException(404, "Không tìm thấy ảnh.")
    st = storage.backend()
    key = f"{PREFIX}/{name}"
    if st.head(key) is None:
        raise HTTPException(404, "Không tìm thấy ảnh.")
    return st.get_bytes(key)
