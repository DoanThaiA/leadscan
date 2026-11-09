"""Ảnh & tài liệu của phiếu cơ hội: admin gắn khi soạn phiếu, thành viên chỉ thấy sau khi mua (R2 giả lập)."""

import io
from datetime import timedelta
from urllib.parse import unquote

import pytest
from PIL import Image

from app.db import new_session, utcnow
from app.models import OpportunityAttachment
from app.services import storage
from tests.test_member import ask, make_opp, member, pay_membership  # noqa: F401


@pytest.fixture
def r2():
    st = storage.MemoryStorage()
    storage.set_backend(st)
    yield st
    storage.set_backend(None)


def jpeg_with_exif(w: int = 40, h: int = 20) -> bytes:
    img = Image.new("RGB", (w, h), (250, 83, 32))
    exif = Image.Exif()
    exif[0x0112] = 6  # xoay 90°
    exif[0x8825] = {1: "N", 2: (21.0, 1.0, 30.0)}  # GPS
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


PDF = b"%PDF-1.4\n% thu\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def upload(admin, st, filename: str, data: bytes, put_type: str | None = None) -> int:
    r = admin.post("/api/admin/attachments/init", json={"filename": filename, "size": len(data)})
    assert r.status_code == 201, r.text
    body = r.json()
    key = unquote(body["upload_url"].removeprefix("memory://put/").split("?")[0])
    st.put_bytes(key, data, put_type or body["content_type"])  # trình duyệt PUT thẳng lên R2
    done = admin.post(f"/api/admin/attachments/{body['attachment']['id']}/complete")
    assert done.status_code == 200, done.text
    return body["attachment"]["id"]


def opp_body(admin, oid: int) -> dict:
    o = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]
    keys = ("title", "summary", "industry", "province", "region", "source_type", "price", "max_buyers", "buyer_name", "detail", "status")
    return {**{k: o[k] for k in keys}, "contacts": []}


def test_chua_cau_hinh_r2(admin):
    assert admin.get("/api/admin/attachments/config").json()["configured"] is False
    r = admin.post("/api/admin/attachments/init", json={"filename": "a.jpg", "size": 100})
    assert r.status_code == 503 and "Cloudflare R2" in r.json()["detail"]


def test_admin_gan_tep_khi_tao_phieu_thanh_vien_xem_sau_khi_mua(admin, member, r2):
    cfg = admin.get("/api/admin/attachments/config").json()
    assert cfg["configured"] and "pdf" in cfg["file_exts"] and "svg" not in cfg["image_exts"]

    img = upload(admin, r2, "Ảnh RFQ gốc.jpg", jpeg_with_exif())
    pdf = upload(admin, r2, "../../Báo giá.pdf", PDF)
    oid = make_opp(admin, attachment_ids=[pdf, img], attachment_captions={str(img): "Ảnh chụp yêu cầu báo giá"})  # thứ tự = thứ tự gửi

    atts = admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]["attachments"]
    assert [a["id"] for a in atts] == [pdf, img]
    a_pdf, a_img = atts
    assert a_pdf["filename"] == "Báo giá.pdf" and a_pdf["kind"] == "file" and a_pdf["url"] is None
    assert "attachment" in unquote(a_pdf["download_url"])  # tài liệu luôn tải về, không mở trong trình duyệt
    assert a_img["kind"] == "image" and a_img["caption"] == "Ảnh chụp yêu cầu báo giá"
    assert (a_img["width"], a_img["height"]) == (20, 40)  # đã xoay theo EXIF
    assert ".thumb.webp" in a_img["thumb_url"] and "inline" in unquote(a_img["url"])
    with new_session() as db:
        row = db.get(OpportunityAttachment, img)
        clean = Image.open(io.BytesIO(r2.get_bytes(row.key)))
        assert not clean.getexif()  # đã bỏ EXIF (GPS)
        assert Image.open(io.BytesIO(r2.get_bytes(row.thumb_key))).format == "WEBP"

    # thành viên chưa mua: chỉ thấy số lượng
    ask(member)
    r = member.get(f"/api/member/opportunities/{oid}").json()
    assert r["attachment_counts"] == {"images": 1, "files": 1} and "attachments" not in r
    # mua phiếu → thấy tệp kèm link xem/tải
    pay_membership(member)
    assert member.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    r = member.get(f"/api/member/opportunities/{oid}").json()
    assert [a["id"] for a in r["attachments"]] == [pdf, img] and r["attachments"][1]["thumb_url"]


