"""Tuyển dụng: admin đăng bài, trang công khai, ứng viên gửi hồ sơ → email về hộp thư tuyển dụng."""

import base64
import json
from datetime import date, timedelta
from urllib.parse import unquote

import pytest
import respx

from app import db as dbmod
from app.config import get_settings
from app.models import JobApplication
from app.schemas_jobs import slugify
from app.services import storage

JOBS = "/api/admin/jobs"
APPS = "/api/admin/job-applications"
PDF = b"%PDF-1.4\n% CV thu\n%%EOF"


def job(**over) -> dict:
    d = {
        "title": "Chuyên viên Kinh doanh B2B",
        "status": "published",
        "department": "Kinh doanh",
        "location": "Hà Nội",
        "salary": "12 – 20 triệu/tháng",
        "summary": "Tìm và chăm sóc khách hàng doanh nghiệp.",
        "description": "## A. Bán hàng\n- Tư vấn gói thành viên\n- Chăm sóc khách hàng",
        "requirements": "- 1 năm kinh nghiệm B2B",
        "benefits": "- Thưởng theo doanh số",
    }
    d.update(over)
    return d


def application(**over) -> dict:
    d = {
        "full_name": "Trần Thị Bình",
        "phone": "0912 345 678",
        "email": "Binh@Gmail.com",
        "cv_url": "drive.google.com/file/d/abc",
        "portfolio_url": "",
        "intro": "3 năm bán hàng phần mềm B2B.",
        "website_url": "",
        "elapsed_ms": 8000,
    }
    d.update(over)
    return d


@pytest.fixture
def r2():
    """Cloudflare R2 giả lập trong bộ nhớ."""
    st = storage.MemoryStorage()
    storage.set_backend(st)
    yield st
    storage.set_backend(None)


