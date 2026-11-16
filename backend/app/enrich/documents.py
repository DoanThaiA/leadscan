"""Tài liệu công bố thông tin của doanh nghiệp niêm yết (giai đoạn 3): nạp → tải → bóc tách → ghi kho B hoặc chờ duyệt.

Nạp: nhân viên tải file lên, hoặc khai danh sách đường dẫn (MST hoặc mã CK + URL). Hệ thống không tự dò cả trang
công bố thông tin (mục 2: không thu thập diện rộng) — chỉ tải đúng đường dẫn được khai, qua giới hạn tốc độ + robots.txt.

Tự ghi vào kho khi bóc tách bằng bảng/luật đủ cả HĐQT và Ban điều hành (≥ MIN_AUTO người). Còn lại — thiếu nhóm,
dùng mô hình ngôn ngữ, PDF dạng ảnh — vào hàng chờ duyệt (B09): biên tập viên sửa danh sách rồi duyệt.
"""

import logging
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.enrich import governance, llm, raw_store, runner, sources
from app.enrich.apply import Applied, Origin, apply_facts
from app.enrich.connectors.base import Facts, PersonFact
from app.enrich.normalize import clean_text, parse_date, parse_mst
from app.models import AdminUser
from app.models_enrich import DOC_TYPES, PERSON_GROUPS, EnrichCompany, EnrichDocument, SourcePage

log = logging.getLogger("leadscan.enrich.docs")

SOURCE = "cbtt"
MIN_AUTO = 3  # tối thiểu số người để tự ghi không cần duyệt
MAX_FETCH_ATTEMPTS = 3


class DocError(ValueError):
    pass


def find_company(db: Session, ref: str) -> EnrichCompany | None:
    """ref = MST hoặc mã chứng khoán."""
    ref = (ref or "").strip()
    res = parse_mst(ref)
    if res.mst:
        return db.get(EnrichCompany, res.mst)
    if ref and len(ref) <= 10:
        return db.scalar(select(EnrichCompany).where(func.upper(EnrichCompany.ma_ck) == ref.upper()))
    return None


def _source(db: Session):
    src = sources.ensure(db, SOURCE)
    if not src.enabled:
        raise DocError(f"Nguồn “{src.name}” đang tắt.")
    return src


# ------------------------------------------------------------------ nạp


def add_upload(
    db: Session, user: AdminUser, *, ref: str, doc_type: str, period: str, source_url: str, file_name: str, data: bytes
) -> EnrichDocument:
    c = find_company(db, ref)
    if not c:
        raise DocError("Không tìm thấy doanh nghiệp theo MST / mã CK này trong hệ thống.")
    if doc_type not in DOC_TYPES:
        raise DocError("Loại tài liệu không hợp lệ.")
    src = _source(db)
    url = source_url.strip() or f"tai-len:{file_name}"
    ctype = "application/pdf" if file_name.lower().endswith(".pdf") or data[:5] == b"%PDF-" else (
        "text/html" if file_name.lower().endswith((".htm", ".html")) else "text/plain"
    )
    page, _ = raw_store.save_page(db, src.code, url, data, ctype, mst=c.mst)
    doc = EnrichDocument(
        mst=c.mst, doc_type=doc_type, period=clean_text(period, 40) or "", source_url=url[:1000],
        source_page_id=page.id, status="fetched", created_by_id=user.id,
    )
    db.add(doc)
    db.commit()
    parse_document(db, doc.id)
    db.refresh(doc)
    return doc


