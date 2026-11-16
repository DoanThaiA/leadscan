"""Tầng 3 bóc tách (B01): Claude đọc văn bản báo cáo quản trị và trả danh sách người + chức danh theo JSON schema.

• TẮT mặc định (LEADSCAN_ENRICH_LLM_ENABLED). Chỉ gửi VĂN BẢN đã cắt mục người nội bộ / người có liên quan
  (governance.text_for_model) — không gửi file PDF gốc.
• Lưu đệm theo (mã băm văn bản, tác vụ + phiên bản prompt, model) trong kho B — cùng nội dung không gọi lại.
• Bật fallback phía máy chủ ("fallbacks": "default"): nếu model bị bộ lọc an toàn từ chối, API tự chạy lại trên model
  dự phòng trong cùng request. Từ chối hẳn (stop_reason "refusal") → coi như tầng 3 thất bại, tài liệu vào hàng chờ duyệt.
"""

import hashlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models_enrich import LlmCache

log = logging.getLogger("leadscan.enrich.llm")

TASK = "governance-v1"  # đổi prompt / schema → tăng phiên bản để không dùng lại kết quả cũ

SYSTEM = (
    "Bạn bóc tách danh sách thành viên quản trị từ báo cáo tình hình quản trị công ty / báo cáo thường niên của doanh "
    "nghiệp niêm yết Việt Nam. Chỉ lấy người thuộc: Hội đồng quản trị hoặc Hội đồng thành viên (nhom=hdqt), Ban kiểm soát "
    "hoặc Uỷ ban kiểm toán (bks), Ban điều hành / Ban Tổng Giám đốc (bdh), Kế toán trưởng (ktt). "
    "Với mỗi người chỉ ghi: họ tên đầy đủ (bỏ Ông/Bà), chức danh đúng như văn bản, nhóm, ngày bổ nhiệm và ngày miễn nhiệm "
    "nếu văn bản ghi rõ (YYYY-MM-DD, không có thì null). "
    "KHÔNG ghi ngày sinh, số giấy tờ, địa chỉ, số cổ phiếu, trình độ, người thân hay bất kỳ người có liên quan / người nội bộ "
    "nào khác. Không suy đoán người không có trong văn bản. Không có ai thì trả danh sách rỗng."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ho_ten": {"type": "string"},
                    "chuc_danh": {"type": "string"},
                    "nhom": {"type": "string", "enum": ["hdqt", "bks", "bdh", "ktt", "khac"]},
                    "tu_ngay": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "den_ngay": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["ho_ten", "chuc_danh", "nhom", "tu_ngay", "den_ngay"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["people"],
    "additionalProperties": False,
}


class LlmError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(get_settings().enrich_llm_enabled)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def call_model(text: str) -> tuple[list[dict], int, int]:
    """Gọi Claude. Trả về (people, input_tokens, output_tokens). Tách riêng để test thay thế được."""
    import anthropic

    cfg = get_settings()
    client = anthropic.Anthropic(timeout=180.0, max_retries=2)
    try:
        resp = client.beta.messages.create(
            model=cfg.enrich_llm_model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"<van_ban>\n{text}\n</van_ban>"}],
            output_config={
                "effort": cfg.enrich_llm_effort,
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.BadRequestError as e:
        raise LlmError(f"Yêu cầu không hợp lệ: {e.message}") from e
    except anthropic.AuthenticationError as e:
        raise LlmError("Khoá ANTHROPIC_API_KEY không hợp lệ hoặc chưa cấu hình.") from e
    except anthropic.RateLimitError as e:
        raise LlmError("Vượt giới hạn tốc độ của API — thử lại sau.") from e
    except anthropic.APIStatusError as e:
        raise LlmError(f"API lỗi {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LlmError("Không kết nối được API mô hình.") from e

    if resp.stop_reason == "refusal":
        raise LlmError("Mô hình từ chối xử lý tài liệu này.")
    if resp.stop_reason == "max_tokens":
        raise LlmError("Kết quả quá dài, bị cắt.")
    body = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise LlmError("Mô hình trả về JSON không hợp lệ.") from e
    return list(data.get("people") or []), resp.usage.input_tokens, resp.usage.output_tokens


def extract_people(db: Session, text: str) -> list[dict] | None:
    """Tầng 3 có lưu đệm. None nếu tầng 3 tắt; ném LlmError nếu gọi thất bại."""
    if not enabled() or not text.strip():
        return None
    model = get_settings().enrich_llm_model
    h = _hash(text)
    hit = db.scalar(select(LlmCache).where(LlmCache.content_hash == h, LlmCache.task == TASK, LlmCache.model == model))
    if hit:
        return list(hit.result.get("people") or [])
    people, tin, tout = call_model(text)
    db.add(LlmCache(content_hash=h, task=TASK, model=model, result={"people": people}, input_tokens=tin, output_tokens=tout))
    try:
        db.commit()
    except IntegrityError:  # worker khác vừa lưu cùng nội dung
        db.rollback()
    log.info("LLM bóc tách %s người (%s in / %s out tokens)", len(people), tin, tout)
    return people
