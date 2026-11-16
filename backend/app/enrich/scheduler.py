"""Vận hành tự động (giai đoạn 5): lịch tái thu thập (A12), cảnh báo thay đổi (C06), dọn bản gốc quá hạn (N07).

Celery beat gọi các hàm ở đây (app/worker.py) để hệ thống chạy một tuần không cần can thiệp:
  leadscan.enrich_recrawl    mỗi ngày   tạo vòng tái thu thập cho MST quá hạn theo từng nguồn (recrawl_days)
  leadscan.enrich_alerts     10 phút    biến thay đổi / tín hiệu mới thành cảnh báo cho danh sách theo dõi
  leadscan.enrich_digest     mỗi giờ    gửi email tổng hợp cảnh báo (danh sách bật email)
  leadscan.enrich_raw_purge  mỗi ngày   xoá bản gốc quá thời hạn lưu (mặc định 365 ngày)
"""

import logging
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.enrich import raw_store, runner, sources
from app.enrich.connectors import registry
from app.enrich.titles import TITLES
from app.models import AdminUser
from app.models_enrich import (
    ALERT_KINDS,
    CompanyChange,
    CompanyEvidence,
    CrawlJob,
    EnrichAlert,
    EnrichCompany,
    EnrichDocument,
    EnrichImport,
    EnrichRun,
    EnrichSignal,
    EnrichSource,
    PersonChange,
    PersonEvidence,
    SourcePage,
    Watchlist,
    WatchItem,
)
from app.services import storage

log = logging.getLogger("leadscan.enrich.scheduler")

DEFAULT_RECRAWL = {"enabled": True, "daily_limit": 3000}


# ------------------------------------------------------------------ A12: lịch tái thu thập


