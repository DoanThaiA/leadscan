"""Embedding Cohere (giả lập bằng respx) + so khớp chạy nền + Tất cả cơ hội bắt đầu trống."""

import json

import httpx
import pytest
import respx
from sqlalchemy import select

from app.config import get_settings
from app.db import new_session
from app.models import Opportunity, SearchRequest
from app.services import embedding as emb
from tests.test_member import ask, make_opp, member, view  # noqa: F401

COHERE_URL = "https://api.cohere.com/v2/embed"


@pytest.fixture
def cohere(monkeypatch):
    """Bật Cohere với khoá giả; API trả vector hash 1024 chiều để kết quả so khớp có nghĩa."""
    monkeypatch.setenv("COHERE_API_KEY", "test-key")
    monkeypatch.setenv("LEADSCAN_COHERE_COS_LOW", "0.03")  # vector giả là vector hash → dùng khoảng cosine của hash
    monkeypatch.setenv("LEADSCAN_COHERE_COS_HIGH", "0.40")
    get_settings.cache_clear()
    calls: list[dict] = []

    def reply(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append({**body, "auth": request.headers.get("authorization")})
        return httpx.Response(200, json={"id": "x", "embeddings": {"float": [emb.embed_hash(t) for t in body["texts"]]}, "texts": body["texts"]})

    with respx.mock(assert_all_called=False) as mock:
        mock.post(COHERE_URL).mock(side_effect=reply)
        yield calls
    get_settings.cache_clear()


def test_chi_can_cohere_api_key(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "abc")
    get_settings.cache_clear()
    cfg = get_settings()
    assert cfg.cohere_api_key == "abc" and cfg.cohere_embed_url == COHERE_URL
    assert emb.current_model(cfg).startswith("cohere:embed-v5.0-pro+embed-v5.0-fast@1024")
    get_settings.cache_clear()


def test_so_khop_bang_cohere(admin, member, cohere):
    oid = make_opp(admin)
    docs = [c for c in cohere if c["input_type"] == "search_document"]
    assert docs and docs[0]["model"] == "embed-v5.0-pro" and docs[0]["output_dimension"] == 1024
    assert docs[0]["auth"] == "Bearer test-key" and docs[0]["embedding_types"] == ["float"]
    assert "Bắc Ninh" in docs[0]["texts"][0] and "Công ty Điện tử ABC" not in docs[0]["texts"][0]  # không lộ bên mua

    r = ask(member)
    queries = [c for c in cohere if c["input_type"] == "search_query"]
    assert queries[-1]["model"] == "embed-v5.0-fast" and "hộp carton" in queries[-1]["texts"][0]
    assert r["match_status"] == "done" and r["match_count"] == 1
    assert view(member, oid)["score"] >= 60
    with new_session() as db:
        o = db.get(Opportunity, oid)
        assert len(o.embedding) == 1024 and o.embedding_model.startswith("cohere:")

    # chỉ sửa giá → không gọi lại Cohere; sửa nội dung → nhúng lại
    n = len(cohere)
    body = {k: v for k, v in admin.get(f"/api/admin/opportunities/{oid}").json()["opportunity"].items()
            if k in ("title", "summary", "industry", "province", "region", "source_type", "price", "max_buyers", "buyer_name", "detail", "status")}
    admin.put(f"/api/admin/opportunities/{oid}", json={**body, "price": 99_000, "contacts": []})
    assert len(cohere) == n
    admin.put(f"/api/admin/opportunities/{oid}", json={**body, "summary": "Nhà máy điện tử Bắc Ninh cần thùng carton 7 lớp", "contacts": []})
    assert len(cohere) == n + 1 and cohere[-1]["input_type"] == "search_document"


def test_sai_khoa_khong_thu_lai_va_so_khop_du_phong(admin, member, monkeypatch):
    """401 (sai khoá / khoá hết hạn) → không thử lại (đỡ tốn lượt), vẫn so khớp bằng tiêu chí + từ khoá."""
    monkeypatch.setenv("COHERE_API_KEY", "sai-khoa")
    get_settings.cache_clear()
    with respx.mock as mock:
        route = mock.post(COHERE_URL).mock(return_value=httpx.Response(401, json={"message": "invalid api token"}))
        oid = make_opp(admin)
        assert route.call_count == 1  # phiếu cơ hội: 1 lần, không thử lại
        r = member.post("/api/member/search-requests", json={"industries": ["Bao bì & in ấn"], "regions": ["Bắc Ninh"],
                                                             "note": "Cần mua hộp carton cho nhà máy ở Bắc Ninh"})
        assert r.status_code == 201
        assert route.call_count == 2  # phiếu tìm: 1 lần, không thử lại
    out = r.json()
    assert out["match_status"] == "done" and out["match_count"] == 1  # vẫn tìm được nhờ tiêu chí + từ khoá
    assert view(member, oid)["score"] > 0
    item = admin.get("/api/admin/search-requests").json()["items"][0]
    assert "401" in item["match_error"] and "không dùng ngữ nghĩa" in item["match_error"]
    get_settings.cache_clear()


def test_loi_tam_thoi_thi_thu_lai(admin, member, monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "k")
    get_settings.cache_clear()
    with respx.mock as mock:
        route = mock.post(COHERE_URL).mock(return_value=httpx.Response(503, text="busy"))
        member.post("/api/member/search-requests", json={"note": "Cần mua hộp carton cho nhà máy ở Bắc Ninh"})
        assert route.call_count == 4  # 1 lần + 3 lần thử lại, rồi chạy dự phòng
    assert member.get("/api/member/search-requests").json()["items"][0]["match_status"] == "done"
    get_settings.cache_clear()


def test_han_muc_thang_cua_khoa_trial(admin, member, cohere, monkeypatch):
    """Hết hạn mức tháng → không gọi Cohere nữa, so khớp dự phòng; admin thấy số lượt đã dùng."""
    monkeypatch.setenv("LEADSCAN_COHERE_MONTHLY_LIMIT", "2")
    get_settings.cache_clear()
    make_opp(admin)  # lượt 1
    ask(member)  # lượt 2
    used = len(cohere)
    assert used == 2
    make_opp(admin, title="Cần thùng carton 3 lớp cho kho Bắc Ninh")  # hết lượt → không gọi
    r = ask(member, "Tìm khách mua hộp carton tại Bắc Ninh")
    assert len(cohere) == used and r["match_status"] == "done" and r["match_count"] == 2
    stats = admin.get("/api/admin/commerce-stats").json()["cohere"]
    assert stats == {"configured": True, "calls_month": 2, "monthly_limit": 2}
    item = admin.get("/api/admin/search-requests").json()["items"][0]
    assert "hết 2 lần gọi Cohere" in item["match_error"]


def test_tat_ca_co_hoi_ban_dau_trong(admin, member):
    for i in range(3):
        make_opp(admin, title=f"Cần hộp carton lô {i}")
    assert member.get("/api/member/opportunities").json()["total"] == 0
    assert member.get("/api/member/saved").json()["total"] == 0
    d = member.get("/api/member/dashboard").json()
    assert d["matched_count"] == 0 and d["new_opportunities"] == [] and d["saved_count"] == 0
    r = ask(member)
    assert r["match_status"] == "done" and r["match_count"] == 3
    assert member.get("/api/member/opportunities").json()["total"] == 3
    assert member.get("/api/member/dashboard").json()["matched_count"] == 3


def test_kho_an_co_hoi_khong_con_phu_hop(admin, member):
    make_opp(admin)
    r = ask(member)
    assert member.get("/api/member/saved").json()["total"] == 1
    admin.patch(f"/api/admin/search-requests/{r['id']}", json={"status": "rejected", "reply": "Không phù hợp"})
    assert member.get("/api/member/opportunities").json()["total"] == 0
    assert member.get("/api/member/saved").json()["total"] == 0  # cơ hội không còn khớp thì không hiện trong kho
    assert member.get("/api/member/dashboard").json()["saved_count"] == 0
