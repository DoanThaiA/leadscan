"""CRM Lite hạng Vàng: lead tự sinh từ phiếu đã mua, pipeline, ghi chú (che SĐT/email lạ), việc cần làm, tách dữ liệu."""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db import new_session
from app.models_crm import CrmLead
from app.services.crm import mask_pii
from tests.test_matching import other_member
from tests.test_member import ask, make_opp, member, pay_membership  # noqa: F401
from tests.test_tiers import topup


@pytest.fixture(autouse=True)
def gold_15m(monkeypatch):
    monkeypatch.setenv("LEADSCAN_GOLD_TOPUP_THRESHOLD", "15000000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def gold_with_purchase(admin, m, **opp) -> int:
    """Thành viên lên hạng Vàng và mua 1 phiếu; trả về id cơ hội."""
    oid = make_opp(admin, **opp)
    ask(m)
    pay_membership(m)
    topup(m, 5_000_000)
    assert m.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    return oid


def board(m, **params) -> dict:
    r = m.get("/api/member/crm/board", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_chi_hang_vang_moi_vao_crm(admin, member):
    oid = make_opp(admin)
    ask(member)
    pay_membership(member)
    assert member.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    r = member.get("/api/member/crm/board")
    assert r.status_code == 403 and "hạng Vàng" in r.json()["detail"]

    topup(member, 5_000_000)  # lên Vàng → phiếu mua trước đó cũng vào CRM
    b = board(member)
    assert len(b["leads"]) == 1 and b["leads"][0]["stage"] == "new"
    assert [s["key"] for s in b["stages"]] == ["new", "contacting", "interested", "quoted", "won", "lost"]


def test_lead_tu_sinh_khong_trung(admin, member):
    oid = gold_with_purchase(admin, member)
    for _ in range(3):
        b = board(member)
    assert len(b["leads"]) == 1
    lead = b["leads"][0]
    assert lead["opportunity_id"] == oid and lead["title"] == "Cần 200.000 hộp carton 5 lớp/tháng"
    assert lead["buyer_name"] == "Công ty Điện tử ABC" and lead["owner"]["id"] == b["me"]
    with new_session() as db:
        assert db.scalar(select(func.count(CrmLead.id))) == 1

    d = member.get(f"/api/member/crm/leads/{lead['id']}").json()
    assert d["opportunity"]["contacts"][0]["phone"] == "0912345678"  # đầu mối lấy từ bản phiếu đã mua
    assert d["events"][0]["kind"] == "created"


def test_dong_bo_dong_thoi_khong_loi(admin, member, monkeypatch):
    """2 yêu cầu mở CRM cùng lúc: yêu cầu sau vẫn thấy phiếu "thiếu lead" (đọc trước khi bên kia ghi) → không được 500."""
    from app.models import Purchase
    from app.services import crm

    gold_with_purchase(admin, member)
    board(member)  # yêu cầu thứ nhất đã tạo lead
    with new_session() as db:
        p = db.scalar(select(Purchase))
        stale = [(p.id, p.opportunity_id, p.member_user_id, p.created_at)]

        class Rows:
            def all(self):
                return stale

        real, first = db.execute, [True]

        def execute(*a, **k):  # câu đọc đầu tiên thấy dữ liệu cũ (yêu cầu thứ hai đọc trước khi bên kia ghi); các câu sau chạy thật
            if first.pop() if first else False:
                return Rows()
            return real(*a, **k)

        monkeypatch.setattr(db, "execute", execute)
        assert crm.sync_leads(db, p.company_id) == 0  # đụng khoá duy nhất ở flush → bỏ qua, không lỗi
    assert len(board(member)["leads"]) == 1


def test_bang_gioi_han_the_moi_cot(admin, member):
    """Nhiều lead: mỗi cột chỉ trả per_stage thẻ mới cập nhật nhất, nhưng số đếm vẫn là tổng thật."""
    gold_with_purchase(admin, member)
    for i in range(3):
        oid = make_opp(admin, title=f"Cần thêm carton đợt {i}", price=29_000)
        assert member.post(f"/api/member/opportunities/{oid}/purchase").status_code == 200
    b = board(member, per_stage=2)
    assert b["counts"]["new"] == 4 and b["total"] == 4 and len(b["leads"]) == 2
    lid = b["leads"][0]["id"]
    member.patch(f"/api/member/crm/leads/{lid}", json={"stage": "won"})
    b = board(member, per_stage=2)
    assert b["counts"] == {"new": 3, "contacting": 0, "interested": 0, "quoted": 0, "won": 1, "lost": 0}
    assert sorted(x["stage"] for x in b["leads"]) == ["new", "new", "won"]
    assert len(board(member, q="đợt")["leads"]) == 3  # tìm kiếm không bị giới hạn cột


def test_doi_giai_doan_va_lich_su(admin, member):
    gold_with_purchase(admin, member)
    lid = board(member)["leads"][0]["id"]
    r = member.patch(f"/api/member/crm/leads/{lid}", json={"stage": "contacting"})
    assert r.status_code == 200 and r.json()["stage_label"] == "Đang liên hệ"
    assert member.patch(f"/api/member/crm/leads/{lid}", json={"stage": "bay-ba"}).status_code == 422
    ev = member.get(f"/api/member/crm/leads/{lid}").json()["events"]
    assert ev[0]["kind"] == "stage" and ev[0]["content"] == "Mới → Đang liên hệ"

    assert member.patch(f"/api/member/crm/leads/{lid}", json={"unassign": True}).json()["owner"] is None
    assert board(member, owner="me")["leads"] == []
    assert len(board(member, q="carton")["leads"]) == 1 and board(member, q="xi măng")["leads"] == []


def test_ghi_chu_che_sdt_email_la():
    snap = {"contacts": [{"phone": "0912 345 678", "email": "mua@abc.vn"}]}
    text, n = mask_pii("Đã gọi 0912.345.678, gửi mua@abc.vn. Anh Bình bên kho: 0987654321, binh@gmail.com, +84 903 111 222", snap)
    assert n == 3
    assert "0912.345.678" in text and "mua@abc.vn" in text
    assert "0987654321" not in text and "binh@gmail.com" not in text and "903 111 222" not in text
    assert text.count("[đã ẩn SĐT]") == 2 and "[đã ẩn email]" in text
    assert mask_pii("Báo giá 1.250.000đ, giao 200000 hộp", snap) == ("Báo giá 1.250.000đ, giao 200000 hộp", 0)


def test_them_ghi_chu_qua_api(admin, member):
    gold_with_purchase(admin, member)
    lid = board(member)["leads"][0]["id"]
    r = member.post(f"/api/member/crm/leads/{lid}/notes", json={"content": "Gọi 0912345678 ok, xin thêm số 0987654321"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["masked"] == 1 and body["warning"]
    assert "0912345678" in body["note"]["content"] and "0987654321" not in body["note"]["content"]
    notes = member.get(f"/api/member/crm/leads/{lid}").json()["notes"]
    assert len(notes) == 1
    assert member.delete(f"/api/member/crm/notes/{notes[0]['id']}").status_code == 204


def test_viec_can_lam(admin, member):
    gold_with_purchase(admin, member)
    lid = board(member)["leads"][0]["id"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = member.post(f"/api/member/crm/leads/{lid}/tasks", json={"title": "Gửi báo giá", "due_date": yesterday})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["overdue"] is True and r.json()["assignee"]["id"] == board(member)["me"]

    lead = board(member)["leads"][0]
    assert lead["open_tasks"] == 1 and lead["overdue"] is True and lead["next_due"] == yesterday
    t = member.get("/api/member/crm/tasks").json()
    assert t["counts"]["overdue"] == 1 and t["items"][0]["lead"]["title"].startswith("Cần 200.000")

    assert member.patch(f"/api/member/crm/tasks/{tid}", json={"done": True}).json()["done"] is True
    assert member.get("/api/member/crm/tasks").json()["items"] == []
    assert len(member.get("/api/member/crm/tasks", params={"status": "done"}).json()["items"]) == 1
    assert board(member)["leads"][0]["open_tasks"] == 0
    assert member.delete(f"/api/member/crm/tasks/{tid}").status_code == 204


def test_doanh_nghiep_khac_khong_thay_lead(admin, member, client):
    gold_with_purchase(admin, member)
    lid = board(member)["leads"][0]["id"]
    tid = member.post(f"/api/member/crm/leads/{lid}/tasks", json={"title": "Gọi lại"}).json()["id"]

    b = other_member(client, 2)
    ask(b)
    pay_membership(b)
    topup(b, 5_000_000)
    assert board(b)["leads"] == []
    assert b.get(f"/api/member/crm/leads/{lid}").status_code == 404
    assert b.patch(f"/api/member/crm/leads/{lid}", json={"stage": "won"}).status_code == 404
    assert b.post(f"/api/member/crm/leads/{lid}/notes", json={"content": "x"}).status_code == 404
    assert b.patch(f"/api/member/crm/tasks/{tid}", json={"done": True}).status_code == 404
    me_b = b.get("/api/member/auth/me").json()["id"]
    assert member.patch(f"/api/member/crm/leads/{lid}", json={"owner_id": me_b}).status_code == 422  # không giao cho người ngoài
