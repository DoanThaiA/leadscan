"""Embedding văn bản để so khớp ngữ nghĩa giữa yêu cầu của khách và mô tả phiếu cơ hội.

Hai chế độ:
  cohere  có COHERE_API_KEY → gọi Cohere Embed v2 (đa ngôn ngữ, có tiếng Việt). Phiếu cơ hội nhúng với
          input_type="search_document" (Embed 5 Pro), phiếu tìm của khách với input_type="search_query" (Embed 5 Fast);
          hai mô hình cùng không gian vector. Khoá Trial miễn phí dùng được cả hai, giới hạn 1.000 lần gọi/tháng —
          số lần gọi được đếm trong bảng api_usage (services/usage.py). Lỗi API → EmbeddingError (không trộn mô hình).
  hash    không có khoá (dev/test): vector băm đặc trưng (từ đơn, cụm 2 từ, n-gram ký tự) đã bỏ dấu tiếng Việt
          + nhãn "khái niệm" cho thuật ngữ thương mại đồng nghĩa (carton ≈ thùng giấy ≈ bao bì).
Vector 1024 chiều đã chuẩn hoá L2, lưu cột pgvector (PostgreSQL) hoặc JSON (SQLite khi test); cosine = tích vô hướng.
"""

import logging
import math
import re
import unicodedata
import zlib

import httpx

from app.config import Settings

log = logging.getLogger("leadscan.embedding")

EMBED_DIM = 1024  # số chiều cột pgvector (Cohere output_dimension = 1024; vector hash cũng 1024)
HASH_DIM = EMBED_DIM
HASH_MODEL = "hash-v2-1024"
COHERE_BATCH = 96  # Cohere nhận tối đa 96 văn bản mỗi lần gọi
MAX_CHARS = 8000

_STOP = set(
    """va la cua cho cac nhung mot nhieu co khong can cung voi tai trong tu den khi neu ma de duoc se da dang
    nay do nhu ve theo tren duoi sau truoc rat hay hoac ra vao len xuong minh toi chung ban cong ty doanh nghiep
    the and for with from that this are our you your have has will can all any per each need needs looking
    tim kiem nhu cau muon mua ban cung cap san pham khach hang don hang thang nam""".split()
)

