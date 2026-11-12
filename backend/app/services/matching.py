"""So khớp phiếu cơ hội ↔ phiếu tìm cơ hội của khách, chấm điểm RIÊNG cho từng doanh nghiệp.

Luồng:
  1. Admin thêm phiếu cơ hội — phiếu KHÔNG mang điểm.
  2. Khách gửi phiếu tìm cơ hội (tiêu chí + mô tả). Hệ thống so với mọi phiếu cơ hội đang bán
     (và ngược lại: phiếu cơ hội mới mở bán được so với mọi phiếu tìm cơ hội đã có).
  3. Mỗi cặp được chấm điểm "hybrid":
       - tiêu chí   : ngành / khu vực / loại cơ hội khớp tiêu chí đã chọn (chỉ tính nhóm khách có chọn)
       - từ khoá    : mô tả của khách bao phủ bao nhiêu từ/cụm từ trong phiếu cơ hội
       - ngữ nghĩa  : cosine giữa embedding mô tả của khách và embedding mô tả phiếu cơ hội
     khớp yêu cầu = 0.40·tiêu chí + 0.35·ngữ nghĩa + 0.25·từ khoá  (khách không chọn tiêu chí: 0.60·ngữ nghĩa + 0.40·từ khoá)
     điểm tổng    = 0.75·khớp yêu cầu + 0.10·cấp thiết (hạn chót) + 0.15·tin cậy (nguồn, enrich, đầu mối)
  4. Cặp đạt ngưỡng "khớp yêu cầu" (và điểm tối thiểu khách chọn) được ghi vào:
       SearchRequestMatch  cơ hội phù hợp của từng phiếu tìm cơ hội
       UserOpportunity     "Tất cả cơ hội" của doanh nghiệp — gộp từ mọi phiếu, mỗi cơ hội 1 dòng, điểm cao nhất
     và tự thêm vào "Kho của tôi" (lần đầu tiên cơ hội xuất hiện với doanh nghiệp).
     Phiếu tìm "tìm kiếm liên tục": cơ hội MỚI mở bán / vừa sửa mà khớp phiếu lần đầu → MemberNotification
     (báo trong cổng + email gộp), mỗi cặp (phiếu tìm, cơ hội) báo đúng 1 lần.
  5. Giá phiếu thành viên phải trả: price_of() = giá cơ bản × hệ số điểm × cấp thiết × đủ thông tin × giá trị đơn —
     tham số chỉnh ở trang quản trị (services/pricing.py).

Kỹ thuật:
  - Embedding: Cohere (services/embedding.py), lưu cột pgvector vector(1024). Chỉ gọi lại API khi văn bản đổi (sha1).
  - Ứng viên: PostgreSQL lấy N phiếu gần nhất bằng toán tử cosine `<=>` của pgvector (cfg.match_candidates),
    rồi chấm hybrid từng cặp. SQLite (test) tính cosine bằng Python.
  - Chạy nền bằng Celery (worker.match_request_task / match_opportunity_task); "Tất cả cơ hội" của doanh nghiệp
    chỉ có dòng khi doanh nghiệp đã gửi phiếu tìm cơ hội và có cơ hội đạt ngưỡng.
  - Dự phòng (semantic=False): khi không lấy được embedding (hết 1.000 lượt/tháng của khoá Trial, sai khoá, Cohere lỗi)
    vẫn so khớp bằng tiêu chí + từ khoá: khớp yêu cầu = 0.60·tiêu chí + 0.40·từ khoá (không chọn tiêu chí: chỉ từ khoá).
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import Float, bindparam, or_, select, text
from sqlalchemy.orm import Session, selectinload, undefer

from app.db import EmbeddingVector
from app.services import pricing

from app.config import Settings, get_settings
from app.models import MemberNotification, Opportunity, Purchase, SavedOpportunity, SearchRequest, SearchRequestMatch, UserOpportunity
from app.services import embedding as emb
from app.services import products as prod

W_CRITERIA, W_SEMANTIC, W_KEYWORD = 0.40, 0.35, 0.25
W_SEMANTIC_ONLY, W_KEYWORD_ONLY = 0.60, 0.40  # khách không chọn tiêu chí nào
W_CRITERIA_NOSEM, W_KEYWORD_NOSEM = 0.60, 0.40  # dự phòng không có embedding
W_FIT, W_URGENCY, W_TRUST = 0.75, 0.10, 0.15
CRITERIA_WEIGHTS = {"industries": 40, "regions": 30, "sources": 20}
HASH_COS_RANGE = (0.03, 0.40)  # vector hash: cosine ≤ 0.03 → 0 điểm ngữ nghĩa, ≥ 0.40 → 100 điểm

TRUST_BY_SOURCE = {
    "Nguồn chính thống": 90,
    "Dự án & gói thầu": 85,
    "Nhà máy / FDI mới": 80,
    "Hội chợ & triển lãm": 75,
    "Kết nối giao thương": 75,
    "App đăng mua": 75,
    "Email hỏi hàng": 70,
    "Website doanh nghiệp": 70,
    "Mạng xã hội & nhóm chat": 55,
}
DOMESTIC_REGIONS = {"mien bac", "mien trung", "mien nam"}


_UNITS = [("ty", 1_000_000_000), ("ti", 1_000_000_000), ("billion", 1_000_000_000), ("trieu", 1_000_000), ("tr", 1_000_000),
          ("million", 1_000_000), ("nghin", 1_000), ("ngan", 1_000), ("k", 1_000)]
_FX = {"usd": 25_000, "$": 25_000, "eur": 27_000, "€": 27_000}


def parse_value_vnd(text_: str) -> int:
    """Giá trị ước tính dạng chữ → VNĐ (khoảng thì lấy số lớn nhất). "2–3 tỷ" → 3 tỷ; "500 triệu"; "120.000 USD"; "$120k". Không đọc được → 0."""
    raw = (text_ or "").lower().replace(",", ".")
    fx = next((r for k, r in _FX.items() if k in raw), 1)
    best = 0
    for m in re.finditer(r"(\d+(?:\.\d+)*)\s*([^\W\d_]*)", raw):
        num, unit = m.group(1), emb.fold(m.group(2))
        parts = num.split(".")
        # "1.200.000" / "120.000" là phân cách nghìn; "1.5" là số thập phân
        val = float(num.replace(".", "")) if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3) else float(num)
        mult = next((v for k, v in _UNITS if unit == k), 1)
        best = max(best, int(val * mult * fx))
    return best


def info_completeness(o: Opportunity) -> float:
    """Tỷ lệ thông tin phiếu có đủ (0–1): bên mua, đầu mối (tên, chức vụ, SĐT, email), số lượng, giá trị, hạn chót, nguồn, chi tiết."""
    cs = o.contacts or []
    checks = [
        bool(o.buyer_name), any(c.full_name for c in cs), any(c.title for c in cs), any(c.phone for c in cs), any(c.email for c in cs),
        bool(o.scale), bool(o.estimated_value), o.deadline is not None, bool(o.source_url), len(o.detail or "") >= 100,
    ]
    return sum(checks) / len(checks)


def price_for(base_price: int, score: int, urgency: int = 50, info: float = 0.0, value_vnd: int = 0) -> int:
    """Giá phiếu theo công thức đang áp dụng (tham số chỉnh trên trang quản trị — services/pricing.py)."""
    return pricing.price_for(base_price, score, urgency, info, value_vnd)


def price_of(o: Opportunity, score: int, urgency: int) -> int:
    """Giá phiếu o cho 1 doanh nghiệp có điểm score (độ cấp thiết urgency) — dùng ở mọi nơi hiển thị & khi mua."""
    return price_for(o.price, score, urgency, info_completeness(o), parse_value_vnd(o.estimated_value))


# ------------------------------------------------------------------ chuẩn bị văn bản


def opp_text(o: Opportunity) -> str:
    """Văn bản dùng để so khớp (không gồm tên bên mua & đầu mối)."""
    parts = [o.title, o.summary, o.industry, o.scale, o.province, o.region, o.source_type, (o.detail or "")[:2000]]
    return ". ".join(p for p in parts if p)


def request_text(r: SearchRequest) -> str:
    c = r.criteria or {}
    extra = [*c.get("industries", []), *c.get("regions", []), *c.get("sizes", []), *c.get("sources", [])]
    return ". ".join(p for p in [r.note, " ".join(extra)] if p)


def _sha(model: str, text_: str) -> str:
    return hashlib.sha1(f"{model}\n{text_}".encode()).hexdigest()


def sync_opp_embeddings(db: Session, cfg: Settings, opps: list[Opportunity], force: bool = False) -> int:
    """Nhúng (theo lô) các phiếu cơ hội có văn bản mới/đổi hoặc khác mô hình. Trả về số phiếu đã nhúng."""
    model = emb.current_model(cfg)
    todo = []
    for o in opps:
        t = opp_text(o)
        if force or o.embedding_model != model or o.embedding_sha != _sha(model, t):
            todo.append((o, t))
    if todo:
        vecs, used = emb.embed_documents(cfg, [t for _, t in todo])
        for (o, t), v in zip(todo, vecs):
            o.embedding, o.embedding_model, o.embedding_sha = v, used, _sha(used, t)
        db.flush()
    return len(todo)


def sync_request_embeddings(db: Session, cfg: Settings, reqs: list[SearchRequest], force: bool = False) -> int:
    model = emb.current_model(cfg)
    todo = []
    for r in reqs:
        t = request_text(r)
        if force or r.embedding_model != model or r.embedding_sha != _sha(model, t):
            todo.append((r, t))
    if todo:
        vecs, used = emb.embed_queries(cfg, [t for _, t in todo])
        for (r, t), v in zip(todo, vecs):
            r.embedding, r.embedding_model, r.embedding_sha = v, used, _sha(used, t)
        db.flush()
    return len(todo)


def _catch_up(db: Session, cfg: Settings) -> None:
    """Phiếu chưa có vector của mô hình hiện tại (vd. vừa thêm COHERE_API_KEY) → nhúng bù trước khi tìm."""
    model = emb.current_model(cfg)
    opps = db.scalars(select(Opportunity).where(Opportunity.status == "published", Opportunity.embedding_model != model)).unique().all()
    sync_opp_embeddings(db, cfg, list(opps))
    reqs = db.scalars(select(SearchRequest).where(SearchRequest.status != "rejected", SearchRequest.embedding_model != model)).unique().all()
    sync_request_embeddings(db, cfg, list(reqs))


def _is_pg(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _nearest_opps(db: Session, cfg: Settings, req: SearchRequest, today: date) -> list[tuple[Opportunity, float]]:
    """Phiếu cơ hội đang bán gần nhất với phiếu tìm (cosine), tối đa cfg.match_candidates."""
    base = (
        select(Opportunity)
        .options(selectinload(Opportunity.contacts))
        .where(
            Opportunity.status == "published",
            or_(Opportunity.deadline.is_(None), Opportunity.deadline >= today),
            Opportunity.embedding_model == req.embedding_model,
            Opportunity.embedding.is_not(None),
        )
    )
    if _is_pg(db):
        dist = Opportunity.embedding.op("<=>", return_type=Float)(bindparam("qv", req.embedding, type_=EmbeddingVector(emb.EMBED_DIM)))
        rows = db.execute(base.add_columns((1 - dist).label("sim")).order_by(dist).limit(cfg.match_candidates)).unique().all()
        return [(o, float(sim)) for o, sim in rows]
    opps = db.scalars(base.options(undefer(Opportunity.embedding))).unique().all()
    scored = sorted(((o, emb.cosine(req.embedding, o.embedding)) for o in opps), key=lambda x: -x[1])
    return scored[: cfg.match_candidates]


def _all_opps(db: Session, today: date) -> list[tuple[Opportunity, None]]:
    """Dự phòng không có embedding: mọi phiếu cơ hội đang bán còn hạn."""
    rows = db.scalars(
        select(Opportunity)
        .options(selectinload(Opportunity.contacts))
        .where(Opportunity.status == "published", or_(Opportunity.deadline.is_(None), Opportunity.deadline >= today))
    ).unique().all()
    return [(o, None) for o in rows]


def _all_requests(db: Session) -> list[tuple[SearchRequest, None]]:
    return [(r, None) for r in db.scalars(select(SearchRequest).where(SearchRequest.status != "rejected")).unique().all()]


def _nearest_requests(db: Session, cfg: Settings, opp: Opportunity) -> list[tuple[SearchRequest, float]]:
    """Phiếu tìm cơ hội (chưa bị từ chối) gần nhất với phiếu cơ hội."""
    base = select(SearchRequest).where(
        SearchRequest.status != "rejected",
        SearchRequest.embedding_model == opp.embedding_model,
        SearchRequest.embedding.is_not(None),
    )
    if _is_pg(db):
        dist = SearchRequest.embedding.op("<=>", return_type=Float)(bindparam("ov", opp.embedding, type_=EmbeddingVector(emb.EMBED_DIM)))
        rows = db.execute(base.add_columns((1 - dist).label("sim")).order_by(dist).limit(cfg.match_candidates)).unique().all()
        return [(r, float(sim)) for r, sim in rows]
    reqs = db.scalars(base.options(undefer(SearchRequest.embedding))).unique().all()
    scored = sorted(((r, emb.cosine(opp.embedding, r.embedding)) for r in reqs), key=lambda x: -x[1])
    return scored[: cfg.match_candidates]


# ------------------------------------------------------------------ chấm điểm


@dataclass
class Scored:
    score: int
    fit: int
    urgency: int
    trust: int
    reasons: list[str] = field(default_factory=list)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def accented(text: str) -> bool:
    """Văn bản gõ có dấu tiếng Việt (khi đó mọi từ trong nó, kể cả "bao", "may", được hiểu đúng như đã viết)."""
    return emb.has_marks(emb.vtext(text))


class WordBag:
    """Các từ của 1 văn bản để so từ khoá. Hai văn bản cùng gõ có dấu → từ phải giống hệt cả dấu
    ("giày" ≠ "giấy", "may" ≠ "máy", "bao" ≠ "bảo"); một bên gõ không dấu → so sau khi bỏ dấu
    (khách gõ "hop carton" vẫn khớp "hộp carton")."""

    def __init__(self, text: str):
        words = emb.vtokens(text, keep_stop=True)
        self.accented = accented(text)
        self.exact = set(words)
        self.folded = {emb.fold(w) for w in words}
        self.vtext = f" {' '.join(words)} "
        self.ftext = f" {emb.fold(text)} "

    def has(self, w: str, strict: bool) -> bool:
        """strict = văn bản chứa từ w được gõ có dấu."""
        return w in self.exact if strict and self.accented else emb.fold(w) in self.folded

    def has_phrase(self, p: str, strict: bool) -> bool:
        return f" {p} " in self.vtext if strict and self.accented else f" {emb.fold(p)} " in self.ftext


def _same_or_within(a: str, b: str) -> bool:
    """Tên ngành a, b trùng / chứa nhau (có dấu thì so có dấu)."""
    if emb.has_marks(emb.vtext(a)) and emb.has_marks(emb.vtext(b)):
        x, y = emb.vtext(a), emb.vtext(b)
    else:
        x, y = emb.fold(a), emb.fold(b)
    return bool(x and y) and (x == y or f" {x} " in f" {y} " or f" {y} " in f" {x} ")


def _industry_score(wanted: list[str], o: Opportunity, bag: WordBag) -> tuple[float, str]:
    best, hit = 0.0, ""
    ind = WordBag(o.industry)
    for w in wanted:
        if not emb.fold(w):
            continue
        wt, strict = set(emb.vtokens(w)), accented(w)
        ratio = sum(bag.has(t, strict) for t in wt) / len(wt) if wt else 0.0
        if o.industry and _same_or_within(w, o.industry):
            s = 100.0
        elif ratio >= 0.5 and any(ind.has(t, strict) for t in wt):
            s = 80.0
        elif bag.has_phrase(emb.vtext(w), strict) or ratio >= 0.5:
            s = 55.0  # ngành khách chọn xuất hiện trong nội dung phiếu dù cột "ngành" khác
        elif emb.concepts(w) & emb.concepts(o.industry + " " + o.title):
            s = 45.0  # cùng khái niệm (vd. "Bao bì & in ấn" ~ "thùng carton")
        else:
            s = 0.0
        if s > best:
            best, hit = s, w
    return best, hit


def _region_score(wanted: list[str], o: Opportunity) -> tuple[float, str]:
    prov_name = prod.canonical_province(o.province or "")
    prov, reg = emb.fold(prov_name), emb.fold(o.region or prod.province_region(prov_name))
    best, hit = 0.0, ""
    for w in wanted:
        wf = emb.fold(w)
        if not wf:
            continue
        if wf == "toan quoc":
            s = 100.0 if reg != "quoc te" else 60.0
        elif wf == "quoc te":
            s = 100.0 if reg == "quoc te" or any(k in prov for k in ("toan cau", "quoc te")) else 0.0
        elif wf in DOMESTIC_REGIONS:
            s = 100.0 if reg == wf else (70.0 if reg == "toan quoc" else 0.0)
        else:  # tỉnh/thành ("TP.HCM" = "Hồ Chí Minh" = "Sài Gòn")
            wf = emb.fold(prod.canonical_province(w))
            w_reg = emb.fold(prod.province_region(w))
            if prov and (wf in prov or prov in wf):
                s = 100.0
            elif w_reg and reg == w_reg:
                s = 50.0  # tỉnh lân cận cùng miền (khách cần giao tại TP.HCM, cơ hội ở Bình Dương)
            elif reg == "toan quoc":
                s = 35.0
            else:
                s = 0.0
        if s > best:
            best, hit = s, w
    return best, hit


def _combined_region(q: "RequestCtx", o: Opportunity) -> tuple[float | None, str, bool]:
    """Điểm khu vực từ tiêu chí đã chọn + địa danh khách ghi trong mô tả. Trả về (điểm, khu vực khớp, khớp theo mô tả).

    Mô tả ghi rõ địa điểm (vd. "giao hàng tại TP.HCM") được ƯU TIÊN hơn ô tiêu chí cố định (vd. "Quốc tế"):
    cơ hội đúng địa điểm trong mô tả được đủ điểm, cơ hội chỉ khớp ô tiêu chí được một nửa."""
    chips = q.criteria.get("regions") or []
    if not q.places:
        return (_region_score(chips, o)[0], _region_score(chips, o)[1], False) if chips else (None, "", False)
    ns, nhit = _region_score(q.places, o)
    cs, chit = _region_score(chips, o) if chips else (0.0, "")
    if ns >= cs / 2:
        return ns, nhit, True
    return cs / 2, chit, False


def _criteria_score(q: "RequestCtx", o: Opportunity, bag: WordBag) -> tuple[float | None, list[str]]:
    c = q.criteria
    total = weight = 0.0
    reasons: list[str] = []
    if c.get("industries"):
        s, hit = _industry_score(c["industries"], o, bag)
        total, weight = total + s * CRITERIA_WEIGHTS["industries"], weight + CRITERIA_WEIGHTS["industries"]
        if s >= 45:
            reasons.append(f"Ngành hàng khớp: {hit}")
    s, hit, by_note = _combined_region(q, o)
    if s is not None:
        total, weight = total + s * CRITERIA_WEIGHTS["regions"], weight + CRITERIA_WEIGHTS["regions"]
        if s >= 60:
            reasons.append(f"Khu vực khớp{' (theo mô tả)' if by_note else ''}: {hit}")
        elif s >= 35 and by_note:
            reasons.append(f"Gần khu vực bạn cần: {hit}")
    if c.get("sources"):
        want = {emb.fold(x) for x in c["sources"]}
        s = 100.0 if emb.fold(o.source_type) in want else 0.0
        total, weight = total + s * CRITERIA_WEIGHTS["sources"], weight + CRITERIA_WEIGHTS["sources"]
        if s:
            reasons.append(f"Loại cơ hội khớp: {o.source_type}")
    return (total / weight if weight else None), reasons


def _keyword_score(q_words: list[str], q_bigrams: set[str], bag: WordBag, strict: bool) -> tuple[float, list[str]]:
    """Độ bao phủ từ khoá của yêu cầu trong phiếu; từ dài (đặc trưng hơn) nặng hơn, cụm 2 từ nặng gấp đôi.

    So có phân biệt dấu (WordBag) để "may" (may mặc) không khớp "máy", "gia công" không khớp "giá"."""
    if not q_words:
        return 0.0, []
    uniq = list(dict.fromkeys(q_words))
    total = sum(1 + min(len(emb.fold(t)), 8) / 8 for t in uniq)
    got_w, hits = 0.0, []
    for t in uniq:
        if bag.has(t, strict):
            got_w += 1 + min(len(emb.fold(t)), 8) / 8
            hits.append(t)
    for bg in q_bigrams:
        if bag.has_phrase(bg, strict):
            got_w += 2
            total += 2
    need = min(total, 6.0)  # chỉ cần khớp ~6 đơn vị là đủ điểm tối đa — mô tả dài không bị phạt
    return _clamp(100 * got_w / need if need else 0.0), hits


def urgency_of(o: Opportunity, today: date) -> int:
    """Độ cấp thiết theo hạn chót (tính tại thời điểm gọi — giá phiếu tăng dần khi hạn chót tới gần)."""
    return urgency_from_days((o.deadline - today).days if o.deadline else None)


def urgency_from_days(days: int | None) -> int:
    """Số ngày còn tới hạn chót → độ cấp thiết (None = không có hạn chót; âm = đã quá hạn)."""
    if days is None:
        return 50
    if days < 0:
        return 0
    return 100 if days <= 3 else 90 if days <= 7 else 80 if days <= 14 else 65 if days <= 30 else 50


def _trust(o: Opportunity) -> int:
    t = TRUST_BY_SOURCE.get(o.source_type, 60) + min(2, o.enrich_round) * 5
    t += 5 if o.contacts else 0
    t += 5 if o.source_url else 0
    return int(_clamp(t))


class RequestCtx:
    """Dữ liệu đã tính sẵn của 1 phiếu tìm cơ hội để chấm với nhiều phiếu cơ hội."""

    def __init__(self, r: SearchRequest):
        self.r = r
        self.criteria = r.criteria or {}
        self.q_words = emb.vtokens(r.note)  # giữ dấu: hiển thị lý do đúng chữ khách viết, so có phân biệt dấu
        self.q_bigrams = {f"{a} {b}" for a, b in zip(self.q_words, self.q_words[1:])}
        self.accented = accented(r.note or "")
        self.min_score = int(self.criteria.get("min_score") or 0)
        self.has_criteria = any(self.criteria.get(k) for k in CRITERIA_WEIGHTS)
        self.products = prod.find_products(r.note or "")  # sản phẩm cụ thể khách cần (túi giữ nhiệt…)
        self.places = prod.find_places(r.note or "")  # địa điểm khách ghi trong mô tả (TP.HCM, miền Nam…)


def cos_range(cfg: Settings, model: str) -> tuple[float, float]:
    """Khoảng cosine quy ra 0–100 điểm ngữ nghĩa; mỗi mô hình embedding có phân bố cosine khác nhau."""
    return HASH_COS_RANGE if model.startswith("hash") else (cfg.cohere_cos_low, cfg.cohere_cos_high)


def score_pair(q: RequestCtx, o: Opportunity, cos: float | None, cfg: Settings, today: date | None = None) -> Scored:
    """Chấm 1 cặp (phiếu tìm, phiếu cơ hội). cos = cosine embedding (pgvector đã tính sẵn); None = không có embedding."""
    today = today or date.today()
    bag = WordBag(opp_text(o))

    kw, hits = _keyword_score(q.q_words, q.q_bigrams, bag, q.accented)
    sem = 0.0
    if cos is not None:
        lo, hi = cos_range(cfg, o.embedding_model)
        sem = _clamp(100 * (cos - lo) / (hi - lo))

    reasons: list[str] = []
    crit, crit_reasons = _criteria_score(q, o, bag)
    if cos is None:  # dự phòng: chỉ tiêu chí + từ khoá
        fit = kw if crit is None else W_CRITERIA_NOSEM * crit + W_KEYWORD_NOSEM * kw
    elif crit is None:
        fit = W_SEMANTIC_ONLY * sem + W_KEYWORD_ONLY * kw
    else:
        fit = W_CRITERIA * crit + W_SEMANTIC * sem + W_KEYWORD * kw
    if crit is not None:
        if _combined_region(q, o)[0] == 0:
            fit *= 0.75 if q.places else 0.8  # sai khu vực khách yêu cầu → trừ điểm (ghi rõ trong mô tả thì trừ nặng hơn)

    # Đối chiếu SẢN PHẨM cụ thể: cùng ngành nhưng khác sản phẩm thì không được điểm cao
    # chỉ xét nội dung cơ hội — KHÔNG xét cột ngành (ngành rộng như "Bao bì & in ấn" chính là nguyên nhân khớp sai)
    rel, rel_keys = prod.product_relation(q.products, ". ".join(p for p in (o.title, o.summary, o.scale, (o.detail or "")[:2000]) if p))
    if rel == "direct":
        fit = 0.6 * fit + 40
        reasons.append("Đúng sản phẩm: " + ", ".join(prod.product_names(rel_keys)))
    elif rel == "equivalent":
        fit = min(0.6 * fit + 24, 70)
        reasons.append(f"Sản phẩm tương đương: {', '.join(prod.product_names(rel_keys))} (bạn tìm {', '.join(prod.product_names(q.products))})")
    elif rel == "unknown":
        fit = min(fit, 50)
        reasons.append("Chưa xác định được sản phẩm cụ thể trong cơ hội")
    elif rel == "unrelated":
        fit = min(fit, 20)  # dưới ngưỡng khớp → không đưa vào kết quả
        reasons.append(f"Khác sản phẩm: {', '.join(prod.product_names(rel_keys))}" if rel_keys else "Không nhắc tới sản phẩm bạn cần")
    if rel != "unrelated" and crit is not None:
        reasons += crit_reasons  # lý do sản phẩm đứng đầu (thẻ cơ hội chỉ hiện 2 lý do đầu)
    shown = [h for h in hits if len(h) > 2]
    if shown:
        reasons.append("Từ khoá trùng: " + ", ".join(shown[:5]))
    if sem >= 60:
        reasons.append("Nội dung gần với mô tả yêu cầu của bạn")
    elif sem >= 35:
        reasons.append("Nội dung có liên quan tới mô tả yêu cầu")

    urgency, trust = urgency_of(o, today), _trust(o)
    fit_i = round(_clamp(fit))
    total = round(W_FIT * fit_i + W_URGENCY * urgency + W_TRUST * trust)
    return Scored(score=int(_clamp(total)), fit=fit_i, urgency=urgency, trust=trust, reasons=reasons)


def is_match(q: RequestCtx, s: Scored, cfg: Settings) -> bool:
    return s.fit >= cfg.match_min_fit and s.score >= q.min_score


# ------------------------------------------------------------------ ghi kết quả


def _matchable(o: Opportunity, today: date) -> bool:
    return o.status == "published" and (o.deadline is None or o.deadline >= today)


def _upsert_request_match(db: Session, req_id: int, opp_id: int, s: Scored, existing: SearchRequestMatch | None) -> None:
    if existing:
        existing.score, existing.score_fit, existing.score_urgency, existing.score_trust, existing.reasons = s.score, s.fit, s.urgency, s.trust, s.reasons
    else:
        db.add(SearchRequestMatch(request_id=req_id, opportunity_id=opp_id, score=s.score, score_fit=s.fit, score_urgency=s.urgency, score_trust=s.trust, reasons=s.reasons))


def _notify_new_match(db: Session, req: SearchRequest, opp: Opportunity, score: int) -> bool:
    """Cơ hội vừa khớp phiếu tìm lần đầu → thông báo cho doanh nghiệp (mỗi cặp 1 lần, không báo lặp khi sửa phiếu)."""
    if req.status != "open":
        return False
    if db.scalar(select(MemberNotification.id).where(MemberNotification.request_id == req.id, MemberNotification.opportunity_id == opp.id)):
        return False
    db.add(MemberNotification(company_id=req.company_id, request_id=req.id, opportunity_id=opp.id, score=score))
    return True


def _lock_company(db: Session, company_id: int) -> None:
    """Hai việc nền cùng ghi "Tất cả cơ hội" của 1 doanh nghiệp thì chạy lần lượt (khoá tới hết giao dịch)."""
    if _is_pg(db):
        db.execute(text("SELECT pg_advisory_xact_lock(4242, :cid)"), {"cid": company_id})


def refresh_company(
    db: Session, company_id: int, opp_ids: set[int], member_user_id: int | None = None, below: dict[int, tuple[Scored, int]] | None = None
) -> int:
    """Gộp các phiếu tìm của doanh nghiệp thành "Tất cả cơ hội": mỗi cơ hội 1 dòng, điểm = điểm cao nhất. Trả về số dòng MỚI.

    below: {opp_id: (điểm, phiếu tìm)} điểm mới nhất DƯỚI ngưỡng — dùng cho cơ hội đã mua nhưng sau khi sửa không còn khớp,
    để điểm hiển thị là điểm hiện tại (điểm lúc mua nằm trong bản lưu của phiếu đã mua)."""
    if not opp_ids:
        return 0
    _lock_company(db, company_id)
    db.flush()
    rows = db.execute(
        select(SearchRequestMatch, SearchRequest.id)
        .join(SearchRequest, SearchRequest.id == SearchRequestMatch.request_id)
        .where(SearchRequest.company_id == company_id, SearchRequestMatch.opportunity_id.in_(opp_ids))
        .order_by(SearchRequestMatch.score.desc(), SearchRequestMatch.id)
    ).all()
    best: dict[int, tuple[SearchRequestMatch, int]] = {}
    for m, rid in rows:
        best.setdefault(m.opportunity_id, (m, rid))  # đã sắp theo điểm giảm dần → dòng đầu là cao nhất
    existing = {u.opportunity_id: u for u in db.scalars(select(UserOpportunity).where(UserOpportunity.company_id == company_id, UserOpportunity.opportunity_id.in_(opp_ids))).unique()}
    bought = set(db.scalars(select(Purchase.opportunity_id).where(Purchase.company_id == company_id, Purchase.opportunity_id.in_(opp_ids))).all())
    saved = set(db.scalars(select(SavedOpportunity.opportunity_id).where(SavedOpportunity.company_id == company_id, SavedOpportunity.opportunity_id.in_(opp_ids))).all())
    new = 0
    for oid in sorted(opp_ids):
        u = existing.get(oid)
        if oid in best:
            m, rid = best[oid]
            if u is None:
                u = UserOpportunity(company_id=company_id, opportunity_id=oid)
                db.add(u)
                new += 1
                if oid not in saved:  # cơ hội phù hợp tự vào kho (lần đầu; khách bỏ khỏi kho thì không tự thêm lại)
                    db.add(SavedOpportunity(company_id=company_id, opportunity_id=oid, member_user_id=member_user_id))
            u.score, u.score_fit, u.score_urgency, u.score_trust, u.reasons, u.best_request_id = m.score, m.score_fit, m.score_urgency, m.score_trust, m.reasons, rid
        elif u is not None and oid not in bought:
            db.delete(u)  # không còn phiếu tìm nào khớp (phiếu bị từ chối, cơ hội sửa nội dung/đóng) — đã mua thì giữ
        elif u is not None and below and oid in below:  # đã mua, nay không còn khớp → cập nhật điểm hiện tại
            sc, rid = below[oid]
            u.score, u.score_fit, u.score_urgency, u.score_trust, u.best_request_id = sc.score, sc.fit, sc.urgency, sc.trust, rid
            u.reasons = ["Cơ hội đã được chỉnh sửa và không còn khớp yêu cầu của bạn", *sc.reasons]
    return new


def match_request(db: Session, req: SearchRequest, cfg: Settings | None = None, semantic: bool = True) -> int:
    """So phiếu tìm cơ hội với các phiếu cơ hội đang bán gần nhất; ghi kết quả. Trả về số cơ hội phù hợp.

    semantic=False: không gọi Cohere, so với mọi phiếu đang bán bằng tiêu chí + từ khoá (dự phòng).
    """
    cfg = cfg or get_settings()
    today = date.today()
    prev = {m.opportunity_id: m for m in db.scalars(select(SearchRequestMatch).where(SearchRequestMatch.request_id == req.id)).unique()}
    touched: set[int] = set(prev)
    matched = 0
    if req.status != "rejected":
        if semantic:
            sync_request_embeddings(db, cfg, [req])  # có thể ném EmbeddingError
            _catch_up(db, cfg)
        q = RequestCtx(req)
        for o, cos in (_nearest_opps(db, cfg, req, today) if semantic else _all_opps(db, today)):
            s = score_pair(q, o, cos, cfg, today)
            if is_match(q, s, cfg):
                _upsert_request_match(db, req.id, o.id, s, prev.pop(o.id, None))
                touched.add(o.id)
                matched += 1
    for stale in prev.values():  # trước khớp, nay không còn
        db.delete(stale)
    refresh_company(db, req.company_id, touched, req.member_user_id)
    db.flush()
    return matched


def match_opportunity(db: Session, opp: Opportunity, cfg: Settings | None = None, semantic: bool = True) -> int:
    """So 1 phiếu cơ hội (mới mở bán / vừa sửa / vừa đóng) với các phiếu tìm cơ hội. Trả về số phiếu tìm khớp.

    Phiếu tìm nào khớp lần đầu → thêm thông báo "cơ hội mới phù hợp" cho doanh nghiệp đó.
    """
    cfg = cfg or get_settings()
    today = date.today()
    prev = {m.request_id: m for m in db.scalars(select(SearchRequestMatch).where(SearchRequestMatch.opportunity_id == opp.id)).unique()}
    by_company: dict[int, int | None] = {}
    below: dict[int, tuple[Scored, int]] = {}  # doanh nghiệp từng khớp, nay dưới ngưỡng: điểm cao nhất hiện tại
    if prev:
        for r in db.scalars(select(SearchRequest).where(SearchRequest.id.in_(list(prev)))).unique():
            by_company[r.company_id] = r.member_user_id
    matched = 0
    if _matchable(opp, today):
        if semantic:
            sync_opp_embeddings(db, cfg, [opp])  # chỉ gọi API khi nội dung đổi; có thể ném EmbeddingError
            _catch_up(db, cfg)
        for r, cos in (_nearest_requests(db, cfg, opp) if semantic else _all_requests(db)):
            q = RequestCtx(r)
            s = score_pair(q, opp, cos, cfg, today)
            if is_match(q, s, cfg):
                existing = prev.pop(r.id, None)
                _upsert_request_match(db, r.id, opp.id, s, existing)
                if existing is None:
                    _notify_new_match(db, r, opp, s.score)
                by_company[r.company_id] = r.member_user_id
                matched += 1
            elif r.company_id in by_company and (r.company_id not in below or s.score > below[r.company_id][0].score):
                below[r.company_id] = (s, r.id)
    for stale in prev.values():
        db.delete(stale)
    for cid in sorted(by_company):  # khoá theo thứ tự tăng dần → không khoá chéo giữa các việc nền
        refresh_company(db, cid, {opp.id}, by_company[cid], {opp.id: below[cid]} if cid in below else None)
    db.flush()
    return matched


def rematch_all(db: Session, cfg: Settings | None = None, reembed: bool = False) -> tuple[int, int, str]:
    """Tính lại toàn bộ (sau khi đổi thuật toán/mô hình embedding).

    Trả về (số phiếu tìm, số cặp phù hợp, lý do nếu phải chạy dự phòng không embedding).
    """
    from app.db import utcnow

    cfg = cfg or get_settings()
    reqs = list(db.scalars(select(SearchRequest).order_by(SearchRequest.id)).unique())
    note = ""
    try:
        sync_opp_embeddings(db, cfg, list(db.scalars(select(Opportunity).where(Opportunity.status == "published")).unique()), force=reembed)
        sync_request_embeddings(db, cfg, [r for r in reqs if r.status != "rejected"], force=reembed)
    except emb.EmbeddingError as e:
        note = str(e)
    total = 0
    for r in reqs:
        total += match_request(db, r, cfg, semantic=not note)
        r.match_status, r.matched_at = "done", utcnow()
        r.match_error = f"So khớp không dùng ngữ nghĩa: {note}"[:300] if note else ""
    return len(reqs), total, note
