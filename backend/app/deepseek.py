"""Gọi mô hình DeepSeek (API định dạng OpenAI: POST {base_url}/chat/completions) — dùng chung cho mọi tính năng AI.

• Khoá: DEEPSEEK_API_KEY (hoặc LEADSCAN_DEEPSEEK_API_KEY). Chưa có khoá → DeepSeekError, không gọi mạng.
• effort: "none" = tắt chế độ suy nghĩ (rẻ, nhanh — đủ cho trích xuất / phân loại / viết ngắn);
  "low" | "medium" | "high" | "max" = bật suy nghĩ với mức tương ứng (token suy nghĩ tính như token ra).
• json_schema: bật JSON Output (response_format json_object) và đưa schema vào system prompt — DeepSeek chỉ bảo đảm
  JSON hợp lệ, không ép theo schema, nên nơi gọi vẫn phải kiểm tra / làm sạch kết quả.
"""

import json
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings

log = logging.getLogger("leadscan.deepseek")

RETRIES = 2  # thử lại khi 429 / 5xx / lỗi kết nối, giãn cách 1s, 2s


class DeepSeekError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


@dataclass
class Reply:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


def _error_message(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error", {}).get("message") or r.text)[:300]
    except ValueError:
        return r.text[:300]


def chat(
    system: str,
    user: str,
    *,
    model: str,
    max_tokens: int,
    effort: str = "none",
    json_schema: dict | None = None,
    timeout: float = 120.0,
) -> Reply:
    cfg = get_settings()
    if not cfg.deepseek_api_key:
        raise DeepSeekError("Máy chủ chưa cấu hình khoá DEEPSEEK_API_KEY cho AI.")
    if json_schema is not None:
        system = (
            f"{system}\n\nChỉ trả lời bằng DUY NHẤT một đối tượng JSON hợp lệ (không kèm chữ nào khác), "
            f"đủ mọi trường bắt buộc, đúng JSON Schema sau:\n{json.dumps(json_schema, ensure_ascii=False)}"
        )
    body: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "stream": False,
    }
    if effort in ("", "none"):
        body["thinking"] = {"type": "disabled"}
    else:
        body["thinking"] = {"type": "enabled"}
        body["reasoning_effort"] = effort
    if json_schema is not None:
        body["response_format"] = {"type": "json_object"}

    url = cfg.deepseek_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.deepseek_api_key}"}
    for attempt in range(RETRIES + 1):
        last = attempt == RETRIES
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as e:
            if not last:
                time.sleep(attempt + 1)
                continue
            raise DeepSeekError("Không kết nối được dịch vụ AI DeepSeek.", retryable=True) from e
        if r.status_code == 429 or r.status_code >= 500:
            if not last:
                time.sleep(attempt + 1)
                continue
            msg = "Dịch vụ AI đang quá tải, thử lại sau." if r.status_code in (429, 503) else f"Dịch vụ AI lỗi {r.status_code}."
            raise DeepSeekError(msg, retryable=True, status=r.status_code)
        if r.status_code == 401:
            raise DeepSeekError("Khoá DEEPSEEK_API_KEY không hợp lệ.", status=401)
        if r.status_code == 402:
            raise DeepSeekError("Tài khoản DeepSeek hết số dư — cần nạp thêm.", status=402)
        if r.status_code >= 400:
            raise DeepSeekError(f"Yêu cầu AI không hợp lệ ({r.status_code}): {_error_message(r)}", status=r.status_code)
        break

    try:
        data = r.json()
        choice = data["choices"][0]
        text = (choice["message"].get("content") or "").strip()
        usage = data.get("usage") or {}
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise DeepSeekError("Dịch vụ AI trả về dữ liệu không đọc được.", retryable=True) from e
    finish = choice.get("finish_reason") or ""
    if finish == "content_filter":
        raise DeepSeekError("AI từ chối xử lý nội dung này.")
    if finish == "length":
        raise DeepSeekError("Kết quả AI quá dài, bị cắt.")
    if finish == "insufficient_system_resource":
        raise DeepSeekError("Dịch vụ AI tạm thiếu tài nguyên, thử lại sau.", retryable=True)
    return Reply(
        text=text,
        model=data.get("model") or model,
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        finish_reason=finish,
    )


def chat_json(system: str, user: str, *, schema: dict, **kw) -> tuple[dict, Reply]:
    """chat() ở chế độ JSON; trả (đối tượng JSON, Reply). JSON rỗng / sai → DeepSeekError (rỗng thì thử lại được)."""
    rep = chat(system, user, json_schema=schema, **kw)
    if not rep.text:
        raise DeepSeekError("AI trả về nội dung rỗng.", retryable=True)
    try:
        data = json.loads(rep.text)
    except json.JSONDecodeError as e:
        raise DeepSeekError("AI trả về JSON không hợp lệ.") from e
    if not isinstance(data, dict):
        raise DeepSeekError("AI trả về dữ liệu sai mẫu.")
    return data, rep
