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
  5. Giá phiếu thành viên phải trả đồng biến với điểm của chính họ: price_for().
"""

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Opportunity, Purchase, SavedOpportunity, SearchRequest, SearchRequestMatch, UserOpportunity
from app.services import embedding as emb

W_CRITERIA, W_SEMANTIC, W_KEYWORD = 0.40, 0.35, 0.25
W_SEMANTIC_ONLY, W_KEYWORD_ONLY = 0.60, 0.40  # khách không chọn tiêu chí nào
W_FIT, W_URGENCY, W_TRUST = 0.75, 0.10, 0.15
CRITERIA_WEIGHTS = {"industries": 40, "regions": 30, "sources": 20}
COS_LOW, COS_HIGH = 0.03, 0.40  # cosine ≤ LOW → 0 điểm, ≥ HIGH → 100 điểm

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


def price_for(base_price: int, score: int) -> int:
    """Giá phiếu theo điểm của thành viên: đồng biến, 0 điểm = 50% giá cơ bản, 50 điểm = giá cơ bản, 100 điểm = 150%."""
    if base_price <= 0:
        return 0
    return max(1000, round(base_price * (0.5 + max(0, min(100, score)) / 100) / 1000) * 1000)


# ------------------------------------------------------------------ chuẩn bị văn bản


def opp_text(o: Opportunity) -> str:
    """Văn bản dùng để so khớp (không gồm tên bên mua & đầu mối)."""
    parts = [o.title, o.summary, o.industry, o.scale, o.province, o.region, o.source_type, (o.detail or "")[:2000]]
    return ". ".join(p for p in parts if p)


def request_text(r: SearchRequest) -> str:
    c = r.criteria or {}
    extra = [*c.get("industries", []), *c.get("regions", []), *c.get("sizes", []), *c.get("sources", [])]
    return ". ".join(p for p in [r.note, " ".join(extra)] if p)


def ensure_embeddings(cfg: Settings, o: Opportunity | None = None, r: SearchRequest | None = None, force: bool = False) -> None:
    model = emb.current_model(cfg)
    if o is not None and (force or not o.embedding or o.embedding_model != model):
        o.embedding, o.embedding_model = emb.embed(cfg, opp_text(o))
    if r is not None and (force or not r.embedding or r.embedding_model != model):
        r.embedding, r.embedding_model = emb.embed(cfg, request_text(r))


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


def _industry_score(wanted: list[str], o: Opportunity, o_fold: str, o_tokens: set[str]) -> tuple[float, str]:
    best, hit = 0.0, ""
    oi = emb.fold(o.industry)
    for w in wanted:
        wf = emb.fold(w)
        if not wf:
            continue
        wt = set(emb.tokens(w))
        if oi and (wf == oi or wf in oi or oi in wf):
            s = 100.0
        elif wt and len(wt & o_tokens) / len(wt) >= 0.5 and wt & set(emb.tokens(o.industry)):
            s = 80.0
        elif wf in o_fold or (wt and len(wt & o_tokens) / len(wt) >= 0.5):
            s = 55.0  # ngành khách chọn xuất hiện trong nội dung phiếu dù cột "ngành" khác
        elif emb.concepts(w) & emb.concepts(o.industry + " " + o.title):
            s = 45.0  # cùng khái niệm (vd. "Bao bì & in ấn" ~ "thùng carton")
        else:
            s = 0.0
        if s > best:
            best, hit = s, w
    return best, hit


def _region_score(wanted: list[str], o: Opportunity) -> tuple[float, str]:
    prov, reg = emb.fold(o.province), emb.fold(o.region)
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
        else:  # tỉnh/thành
            s = 100.0 if (prov and (wf in prov or prov in wf)) else (35.0 if reg in ("toan quoc",) else 0.0)
        if s > best:
            best, hit = s, w
    return best, hit


def _criteria_score(c: dict, o: Opportunity, o_fold: str, o_tokens: set[str]) -> tuple[float | None, list[str]]:
    total = weight = 0.0
    reasons: list[str] = []
    if c.get("industries"):
        s, hit = _industry_score(c["industries"], o, o_fold, o_tokens)
        total, weight = total + s * CRITERIA_WEIGHTS["industries"], weight + CRITERIA_WEIGHTS["industries"]
        if s >= 45:
            reasons.append(f"Ngành hàng khớp: {hit}")
    if c.get("regions"):
        s, hit = _region_score(c["regions"], o)
        total, weight = total + s * CRITERIA_WEIGHTS["regions"], weight + CRITERIA_WEIGHTS["regions"]
        if s >= 60:
            reasons.append(f"Khu vực khớp: {hit}")
    if c.get("sources"):
        want = {emb.fold(x) for x in c["sources"]}
        s = 100.0 if emb.fold(o.source_type) in want else 0.0
        total, weight = total + s * CRITERIA_WEIGHTS["sources"], weight + CRITERIA_WEIGHTS["sources"]
        if s:
            reasons.append(f"Loại cơ hội khớp: {o.source_type}")
    return (total / weight if weight else None), reasons


def _keyword_score(q_tokens: list[str], q_bigrams: set[str], o_tokens: set[str], o_fold: str) -> tuple[float, list[str]]:
    """Độ bao phủ từ khoá của yêu cầu trong phiếu; từ dài (đặc trưng hơn) nặng hơn, cụm 2 từ nặng gấp đôi."""
    if not q_tokens:
        return 0.0, []
    uniq = list(dict.fromkeys(q_tokens))
    total = sum(1 + min(len(t), 8) / 8 for t in uniq)
    got_w, hits = 0.0, []
    for t in uniq:
        if t in o_tokens:
            got_w += 1 + min(len(t), 8) / 8
            hits.append(t)
    for bg in q_bigrams:
        if f" {bg} " in f" {o_fold} ":
            got_w += 2
            total += 2
    need = min(total, 6.0)  # chỉ cần khớp ~6 đơn vị là đủ điểm tối đa — mô tả dài không bị phạt
    return _clamp(100 * got_w / need if need else 0.0), hits


def _urgency(o: Opportunity, today: date) -> int:
    if not o.deadline:
        return 50
    d = (o.deadline - today).days
    if d < 0:
        return 0
    return 100 if d <= 3 else 90 if d <= 7 else 80 if d <= 14 else 65 if d <= 30 else 50


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
        self.vec, self.model = r.embedding or [], r.embedding_model
        self.text = request_text(r)
        self.q_tokens = emb.tokens(r.note)
        self.shown = {}  # token đã bỏ dấu → từ gốc khách viết (để hiển thị lý do cho dễ đọc)
        for w in re.findall(r"\w+", (r.note or "").lower()):
            self.shown.setdefault(emb.fold(w), w)
        self.q_bigrams = {f"{a} {b}" for a, b in zip(self.q_tokens, self.q_tokens[1:])}
        self.min_score = int(self.criteria.get("min_score") or 0)
        self.has_criteria = any(self.criteria.get(k) for k in CRITERIA_WEIGHTS)
        self._fallback_vec: list[float] | None = None

    def fallback_vec(self) -> list[float]:
        if self._fallback_vec is None:
            self._fallback_vec = emb.embed_hash(self.text)
        return self._fallback_vec


def score_pair(q: RequestCtx, o: Opportunity, today: date | None = None) -> Scored:
    today = today or date.today()
    text = opp_text(o)
    o_fold = emb.fold(text)
    o_tokens = set(o_fold.split())

    kw, hits = _keyword_score(q.q_tokens, q.q_bigrams, o_tokens, o_fold)
    if q.model == o.embedding_model and q.vec and o.embedding:
        cos = emb.cosine(q.vec, o.embedding)
    else:  # khác mô hình embedding (vd. API lỗi một phía) → so bằng vector hash cho công bằng
        cos = emb.cosine(q.fallback_vec(), emb.embed_hash(text))
    sem = _clamp(100 * (cos - COS_LOW) / (COS_HIGH - COS_LOW))

    reasons: list[str] = []
    crit, crit_reasons = _criteria_score(q.criteria, o, o_fold, o_tokens)
    if crit is None:
        fit = W_SEMANTIC_ONLY * sem + W_KEYWORD_ONLY * kw
    else:
        fit = W_CRITERIA * crit + W_SEMANTIC * sem + W_KEYWORD * kw
        reasons += crit_reasons
        if q.criteria.get("regions") and _region_score(q.criteria["regions"], o)[0] == 0:
            fit *= 0.8  # sai khu vực khách yêu cầu → trừ điểm
    shown = [q.shown.get(h, h) for h in hits if len(h) > 2]
    if shown:
        reasons.append("Từ khoá trùng: " + ", ".join(shown[:5]))
    if sem >= 60:
        reasons.append("Nội dung gần với mô tả yêu cầu của bạn")
    elif sem >= 35:
        reasons.append("Nội dung có liên quan tới mô tả yêu cầu")

    urgency, trust = _urgency(o, today), _trust(o)
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


def refresh_company(db: Session, company_id: int, opp_ids: set[int], member_user_id: int | None = None) -> int:
    """Gộp các phiếu tìm của doanh nghiệp thành "Tất cả cơ hội": mỗi cơ hội 1 dòng, điểm = điểm cao nhất. Trả về số dòng MỚI."""
    if not opp_ids:
        return 0
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
    for oid in opp_ids:
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
        elif u is not None and u.best_request_id is not None and oid not in bought:
            db.delete(u)  # không còn phiếu nào khớp (vd. phiếu cơ hội đã sửa nội dung); dòng cũ không gắn phiếu thì giữ
    return new


def match_request(db: Session, req: SearchRequest, cfg: Settings | None = None) -> int:
    """So phiếu tìm cơ hội với mọi phiếu cơ hội đang bán; ghi kết quả. Trả về số cơ hội phù hợp."""
    cfg = cfg or get_settings()
    ensure_embeddings(cfg, r=req)
    today = date.today()
    q = RequestCtx(req)
    prev = {m.opportunity_id: m for m in db.scalars(select(SearchRequestMatch).where(SearchRequestMatch.request_id == req.id)).unique()}
    touched: set[int] = set(prev)
    matched = 0
    if req.status != "rejected":
        opps = db.scalars(select(Opportunity).where(Opportunity.status == "published")).unique().all()
        for o in opps:
            if not _matchable(o, today):
                continue
            ensure_embeddings(cfg, o=o)
            s = score_pair(q, o, today)
            if is_match(q, s, cfg):
                _upsert_request_match(db, req.id, o.id, s, prev.pop(o.id, None))
                touched.add(o.id)
                matched += 1
    for stale in prev.values():  # trước khớp, nay không còn
        db.delete(stale)
    refresh_company(db, req.company_id, touched, req.member_user_id)
    db.flush()
    return matched


def match_opportunity(db: Session, opp: Opportunity, cfg: Settings | None = None) -> int:
    """So 1 phiếu cơ hội (mới mở bán / vừa sửa) với mọi phiếu tìm cơ hội. Trả về số phiếu tìm khớp."""
    cfg = cfg or get_settings()
    today = date.today()
    ensure_embeddings(cfg, o=opp, force=True)  # nội dung có thể vừa đổi
    prev = {(m.request_id): m for m in db.scalars(select(SearchRequestMatch).where(SearchRequestMatch.opportunity_id == opp.id)).unique()}
    reqs = db.scalars(select(SearchRequest).where(SearchRequest.status != "rejected")).unique().all() if _matchable(opp, today) else []
    by_company: dict[int, int | None] = {r.company_id: r.member_user_id for r in db.scalars(select(SearchRequest).where(SearchRequest.id.in_(list(prev)))).unique()} if prev else {}
    matched = 0
    for r in reqs:
        ensure_embeddings(cfg, r=r)
        q = RequestCtx(r)
        s = score_pair(q, opp, today)
        if is_match(q, s, cfg):
            _upsert_request_match(db, r.id, opp.id, s, prev.pop(r.id, None))
            by_company[r.company_id] = r.member_user_id
            matched += 1
    for stale in prev.values():
        db.delete(stale)
    for cid, uid in by_company.items():
        refresh_company(db, cid, {opp.id}, uid)
    db.flush()
    return matched


def rematch_all(db: Session, cfg: Settings | None = None) -> tuple[int, int]:
    """Tính lại toàn bộ (sau khi đổi thuật toán/mô hình embedding). Trả về (số phiếu tìm, số cặp phù hợp)."""
    cfg = cfg or get_settings()
    reqs = db.scalars(select(SearchRequest).order_by(SearchRequest.id)).unique().all()
    for o in db.scalars(select(Opportunity)).unique():
        ensure_embeddings(cfg, o=o, force=True)
    total = 0
    for r in reqs:
        ensure_embeddings(cfg, r=r, force=True)
        total += match_request(db, r, cfg)
    return len(reqs), total
