"""Ảnh & tài liệu của phiếu cơ hội: kiểm tra loại/dung lượng, gắn vào phiếu, tạo link xem/tải.

Luồng (admin soạn phiếu):
  1. init     : khai báo tên + dung lượng → tạo dòng pending, trả link PUT ký sẵn lên R2
  2. (trình duyệt PUT tệp thẳng lên R2)
  3. complete : HEAD tệp trên R2 — có thật, đúng dung lượng/loại → ready; ảnh → việc nền tạo ảnh nhỏ
  4. lưu phiếu: attachment_ids (đúng thứ tự hiển thị) → gắn vào phiếu; tệp bị bỏ khỏi danh sách → xoá
"""

from __future__ import annotations

import re
import unicodedata
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AdminUser, Opportunity, OpportunityAttachment
from app.services import storage

# Loại tệp cho phép — xác định theo đuôi tệp ở server (không tin loại trình duyệt gửi). Chặn svg/html (có thể chứa mã).
IMAGE_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
FILE_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "csv": "text/csv",
    "txt": "text/plain",
    "zip": "application/zip",
}
THUMB_WIDTH = 480
ORPHAN_HOURS = 24  # tệp upload nhưng không được gắn vào phiếu nào → xoá sau ngần này giờ


def limits(cfg: Settings | None = None) -> dict:
    cfg = cfg or get_settings()
    return {
        "configured": storage.configured(cfg),
        "max_files": cfg.attach_max_files,
        "image_max_mb": cfg.attach_image_max_mb,
        "file_max_mb": cfg.attach_file_max_mb,
        "image_exts": sorted(IMAGE_TYPES),
        "file_exts": sorted(FILE_TYPES),
    }


def safe_filename(name: str) -> str:
    """Giữ tiếng Việt, bỏ đường dẫn và ký tự lạ; tối đa 120 ký tự (giữ đuôi)."""
    name = unicodedata.normalize("NFC", (name or "").replace("\\", "/").split("/")[-1]).strip()
    name = re.sub(r"[\x00-\x1f<>:\"|?*]+", "", name)
    name = re.sub(r"\s+", " ", name).strip(" .") or "tep"
    if len(name) > 120:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 120 - len(ext) - 1] + "." + ext) if dot and len(ext) <= 8 else name[:120]
    return name


def classify(filename: str, size: int, cfg: Settings | None = None) -> tuple[str, str]:
    """→ (kind, content_type). Sai loại / quá dung lượng → 400."""
    cfg = cfg or get_settings()
    ext = filename.rpartition(".")[2].lower() if "." in filename else ""
    if ext in IMAGE_TYPES:
        kind, ctype, max_mb = "image", IMAGE_TYPES[ext], cfg.attach_image_max_mb
    elif ext in FILE_TYPES:
        kind, ctype, max_mb = "file", FILE_TYPES[ext], cfg.attach_file_max_mb
    else:
        raise HTTPException(400, f"Không hỗ trợ tệp .{ext or '?'} — chỉ nhận ảnh ({', '.join(sorted(IMAGE_TYPES))}) "
                                 f"và tài liệu ({', '.join(sorted(FILE_TYPES))}).")
    if size <= 0:
        raise HTTPException(400, "Tệp rỗng.")
    if size > max_mb * 1024 * 1024:
        raise HTTPException(400, f"{'Ảnh' if kind == 'image' else 'Tài liệu'} tối đa {max_mb} MB.")
    return kind, ctype


def _require_storage() -> None:
    if not storage.configured():
        raise HTTPException(503, "Chưa cấu hình lưu trữ tệp (Cloudflare R2). Liên hệ kỹ thuật để bật tính năng này.")


def init_upload(db: Session, admin: AdminUser, filename: str, size: int) -> tuple[OpportunityAttachment, str]:
    _require_storage()
    name = safe_filename(filename)
    kind, ctype = classify(name, size)
    key = f"opportunities/{uuid.uuid4().hex}/{name}"
    a = OpportunityAttachment(uploaded_by_id=admin.id, key=key, filename=name, content_type=ctype, size=size, kind=kind)
    db.add(a)
    db.commit()
    return a, storage.backend().presign_put(key, ctype)


def complete_upload(db: Session, a: OpportunityAttachment) -> OpportunityAttachment:
    """Kiểm tra tệp đã lên R2 đúng như khai báo. Sai → xoá tệp, báo lỗi."""
    _require_storage()
    if a.status == "ready":
        return a
    st = storage.backend()
    info = st.head(a.key)
    if info is None:
        raise HTTPException(400, "Chưa thấy tệp trên kho lưu trữ — vui lòng tải lên lại.")
    max_mb = get_settings().attach_image_max_mb if a.kind == "image" else get_settings().attach_file_max_mb
    if info.size > max_mb * 1024 * 1024 or (info.content_type and info.content_type.split(";")[0] != a.content_type):
        st.delete([a.key])
        db.delete(a)
        db.commit()
        raise HTTPException(400, "Tệp tải lên không khớp loại hoặc vượt dung lượng cho phép.")
    if a.kind == "image":
        try:
            process_image(st, a)
        except ValueError as e:
            st.delete([a.key, a.thumb_key])
            db.delete(a)
            db.commit()
            raise HTTPException(400, str(e)) from e
    else:
        a.size = info.size
    a.status = "ready"
    db.commit()
    return a


