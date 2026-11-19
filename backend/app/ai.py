"""Cổng gọi AI sinh văn bản dùng chung: Cohere trước, có sự cố thì tự xuống DeepSeek.

Luồng mỗi lượt gọi:
  1. Có COHERE_API_KEY và còn lượt trong tháng → gọi Cohere Chat v2 (Command A+, tắt suy nghĩ).
     Khoá Trial: tối đa 1.000 lượt gọi/tháng cho MỌI endpoint (tính chung với embedding so khớp) và 20 lượt/phút cho chat.
     Vì vậy chat có trần riêng (cohere_chat_monthly_limit) để chừa lượt cho embedding, và cũng cộng vào bộ đếm chung "cohere".
  2. Cohere lỗi vì bất kỳ lý do gì (hết lượt, 429 quá tần suất, 401/402/403 khoá trial hết hạn, 5xx, quá thời gian,
     kết quả rỗng / sai JSON) → gọi DeepSeek (deepseek-flash, tắt suy nghĩ) với cùng prompt. Không thử lại Cohere:
     trial chỉ 20 lượt/phút nên chờ thì chậm, xuống DeepSeek ngay rẻ và nhanh hơn.
  3. DeepSeek cũng lỗi (hoặc chưa có DEEPSEEK_API_KEY) → AiError, nơi gọi tự xử lý như trước.

Kết quả ghi rõ nhà cung cấp + model đã trả lời và chi phí (Cohere trial = 0 USD) để báo cáo / tính ngân sách.
"""

import json
import logging
from dataclasses import dataclass

import httpx

from app import deepseek
from app.config import Settings, get_settings

log = logging.getLogger("leadscan.ai")


class AiError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Reply:
    text: str
    provider: str  # "cohere" | "deepseek"
    model: str
    input_tokens: int
    output_tokens: int
    data: dict | None = None  # kết quả JSON khi gọi với schema
    fallback_reason: str = ""  # vì sao không dùng được Cohere (rỗng = Cohere đã trả lời)

    @property
    def cost_usd(self) -> float:
        cfg = get_settings()
        pin, pout = (
            (cfg.cohere_price_in, cfg.cohere_price_out) if self.provider == "cohere" else (cfg.deepseek_price_in, cfg.deepseek_price_out)
        )
        return (self.input_tokens * pin + self.output_tokens * pout) / 1_000_000


class _CohereFailed(Exception):
    pass


def configured() -> bool:
    cfg = get_settings()
    return bool(cfg.cohere_api_key or cfg.deepseek_api_key)


def describe() -> str:
    """Chuỗi hiển thị cho admin: model chính → model dự phòng."""
    cfg = get_settings()
    parts = []
    if cfg.cohere_api_key:
        parts.append(cfg.cohere_chat_model)
    if cfg.deepseek_api_key:
        parts.append(cfg.deepseek_model)
    return " → ".join(parts) or "chưa cấu hình khoá AI"


def _reserve_cohere(cfg: Settings) -> bool:
    from app.services import usage

    if not usage.reserve_call("cohere-chat", cfg.cohere_chat_monthly_limit):
        return False
    return usage.reserve_call("cohere", cfg.cohere_monthly_limit)


def _cohere(cfg: Settings, system: str, user: str, schema: dict | None, max_tokens: int, timeout: float) -> Reply:
    body: dict = {
        "model": cfg.cohere_chat_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }
    if schema is not None:
        body["response_format"] = {"type": "json_object", "schema": schema}
    try:
        r = httpx.post(
            cfg.cohere_chat_url,
            headers={"Authorization": f"Bearer {cfg.cohere_api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        raise _CohereFailed(f"không kết nối được ({type(e).__name__})") from e
    if r.status_code >= 400:
        raise _CohereFailed(f"lỗi {r.status_code}: {r.text[:200]}")
    try:
        d = r.json()
        content = d["message"].get("content") or []
        text = "".join(c.get("text", "") for c in content if c.get("type") == "text").strip()
        tokens = (d.get("usage") or {}).get("tokens") or (d.get("usage") or {}).get("billed_units") or {}
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise _CohereFailed("trả dữ liệu không đọc được") from e
    finish = d.get("finish_reason") or ""
    if finish not in ("COMPLETE", "STOP_SEQUENCE", ""):
        raise _CohereFailed(f"kết thúc bất thường ({finish})")
    if not text:
        raise _CohereFailed("trả nội dung rỗng")
    rep = Reply(text, "cohere", cfg.cohere_chat_model, int(tokens.get("input_tokens") or 0), int(tokens.get("output_tokens") or 0))
    if schema is not None:
        try:
            rep.data = json.loads(text)
        except json.JSONDecodeError as e:
            raise _CohereFailed("trả JSON không hợp lệ") from e
        if not isinstance(rep.data, dict):
            raise _CohereFailed("trả JSON sai mẫu")
    return rep


def generate(system: str, user: str, *, schema: dict | None = None, max_tokens: int = 4000, timeout: float = 120.0) -> Reply:
    """Sinh văn bản (hoặc JSON khi có schema). Cohere trước, DeepSeek dự phòng. Lỗi cả hai → AiError."""
    cfg = get_settings()
    reason = ""
    if not cfg.cohere_api_key:
        reason = "chưa có COHERE_API_KEY"
    elif not _reserve_cohere(cfg):
        reason = "hết lượt Cohere của tháng"
    else:
        try:
            return _cohere(cfg, system, user, schema, max_tokens, timeout)
        except _CohereFailed as e:
            reason = f"Cohere {e}"
    if cfg.cohere_api_key:
        log.warning("AI dùng DeepSeek dự phòng: %s", reason)
    if not cfg.deepseek_api_key:
        if cfg.cohere_api_key:
            raise AiError(f"Dịch vụ AI tạm thời không dùng được ({reason}); chưa cấu hình DEEPSEEK_API_KEY để dự phòng.", retryable=True)
        raise AiError("Máy chủ chưa cấu hình khoá AI (COHERE_API_KEY hoặc DEEPSEEK_API_KEY).")
    try:
        if schema is not None:
            data, dr = deepseek.chat_json(system, user, schema=schema, model=cfg.deepseek_model, max_tokens=max_tokens, timeout=timeout)
        else:
            data, dr = None, deepseek.chat(system, user, model=cfg.deepseek_model, max_tokens=max_tokens, timeout=timeout)
    except deepseek.DeepSeekError as e:
        raise AiError(str(e), retryable=e.retryable) from e
    return Reply(dr.text, "deepseek", dr.model, dr.input_tokens, dr.output_tokens, data, reason)
