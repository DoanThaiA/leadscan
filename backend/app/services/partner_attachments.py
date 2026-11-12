"""Ảnh đối tác gắn vào cơ hội gửi — lưu Cloudflare R2 (bucket riêng tư), thư mục partner-submissions/.

Luồng: init (cấp link upload ký sẵn) → trình duyệt PUT thẳng lên R2 → complete (kiểm tra đúng ảnh, xoá EXIF/GPS, tạo ảnh nhỏ)
→ gửi / sửa cơ hội kèm attachment_ids → gắn vào cơ hội. Ảnh chưa gắn sau 24 giờ: việc dọn dẹp xoá.
Admin tạo phiếu từ cơ hội: ảnh được SAO CHÉP sang phiếu (phần mở khoá sau khi mua) — xoá cơ hội / phiếu không ảnh hưởng nhau.
Chỉ nhận ảnh (jpg, png, webp); không nhận tài liệu — tài liệu dán link ở ô "Tài liệu, link chứng minh".
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AdminUser, Opportunity, OpportunityAttachment, PartnerAttachment, PartnerSubmission, PartnerUser
from app.services import attachments, storage

IMAGE_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def config() -> dict:
    cfg = get_settings()
    return {"enabled": storage.configured(), "max_files": cfg.partner_attach_max, "max_mb": cfg.attach_image_max_mb,
            "types": sorted(IMAGE_TYPES)}


def init_upload(db: Session, p: PartnerUser, filename: str, size: int) -> tuple[PartnerAttachment, str]:
    if not storage.configured():
        raise HTTPException(503, "Chưa mở tải ảnh lên. Vui lòng dán link ảnh vào ô Tài liệu, link chứng minh.")
    cfg = get_settings()
    name = attachments.safe_filename(filename)
    ext = name.rpartition(".")[2].lower() if "." in name else ""
    if ext not in IMAGE_TYPES:
        raise HTTPException(400, f"Chỉ nhận ảnh {', '.join(sorted(IMAGE_TYPES))}.")
    if size <= 0 or size > cfg.attach_image_max_mb * 1024 * 1024:
        raise HTTPException(400, f"Ảnh tối đa {cfg.attach_image_max_mb} MB.")
    a = PartnerAttachment(partner_id=p.id, key=f"partner-submissions/{uuid.uuid4().hex}/{name}", filename=name,
                          content_type=IMAGE_TYPES[ext], size=size, kind="image")
    db.add(a)
    db.commit()
    return a, storage.backend().presign_put(a.key, a.content_type)


def complete_upload(db: Session, p: PartnerUser, a: PartnerAttachment) -> PartnerAttachment:
    if a.partner_id != p.id:
        raise HTTPException(404, "Không tìm thấy ảnh.")
    if a.status == "ready":
        return a
    st = storage.backend()
    info = st.head(a.key)
    if info is None:
        raise HTTPException(400, "Chưa thấy ảnh trên kho lưu trữ — vui lòng tải lên lại.")
    if info.size > get_settings().attach_image_max_mb * 1024 * 1024:
        st.delete([a.key])
        db.delete(a)
        db.commit()
        raise HTTPException(400, "Ảnh vượt dung lượng cho phép.")
    try:
        attachments.process_image(st, a)  # xác nhận đúng ảnh, xoay theo EXIF rồi xoá EXIF (GPS), tạo ảnh nhỏ
    except ValueError as e:
        st.delete([k for k in (a.key, a.thumb_key) if k])
        db.delete(a)
        db.commit()
        raise HTTPException(400, str(e)) from e
    a.status = "ready"
    db.commit()
    return a


def for_submission(db: Session, sub_id: int) -> list[PartnerAttachment]:
    return list(db.scalars(select(PartnerAttachment).where(PartnerAttachment.submission_id == sub_id, PartnerAttachment.status == "ready")
                           .order_by(PartnerAttachment.position, PartnerAttachment.id)))


def link(db: Session, p: PartnerUser, s: PartnerSubmission, ids: list[int]) -> list[str]:
    """Đặt ảnh của cơ hội đúng theo ids (thứ tự hiển thị). Trả về key R2 cần xoá (ảnh bị bỏ). Gọi trước commit."""
    ids = list(dict.fromkeys(int(i) for i in ids))
    cfg = get_settings()
    if len(ids) > cfg.partner_attach_max:
        raise HTTPException(400, f"Mỗi cơ hội tối đa {cfg.partner_attach_max} ảnh.")
    current = {a.id: a for a in db.scalars(select(PartnerAttachment).where(PartnerAttachment.submission_id == s.id))} if s.id else {}
    wanted = []
    for i in ids:
        a = current.get(i) or db.get(PartnerAttachment, i)
        if not a or a.partner_id != p.id or a.status != "ready" or (a.submission_id not in (None, s.id)):
            raise HTTPException(400, "Có ảnh không hợp lệ hoặc chưa tải lên xong — vui lòng thử lại.")
        wanted.append(a)
    for pos, a in enumerate(wanted):
        a.submission_id, a.position = s.id, pos
    keep = {a.id for a in wanted}
    purge = []
    for a in current.values():
        if a.id not in keep:
            purge += [a.key, a.thumb_key]
            db.delete(a)
    return [k for k in purge if k]


def out(a: PartnerAttachment) -> dict:
    """Ảnh kèm link xem ngắn hạn (chỉ gọi khi người xem có quyền: chính đối tác hoặc quản trị)."""
    d = {"id": a.id, "filename": a.filename, "width": a.width, "height": a.height, "size": a.size, "url": None, "thumb_url": None}
    if storage.configured():
        st, ttl = storage.backend(), get_settings().attach_url_ttl
        try:
            d["url"] = st.presign_get(a.key, a.filename, True, ttl)
            d["thumb_url"] = st.presign_get(a.thumb_key, a.filename, True, ttl) if a.thumb_key else d["url"]
        except storage.StorageError:
            pass
    return d


def copy_to_opportunity(db: Session, s: PartnerSubmission, o: Opportunity, actor: AdminUser) -> int:
    """Sao chép ảnh của cơ hội đối tác sang phiếu (phần mở khoá sau khi mua). Trả về số ảnh đã chép."""
    rows = for_submission(db, s.id)
    if not rows or not storage.configured():
        return 0
    st = storage.backend()
    n = 0
    for pos, a in enumerate(rows):
        base = f"opportunities/{uuid.uuid4().hex}/{a.filename}"
        try:
            st.put_bytes(base, st.get_bytes(a.key), a.content_type)
            thumb = ""
            if a.thumb_key:
                thumb = f"{base}.thumb.webp"
                st.put_bytes(thumb, st.get_bytes(a.thumb_key), "image/webp")
        except storage.StorageError:
            continue
        db.add(OpportunityAttachment(opportunity_id=o.id, uploaded_by_id=actor.id, key=base, thumb_key=thumb, filename=a.filename,
                                     content_type=a.content_type, size=a.size, kind="image", width=a.width, height=a.height,
                                     caption="", position=pos, status="ready"))
        n += 1
    return n