def due_msts(db: Session, src: EnrichSource, limit: int) -> list[str]:
    """MST chưa từng chạy nguồn này, hoặc lần xong gần nhất cũ hơn recrawl_days; bỏ MST đang có việc mở."""
    days = int(sources.setting(src, "recrawl_days", 90) or 90)
    cutoff = utcnow() - timedelta(days=days)
    last = (
        select(CrawlJob.mst, func.max(func.coalesce(CrawlJob.finished_at, CrawlJob.created_at)).label("last"))
        .where(CrawlJob.connector == src.code, CrawlJob.status.in_(("done", "not_found", "failed", "skipped")))
        .group_by(CrawlJob.mst)
        .subquery()
    )
    open_jobs = select(CrawlJob.mst).where(CrawlJob.connector == src.code, CrawlJob.status.in_(runner.OPEN))
    stmt = (
        select(EnrichCompany.mst)
        .outerjoin(last, last.c.mst == EnrichCompany.mst)
        .where((last.c.last.is_(None)) | (last.c.last < cutoff), EnrichCompany.mst.not_in(open_jobs))
        .order_by(last.c.last.is_not(None), last.c.last, EnrichCompany.mst)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def schedule_recrawl(db: Session) -> list[dict]:
    """Tạo vòng tái thu thập cho từng nguồn tự động / thủ công đang bật. Trả về danh sách vòng đã tạo."""
    cfg = {**DEFAULT_RECRAWL, **runner.get_setting(db, "recrawl")}
    if not cfg.get("enabled"):
        return []
    sources.ensure_all(db)  # nguồn khai trong mã nhưng chưa có bản ghi → tạo với cấu hình mặc định
    created = []
    for src in db.scalars(select(EnrichSource).where(EnrichSource.enabled.is_(True))).all():
        c = registry.get(src.code)
        if not c or c.kind not in ("http", "manual"):
            continue
        msts = due_msts(db, src, int(cfg.get("daily_limit", 3000)))
        if not msts:
            continue
        run = EnrichRun(name=f"Tái thu thập tự động — {src.name} {utcnow():%d/%m/%Y}", connectors=[src.code], status="running")
        db.add(run)
        db.flush()
        status = "manual" if c.kind == "manual" else "pending"
        db.add_all([CrawlJob(mst=m, connector=src.code, status=status, run_id=run.id) for m in msts])
        run.job_count = len(msts)
        db.commit()
        created.append({"run_id": run.id, "connector": src.code, "jobs": len(msts)})
        log.info("Tái thu thập %s: %s MST", src.code, len(msts))
    return created


def file_reminders(db: Session) -> list[dict]:
    """Nguồn nhập file / tài liệu không tự chạy được: báo khi lần nhập gần nhất đã quá chu kỳ tái thu thập."""
    sources.ensure_all(db)
    out = []
    for src in db.scalars(select(EnrichSource).where(EnrichSource.enabled.is_(True))).all():
        c = registry.get(src.code)
        if not c or c.kind != "file":
            continue
        days = int(sources.setting(src, "recrawl_days", 90) or 90)
        last = db.scalar(select(func.max(EnrichImport.created_at)).where(EnrichImport.source_code == src.code))
        if last is None or last < utcnow() - timedelta(days=days):
            out.append({"source": src.code, "name": src.name, "last_import": last.isoformat() + "Z" if last else None, "every_days": days})
    return out


# ------------------------------------------------------------------ C06: cảnh báo


def _money(v) -> str:
    return f"{v:,} đ".replace(",", ".") if isinstance(v, int) else ""


def _change_alert(ch: CompanyChange) -> tuple[str, str] | None:
    if ch.field == "dia_chi":
        return "dia_chi", f"Đổi địa chỉ: “{(ch.old_value or '')[:120]}” → “{(ch.new_value or '')[:120]}”"
    if ch.field == "trang_thai":
        return "trang_thai", f"Tình trạng MST: {ch.old_value or '—'} → {ch.new_value or '—'}"
    if ch.field in ("tinh", "ten_khong_dau"):
        return None  # đã gộp trong cảnh báo địa chỉ / tên
    return "khac", f"Đổi {ch.field}: “{(ch.old_value or '')[:80]}” → “{(ch.new_value or '')[:80]}”"


def _signal_alert(s: EnrichSignal) -> tuple[str, str] | None:
    p = s.payload or {}
    if s.kind == "no_thue":
        return "no_thue", f"Có tên trong danh sách nợ thuế {_money(p.get('so_tien'))}{' — ' + p['co_quan'] if p.get('co_quan') else ''}".strip()
    if s.kind == "trung_thau":
        return "trung_thau", f"Trúng thầu gói “{(p.get('goi_thau') or '')[:150]}” {_money(p.get('gia_trung_thau'))}".strip()
    if s.kind == "bo_nhiem":
        title = p.get("chuc_danh") or ""
        kind = "nguoi_dai_dien" if "đại diện" in title.lower() else "bo_nhiem"
        return kind, f"Bổ nhiệm {title}"
    return "khac", f"Tín hiệu: {s.kind}"


def _person_change_alert(ch: PersonChange) -> tuple[str, str, str] | None:
    """field = vai_tro:<mst>:<mã chức danh> — người ra quyết định thôi giữ chức (không ghi tên trong cảnh báo)."""
    parts = (ch.field or "").split(":")
    if len(parts) != 3 or parts[0] != "vai_tro":
        return None
    mst, code = parts[1], parts[2]
    title, decision = TITLES.get(code, ("", False))
    if not decision:
        return None
    return mst, "nguoi_dai_dien", f"{title} thôi giữ chức ({ch.new_value})"


def scan_alerts(db: Session) -> int:
    """Biến thay đổi / tín hiệu mới (sau con trỏ lần trước) thành cảnh báo. Trả về số cảnh báo tạo."""
    cur = runner.get_setting(db, "alert_cursor")
    c_change, c_signal, c_person = int(cur.get("change", 0)), int(cur.get("signal", 0)), int(cur.get("person", 0))
    events: list[tuple[str, str, str, str, object]] = []  # (mst, kind, summary, ref, thời điểm phát hiện)
    max_change, max_signal, max_person = c_change, c_signal, c_person
    for ch in db.scalars(select(CompanyChange).where(CompanyChange.id > c_change).order_by(CompanyChange.id).limit(5000)):
        max_change = ch.id
        a = _change_alert(ch)
        if a:
            events.append((ch.mst, a[0], a[1], f"change:{ch.id}", ch.detected_at))
    for s in db.scalars(select(EnrichSignal).where(EnrichSignal.id > c_signal).order_by(EnrichSignal.id).limit(5000)):
        max_signal = s.id
        a = _signal_alert(s)
        if a:
            events.append((s.mst, a[0], a[1], f"signal:{s.id}", s.created_at))
    for pc in db.scalars(select(PersonChange).where(PersonChange.id > c_person).order_by(PersonChange.id).limit(5000)):
        max_person = pc.id
        a = _person_change_alert(pc)
        if a:
            events.append((a[0], a[1], a[2], f"role-end:{pc.id}", pc.detected_at))
    created = 0
    if events:
        msts = {e[0] for e in events}
        lists: dict[str, list[tuple[Watchlist, object]]] = defaultdict(list)
        for item, wl in db.execute(select(WatchItem, Watchlist).join(Watchlist, Watchlist.id == WatchItem.watchlist_id).where(WatchItem.mst.in_(msts))):
            lists[item.mst].append((wl, item.added_at))
        for mst, kind, summary, ref, at in events:
            for wl, added_at in lists.get(mst, []):
                if wl.owner_id is None or (wl.kinds and kind not in wl.kinds):
                    continue
                if at and added_at and at < added_at:
                    continue  # thay đổi xảy ra trước khi bắt đầu theo dõi doanh nghiệp này
                db.add(EnrichAlert(user_id=wl.owner_id, watchlist_id=wl.id, mst=mst, kind=kind, summary=summary[:500], ref=ref))
                created += 1
    runner.set_setting(db, "alert_cursor", {"change": max_change, "signal": max_signal, "person": max_person}, None)
    return created


def send_digests(db: Session) -> int:
    """Email tổng hợp cảnh báo chưa gửi, cho danh sách theo dõi bật email. Trả về số email đã gửi."""
    from app.services.notify import send_mail

    rows = db.execute(
        select(EnrichAlert, Watchlist)
        .join(Watchlist, Watchlist.id == EnrichAlert.watchlist_id)
        .where(Watchlist.email_digest.is_(True), EnrichAlert.emailed_at.is_(None))
        .order_by(EnrichAlert.id)
        .limit(5000)
    ).all()
    by_user: dict[int, list[EnrichAlert]] = defaultdict(list)
    for a, _ in rows:
        by_user[a.user_id].append(a)
    sent = 0
    cfg = get_settings()
    for uid, alerts in by_user.items():
        user = db.get(AdminUser, uid)
        if not user or not user.is_active:
            continue
        names = dict(db.execute(select(EnrichCompany.mst, EnrichCompany.ten).where(EnrichCompany.mst.in_({a.mst for a in alerts}))).all())
        lines = [f"• {names.get(a.mst) or a.mst} ({a.mst}) — {ALERT_KINDS.get(a.kind, a.kind)}: {a.summary}" for a in alerts[:200]]
        body = "Thay đổi mới ở các doanh nghiệp bạn theo dõi:\n\n" + "\n".join(lines) + "\n\nXem chi tiết ở trang Làm giàu theo MST → Theo dõi & cảnh báo."
        if send_mail(cfg, f"[LeadScan] {len(alerts)} cảnh báo doanh nghiệp theo dõi", body, to=user.email):
            sent += 1
        now = utcnow()
        for a in alerts:
            a.emailed_at = now
    db.commit()
    return sent


# ------------------------------------------------------------------ N07: dọn bản gốc quá hạn


def purge_raw(db: Session, days: int | None = None) -> int:
    days = days if days is not None else int(get_settings().enrich_raw_retention_days)
    cutoff = utcnow() - timedelta(days=days)
    pages = db.scalars(select(SourcePage).where(SourcePage.fetched_at < cutoff).limit(5000)).all()
    keys = [p.storage_key for p in pages if p.storage_key]
    if keys:
        if raw_store._use_r2():  # noqa: SLF001
            storage.backend().delete(keys)
        else:
            for k in keys:
                path = raw_store._local_dir() / k  # noqa: SLF001
                path.unlink(missing_ok=True)
    ids = [p.id for p in pages]
    if ids:
        # bằng chứng / tín hiệu / tài liệu giữ lại, chỉ bỏ liên kết tới bản gốc (vẫn còn đường dẫn, trích đoạn, thời điểm)
        for model in (CompanyEvidence, PersonEvidence, EnrichSignal, EnrichImport, EnrichDocument):
            db.execute(update(model).where(model.source_page_id.in_(ids)).values(source_page_id=None))
    for p in pages:
        db.delete(p)
    db.commit()
    return len(pages)
