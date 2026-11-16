"""Vòng thu thập và hàng đợi theo MST (A06, A07, A08, A11, A13, N02).

Trạng thái mỗi công việc (MST × connector) nằm trong CSDL (CrawlJob) — Celery chỉ là bộ thực thi, nên dừng
giữa chừng rồi chạy lại không mất tiến độ và không tải trùng:
  pending → queued (dispatch đã giao cho worker) → running → done | not_found | failed | manual
  Lỗi tạm thời → pending với next_attempt_at lùi dần; quá max_retries → failed.
  queued/running quá STALE_MINUTES (worker chết, mất điện) → trả về pending (N02: mất tối đa 1 việc mỗi luồng).

Giới hạn tốc độ theo tên miền (A08): mỗi request đặt chỗ trên DomainSlot (khoá dòng) → các worker xếp hàng cách
nhau ≥ min_interval_s (tối thiểu 2 giây). Mỗi request ghi FetchLog để chứng minh.
"""

import logging
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.enrich import merge, raw_store, sources
from app.enrich.apply import Applied, Origin, apply_facts
from app.enrich.connectors import registry
from app.enrich.connectors.base import NeedsHuman, NotFound
from app.models import AdminUser
from app.models_enrich import (
    CrawlJob,
    DomainSlot,
    EnrichBatchItem,
    EnrichCompany,
    EnrichRun,
    EnrichSetting,
    EnrichSource,
    FetchLog,
    SourcePage,
)

log = logging.getLogger("leadscan.enrich")

VN = ZoneInfo("Asia/Ho_Chi_Minh")
STALE_MINUTES = 30
MAX_INLINE_WAIT_S = 30  # chờ lượt tên miền lâu hơn thế thì trả việc về hàng đợi thay vì giữ worker
ERROR_WINDOW = timedelta(hours=1)
ERROR_RATE = 0.2  # A13: > 20% lỗi trong 1 giờ → tự tạm dừng
ERROR_MIN_SAMPLE = 10
OPEN = ("pending", "queued", "running", "manual")

DEFAULT_SETTINGS = {
    "paused": {"on": False, "reason": ""},
    "window": {"enabled": False, "start": 22, "end": 6},  # giờ Việt Nam; qua đêm được
    "max_running": {"per_connector": 2},
    "recrawl": {"enabled": True, "daily_limit": 3000},  # A12: lịch tái thu thập tự động
    "alert_cursor": {},  # C06: vị trí đã quét thay đổi / tín hiệu
}


# ------------------------------------------------------------------ cấu hình vận hành (A07)


def get_setting(db: Session, key: str) -> dict:
    row = db.get(EnrichSetting, key)
    return {**DEFAULT_SETTINGS.get(key, {}), **(row.value if row else {})}


def set_setting(db: Session, key: str, value: dict, user: AdminUser | None) -> dict:
    row = db.get(EnrichSetting, key)
    merged = {**DEFAULT_SETTINGS.get(key, {}), **(row.value if row else {}), **value}
    if row:
        row.value = merged
        row.updated_by_id = user.id if user else None
    else:
        db.add(EnrichSetting(key=key, value=merged, updated_by_id=user.id if user else None))
    db.commit()
    return merged


def in_window(window: dict, now: datetime | None = None) -> bool:
    if not window.get("enabled"):
        return True
    hour = (now or datetime.now(VN)).astimezone(VN).hour
    start, end = int(window.get("start", 0)) % 24, int(window.get("end", 0)) % 24
    if start == end:
        return True
    return start <= hour < end if start < end else hour >= start or hour < end


def can_run_now(db: Session) -> tuple[bool, str]:
    paused = get_setting(db, "paused")
    if paused.get("on"):
        return False, "Đang dừng khẩn cấp" + (f": {paused['reason']}" if paused.get("reason") else "")
    if not in_window(get_setting(db, "window")):
        w = get_setting(db, "window")
        return False, f"Ngoài khung giờ chạy ({w['start']}h–{w['end']}h)"
    return True, ""


# ------------------------------------------------------------------ vòng thu thập


class RunError(ValueError):
    pass


