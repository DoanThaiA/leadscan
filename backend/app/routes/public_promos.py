"""Khuyến mãi công khai: /api/promos — banner popup trên trang chủ (không cần đăng nhập)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response

from app.db import new_session
from app.services import job_covers, promos
from app.services.storage import StorageError

router = APIRouter(prefix="/api/promos")


@router.get("")
def active():
    """Banner các mã đang dùng được. Cache ngắn để admin sửa thì trang chủ cập nhật sau ≤ 1 phút."""
    with new_session() as db:
        items = promos.active_banners(db)
    return JSONResponse({"items": items}, headers={"Cache-Control": "public, max-age=60"})


@router.get("/banners/{name}")
def banner(name: str):
    """Ảnh banner (đọc từ R2 riêng tư). Tên tệp là duy nhất → cache 1 năm."""
    try:
        data = job_covers.read_cover(name, prefix=promos.BANNER_PREFIX)
    except StorageError:
        raise HTTPException(502, "Kho lưu trữ tạm thời lỗi.") from None
    return Response(data, media_type="image/webp", headers={
        "Cache-Control": "public, max-age=31536000, immutable",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'",
    })