# Thuật ngữ (đã bỏ dấu) → nhãn khái niệm: văn bản chứa bất kỳ cụm nào ở danh sách sẽ mang nhãn đó.
_CONCEPTS: dict[str, list[str]] = {
    "bao bi": ["carton", "thung giay", "hop giay", "bao pp", "pp det", "fibc", "bao jumbo", "bao dua", "mang pe", "packaging", "carton box", "pallet", "tem nhan", "in an"],
    "nhua": ["hat nhua", "pp", "pe", "pvc", "pet", "abs", "plastic", "ep nhua", "phun nhua", "cao su"],
    "det may": ["vai", "soi", "may mac", "garment", "textile", "fabric", "ao quan", "giay da", "footwear", "jacket", "vay ngu", "lua"],
    "thuc pham": ["food", "do uong", "beverage", "gia vi", "banh keo", "sua", "nuoc giai khat"],
    "nong san": ["gao", "ca phe", "coffee", "tieu", "dieu", "cashew", "hat dieu", "thuy san", "tom", "ca tra", "trai cay", "rau qua", "agriculture", "rice", "seafood", "phan bon", "fertilizer", "thuc an chan nuoi", "feed"],
    "dien tu": ["linh kien", "pcb", "mach in", "electronics", "semiconductor", "ban dan", "cap dien", "iot"],
    "co khi": ["may moc", "machinery", "gia cong", "cnc", "khuon", "mold", "thiet bi", "phu tung", "kim loai", "thep", "inox"],
    "hoa chat": ["chemical", "dung moi", "son", "phu gia", "vat tu"],
    "xay dung": ["gach", "xi mang", "cement", "vat lieu xay dung", "construction", "noi that", "furniture", "go", "wood", "du an", "goi thau"],
    "logistics": ["van tai", "van chuyen", "freight", "shipping", "kho van", "forwarder", "container", "hai quan", "giao nhan"],
    "nhap khau": ["importer", "import", "nha nhap khau", "buyer", "rfq", "dat hang", "hoi hang", "inquiry", "quote", "bao gia"],
    "xuat khau": ["exporter", "export", "fob", "cif", "nha xuat khau"],
    "chau phi": ["africa", "nigeria", "ghana", "kenya", "ai cap", "egypt"],
    "dong nam a": ["asean", "thai lan", "indonesia", "malaysia", "philippines", "singapore", "campuchia", "lao"],
    "chau au": ["europe", "eu", "duc", "germany", "phap", "italy", "tay ban nha", "ha lan"],
    "bac my": ["usa", "my", "united states", "canada", "walmart"],
    "trung quoc": ["china", "trung hoa", "dai luc"],
    "nang luong": ["dien mat troi", "solar", "pin", "battery", "dien gio", "energy", "luoi dien"],
    "cong nghe": ["phan mem", "software", "it", "ai", "cloud", "chuyen doi so", "erp"],
}
_REV: dict[str, str] = {}
for _concept, _terms in _CONCEPTS.items():
    _REV[_concept] = _concept
    for _t in _terms:
        _REV[_t] = _concept


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt, ký tự lạ → khoảng trắng."""
    t = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def tokens(text: str, keep_stop: bool = False) -> list[str]:
    out = []
    for w in fold(text).split():
        if len(w) < 2 and not w.isdigit():
            continue
        if not keep_stop and w in _STOP:
            continue
        out.append(w)
    return out


def vtext(text: str) -> str:
    """Chữ thường GIỮ dấu tiếng Việt (NFC), ký tự lạ → khoảng trắng — để phân biệt "giày"/"giấy", "may"/"máy"."""
    t = unicodedata.normalize("NFC", (text or "").lower())
    return re.sub(r"[\W_]+", " ", t).strip()


def vtokens(text: str, keep_stop: bool = False) -> list[str]:
    """Như tokens() nhưng giữ dấu."""
    out = []
    for w in vtext(text).split():
        f = fold(w)
        if len(f) < 2 and not f.isdigit():
            continue
        if not keep_stop and f in _STOP:
            continue
        out.append(w)
    return out


def has_marks(word: str) -> bool:
    """Từ (đã vtext) có dấu tiếng Việt không — khách gõ không dấu thì so sau khi bỏ dấu."""
    return fold(word) != word


def concepts(text: str) -> set[str]:
    """Các nhãn khái niệm xuất hiện trong văn bản (so khớp cụm đã bỏ dấu, theo ranh giới từ)."""
    f = f" {fold(text)} "
    return {c for term, c in _REV.items() if f" {term} " in f}


def _features(text: str) -> dict[str, float]:
    toks = tokens(text)
    feats: dict[str, float] = {}

    def add(key: str, w: float) -> None:
        feats[key] = feats.get(key, 0.0) + w

    for t in toks:
        add("u:" + t, 1.0)
        if len(t) >= 5:  # n-gram ký tự giúp khớp biến thể (carton/cartons, dệt/dệt may)
            for i in range(len(t) - 2):
                add("c:" + t[i : i + 3], 0.15)
    for a, b in zip(toks, toks[1:]):
        add(f"b:{a} {b}", 1.0)
    for c in concepts(text):
        add("k:" + c, 2.5)  # khái niệm trọng số cao: cầu nối ngữ nghĩa giữa hai cách diễn đạt
    return feats


def embed_hash(text: str) -> list[float]:
    vec = [0.0] * HASH_DIM
    for key, w in _features(text).items():
        h = zlib.crc32(key.encode("utf-8"))
        sign = 1.0 if (h >> 31) & 1 else -1.0
        vec[h % HASH_DIM] += sign * (1.0 + math.log(w) if w > 1 else w)  # tf dưới tuyến tính
    norm = math.sqrt(sum(x * x for x in vec))
    return [round(x / norm, 5) for x in vec] if norm else vec


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


class EmbeddingError(RuntimeError):
    """Không lấy được vector từ Cohere.

    retryable=True  : lỗi tạm (mạng, 429 quá tần suất, 5xx) → việc nền thử lại sau.
    retryable=False : thử lại vô ích (sai khoá, hết hạn mức tháng của khoá Trial, yêu cầu sai) → so khớp không dùng embedding.
    """

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def current_model(cfg: Settings) -> str:
    """Nhãn "không gian vector": chỉ so sánh vector cùng nhãn."""
    if cfg.cohere_api_key:
        return f"cohere:{cfg.cohere_doc_model}+{cfg.cohere_query_model}@{EMBED_DIM}"
    return HASH_MODEL


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


def _cohere(cfg: Settings, texts: list[str], input_type: str, model: str) -> list[list[float]]:
    from app.services import usage

    out: list[list[float]] = []
    for i in range(0, len(texts), COHERE_BATCH):  # mỗi lần gọi tối đa 96 văn bản → tiết kiệm lượt gọi của khoá Trial
        batch = texts[i : i + COHERE_BATCH]
        if not usage.reserve_call("cohere", cfg.cohere_monthly_limit):
            raise EmbeddingError(f"Đã dùng hết {cfg.cohere_monthly_limit} lần gọi Cohere của tháng này", retryable=False)
        try:
            r = httpx.post(
                cfg.cohere_embed_url,
                headers={"Authorization": f"Bearer {cfg.cohere_api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "input_type": input_type,
                    "texts": batch,
                    "embedding_types": ["float"],
                    "output_dimension": EMBED_DIM,
                    "truncate": "END",
                },
                timeout=60,
            )
        except httpx.HTTPError as e:
            raise EmbeddingError(f"Không kết nối được Cohere: {e}") from e
        if r.status_code >= 400:
            # 429 quá tần suất & 5xx: thử lại được. 400/401/402/403/404...: sai khoá, hết hạn mức, sai model → không thử lại.
            retry = r.status_code == 429 or r.status_code >= 500
            raise EmbeddingError(f"Cohere trả lỗi {r.status_code}: {r.text[:200]}", retryable=retry)
        try:
            vecs = r.json()["embeddings"]["float"]
        except (KeyError, ValueError, TypeError) as e:
            raise EmbeddingError(f"Cohere trả dữ liệu không đúng định dạng: {e}", retryable=False) from e
        if len(vecs) != len(batch) or any(len(v) != EMBED_DIM for v in vecs):
            raise EmbeddingError(f"Cohere trả về {len(vecs)} vector, cần {len(batch)} vector {EMBED_DIM} chiều", retryable=False)
        out += [_normalize([float(x) for x in v]) for v in vecs]
    return out


def _clean(texts: list[str]) -> list[str]:
    return [((t or "").strip()[:MAX_CHARS] or "-") for t in texts]


def embed_documents(cfg: Settings, texts: list[str]) -> tuple[list[list[float]], str]:
    """Vector cho phiếu cơ hội (tài liệu được tìm). Trả về (các vector, nhãn mô hình)."""
    texts = _clean(texts)
    if cfg.cohere_api_key:
        return _cohere(cfg, texts, "search_document", cfg.cohere_doc_model), current_model(cfg)
    return [embed_hash(t) for t in texts], HASH_MODEL


def embed_queries(cfg: Settings, texts: list[str]) -> tuple[list[list[float]], str]:
    """Vector cho phiếu tìm cơ hội của khách (câu truy vấn)."""
    texts = _clean(texts)
    if cfg.cohere_api_key:
        return _cohere(cfg, texts, "search_query", cfg.cohere_query_model), current_model(cfg)
    return [embed_hash(t) for t in texts], HASH_MODEL