def add_urls(db: Session, user: AdminUser, items: list[dict]) -> dict:
    """items: [{ref, url, doc_type?, period?}]. Trả về biên bản: tạo / bỏ qua kèm lý do."""
    _source(db)
    created, skipped = [], []
    for i, it in enumerate(items, start=1):
        url = (it.get("url") or "").strip()
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.netloc:
            skipped.append({"line": i, "value": url[:100], "reason": "Đường dẫn không hợp lệ"})
            continue
        c = find_company(db, it.get("ref", ""))
        if not c:
            skipped.append({"line": i, "value": it.get("ref", "")[:30], "reason": "MST / mã CK không có trong hệ thống"})
            continue
        if db.scalar(select(EnrichDocument.id).where(EnrichDocument.mst == c.mst, EnrichDocument.source_url == url[:1000])):
            skipped.append({"line": i, "value": url[:100], "reason": "Đã có tài liệu này"})
            continue
        dt = it.get("doc_type") if it.get("doc_type") in DOC_TYPES else "bao_cao_quan_tri"
        doc = EnrichDocument(mst=c.mst, doc_type=dt, period=clean_text(it.get("period"), 40) or "", source_url=url[:1000], status="pending", created_by_id=user.id)
        db.add(doc)
        db.flush()
        created.append(doc.id)
    db.commit()
    return {"created": len(created), "ids": created, "skipped": skipped}


# ------------------------------------------------------------------ tải (cùng giới hạn tốc độ / robots.txt / nhật ký với runner)


def pending_ids(db: Session, limit: int = 4) -> list[int]:
    ok, _ = runner.can_run_now(db)
    if not ok:
        return []
    return list(
        db.scalars(
            select(EnrichDocument.id)
            .where(EnrichDocument.status == "pending", EnrichDocument.attempts < MAX_FETCH_ATTEMPTS)
            .order_by(EnrichDocument.id)
            .limit(limit)
        )
    )


def fetch_document(db: Session, doc_id: int) -> str:
    doc = db.get(EnrichDocument, doc_id)
    if not doc or doc.status != "pending":
        return doc.status if doc else "missing"
    try:
        src = _source(db)
    except DocError:
        return "pending"
    doc.attempts += 1
    db.commit()
    interval = float(sources.setting(src, "min_interval_s"))
    timeout = float(sources.setting(src, "timeout_s", 60))
    domain = urlparse(doc.source_url).hostname or ""
    try:
        if not runner.robots_allows(db, src, doc.source_url, interval, timeout):
            doc.status, doc.error = "failed", "robots.txt không cho phép tải đường dẫn này."
            db.commit()
            return doc.status
        wait = runner.reserve_slot(db, domain, interval)
        if wait > 0:
            import time

            time.sleep(min(wait, runner.MAX_INLINE_WAIT_S))
        r = runner._logged_get(db, src, doc.source_url, timeout)  # noqa: SLF001
    except httpx.HTTPError as e:
        doc.error = f"Lỗi mạng: {e}"[:2000]
        doc.status = "failed" if doc.attempts >= MAX_FETCH_ATTEMPTS else "pending"
        db.commit()
        runner.check_error_rate(db, src)
        return doc.status
    if r.status_code >= 400:
        doc.error = f"HTTP {r.status_code}"
        doc.status = "failed" if r.status_code == 404 or doc.attempts >= MAX_FETCH_ATTEMPTS else "pending"
        db.commit()
        runner.check_error_rate(db, src)
        return doc.status
    ctype = r.headers.get("content-type", "").split(";")[0]
    page, _ = raw_store.save_page(db, src.code, doc.source_url, r.content, ctype, r.status_code, mst=doc.mst)
    doc.source_page_id = page.id
    doc.status = "fetched"
    doc.error = ""
    db.commit()
    return parse_document(db, doc.id)


# ------------------------------------------------------------------ bóc tách