def _mail(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(f"LEADSCAN_{k.upper()}", v)
    get_settings.cache_clear()


def test_slugify_bo_dau():
    assert slugify("Chuyên viên Kinh doanh B2B (Hà Nội)") == "chuyen-vien-kinh-doanh-b2b-ha-noi"
    assert slugify("Đối tác  Đào tạo") == "doi-tac-dao-tao"


def test_can_dang_nhap(client):
    assert client.get(JOBS).status_code == 401
    assert client.get(APPS).status_code == 401


def test_dang_bai_va_trang_cong_khai(admin, client):
    r = admin.post(JOBS, json=job())
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["slug"] == "chuyen-vien-kinh-doanh-b2b" and j["published_at"] and j["applications"] == 0

    # trùng tiêu đề → slug tự thêm hậu tố
    j2 = admin.post(JOBS, json=job(status="draft")).json()
    assert j2["slug"] == "chuyen-vien-kinh-doanh-b2b-2" and j2["published_at"] is None

    pub = client.get("/api/jobs").json()["items"]
    assert [x["slug"] for x in pub] == ["chuyen-vien-kinh-doanh-b2b"]  # bản nháp không hiện
    assert "apply_email" not in pub[0]

    d = client.get("/api/jobs/chuyen-vien-kinh-doanh-b2b").json()
    assert d["is_open"] is True and d["description"].startswith("## A.")
    assert client.get(f"/api/jobs/{j2['slug']}").status_code == 404  # bản nháp → 404

    # đóng bài: vẫn xem được (link cũ không chết) nhưng không còn trong danh sách / không nhận hồ sơ
    admin.put(f"{JOBS}/{j['id']}", json=job(status="closed", slug=j["slug"]))
    assert client.get("/api/jobs").json()["items"] == []
    assert client.get(f"/api/jobs/{j['slug']}").json()["is_open"] is False
    assert client.post(f"/api/jobs/{j['slug']}/apply", json=application()).status_code == 410


def test_qua_han_nop_tu_an(admin, client):
    admin.post(JOBS, json=job(deadline=(date.today() - timedelta(days=2)).isoformat()))
    assert client.get("/api/jobs").json()["items"] == []
    assert client.post("/api/jobs/chuyen-vien-kinh-doanh-b2b/apply", json=application()).status_code == 410


def test_ung_tuyen_gui_email_kem_cv(admin, client, monkeypatch, r2):
    _mail(monkeypatch, resend_api_key="re_test", recruit_email="tuyendung@leadscan.net")
    j = admin.post(JOBS, json=job()).json()
    cv = {"name": "CV Trần Bình.pdf", "data": base64.b64encode(PDF).decode()}
    with respx.mock(assert_all_called=True) as m:
        route = m.post("https://api.resend.com/emails").respond(200, json={"id": "e1"})
        r = client.post(f"/api/jobs/{j['slug']}/apply", json=application(cv_url="", cv_file=cv))
        assert r.status_code == 200 and r.json() == {"ok": True}, r.text

    sent = [json.loads(c.request.content) for c in route.calls]
    to_hr = next(x for x in sent if x["to"] == ["tuyendung@leadscan.net"])
    assert to_hr["reply_to"] == "binh@gmail.com"
    assert "Chuyên viên Kinh doanh B2B" in to_hr["subject"] and "0912345678" in to_hr["text"]
    assert to_hr["attachments"][0]["filename"] == "CV Trần Bình.pdf"
    assert base64.b64decode(to_hr["attachments"][0]["content"]) == PDF
    receipt = next(x for x in sent if x["to"] == ["binh@gmail.com"])
    assert "Đã nhận hồ sơ" in receipt["subject"]

    a = admin.get(APPS).json()["items"][0]
    assert a["email_sent_at"] and a["cv_filename"] == "CV Trần Bình.pdf" and a["job_slug"] == j["slug"]
    assert a["cv_size"] == len(PDF) and admin.get(JOBS).json()["items"][0]["applications_new"] == 1

    # file nằm trên R2 trong thư mục CV/, DB chỉ giữ key
    [key] = r2.objects
    assert key.startswith("CV/") and key.endswith("/CV Trần Bình.pdf") and r2.objects[key] == (PDF, "application/pdf")
    with dbmod.new_session() as db:
        assert db.get(JobApplication, a["id"]).cv_key == key

    # admin tải CV → chuyển tới link ký sẵn trên R2 (tải về, không mở trong trình duyệt)
    dl = admin.get(f"{APPS}/{a['id']}/cv", follow_redirects=False)
    loc = unquote(dl.headers["location"])
    assert dl.status_code == 302 and loc.startswith(f"memory://get/{key}") and "attachment" in loc

    # xoá hồ sơ → xoá luôn file trên R2
    assert admin.delete(f"{APPS}/{a['id']}").status_code == 204
    assert r2.objects == {}


def test_chua_cau_hinh_r2_chi_nhan_link_cv(admin, client):
    slug = admin.post(JOBS, json=job()).json()["slug"]
    assert client.get(f"/api/jobs/{slug}").json()["cv_upload"] is False
    cv = {"name": "cv.pdf", "data": base64.b64encode(PDF).decode()}
    r = client.post(f"/api/jobs/{slug}/apply", json=application(cv_url="", cv_file=cv))
    assert r.status_code == 422 and "link CV" in r.json()["fields"]["cv_file"]
    assert client.post(f"/api/jobs/{slug}/apply", json=application()).status_code == 200  # link CV vẫn được
    assert admin.get("/api/admin/jobs/meta").json()["storage_ready"] is False


def test_r2_loi_khi_tai_cv(admin, client, r2, monkeypatch):
    slug = admin.post(JOBS, json=job()).json()["slug"]

    def boom(*a, **k):
        raise RuntimeError("R2 timeout")

    monkeypatch.setattr(r2, "put_bytes", boom)
    cv = {"name": "cv.pdf", "data": base64.b64encode(PDF).decode()}
    r = client.post(f"/api/jobs/{slug}/apply", json=application(cv_url="", cv_file=cv))
    assert r.status_code == 503 and "cv_file" in r.json()["fields"]
    with dbmod.new_session() as db:
        assert db.query(JobApplication).count() == 0


def test_email_rieng_cua_bai(admin, client, monkeypatch):
    _mail(monkeypatch, resend_api_key="re_test", recruit_email="chung@leadscan.net")
    j = admin.post(JOBS, json=job(apply_email="Sales-HR@LeadScan.net")).json()
    with respx.mock() as m:
        route = m.post("https://api.resend.com/emails").respond(200, json={"id": "e1"})
        client.post(f"/api/jobs/{j['slug']}/apply", json=application())
    assert ["sales-hr@leadscan.net"] in [json.loads(c.request.content)["to"] for c in route.calls]


def test_kiem_tra_du_lieu(admin, client, r2):
    slug = admin.post(JOBS, json=job()).json()["slug"]
    url = f"/api/jobs/{slug}/apply"
    f = client.post(url, json=application(full_name="", phone="123", email="sai", cv_url="")).json()["fields"]
    assert set(f) >= {"full_name", "phone", "email"}
    assert "cv_url" in client.post(url, json=application(cv_url="")).json()["fields"]  # không link, không file
    fake = {"name": "cv.pdf", "data": base64.b64encode(b"MZ\x90 not a pdf").decode()}
    assert "cv_file" in client.post(url, json=application(cv_file=fake)).json()["fields"]
    exe = {"name": "cv.exe", "data": base64.b64encode(PDF).decode()}
    assert "cv_file" in client.post(url, json=application(cv_file=exe)).json()["fields"]
    assert client.post(url, json=application(elapsed_ms=500)).status_code == 429
    # honeypot: giả vờ thành công, không lưu
    assert client.post(url, json=application(website_url="http://spam")).json() == {"ok": True}
    with dbmod.new_session() as db:
        assert db.query(JobApplication).count() == 0


def test_gioi_han_tan_suat(admin, client, monkeypatch):
    _mail(monkeypatch, apply_rate_limit_per_hour="2")
    slug = admin.post(JOBS, json=job()).json()["slug"]
    for _ in range(2):
        assert client.post(f"/api/jobs/{slug}/apply", json=application()).status_code == 200
    assert client.post(f"/api/jobs/{slug}/apply", json=application()).status_code == 429


def test_chua_cau_hinh_email_van_luu_va_gui_lai(admin, client, monkeypatch):
    slug = admin.post(JOBS, json=job()).json()["slug"]
    assert client.post(f"/api/jobs/{slug}/apply", json=application()).status_code == 200
    a = admin.get(APPS).json()["items"][0]
    assert a["email_sent_at"] is None  # chưa có hộp thư → chỉ lưu
    assert admin.post(f"{APPS}/{a['id']}/resend").status_code == 400

    _mail(monkeypatch, resend_api_key="re_test", recruit_email="tuyendung@leadscan.net")
    with respx.mock() as m:
        m.post("https://api.resend.com/emails").respond(200, json={"id": "e2"})
        r = admin.post(f"{APPS}/{a['id']}/resend")
    assert r.status_code == 200 and r.json()["email_sent_at"]


def test_xu_ly_ho_so_va_phan_quyen(admin, staff, client):
    j = admin.post(JOBS, json=job()).json()
    client.post(f"/api/jobs/{j['slug']}/apply", json=application())
    a = staff.get(APPS, params={"job_id": j["id"]}).json()["items"][0]
    r = staff.patch(f"{APPS}/{a['id']}", json={"status": "interview", "note": "Hẹn thứ 5"})
    assert r.json()["status"] == "interview" and r.json()["note"] == "Hẹn thứ 5"
    assert staff.get(APPS, params={"status": "interview"}).json()["total"] == 1
    assert staff.delete(f"{APPS}/{a['id']}").status_code == 403
    assert staff.delete(f"{JOBS}/{j['id']}").status_code == 403

    # xoá bài vẫn giữ hồ sơ (kèm tên vị trí)
    assert admin.delete(f"{JOBS}/{j['id']}").status_code == 204
    kept = admin.get(f"{APPS}/{a['id']}").json()
    assert kept["job_id"] is None and kept["job_title"] == "Chuyên viên Kinh doanh B2B"
    assert admin.delete(f"{APPS}/{a['id']}").status_code == 204
