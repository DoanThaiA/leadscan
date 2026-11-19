"""Gọi DeepSeek: thân request đúng định dạng OpenAI, bật/tắt suy nghĩ, JSON Output, ánh xạ lỗi."""

import json

import httpx
import pytest
import respx

from app import deepseek
from app.config import get_settings

URL = "https://api.deepseek.com/chat/completions"


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr(deepseek.time, "sleep", lambda s: None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def ok(content: str, finish: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={
        "model": "deepseek-flash",
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
    })


@respx.mock
def test_json_tat_suy_nghi():
    route = respx.post(URL).mock(return_value=ok('{"people": []}'))
    data, rep = deepseek.chat_json("hệ thống", "văn bản", schema={"type": "object"}, model="deepseek-flash", max_tokens=100)
    assert data == {"people": []} and (rep.input_tokens, rep.output_tokens) == (120, 30)
    req = route.calls[0].request
    body = json.loads(req.content)
    assert req.headers["Authorization"] == "Bearer sk-test"
    assert body["thinking"] == {"type": "disabled"} and "reasoning_effort" not in body
    assert body["response_format"] == {"type": "json_object"} and "JSON" in body["messages"][0]["content"]


@respx.mock
def test_bat_suy_nghi_va_thu_lai_khi_5xx():
    route = respx.post(URL).mock(side_effect=[httpx.Response(503), ok("Bản nháp")])
    rep = deepseek.chat("s", "u", model="deepseek-v4-pro", max_tokens=100, effort="low")
    assert rep.text == "Bản nháp" and route.call_count == 2
    body = json.loads(route.calls[0].request.content)
    assert body["thinking"] == {"type": "enabled"} and body["reasoning_effort"] == "low" and "response_format" not in body


@respx.mock
def test_loi_khoa_so_du_cat_ngan():
    respx.post(URL).mock(return_value=httpx.Response(401, json={"error": {"message": "bad key"}}))
    with pytest.raises(deepseek.DeepSeekError, match="DEEPSEEK_API_KEY"):
        deepseek.chat("s", "u", model="deepseek-flash", max_tokens=10)
    respx.post(URL).mock(return_value=httpx.Response(402))
    with pytest.raises(deepseek.DeepSeekError, match="số dư"):
        deepseek.chat("s", "u", model="deepseek-flash", max_tokens=10)
    respx.post(URL).mock(return_value=ok('{"a"', finish="length"))
    with pytest.raises(deepseek.DeepSeekError, match="bị cắt"):
        deepseek.chat_json("s", "u", schema={}, model="deepseek-flash", max_tokens=10)
    respx.post(URL).mock(return_value=ok("   "))
    with pytest.raises(deepseek.DeepSeekError) as e:
        deepseek.chat_json("s", "u", schema={}, model="deepseek-flash", max_tokens=10)
    assert e.value.retryable


def test_chua_co_khoa_khong_goi_mang(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    get_settings.cache_clear()
    with respx.mock(assert_all_called=False) as m:
        route = m.post(URL)
        with pytest.raises(deepseek.DeepSeekError, match="chưa cấu hình"):
            deepseek.chat("s", "u", model="deepseek-flash", max_tokens=10)
        assert not route.called
