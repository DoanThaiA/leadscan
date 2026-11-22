"""Nhu cầu đang tìm — phiếu tìm cơ hội của thành viên, hiển thị ẨN DANH cho đối tác (/doi-tac/nhu-cau) và trợ lý AI.

Mục đích: đối tác biết thành viên đang cần loại khách hàng / cơ hội nào để đi tìm đúng doanh nghiệp có nhu cầu mua.

Chỉ lấy phiếu "Tìm kiếm liên tục" (chưa bị từ chối), gửi trong NEEDS_DAYS ngày gần nhất, của doanh nghiệp còn hạn thành viên
(hết hạn thì không mua được phiếu → đối tác đi tìm cũng không bán được).

Ẩn danh: KHÔNG trả tên / mã / MST / người gửi của thành viên. Mô tả khách tự viết được lọc trước khi trả:
email, số điện thoại, đường link / tên miền, mã số thuế và tên doanh nghiệp của chính thành viên → thay bằng nhãn trung tính.
Mã hiển thị NC-xxxxxx là số phiếu, không suy ra được doanh nghiệp.
"""

import re
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Opportunity, SearchRequest, SearchRequestMatch
from app.services import products as prod
from app.services.catalog import membership_active
from app.services.embedding import fold
from app.services.partner_submissions import _NAME_STOP

NEEDS_DAYS = 180  # phiếu cũ hơn coi như nguội, không đưa cho đối tác
MAX_SCAN = 3000  # số phiếu mới nhất xét mỗi lần (lọc / thống kê làm trong Python vì tiêu chí lưu JSON)
FRESH_DAYS = 7

_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", re.U)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b[\w\-]+(?:\.[\w\-]+)*\.(?:com|vn|net|org|info|biz|asia|io|co)(?:\.vn)?(?:/\S*)?\b", re.I | re.U)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?!\d)")
_TAX_RE = re.compile(r"(?<!\d)\d{10}(?:\s?-\s?\d{3})?(?!\d)")
_TAX_LABEL_RE = re.compile(r"\b(MST|MSDN|mã số thuế|ma so thue)(\s*[:：]?\s*)\d{10}(?:\s?-\s?\d{3})?(?!\d)", re.I | re.U)
_WORD_RE = re.compile(r"\w+", re.U)


def code_of(req_id: int) -> str:
    return f"NC-{req_id:06d}"


def id_of(code: str) -> int | None:
    m = re.fullmatch(r"\s*(?:NC-?)?0*(\d{1,9})\s*", code or "", re.I)
    return int(m.group(1)) if m else None


def _name_tokens(name: str) -> list[str]:
    return [w for w in fold(name).split() if w not in _NAME_STOP]


def _mask_name(text: str, name: str) -> str:
    """Thay tên doanh nghiệp của thành viên trong mô tả (so không dấu, bỏ "Công ty TNHH…") bằng nhãn trung tính."""
    core = _name_tokens(name)
    if not core or (len(core) == 1 and len(core[0]) < 4):
        return text  # tên quá ngắn / chung chung → dễ che nhầm chữ thường
    words = list(_WORD_RE.finditer(text))
    folded = [fold(m.group(0)) for m in words]
    out, last, i, n = [], 0, 0, len(core)
    while i <= len(words) - n:
        if folded[i:i + n] == core:
            out.append(text[last:words[i].start()])
            out.append("[doanh nghiệp]")
            last = words[i + n - 1].end()
            i += n
        else:
            i += 1
    out.append(text[last:])
    return "".join(out)