def create_run(db: Session, user: AdminUser, name: str, connector_codes: list[str], batch_id: int | None) -> EnrichRun:
    codes = list(dict.fromkeys(connector_codes))
    srcs = []
    for code in codes:
        c = registry.get(code)
        if not c or c.kind not in ("http", "manual"):
            raise RunError(f"Nguồn {code} không chạy theo vòng được (chỉ nguồn tự động hoặc tra cứu thủ công).")
        src = sources.ensure(db, code)
        if not src.enabled:
            raise RunError(f"Nguồn “{src.name}” đang tắt.")
        srcs.append((c, src))
    if not srcs:
        raise RunError("Chọn ít nhất một nguồn.")

    msts_q = select(EnrichCompany.mst)
    if batch_id:
        msts_q = select(EnrichBatchItem.mst).where(EnrichBatchItem.batch_id == batch_id)
    msts = list(db.scalars(msts_q))
    if not msts:
        raise RunError("Không có MST nào trong phạm vi đã chọn.")

    run = EnrichRun(name=name, connectors=codes, batch_id=batch_id, status="running", created_by_id=user.id)
    db.add(run)
    db.flush()
    now = utcnow()
    total = 0
    for c, src in srcs:
        busy = set(db.scalars(select(CrawlJob.mst).where(CrawlJob.connector == src.code, CrawlJob.status.in_(OPEN))))
        rows = [
            {
                "mst": m,
                "connector": src.code,
                "status": "manual" if c.kind == "manual" else "pending",
                "attempts": 0,
                "error": "",
                "run_id": run.id,
                "created_at": now,
            }
            for m in msts
            if m not in busy  # A06: MST đang có việc mở cho nguồn này thì không tạo trùng
        ]
        for i in range(0, len(rows), 5000):
            db.execute(insert(CrawlJob), rows[i : i + 5000])
        total += len(rows)
    run.job_count = total
    db.commit()
    db.refresh(run)
    return run


def set_run_status(db: Session, run: EnrichRun, status: str) -> None:
    run.status = status
    if status in ("done", "cancelled"):
        run.finished_at = utcnow()
    if status == "cancelled":
        db.execute(
            update(CrawlJob)
            .where(CrawlJob.run_id == run.id, CrawlJob.status.in_(("pending", "queued", "manual")))
            .values(status="skipped", finished_at=utcnow())
        )
    db.commit()


def _finish_runs(db: Session) -> None:
    for run in db.scalars(select(EnrichRun).where(EnrichRun.status == "running")):
        left = db.scalar(
            select(func.count()).select_from(CrawlJob).where(CrawlJob.run_id == run.id, CrawlJob.status.in_(OPEN))
        )
        if not left:
            run.status = "done"
            run.finished_at = utcnow()
    db.commit()


# ------------------------------------------------------------------ dispatch


def recover_stale(db: Session) -> int:
    """N02: việc queued/running bị bỏ dở (worker chết) → trả về hàng đợi."""
    cutoff = utcnow() - timedelta(minutes=STALE_MINUTES)
    n = db.execute(
        update(CrawlJob)
        .where(CrawlJob.status.in_(("queued", "running")), func.coalesce(CrawlJob.started_at, CrawlJob.created_at) < cutoff)
        .values(status="pending", started_at=None)
    ).rowcount
    db.commit()
    return n or 0


def dispatch(db: Session) -> list[int]:
    """Chọn việc để giao cho worker. Gọi định kỳ (Celery beat mỗi phút) và ngay khi tạo vòng mới."""
    recover_stale(db)
    ok, _ = can_run_now(db)
    if not ok:
        return []
    per = int(get_setting(db, "max_running").get("per_connector", 2))
    now = utcnow()
    picked: list[int] = []
    for src in db.scalars(select(EnrichSource).where(EnrichSource.enabled.is_(True))):
        c = registry.get(src.code)
        if not c or c.kind != "http":
            continue
        busy = db.scalar(
            select(func.count()).select_from(CrawlJob).where(CrawlJob.connector == src.code, CrawlJob.status.in_(("queued", "running")))
        ) or 0
        room = per - busy
        if room <= 0:
            continue
        ids = list(
            db.scalars(
                select(CrawlJob.id)
                .join(EnrichRun, EnrichRun.id == CrawlJob.run_id, isouter=True)
                .where(
                    CrawlJob.connector == src.code,
                    CrawlJob.status == "pending",
                    (CrawlJob.next_attempt_at.is_(None)) | (CrawlJob.next_attempt_at <= now),
                    (EnrichRun.id.is_(None)) | (EnrichRun.status == "running"),
                )
                .order_by(CrawlJob.id)
                .limit(room)
            )
        )
        if ids:
            db.execute(update(CrawlJob).where(CrawlJob.id.in_(ids)).values(status="queued", started_at=now))
            picked += ids
    db.commit()
    if not picked:
        _finish_runs(db)
    return picked


