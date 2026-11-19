"""Tầng 3 bóc tách (B01): AI (Cohere, dự phòng DeepSeek — app/ai.py) đọc văn bản báo cáo quản trị và trả danh sách người + chức danh theo JSON schema.

• TẮT mặc định (LEADSCAN_ENRICH_LLM_ENABLED). Chỉ gửi VĂN BẢN đã cắt mục người nội bộ / người có liên quan
  (governance.text_for_model) — không gửi file PDF gốc.
• Lưu đệm theo (mã băm văn bản, tác vụ + phiên bản prompt, model) trong kho B — cùng nội dung không gọi lại.
• Cohere ép đúng JSON schema; DeepSeek dự phòng chỉ bảo đảm JSON hợp lệ — mục sai mẫu bị bỏ; lỗi → tài liệu vào hàng chờ duyệt.
"""

import hashlib
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


def call_model(text: str) -> tuple[list[dict], int, int, str]:
    """Gọi AI (Cohere → DeepSeek). Trả về (people, input_tokens, output_tokens, model). Tách riêng để test thay thế được."""
    from app import ai

    try:
        rep = ai.generate(SYSTEM, f"<van_ban>\n{text}\n</van_ban>", schema=SCHEMA, max_tokens=8000, timeout=180.0)
    except ai.AiError as e:
        raise LlmError(str(e)) from e
    people = (rep.data or {}).get("people")
    return [p for p in people if isinstance(p, dict)] if isinstance(people, list) else [], rep.input_tokens, rep.output_tokens, rep.model


def extract_people(db: Session, text: str) -> list[dict] | None:
    """Tầng 3 có lưu đệm. None nếu tầng 3 tắt; ném LlmError nếu gọi thất bại."""
    if not enabled() or not text.strip():
        return None
    h = _hash(text)
    # kết quả lưu đệm dùng lại được bất kể model nào đã trả lời (Cohere hay DeepSeek dự phòng)
    hit = db.scalar(select(LlmCache).where(LlmCache.content_hash == h, LlmCache.task == TASK).order_by(LlmCache.id.desc()).limit(1))
    if hit:
        return list(hit.result.get("people") or [])
    people, tin, tout, model = call_model(text)
    db.add(LlmCache(content_hash=h, task=TASK, model=model[:60], result={"people": people}, input_tokens=tin, output_tokens=tout))
    try:
        db.commit()
    except IntegrityError:  # worker khác vừa lưu cùng nội dung
        db.rollback()
    log.info("LLM (%s) bóc tách %s người (%s in / %s out tokens)", model, len(people), tin, tout)
    return people