def sanitize(text: str, company_name: str = "") -> str:
    t = _TAX_LABEL_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[MST]", text or "")  # trước SĐT: MST 10 số bắt đầu bằng 0 trông giống SĐT
    t = _EMAIL_RE.sub("[email]", t)
    t = _URL_RE.sub("[link]", t)
    t = _PHONE_RE.sub("[SĐT]", t)
    t = _TAX_RE.sub("[MST]", t)
    if company_name:
        t = _mask_name(t, company_name)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _match_counts(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(SearchRequestMatch.request_id, func.count())
        .join(Opportunity, Opportunity.id == SearchRequestMatch.opportunity_id)
        .where(SearchRequestMatch.request_id.in_(ids), Opportunity.status == "published")
        .group_by(SearchRequestMatch.request_id)
    ).all()
    return dict(rows)


def _out(r: SearchRequest, matches: int) -> dict:
    c = r.criteria or {}
    text = sanitize(r.note or "", r.company.name if r.company else "")
    return {
        "code": code_of(r.id),
        "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
        "fresh": bool(r.created_at and utcnow() - r.created_at < timedelta(days=FRESH_DAYS)),
        "industries": list(c.get("industries") or []),
        "regions": list(c.get("regions") or []),
        "sizes": list(c.get("sizes") or []),
        "sources": list(c.get("sources") or []),
        "products": prod.product_names(prod.find_products(r.note or "")),
        "places": prod.find_places(r.note or ""),
        "text": text,
        "match_count": matches,  # số phiếu cơ hội đang bán đã khớp — 0 = chưa có cơ hội nào, đối tác tìm được thì giá trị nhất
    }


def _live(db: Session) -> list[SearchRequest]:
    since = utcnow() - timedelta(days=NEEDS_DAYS)
    rows = db.scalars(
        select(SearchRequest)
        .where(SearchRequest.status == "open", SearchRequest.created_at >= since)
        .order_by(SearchRequest.id.desc())
        .limit(MAX_SCAN)
    ).unique().all()
    return [r for r in rows if r.company is not None and membership_active(r.company)]


def _hit(item: dict, q: str, industry: str, region: str) -> bool:
    if industry and industry not in item["industries"]:
        return False
    if region:
        regs = set(item["regions"]) | set(item["places"]) | {prod.province_region(p) for p in item["places"]}
        if regs and region not in regs and "Toàn quốc" not in regs:
            return False
    if q:
        hay = fold(" ".join([item["text"], *item["industries"], *item["products"], *item["regions"]]))
        if not all(w in hay for w in fold(q).split()):
            return False
    return True


def list_needs(
    db: Session, *, q: str = "", industry: str = "", region: str = "", unmet: bool = False, sort: str = "new",
    page: int = 1, page_size: int = 20,
) -> dict:
    rows = _live(db)
    counts = _match_counts(db, [r.id for r in rows])
    items = [_out(r, counts.get(r.id, 0)) for r in rows]
    stats = {
        "total": len(items),
        "unmet": sum(1 for it in items if it["match_count"] == 0),
        "new_7d": sum(1 for it in items if it["fresh"]),
    }
    by_ind: dict[str, int] = {}
    for it in items:
        for ind in it["industries"] or ["Chưa chọn ngành"]:
            by_ind[ind] = by_ind.get(ind, 0) + 1
    stats["industries"] = sorted(([k, v] for k, v in by_ind.items()), key=lambda x: -x[1])[:10]

    picked = [it for it in items if _hit(it, q.strip(), industry, region) and (not unmet or it["match_count"] == 0)]
    if sort == "unmet":
        picked.sort(key=lambda it: it["match_count"])  # sort ổn định: cùng số khớp thì phiếu mới hơn vẫn đứng trước
    total = len(picked)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "items": picked[start:start + page_size], "stats": stats}


def get_need(db: Session, code: str) -> dict | None:
    rid = id_of(code)
    if rid is None:
        return None
    r = db.get(SearchRequest, rid)
    if not r or r.status != "open" or not r.company or not membership_active(r.company):
        return None
    if r.created_at and utcnow() - r.created_at > timedelta(days=NEEDS_DAYS):
        return None
    return _out(r, _match_counts(db, [r.id]).get(r.id, 0))