# ------------------------------------------------------------------ giới hạn tốc độ + robots.txt (A08)


SLOT_MARGIN_S = 0.1  # đệm cho độ trễ giữa lúc đặt lượt và lúc request thực sự đi → khoảng cách thực tế luôn ≥ giới hạn


def reserve_slot(db: Session, domain: str, interval: float) -> float:
    """Đặt lượt gọi tiếp theo cho tên miền. Trả về số giây phải chờ trước khi gọi."""
    if interval > 0:
        interval += SLOT_MARGIN_S
    for _ in range(3):
        now = utcnow()
        slot = db.scalar(select(DomainSlot).where(DomainSlot.domain == domain).with_for_update(of=DomainSlot))
        if slot is None:
            db.add(DomainSlot(domain=domain, next_at=now + timedelta(seconds=interval)))
            try:
                db.commit()
                return 0.0
            except IntegrityError:
                db.rollback()
                continue
        start = max(now, slot.next_at)
        slot.next_at = start + timedelta(seconds=interval)
        db.commit()
        return max(0.0, (start - now).total_seconds())
    raise RuntimeError(f"Không đặt được lượt cho {domain}")


_robots: dict[str, tuple[urllib.robotparser.RobotFileParser | None, datetime]] = {}
ROBOTS_TTL = timedelta(hours=24)


