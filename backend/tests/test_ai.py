"""Cổng AI dùng chung: Cohere (Command A+) trước, lỗi / hết lượt → DeepSeek; nút "AI viết lại" yêu cầu tìm cơ hội."""

import json

import httpx
import pytest
import respx

from app import ai, deepseek
from app.config import get_settings
from app.services import search_ai, usage
from tests.test_member import member  # noqa: F401

COHERE = "https://api.cohere.com/v2/chat"
DEEPSEEK = "https://api.deepseek.com/chat/completions"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def cohere_ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={
        "id": "x", "finish_reason": "COMPLETE",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        "usage": {"billed_units": {"input_tokens": 50, "output_tokens": 20}, "tokens": {"input_tokens": 60, "output_tokens": 20}},
    })


def deepseek_ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={
        "model": "deepseek-flash",
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 40},
    })


@pytest.fixture
def keys(monkeypatch):
    def set_keys(cohere: str = "co-trial", ds: str = "sk-ds", **env):
        monkeypatch.setenv("COHERE_API_KEY", cohere)
        monkeypatch.setenv("DEEPSEEK_API_KEY", ds)
        for k, v in env.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()

    monkeypatch.setattr(deepseek.time, "sleep", lambda s: None)
    set_keys()
    yield set_keys
    get_settings.cache_clear()


@respx.mock
def test_cohere_tra_loi_thi_khong_goi_deepseek(keys):
    co = respx.post(COHERE).mock(return_value=cohere_ok('{"ok": true}'))
    ds = respx.post(DEEPSEEK).mock(return_value=deepseek_ok('{"ok": false}'))
    rep = ai.generate("hệ thống", "nội dung", schema=SCHEMA, max_tokens=500)
    assert (rep.provider, rep.model, rep.data, rep.fallback_reason) == ("cohere", "command-a-plus-05-2026", {"ok": True}, "")
    assert (rep.input_tokens, rep.output_tokens, rep.cost_usd) == (60, 20, 0)  # khoá Trial miễn phí
    body = json.loads(co.calls[0].request.content)
    assert co.calls[0].request.headers["Authorization"] == "Bearer co-trial"
    assert body["thinking"] == {"type": "disabled"} and body["response_format"] == {"type": "json_object", "schema": SCHEMA}
    assert not ds.called
    assert usage.calls_this_month("cohere-chat") == 1 and usage.calls_this_month("cohere") == 1  # tính cả vào hạn mức chung


@pytest.mark.parametrize("bad", [
    httpx.Response(429, json={"message": "trial key rate limit"}),
    httpx.Response(402, json={"message": "trial key exhausted"}),
    httpx.Response(500),
    httpx.ConnectTimeout("hết giờ"),
    cohere_ok("không phải JSON"),
])
@respx.mock
def test_cohere_loi_thi_xuong_deepseek(keys, bad):
    co = respx.post(COHERE)
    co.mock(side_effect=bad) if isinstance(bad, Exception) else co.mock(return_value=bad)
    ds = respx.post(DEEPSEEK).mock(return_value=deepseek_ok('{"ok": true}'))
    rep = ai.generate("s", "u", schema=SCHEMA)
    assert rep.provider == "deepseek" and rep.model == "deepseek-flash" and rep.data == {"ok": True}
    assert rep.fallback_reason.startswith("Cohere") and rep.cost_usd > 0
    assert co.call_count == 1 and ds.call_count == 1  # không thử lại Cohere (trial chỉ 20 lượt/phút)
    body = json.loads(ds.calls[0].request.content)
    assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}


@respx.mock
def test_het_luot_cohere_thang_thi_dung_deepseek(keys):
    keys(LEADSCAN_COHERE_CHAT_MONTHLY_LIMIT=1)
    co = respx.post(COHERE).mock(return_value=cohere_ok("Một"))
    respx.post(DEEPSEEK).mock(return_value=deepseek_ok("Hai"))
    assert ai.generate("s", "u").provider == "cohere"
    rep = ai.generate("s", "u")
    assert rep.provider == "deepseek" and rep.text == "Hai" and "hết lượt" in rep.fallback_reason
    assert co.call_count == 1


@respx.mock
def test_chi_co_deepseek_hoac_khong_co_khoa(keys):
    keys(cohere="")
    co = respx.post(COHERE)
    respx.post(DEEPSEEK).mock(return_value=deepseek_ok("Xin chào"))
    assert ai.generate("s", "u").provider == "deepseek" and not co.called

    keys(cohere="co-trial", ds="")
    respx.post(COHERE).mock(return_value=httpx.Response(429))
    with pytest.raises(ai.AiError, match="DEEPSEEK_API_KEY") as e:
        ai.generate("s", "u")
    assert e.value.retryable

    keys(cohere="", ds="")
    with pytest.raises(ai.AiError, match="chưa cấu hình khoá AI"):
        ai.generate("s", "u")


def test_lam_sach_ban_viet_lai():
    raw = "Dưới đây là yêu cầu đã viết lại:\n\n**Sản phẩm:** túi vải canvas in logo\n- Số lượng: từ 5.000 chiếc/đơn\n\n# Khách hàng cần tìm: chuỗi cà phê"
    assert search_ai.clean(raw) == "Sản phẩm: túi vải canvas in logo\nSố lượng: từ 5.000 chiếc/đơn\nKhách hàng cần tìm: chuỗi cà phê"
    p = search_ai.build_prompt("tui vai in logo, sl 5k", {"industries": ["Bao bì & in ấn"], "regions": [], "sizes": [], "sources": []})
    assert "<yeu_cau>\ntui vai in logo, sl 5k\n</yeu_cau>" in p and "Ngành hàng: Bao bì & in ấn" in p and "Khu vực" not in p


@respx.mock
def test_api_ai_viet_lai(keys, member):
    co = respx.post(COHERE).mock(return_value=cohere_ok("Sản phẩm: túi vải canvas in logo\nSố lượng: từ 5.000 chiếc/đơn"))
    r = member.post("/api/member/search-requests/rewrite", json={"note": "tui vai in logo sl 5k", "industries": ["Bao bì & in ấn"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"note": "Sản phẩm: túi vải canvas in logo\nSố lượng: từ 5.000 chiếc/đơn", "provider": "cohere", "model": "command-a-plus-05-2026"}
    sent = json.loads(co.calls[0].request.content)["messages"]
    assert "tui vai in logo sl 5k" in sent[1]["content"] and "Bao bì & in ấn" in sent[1]["content"]
    assert "response_format" not in json.loads(co.calls[0].request.content)

    assert member.post("/api/member/search-requests/rewrite", json={"note": "túi"}).status_code == 422

    keys(LEADSCAN_SEARCH_AI_REWRITE_PER_HOUR=1)
    assert member.post("/api/member/search-requests/rewrite", json={"note": "túi vải in logo"}).status_code == 429

    keys(cohere="", ds="")
    assert member.post("/api/member/search-requests/rewrite", json={"note": "túi vải in logo"}).status_code == 503


def test_api_ai_viet_lai_can_dang_nhap(client):
    assert client.post("/api/member/search-requests/rewrite", json={"note": "túi vải in logo"}).status_code == 401


@respx.mock
def test_api_ai_viet_lai_loi_thi_bao_than_thien(keys, member):
    keys(ds="")
    respx.post(COHERE).mock(return_value=httpx.Response(429))
    r = member.post("/api/member/search-requests/rewrite", json={"note": "túi vải in logo"})
    assert r.status_code == 502 and "AI đang bận" in r.json()["detail"] and "DEEPSEEK" not in r.json()["detail"]