def process_image(st, a: OpportunityAttachment) -> None:
    """Ảnh: xác nhận đúng là ảnh, xoay theo EXIF rồi XOÁ EXIF (có thể lộ toạ độ GPS), tạo ảnh nhỏ webp."""
    import io

    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = 60_000_000  # chặn ảnh "bom giải nén"
    raw = st.get_bytes(a.key)
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ValueError("Tệp không phải ảnh hợp lệ.") from e
    if a.content_type == "image/gif" or getattr(img, "is_animated", False):
        a.width, a.height = img.size  # ảnh động: giữ nguyên tệp gốc
        clean = None
    else:
        img = ImageOps.exif_transpose(img)
        a.width, a.height = img.size
        buf = io.BytesIO()
        if a.content_type == "image/jpeg":
            img.convert("RGB").save(buf, "JPEG", quality=90, optimize=True)
        elif a.content_type == "image/png":
            img.save(buf, "PNG", optimize=True)
        else:
            img.save(buf, "WEBP", quality=90)
        clean = buf.getvalue()
        st.put_bytes(a.key, clean, a.content_type)  # ghi đè bản gốc đã bỏ EXIF
    a.size = len(clean) if clean is not None else len(raw)
    thumb = img.copy()
    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGBA" if "transparency" in thumb.info or thumb.mode in ("LA", "P") else "RGB")
    thumb.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 3))
    tb = io.BytesIO()
    thumb.save(tb, "WEBP", quality=80)
    a.thumb_key = f"{a.key}.thumb.webp"
    st.put_bytes(a.thumb_key, tb.getvalue(), "image/webp")


def for_opportunity(db: Session, opp_id: int) -> list[OpportunityAttachment]:
    return list(
        db.scalars(
            select(OpportunityAttachment)
            .where(OpportunityAttachment.opportunity_id == opp_id, OpportunityAttachment.status == "ready")
            .order_by(OpportunityAttachment.position, OpportunityAttachment.id)
        )
    )


def counts(db: Session, opp_id: int) -> dict:
    rows = dict(
        db.execute(
            select(OpportunityAttachment.kind, func.count())
            .where(OpportunityAttachment.opportunity_id == opp_id, OpportunityAttachment.status == "ready")
            .group_by(OpportunityAttachment.kind)
        ).all()
    )
    return {"images": rows.get("image", 0), "files": rows.get("file", 0)}


def link(db: Session, opp: Opportunity, ids: list[int], admin: AdminUser, captions: dict[int, str] | None = None) -> list[str]:
    """Đặt danh sách tệp của phiếu đúng theo ids (cũng là thứ tự hiển thị). Trả về key R2 cần xoá (tệp bị bỏ).

    Chỉ nhận: tệp đã thuộc phiếu này, hoặc tệp mới (chưa thuộc phiếu nào) do chính admin này upload, đã ready.
    """
    ids = list(dict.fromkeys(ids))
    if len(ids) > get_settings().attach_max_files:
        raise HTTPException(400, f"Mỗi phiếu tối đa {get_settings().attach_max_files} tệp.")
    current = {a.id: a for a in db.scalars(select(OpportunityAttachment).where(OpportunityAttachment.opportunity_id == opp.id))} if opp.id else {}
    wanted: list[OpportunityAttachment] = []
    for i in ids:
        a = current.get(i) or db.get(OpportunityAttachment, i)
        ok = a is not None and a.status == "ready" and (
            a.opportunity_id == opp.id if a.opportunity_id is not None else a.uploaded_by_id == admin.id
        )
        if not ok:
            raise HTTPException(400, "Có tệp đính kèm không hợp lệ hoặc chưa tải lên xong — vui lòng thử lại.")
        wanted.append(a)
    for pos, a in enumerate(wanted):
        a.opportunity_id, a.position = opp.id, pos
        if captions and a.id in captions:
            update_caption(a, captions[a.id])
    keep = {a.id for a in wanted}
    purge: list[str] = []
    for a in current.values():
        if a.id not in keep:
            purge += [a.key, a.thumb_key]
            db.delete(a)
    return [k for k in purge if k]


def update_caption(a: OpportunityAttachment, caption: str) -> None:
    a.caption = caption.strip()[:300]


def keys_of(db: Session, opp_id: int) -> list[str]:
    rows = db.execute(select(OpportunityAttachment.key, OpportunityAttachment.thumb_key).where(OpportunityAttachment.opportunity_id == opp_id)).all()
    return [k for pair in rows for k in pair if k]


def out(a: OpportunityAttachment, signed: bool = True) -> dict:
    """Thông tin tệp; signed=True kèm link xem/tải ngắn hạn (chỉ gọi khi người xem có quyền)."""
    d = {
        "id": a.id,
        "filename": a.filename,
        "content_type": a.content_type,
        "size": a.size,
        "kind": a.kind,
        "width": a.width,
        "height": a.height,
        "caption": a.caption,
        "status": a.status,
        "url": None,
        "download_url": None,
        "thumb_url": None,
    }
    if signed and a.status == "ready" and storage.configured():
        st, ttl = storage.backend(), get_settings().attach_url_ttl
        try:
            if a.kind == "image":
                d["url"] = st.presign_get(a.key, a.filename, True, ttl)
                d["thumb_url"] = st.presign_get(a.thumb_key, a.filename, True, ttl) if a.thumb_key else d["url"]
            d["download_url"] = st.presign_get(a.key, a.filename, False, ttl)  # tài liệu luôn tải về, không mở trong trình duyệt
        except storage.StorageError:
            pass
    return d
