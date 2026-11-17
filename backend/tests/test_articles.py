"""Cẩm nang (blog SEO): admin soạn / đăng / hẹn giờ, trang công khai chỉ thấy bài đã đăng, lệnh import-articles."""

import json
from datetime import timedelta

from app.cli import main as cli
from app.db import utcnow
from tests.test_partner import new_client


def body(**over) -> dict:
    b = {
        "title": "Cách tìm khách hàng B2B cho nhà máy bao bì",
        "excerpt": "5 nguồn khách hàng doanh nghiệp đang cần mua bao bì.",
        "category": "Tìm khách hàng B2B",
        "body": "## Vì sao khó\nNội dung **đậm** và [cơ hội bao bì](/co-hoi/nganh/bao-bi-in-an).\n\n- Ý 1\n- Ý 2",
        "status": "published",
    }
    b.update(over)
    return b


def test_admin_create_publish_and_public(admin):
    r = admin.post("/api/admin/articles", json=body())
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["slug"] == "cach-tim-khach-hang-b2b-cho-nha-may-bao-bi" and a["is_live"] and a["published_at"] and a["author_name"] == ""
    # trùng tiêu đề → slug tự thêm số
    assert admin.post("/api/admin/articles", json=body(status="draft")).json()["slug"].endswith("-2")

    anon = new_client()
    lst = anon.get("/api/articles").json()
    assert lst["total"] == 1 and lst["items"][0]["slug"] == a["slug"] and "body" not in lst["items"][0]
    assert ["Tìm khách hàng B2B", 1] in lst["categories"]
    d = anon.get(f"/api/articles/{a['slug']}").json()
    assert d["body"].startswith("## Vì sao") and d["author_name"] == "LeadScan" and d["reading_minutes"] >= 1 and d["related"] == []
    assert anon.get(f"/api/articles/{a['slug']}-2").status_code == 404  # bản nháp không công khai


def test_schedule_and_update_keeps_date(admin):
    future = (utcnow() + timedelta(days=2)).isoformat() + "Z"
    a = admin.post("/api/admin/articles", json=body(published_at=future)).json()
    assert a["is_live"] is False
    anon = new_client()
    assert anon.get("/api/articles").json()["total"] == 0 and anon.get(f"/api/articles/{a['slug']}").status_code == 404
    # sửa bài, để trống ngày đăng → giữ ngày hẹn cũ
    b = admin.put(f"/api/admin/articles/{a['id']}", json=body(title="Tiêu đề mới cho bài hẹn giờ", slug=a["slug"])).json()
    assert b["published_at"] == a["published_at"] and b["slug"] == a["slug"]
    past = (utcnow() - timedelta(hours=1)).isoformat() + "Z"
    admin.put(f"/api/admin/articles/{a['id']}", json=body(published_at=past, slug=a["slug"]))
    assert anon.get("/api/articles").json()["total"] == 1


def test_related_and_category_filter(admin):
    for i, cat in enumerate(["Tìm khách hàng B2B", "Tìm khách hàng B2B", "Đối tác & hoa hồng"]):
        admin.post("/api/admin/articles", json=body(title=f"Bài số {i} về khách hàng B2B", category=cat))
    anon = new_client()
    assert anon.get("/api/articles?category=%C4%90%E1%BB%91i%20t%C3%A1c%20%26%20hoa%20h%E1%BB%93ng").json()["total"] == 1
    d = anon.get("/api/articles/bai-so-0-ve-khach-hang-b2b").json()
    assert [r["slug"] for r in d["related"]][0] == "bai-so-1-ve-khach-hang-b2b" and len(d["related"]) == 2


def test_validation_and_permissions(admin, staff):
    bad = admin.post("/api/admin/articles", json=body(title="abc", status="x", cover_image="java script:x"))
    assert bad.status_code == 422 and {"title", "status", "cover_image"} <= set(bad.json()["fields"])
    a = staff.post("/api/admin/articles", json=body()).json()  # nhân viên được soạn
    assert staff.delete(f"/api/admin/articles/{a['id']}").status_code == 403  # chỉ quản trị viên được xoá
    assert admin.delete(f"/api/admin/articles/{a['id']}").status_code == 204
    assert new_client().get("/api/admin/articles").status_code == 401


def test_import_articles_cli(tmp_path, admin):
    (tmp_path / "a.json").write_text(json.dumps([
        {"_note": "bỏ qua", "title": "Hoa hồng giới thiệu khách hàng B2B tính thế nào", "body": ["## Mở đầu", "Nội dung"], "category": "Đối tác & hoa hồng"},
    ], ensure_ascii=False), encoding="utf-8")
    assert cli(["import-articles", str(tmp_path)]) == 0
    lst = admin.get("/api/admin/articles").json()
    assert lst["counts"] == {"draft": 1} and lst["items"][0]["slug"] == "hoa-hong-gioi-thieu-khach-hang-b2b-tinh-the-nao"
    assert cli(["import-articles", str(tmp_path), "--status", "published"]) == 0  # chạy lại = cập nhật, không nhân bản
    assert new_client().get("/api/articles").json()["total"] == 1
    assert admin.get(f"/api/admin/articles/{lst['items'][0]['id']}").json()["body"] == "## Mở đầu\nNội dung"


def test_area_filter_counts_and_related(admin):
    admin.post("/api/admin/articles", json=body(title="Tìm khách hàng B2B tại Bắc Ninh", area="bac-ninh"))
    admin.post("/api/admin/articles", json=body(title="Tìm khách hàng B2B miền Bắc nói chung", area="mien-bac", category="Kiến thức ngành"))
    admin.post("/api/admin/articles", json=body(title="Bài chung không gắn khu vực nào", category="Kiến thức ngành"))
    anon = new_client()
    lst = anon.get("/api/articles?areas=bac-ninh,mien-bac").json()
    assert lst["total"] == 2 and {i["area"] for i in lst["items"]} == {"bac-ninh", "mien-bac"}
    assert lst["area_counts"] == {"bac-ninh": 1, "mien-bac": 1}
    assert anon.get("/api/articles?areas=bac-ninh").json()["total"] == 1
    assert anon.get("/api/articles?areas=,,").json()["total"] == 3  # chỉ dấu phẩy = không lọc
    # liên quan: cùng khu vực trước, rồi cùng chủ đề (bài số 3), rồi còn lại
    d = anon.get("/api/articles/tim-khach-hang-b2b-tai-bac-ninh").json()
    assert d["area"] == "bac-ninh" and len(d["related"]) == 2 and len({r["slug"] for r in d["related"]}) == 2
    bad = admin.post("/api/admin/articles", json=body(title="Bài sai khu vực thử", area="Bắc Ninh!"))
    assert bad.status_code == 422 and "area" in bad.json()["fields"]

