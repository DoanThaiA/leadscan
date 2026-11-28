"""Đọc chữ trong ảnh chuyển khoản bằng OCR.space và so khớp với đơn đăng ký sự kiện.

Khoá API đặt trong .env: OCR_SPACE_API_KEY (hoặc LEADSCAN_OCR_SPACE_API_KEY). Chưa có khoá thì
không gọi ra ngoài — mọi ảnh khách gửi vào trạng thái "Chờ đối soát" để ban tổ chức tự xác nhận.

So khớp (hàm `verify`):
  • MÃ ĐĂNG KÝ  — bắt buộc. Tìm trong chữ đã chuẩn hoá (bỏ dấu cách, chỉ giữ A–Z 0–9).
  • SỐ TIỀN     — tìm mọi cụm số trong ảnh (500.000 / 500,000 / 500000 / 500000 VND) và so với số phải nộp.
  • SỐ TÀI KHOẢN— chỉ để tham khảo, không bắt buộc (nhiều app ngân hàng che bớt số).
Đủ mã + đủ tiền → "matched" (tự xác nhận đã thanh toán). Thiếu bất kỳ điều kiện nào → "mismatch"
(chờ đối soát). Không đọc được chữ → "unreadable". Gọi API lỗi → "error" (admin bấm "Đọc lại ảnh").
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.config import Settings, get_settings

log = logging.getLogger("leadscan.ocr")

TEXT_KEEP = 4000  # số ký tự chữ đọc được lưu lại cho admin xem


def enabled(cfg: Settings | None = None) -> bool:
    return bool((cfg or get_settings()).ocr_space_api_key)


@dataclass
class OcrResult:
    """status: matched | mismatch | unreadable | error | off"""

    status: str
    text: str = ""
    amount: int | None = None
    checks: dict[str, bool] = field(default_factory=dict)
    message: str = ""


def _normalize(s: str) -> str:
    """"SK 7KQ4 M2" → "SK7KQ4M2" (chỉ giữ chữ và số, viết hoa) để tìm mã không phụ thuộc cách xuống dòng."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def read_text(data: bytes, filename: str, mime: str, cfg: Settings | None = None) -> tuple[str, str]:
    """Gọi OCR.space, trả về (chữ đọc được, thông báo lỗi). Lỗi → ("", "lý do")."""
    cfg = cfg or get_settings()
    if not cfg.ocr_space_api_key:
        return "", "Chưa cấu hình OCR_SPACE_API_KEY."
    payload = {
        "apikey": cfg.ocr_space_api_key,
        "OCREngine": str(cfg.ocr_space_engine),
        "scale": "true",
        "isTable": "true",
        "detectOrientation": "true",
    }
    if cfg.ocr_space_engine != 2:
        payload["language"] = cfg.ocr_space_language
    try:
        r = httpx.post(
            cfg.ocr_space_url,
            data=payload,
            files={"file": (filename or "bien-lai.jpg", data, mime or "image/jpeg")},
            timeout=cfg.ocr_space_timeout,
        )
    except httpx.HTTPError as e:
        log.warning("OCR.space lỗi mạng: %s", e)
        return "", "Không gọi được OCR.space, vui lòng thử lại."
    if r.status_code != 200:
        log.warning("OCR.space trả HTTP %s: %s", r.status_code, r.text[:300])
        return "", f"OCR.space trả lỗi HTTP {r.status_code}."
    try:
        d = r.json()
    except ValueError:
        return "", "OCR.space trả dữ liệu không đọc được."
    if d.get("IsErroredOnProcessing"):
        msg = d.get("ErrorMessage") or d.get("ErrorDetails") or "OCR.space báo lỗi xử lý ảnh."
        if isinstance(msg, list):
            msg = " ".join(str(x) for x in msg)
        return "", str(msg)[:300]
    parts = [str(p.get("ParsedText") or "") for p in (d.get("ParsedResults") or [])]
    return "\n".join(x for x in parts if x).strip(), ""


# Cụm số có thể là số tiền: 500.000 · 500,000 · 500000 · 500 000
_AMOUNT_RE = re.compile(r"\d[\d.,\s]{2,}\d|\d{4,}")


def _amounts(text: str) -> list[int]:
    out: list[int] = []
    for m in _AMOUNT_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        # bỏ cụm quá ngắn (số thứ tự) hoặc quá dài (số tài khoản, mã giao dịch, ngày giờ dính nhau)
        if 4 <= len(digits) <= 12:
            out.append(int(digits))
    return out


def verify(
    data: bytes,
    filename: str,
    mime: str,
    code: str,
    amount: int,
    account_no: str = "",
    cfg: Settings | None = None,
) -> OcrResult:
    """Đọc ảnh và so khớp với mã đăng ký + số tiền phải nộp."""
    cfg = cfg or get_settings()
    if not enabled(cfg):
        return OcrResult("off", message="Chưa bật đối soát tự động (thiếu OCR_SPACE_API_KEY).")

    text, err = read_text(data, filename, mime, cfg)
    if err:
        return OcrResult("error", message=err)
    if not text.strip():
        return OcrResult("unreadable", message="Không đọc được chữ trong ảnh. Ban tổ chức sẽ đối soát thủ công.")

    flat = _normalize(text)
    found = _amounts(text)
    tol = max(0, cfg.ocr_amount_tolerance)
    checks = {
        "code": bool(code) and _normalize(code) in flat,
        "amount": amount <= 0 or any(abs(v - amount) <= tol for v in found),
        "account": bool(account_no) and _normalize(account_no) in flat,
    }
    best = max((v for v in found if abs(v - amount) <= tol), default=None) if amount > 0 else None
    if best is None and found:
        best = max(found)

    need_amount = cfg.ocr_require_amount and amount > 0
    if checks["code"] and (checks["amount"] or not need_amount):
        return OcrResult("matched", text[:TEXT_KEEP], best, checks, "Ảnh khớp mã đăng ký và số tiền.")

    missing = []
    if not checks["code"]:
        missing.append(f"nội dung chuyển khoản “{code}”")
    if need_amount and not checks["amount"]:
        missing.append(f"số tiền {amount:,}đ".replace(",", "."))
    return OcrResult(
        "mismatch",
        text[:TEXT_KEEP],
        best,
        checks,
        "Chưa tìm thấy " + " và ".join(missing) + " trong ảnh. Ban tổ chức sẽ đối soát thủ công.",
    )