def _http(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": get_settings().enrich_user_agent})


def _logged_get(db: Session, src: EnrichSource, url: str, timeout: float) -> httpx.Response:
    domain = urlparse(url).hostname or ""
    started = utcnow()
    t0 = time.monotonic()
    try:
        with _http(timeout) as client:
            r = client.get(url)
    except httpx.HTTPError as e:
        db.add(FetchLog(source_code=src.code, domain=domain, url=url[:1000], ok=False, error=str(e)[:500], duration_ms=int((time.monotonic() - t0) * 1000), at=started))
        db.commit()
        raise
    ok = r.status_code < 500 and r.status_code != 429
    db.add(FetchLog(source_code=src.code, domain=domain, url=url[:1000], http_status=r.status_code, ok=ok, duration_ms=int((time.monotonic() - t0) * 1000), at=started))
    db.commit()
    return r


def _wait_turn(db: Session, domain: str, interval: float) -> float | None:
    """Chờ tới lượt; nếu phải chờ quá lâu thì trả về số giây để xếp lại hàng đợi."""
    wait = reserve_slot(db, domain, interval)
    if wait > MAX_INLINE_WAIT_S:
        return wait
    if wait > 0:
        time.sleep(wait)
    return None


def robots_allows(db: Session, src: EnrichSource, url: str, interval: float, timeout: float) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    cached = _robots.get(base)
    if not cached or utcnow() - cached[1] > ROBOTS_TTL:
        rp = urllib.robotparser.RobotFileParser()
        _wait_turn(db, p.hostname or "", interval)
        try:
            r = _logged_get(db, src, base + "/robots.txt", timeout)
            if r.status_code >= 500:
                rp = None  # máy chủ lỗi → coi như cấm, thử lại lần sau
            elif r.status_code >= 400:
                rp.parse([])  # không có robots.txt → được phép
            else:
                rp.parse(r.text.splitlines())
        except httpx.HTTPError:
            rp = None
        _robots[base] = (rp, utcnow())
        cached = _robots[base]
    rp = cached[0]
    return bool(rp and rp.can_fetch(get_settings().enrich_user_agent, url))


# ------------------------------------------------------------------ chạy một việc


@dataclass
class JobResult:
    status: str
    retry_in: float | None = None  # giây — worker xếp lại việc sau ngần này
    applied: Applied | None = None


def _fail(db: Session, job: CrawlJob, src: EnrichSource, msg: str) -> JobResult:
    job.error = msg[:2000]
    max_retries = int(sources.setting(src, "max_retries", 3))
    if job.attempts < max_retries:
        job.status = "pending"
        job.next_attempt_at = utcnow() + timedelta(seconds=60 * 2 ** (job.attempts - 1))
    else:
        job.status = "failed"
        job.finished_at = utcnow()
    db.commit()
    check_error_rate(db, src)
    return JobResult(job.status)


def _same_site(host: str, base: str) -> bool:
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return bool(host) and strip(host) == strip(base)


def run_job(db: Session, job_id: int) -> JobResult:
    job = db.get(CrawlJob, job_id)
    if not job or job.status not in ("queued", "pending"):
        return JobResult(job.status if job else "missing")
    src = db.get(EnrichSource, job.connector)
    c = registry.get(job.connector)
    if not src or not c or c.kind != "http" or not src.enabled:
        job.status = "pending"
        db.commit()
        return JobResult("pending")
    ok, _ = can_run_now(db)
    if not ok:
        job.status = "pending"
        db.commit()
        return JobResult("pending")

    job.status = "running"
    job.attempts += 1
    job.started_at = utcnow()
    db.commit()

    interval = float(sources.setting(src, "min_interval_s"))
    timeout = float(sources.setting(src, "timeout_s", 20))
    total = Applied()
    try:
        urls = c.urls_for(job.mst, db.get(EnrichCompany, job.mst))
        if not urls:
            raise NotFound()
        first = set(urls)
        queue = list(urls)
        visited: set[str] = set()
        max_pages = int(sources.setting(src, "max_pages", len(urls)) or len(urls))
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            is_first = url in first
            domain = urlparse(url).hostname or ""
            if not robots_allows(db, src, url, interval, timeout):
                if not is_first:
                    continue  # trang phụ bị robots.txt chặn: bỏ qua trang đó
                job.status = "failed"
                job.error = f"robots.txt không cho phép: {url}"
                job.finished_at = utcnow()
                db.commit()
                return JobResult("failed")
            retry = _wait_turn(db, domain, interval)
            if retry is not None:
                job.status = "queued"
                db.commit()
                return JobResult("queued", retry_in=retry)
            r = _logged_get(db, src, url, timeout)
            if r.status_code >= 400 and not is_first:
                continue
            if r.status_code == 404:
                raise NotFound()
            if r.status_code >= 400:
                return _fail(db, job, src, f"HTTP {r.status_code} khi tải {url}")
            ctype = r.headers.get("content-type", "").split(";")[0]
            page, _new = raw_store.save_page(db, src.code, str(r.url), r.content, ctype, r.status_code, mst=job.mst)
            facts = c.parse(job.mst, str(r.url), r.content, ctype)
            total.add(
                apply_facts(
                    db,
                    job.mst,
                    facts,
                    Origin(source=src, source_url=str(r.url), content_hash=page.content_hash, method=facts.method, source_page_id=page.id),
                )
            )
            # chỉ đi tiếp trong cùng website (A08: không thu thập diện rộng)
            base_host = urlparse(urls[0]).hostname or ""
            for nxt in facts.follow:
                h = urlparse(nxt).hostname or ""
                if nxt not in visited and nxt not in queue and _same_site(h, base_host):
                    queue.append(nxt)
        job.status = "done"
    except NotFound:
        job.status = "not_found"
    except NeedsHuman as e:
        job.status = "manual"
        job.error = str(e)[:2000] or "Nguồn yêu cầu xác minh thủ công (captcha)"
    except httpx.HTTPError as e:
        db.rollback()
        return _fail(db, job, src, f"Lỗi mạng: {e}")
    except Exception as e:  # noqa: BLE001 — lỗi bóc tách: ghi lại, không làm sập worker
        db.rollback()
        log.exception("Connector %s lỗi với MST %s", src.code, job.mst)
        return _fail(db, job, src, f"Lỗi bóc tách: {e}")
    job.error = "" if job.status == "done" else job.error
    job.finished_at = utcnow()
    db.commit()
    return JobResult(job.status, applied=total)


# ------------------------------------------------------------------ tự tạm dừng nguồn hỏng (A13)


def error_rate(db: Session, source_code: str) -> tuple[int, int]:
    since = utcnow() - ERROR_WINDOW
    rows = db.execute(
        select(FetchLog.ok, func.count()).where(FetchLog.source_code == source_code, FetchLog.at >= since).group_by(FetchLog.ok)
    ).all()
    counts = {bool(ok): n for ok, n in rows}
    return counts.get(False, 0), counts.get(False, 0) + counts.get(True, 0)


def check_error_rate(db: Session, src: EnrichSource) -> bool:
    """True nếu vừa tự tạm dừng nguồn."""
    bad, total = error_rate(db, src.code)
    if not src.enabled or total < ERROR_MIN_SAMPLE or bad / total <= ERROR_RATE:
        return False
    src.enabled = False
    src.paused_at = utcnow()
    src.paused_reason = f"Tự tạm dừng: {bad}/{total} request lỗi trong 1 giờ (> {int(ERROR_RATE * 100)}%)."
    db.commit()
    log.warning("Tạm dừng connector %s: %s", src.code, src.paused_reason)
    try:
        from app.services.notify import send_mail

        send_mail(
            get_settings(),
            f"[LeadScan] Nguồn dữ liệu “{src.name}” đã tự tạm dừng",
            f"{src.paused_reason}\n\nKiểm tra nguồn (có thể đã đổi giao diện) rồi bật lại ở trang Làm giàu theo MST → Nguồn.",
        )
    except Exception:  # noqa: BLE001 — gửi mail lỗi không chặn việc tạm dừng
        log.exception("Không gửi được cảnh báo tạm dừng nguồn")
    return True


# ------------------------------------------------------------------ bóc tách lại từ bản gốc (A09)


def reparse_source(db: Session, source_code: str) -> dict:
    """Bóc tách lại mọi bản gốc đã lưu của một connector tự động — không tải lại lần nào."""
    c = registry.get(source_code)
    src = db.get(EnrichSource, source_code)
    if not c or not src or c.kind != "http":
        raise RunError("Chỉ bóc tách lại được nguồn tự động có bản gốc đã lưu.")
    total = Applied()
    pages = errors = 0
    touched: set[str] = set()
    for page in db.scalars(select(SourcePage).where(SourcePage.source_code == source_code, SourcePage.mst.is_not(None))).all():
        mst = page.mst
        try:
            data = raw_store.get(page.storage_key)
            facts = c.parse(mst, page.url, data, page.content_type)
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        pages += 1
        total.add(
            apply_facts(
                db,
                mst,
                facts,
                Origin(source=src, source_url=page.url, content_hash=page.content_hash, method="luat", source_page_id=page.id, fetched_at=page.fetched_at),
                recompute=False,
            )
        )
        touched.add(mst)
    merge.recompute_companies(db, touched)
    db.commit()
    return {"pages": pages, "errors": errors, "evidence": total.evidence, "duplicates": total.duplicates}


# ------------------------------------------------------------------ tiến trình (A11)


def progress(db: Session, run: EnrichRun) -> dict:
    rows = db.execute(
        select(CrawlJob.connector, CrawlJob.status, func.count()).where(CrawlJob.run_id == run.id).group_by(CrawlJob.connector, CrawlJob.status)
    ).all()
    srcs = sources.all_sources(db)
    by: dict[str, dict] = {}
    for code, status, n in rows:
        by.setdefault(code, {})[status] = n
    out = []
    eta = 0.0
    for code in run.connectors:
        counts = by.get(code, {})
        c = registry.get(code)
        src = srcs.get(code)
        total = sum(counts.values())
        remaining = sum(counts.get(s, 0) for s in ("pending", "queued", "running"))
        per_job = 0
        if c and c.kind == "http":
            try:
                per_job = int(sources.setting(src, "max_pages", 0) or 0) or len(c.urls("0000000000"))
            except NotImplementedError:
                per_job = 1
        seconds = remaining * per_job * float(sources.setting(src, "min_interval_s")) if src and per_job else 0
        eta = max(eta, seconds)  # các tên miền chạy song song → vòng xong khi nguồn chậm nhất xong
        out.append(
            {
                "connector": code,
                "name": src.name if src else code,
                "kind": c.kind if c else "",
                "enabled": bool(src and src.enabled),
                "paused_reason": src.paused_reason if src else "",
                "total": total,
                "done": counts.get("done", 0),
                "not_found": counts.get("not_found", 0),
                "failed": counts.get("failed", 0),
                "manual": counts.get("manual", 0),
                "skipped": counts.get("skipped", 0),
                "remaining": remaining,
                "eta_seconds": int(seconds),
            }
        )
    return {"connectors": out, "eta_seconds": int(eta)}


def domain_gaps(db: Session, hours: int = 24) -> list[dict]:
    """A08 — bằng chứng: khoảng cách nhỏ nhất giữa 2 request liên tiếp tới cùng tên miền trong `hours` giờ qua."""
    since = utcnow() - timedelta(hours=hours)
    out: dict[str, dict] = {}
    last: dict[str, datetime] = {}
    for domain, at in db.execute(select(FetchLog.domain, FetchLog.at).where(FetchLog.at >= since).order_by(FetchLog.domain, FetchLog.at)):
        d = out.setdefault(domain, {"domain": domain, "requests": 0, "min_gap_s": None})
        d["requests"] += 1
        if domain in last:
            gap = (at - last[domain]).total_seconds()
            d["min_gap_s"] = gap if d["min_gap_s"] is None else min(d["min_gap_s"], gap)
        last[domain] = at
    return sorted(out.values(), key=lambda d: -d["requests"])