def parse_document(db: Session, doc_id: int) -> str:
    doc = db.get(EnrichDocument, doc_id)
    page = db.get(SourcePage, doc.source_page_id) if doc and doc.source_page_id else None
    if not doc or not page:
        return "missing"
    try:
        data = raw_store.get(page.storage_key)
        parsed = governance.load(data, page.content_type, page.url)
    except Exception as e:  # noqa: BLE001 — file hỏng / định dạng lạ
        doc.status, doc.error = "failed", f"Không đọc được tài liệu: {e}"[:2000]
        db.commit()
        return doc.status

    model_note: list[str] = []

    def model_fn(text: str):
        try:
            return llm.extract_people(db, text)
        except llm.LlmError as e:
            model_note.append(f"Tầng mô hình ngôn ngữ lỗi: {e}")
            return None

    ex = governance.extract(parsed, model_fn if llm.enabled() else None)
    ex.notes += model_note
    doc.extracted = ex.to_dict()
    doc.method = ex.method
    doc.parsed_at = utcnow()
    doc.error = ""
    auto = ex.complete and ex.method in ("cau_truc", "luat") and len(ex.people) >= MIN_AUTO
    if auto:
        apply_people(db, doc, page, ex.to_dict()["people"], actor_id=None, method=ex.method)
        doc.status = "parsed"
    else:
        doc.status = "needs_review"
    db.commit()
    return doc.status


def apply_people(db: Session, doc: EnrichDocument, page: SourcePage | None, people: list[dict], actor_id: int | None, method: str) -> Applied:
    src = sources.ensure(db, SOURCE)
    facts = Facts()
    for p in people:
        title = clean_text(p.get("chuc_danh"), 200) or governance.GROUP_DEFAULT_TITLE.get(p.get("nhom") or "khac", "Khác")
        facts.people.append(
            PersonFact(
                ho_ten=p.get("ho_ten", ""),
                chuc_danh=title,
                excerpt=(p.get("nguon_trich") or f"{DOC_TYPES.get(doc.doc_type, '')} {doc.period}").strip()[:2000],
                tu_ngay=parse_date(p.get("tu_ngay")),
                den_ngay=parse_date(p.get("den_ngay")),
            )
        )
    origin = Origin(
        source=src,
        source_url=doc.source_url,
        content_hash=page.content_hash if page else f"doc:{doc.id}",
        method=method,
        source_page_id=page.id if page else None,
        actor_id=actor_id,
    )
    return apply_facts(db, doc.mst, facts, origin)


def review(db: Session, user: AdminUser, doc_id: int, action: str, people: list[dict]) -> EnrichDocument:
    doc = db.get(EnrichDocument, doc_id)
    if not doc:
        raise DocError("Không tìm thấy tài liệu.")
    if doc.status not in ("needs_review", "parsed"):
        raise DocError("Tài liệu này không ở trạng thái chờ duyệt.")
    if action == "reject":
        doc.status = "rejected"
    elif action == "approve":
        clean = []
        for p in people:
            name = governance.clean_name(p.get("ho_ten", ""))
            if not name:
                raise DocError(f"Họ tên không hợp lệ: “{p.get('ho_ten', '')}”.")
            nhom = p.get("nhom") if p.get("nhom") in PERSON_GROUPS else "khac"
            for k in ("tu_ngay", "den_ngay"):
                if p.get(k) and not parse_date(p.get(k)):
                    raise DocError(f"Ngày không hợp lệ: {p.get(k)}")
            clean.append({**p, "ho_ten": name, "nhom": nhom})
        if not clean:
            raise DocError("Danh sách trống — nếu tài liệu không có thông tin thì bấm Từ chối.")
        original = {(governance.bo_dau(x["ho_ten"]), x.get("chuc_danh")) for x in (doc.extracted or {}).get("people", [])}
        page = db.get(SourcePage, doc.source_page_id) if doc.source_page_id else None
        same = [p for p in clean if (governance.bo_dau(p["ho_ten"]), p.get("chuc_danh")) in original]
        edited = [p for p in clean if p not in same]
        # B09: phần biên tập viên sửa / thêm là quyết định biên tập — không bị vòng chạy sau ghi đè
        if same:
            apply_people(db, doc, page, same, user.id, doc.method or "luat")
        if edited:
            apply_people(db, doc, page, edited, user.id, "thu_cong")
        doc.status = "approved"
        doc.extracted = {**(doc.extracted or {}), "approved_people": clean}
    else:
        raise DocError("Thao tác không hợp lệ.")
    doc.reviewed_by_id = user.id
    doc.reviewed_at = utcnow()
    db.commit()
    db.refresh(doc)
    return doc
