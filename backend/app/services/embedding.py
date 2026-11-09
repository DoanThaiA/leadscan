"""Embedding văn bản để so khớp ngữ nghĩa giữa yêu cầu của khách và mô tả phiếu cơ hội.

Hai chế độ (cấu hình LEADSCAN_EMBED_PROVIDER):
  hash    mặc định, chạy tại chỗ, không cần khoá API. Vector băm đặc trưng (từ đơn, cụm 2 từ, n-gram ký tự)
          đã bỏ dấu tiếng Việt + gắn nhãn "khái niệm" cho thuật ngữ thương mại đồng nghĩa (carton ≈ thùng giấy ≈ bao bì).
  openai  gọi API /embeddings tương thích OpenAI (mô hình ngữ nghĩa thật). Lỗi mạng → rơi về "hash".
Vector là list[float] đã chuẩn hoá L2, lưu JSON; cosine = tích vô hướng.
"""

import logging
import math
import re
import unicodedata
import zlib

import httpx

from app.config import Settings

log = logging.getLogger("leadscan.embedding")

HASH_DIM = 512
HASH_MODEL = "hash-v1-512"

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


def current_model(cfg: Settings) -> str:
    return f"openai:{cfg.embed_model}" if cfg.embed_provider == "openai" and cfg.embed_api_key else HASH_MODEL


def embed(cfg: Settings, text: str) -> tuple[list[float], str]:
    """Trả về (vector, tên mô hình). Lỗi API → vector "hash" kèm đúng nhãn hash để không so lẫn mô hình."""
    text = (text or "").strip()[:8000]
    if current_model(cfg) != HASH_MODEL:
        try:
            r = httpx.post(
                cfg.embed_url.rstrip("/") + "/embeddings",
                headers={"Authorization": f"Bearer {cfg.embed_api_key}"},
                json={"model": cfg.embed_model, "input": text or " "},
                timeout=20,
            )
            r.raise_for_status()
            vec = [float(x) for x in r.json()["data"][0]["embedding"]]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            return [round(x / norm, 6) for x in vec], current_model(cfg)
        except Exception as e:  # noqa: BLE001 — lỗi mạng/khoá không được làm hỏng việc gửi yêu cầu
            log.warning("Embedding API lỗi, dùng hash: %s", e)
    return embed_hash(text), HASH_MODEL
