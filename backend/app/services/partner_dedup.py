"""So khớp NHU CẦU giữa cơ hội đối tác gửi và cơ hội đã có — để lọc trùng đúng nghĩa.

Trước đây: cùng doanh nghiệp (MST / tên) + cùng ngành ⇒ "trùng", nên 2 nhu cầu khác hẳn của cùng 1 doanh nghiệp vẫn bị đánh trùng.
Nay: cùng doanh nghiệp chỉ là ĐIỀU KIỆN để so; kết luận dựa trên độ giống của mô tả nhu cầu (0–100):

    ngữ nghĩa  = cosine embedding (Cohere; không có khoá → vector hash tại chỗ), quy ra 0–100 theo khoảng của từng mô hình
    từ khoá    = số từ chung / số từ của mô tả ngắn hơn (đã bỏ dấu, bỏ từ dừng)
    độ giống   = 0.6·ngữ nghĩa + 0.4·từ khoá   (không có vector cùng mô hình → chỉ từ khoá)
    sản phẩm   = nhận diện sản phẩm cụ thể (services/products.py): cùng sản phẩm → +10; khác hẳn sản phẩm → tối đa 25

    ≥ SAME  (70) → "same"     trùng nhu cầu      → nghi trùng, trừ 30 điểm chất lượng, đối tác không gửi lại được
    ≥ SIMILAR (45) → "similar" gần giống           → cần người duyệt xem, trừ 10 điểm
    còn lại       → "different" nhu cầu khác       → chỉ ghi "doanh nghiệp đã có cơ hội khác", không trừ điểm

Ngoài cùng doanh nghiệp, còn so với cơ hội CÙNG TỈNH + CÙNG NGÀNH (có thể ghi tên doanh nghiệp khác đi): chỉ báo khi độ giống
≥ NEED_ONLY (80) — bắt trường hợp 1 nhu cầu bị gửi lại dưới tên doanh nghiệp khác.
"""

import hashlib
import logging

from sqlalchemy.orm import Session

from app.config import Settings
from app.services import embedding as emb
from app.services import products as prod

log = logging.getLogger(__name__)

SAME, SIMILAR, NEED_ONLY = 70, 45, 80
W_SEM, W_KW = 0.6, 0.4
HASH_RANGE = (0.10, 0.55)  # vector hash: cosine ≤ 0.10 → 0, ≥ 0.55 → 100 (đo trên mô tả mẫu: viết lại cùng nhu cầu ≈ 0.58)
RELATION_LABELS = {"same": "Trùng nhu cầu", "similar": "Gần giống", "different": "Nhu cầu khác"}


def need_text(need: str, scale: str = "", timing: str = "", title: str = "") -> str:
    """Mô tả nhu cầu + quy mô. KHÔNG gồm thời điểm ("Từ tháng 1/2027"…): cụm chung chung, làm 2 nhu cầu khác nhau trông giống nhau."""
    return ". ".join(x for x in (title, need, scale) if x)


def opp_need_text(title: str, summary: str, scale: str, detail: str) -> str:
    """Phần nội dung nhu cầu của phiếu (bỏ ngành / tỉnh / nguồn — giống nhau giữa các cơ hội cùng nhóm, làm nhiễu điểm)."""
    return ". ".join(x for x in (title, summary, scale, (detail or "")[:2000]) if x)


def sha(model: str, text: str) -> str:
    return hashlib.sha1(f"{model}\n{text}".encode()).hexdigest()


def embed(cfg: Settings, texts: list[str]) -> tuple[list[list[float]] | None, str]:
    """Vector cho các mô tả; lỗi Cohere (hết hạn mức, mạng) → (None, "") và so bằng từ khoá."""
    if not texts:
        return [], emb.current_model(cfg)
    try:
        return emb.embed_documents(cfg, texts)
    except emb.EmbeddingError as e:
        log.warning("Lọc trùng đối tác: không lấy được embedding (%s) — chỉ so từ khoá", e)
        return None, ""


def _cos_range(cfg: Settings, model: str) -> tuple[float, float]:
    return HASH_RANGE if model.startswith("hash") else (cfg.partner_dup_cos_low, cfg.partner_dup_cos_high)


def keyword_overlap(a: str, b: str) -> float:
    ta, tb = set(emb.tokens(a)), set(emb.tokens(b))
    if not ta or not tb:
        return 0.0
    return 100.0 * len(ta & tb) / min(len(ta), len(tb))


def similarity(cfg: Settings, text_a: str, vec_a: list[float] | None, text_b: str, vec_b: list[float] | None, model: str = "") -> tuple[int, list[str]]:
    """Độ giống 0–100 của 2 mô tả nhu cầu + căn cứ (hiển thị cho người duyệt)."""
    kw = keyword_overlap(text_a, text_b)
    basis = [f"từ khoá {kw:.0f}"]
    if vec_a and vec_b and model:
        lo, hi = _cos_range(cfg, model)
        sem = max(0.0, min(100.0, (emb.cosine(vec_a, vec_b) - lo) * 100 / (hi - lo)))
        score = W_SEM * sem + W_KW * kw
        basis.insert(0, f"ngữ nghĩa {sem:.0f}")
    else:
        score = kw
    pa, pb = prod.find_products(text_a), prod.find_products(text_b)
    if pa and pb:
        rel, _ = prod.product_relation(pa, text_b)
        if rel in ("direct", "equivalent"):
            score += 10
            basis.append("cùng sản phẩm: " + ", ".join(prod.product_names(sorted(set(pa) & set(pb)) or pa)))
        elif rel == "unrelated":
            score = min(score, 25)
            basis.append(f"khác sản phẩm ({', '.join(prod.product_names(pa))} ≠ {', '.join(prod.product_names(pb))})")
    return int(round(max(0.0, min(100.0, score)))), basis


def relation(score: int) -> str:
    return "same" if score >= SAME else "similar" if score >= SIMILAR else "different"


def ensure_vectors(db: Session, cfg: Settings, rows: list, text_of, model_attr: str = "embedding_model") -> str:
    """Bảo đảm các dòng (cơ hội đối tác / phiếu) có vector của mô hình hiện tại — chỉ nhúng dòng thiếu, 1 lần gọi cho cả lô.
    Trả về nhãn mô hình ("" nếu không lấy được vector)."""
    model = emb.current_model(cfg)
    missing = [r for r in rows if getattr(r, model_attr) != model or getattr(r, "embedding") is None]
    if missing:
        vecs, got = embed(cfg, [text_of(r) for r in missing])
        if vecs is None:
            return model if len(missing) < len(rows) else ""
        for r, v in zip(missing, vecs):
            r.embedding, r.embedding_model = v, got
            if hasattr(r, "embedding_sha"):
                r.embedding_sha = sha(got, text_of(r))
    return model