def test_chan_loai_tep_va_dung_luong(admin, r2):
    for name in ("logo.svg", "trang.html", "virus.exe", "khongduoi"):
        r = admin.post("/api/admin/attachments/init", json={"filename": name, "size": 100})
        assert r.status_code == 400, name
    assert admin.post("/api/admin/attachments/init", json={"filename": "a.jpg", "size": 11 * 1024 * 1024}).status_code == 400
    assert admin.post("/api/admin/attachments/init", json={"filename": "a.pdf", "size": 26 * 1024 * 1024}).status_code == 400

    # chưa PUT lên R2 mà đã báo xong
    r = admin.post("/api/admin/attachments/init", json={"filename": "a.pdf", "size": 10}).json()
    assert admin.post(f"/api/admin/attachments/{r['attachment']['id']}/complete").status_code == 400

    # đuôi .png nhưng không phải ảnh → bị xoá
    r = admin.post("/api/admin/attachments/init", json={"filename": "gia.png", "size": 12}).json()
    key = unquote(r["upload_url"].removeprefix("memory://put/").split("?")[0])
    r2.put_bytes(key, b"<script>x</script>", "image/png")
    bad = admin.post(f"/api/admin/attachments/{r['attachment']['id']}/complete")
    assert bad.status_code == 400 and "không phải ảnh" in bad.json()["detail"] and r2.head(key) is None

    # PUT sai loại so với khai báo
    r = admin.post("/api/admin/attachments/init", json={"filename": "a.pdf", "size": len(PDF)}).json()
    key = unquote(r["upload_url"].removeprefix("memory://put/").split("?")[0])
    r2.put_bytes(key, PDF, "text/html")
    assert admin.post(f"/api/admin/attachments/{r['attachment']['id']}/complete").status_code == 400

    # tệp chưa tải xong không gắn được vào phiếu
    r = admin.post("/api/admin/attachments/init", json={"filename": "b.pdf", "size": 10}).json()
    resp = admin.post("/api/admin/opportunities", json={"title": "Cần 1 lô carton", "attachment_ids": [r["attachment"]["id"]]})
    assert resp.status_code == 400


def test_sua_phieu_bo_doi_thu_tu_va_xoa_phieu(admin, r2, monkeypatch):
    a = upload(admin, r2, "a.pdf", PDF)
    b = upload(admin, r2, "b.png", jpeg_with_exif())  # nội dung jpeg, đuôi png → vẫn là ảnh hợp lệ, lưu lại thành PNG
    oid = make_opp(admin, attachment_ids=[a, b])
    with new_session() as db:
        key_a = db.get(OpportunityAttachment, a).key

    body = opp_body(admin, oid)
    admin.put(f"/api/admin/opportunities/{oid}", json=body)  # không gửi attachment_ids → giữ nguyên
    assert [x["id"] for x in admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"]["attachments"]] == [a, b]

    c = upload(admin, r2, "c.xlsx", b"PK\x03\x04 bang gia")
    r = admin.put(f"/api/admin/opportunities/{oid}", json={**body, "attachment_ids": [c, b]})
    assert [x["id"] for x in r.json()["attachments"]] == [c, b]
    assert r2.head(key_a) is None  # tệp bị bỏ đã xoá trên R2
    with new_session() as db:
        assert db.get(OpportunityAttachment, a) is None

    # quá số tệp tối đa
    monkeypatch.setenv("LEADSCAN_ATTACH_MAX_FILES", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    assert admin.put(f"/api/admin/opportunities/{oid}", json={**body, "attachment_ids": [c, b]}).status_code == 400
    monkeypatch.delenv("LEADSCAN_ATTACH_MAX_FILES")
    get_settings.cache_clear()

    # xoá phiếu → xoá tệp trên R2
    assert admin.delete(f"/api/admin/opportunities/{oid}").status_code == 204
    assert not r2.objects


def test_khong_gan_tep_cua_nguoi_khac_hay_phieu_khac(admin, staff, r2):
    mine = upload(staff, r2, "cua-staff.pdf", PDF)
    assert admin.post("/api/admin/opportunities", json={"title": "Phiếu A cần carton", "attachment_ids": [mine]}).status_code == 400
    assert admin.delete(f"/api/admin/attachments/{mine}").status_code == 404

    x = upload(admin, r2, "x.pdf", PDF)
    make_opp(admin, attachment_ids=[x])
    assert admin.post("/api/admin/opportunities", json={"title": "Phiếu B cần carton", "attachment_ids": [x]}).status_code == 400
    assert admin.delete(f"/api/admin/attachments/{x}").status_code == 400  # đã thuộc phiếu: bỏ trong form rồi lưu

    y = upload(admin, r2, "y.pdf", PDF)
    assert admin.delete(f"/api/admin/attachments/{y}").status_code == 204  # huỷ tệp vừa tải, chưa lưu


def test_don_tep_upload_bo_do(admin, r2):
    from app.worker import cleanup_task

    old = upload(admin, r2, "bo-do.pdf", PDF)
    new = upload(admin, r2, "moi.pdf", PDF)
    with new_session() as db:
        a = db.get(OpportunityAttachment, old)
        key_old = a.key
        a.created_at = utcnow() - timedelta(hours=25)
        db.commit()
    cleanup_task.apply()
    with new_session() as db:
        assert db.get(OpportunityAttachment, old) is None and db.get(OpportunityAttachment, new) is not None
    assert r2.head(key_old) is None
