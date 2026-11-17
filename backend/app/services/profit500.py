"""Quét danh sách doanh nghiệp từ bảng xếp hạng PROFIT500 (profit500.vn) vào phân hệ làm giàu dữ liệu theo MST.

Nguồn (Vietnam Report):
  • Danh sách: GET /Charts/SearchBusiness?ChartId=&Year=&PageSize=&PageNumber=  → JSON, Result.Data là HTML các dòng
    (hạng, logo, tên + link hồ sơ, CEO, MST, ngành nghề).
  • Hồ sơ:     /Thong-tin-doanh-nghiep/<TEN>-Chart--<MÃ DN>-<NĂM>.html → tab "Giới thiệu chung" (#GeneralIntroduction):
    bảng thông tin (tên tiếng Anh, xếp hạng, MST, mã CK, trụ sở, tel, fax, email, website, năm thành lập, ngành)
    và đoạn "Giới thiệu".

robots.txt của trang cho phép 2 đường dẫn trên. Script đi chậm (mặc định nghỉ 1 giây giữa các request),
có User-Agent riêng và ghi nguồn (source_url) cho từng doanh nghiệp — trang yêu cầu ghi rõ nguồn
"Vietnam Report" khi dùng lại thông tin.

Mỗi lượt quét = một lô (EnrichBatch) của nguồn "profit500" (tin cậy 0,7), bắt buộc khai mục đích sử dụng được phép.
Doanh nghiệp không có MST không vào được phân hệ (MST là khoá) → bỏ qua và đếm. Tên CEO, logo không lưu.

Chạy:  python -m app.cli crawl-profit500 --chart 12 --year 2026 --purposes ban_hang_b2b [--limit 20] [--update]
"""

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enrich import sources
from app.enrich.connectors.base import SignalFact
from app.enrich.importer import Row, existing_msts, save_batch, split_emails, split_phones
from app.enrich.normalize import parse_mst
from app.models import AdminUser
from app.models_enrich import CompanyEvidence, EnrichBatch

log = logging.getLogger("leadscan.profit500")

BASE_URL = "https://profit500.vn"
USER_AGENT = "LeadScanBot/1.0 (+https://leadscan.net)"
SOURCE = "profit500"

CHARTS = {
    12: "Top 500 Doanh nghiệp lợi nhuận tốt nhất Việt Nam",
    13: "Top 500 Doanh nghiệp tư nhân lợi nhuận tốt nhất Việt Nam",
    17: "Top 50 Doanh nghiệp lợi nhuận xuất sắc Việt Nam",
}

PROFILE_RE = re.compile(r"-Chart--(\d+)-(\d{4})\.html", re.I)

# Nhãn trong bảng "Giới thiệu chung" → khoá dữ liệu (xem enrich_row). Nhãn khác lưu vào `extra`.
LABEL_MAP = {
    "tên tiếng anh": "name_en",
    "xếp hạng profit500": "rank_label",
    "mã số thuế": "tax_code",
    "mã chứng khoán": "stock_code",
    "trụ sở chính": "address",
    "tel": "phone",
    "điện thoại": "phone",
    "fax": "fax",
    "email": "email",
    "website": "website",
    "năm thành lập": "founded_year",
    "ngành nghề": "industry",
}
NOT_LISTED = {"chưa niêm yết", "chua niem yet", "-", "n/a"}


# ------------------------------------------------------------------ đọc HTML


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def decode_cfemail(hexstr: str) -> str:
    """Giải mã email bị Cloudflare che (data-cfemail): byte đầu là khoá XOR."""
    try:
        data = bytes.fromhex(hexstr)
        return bytes(b ^ data[0] for b in data[1:]).decode("utf-8")
    except (ValueError, IndexError):
        return ""


def parse_profile_url(url: str) -> tuple[str | None, int | None]:
    """'/Thong-tin-doanh-nghiep/X-Chart--261-2026.html' → ('261', 2026)."""
    m = PROFILE_RE.search(url or "")
    return (m.group(1), int(m.group(2))) if m else (None, None)


def province_from_address(address: str) -> str:
    """Lấy tỉnh/thành từ phần cuối địa chỉ: 'Xã A - Huyện B - Tỉnh Long An' → 'Long An'."""
    parts = [p.strip(" .") for p in re.split(r"\s+-\s+|,", address or "") if p.strip(" .")]
    if not parts:
        return ""
    last = re.sub(r"^(tỉnh|thành phố|tp\.?|t\.p\.?)\s+", "", parts[-1], flags=re.I).strip()
    return last[:80] if len(last) <= 40 else ""


def parse_list_html(html: str) -> list[dict]:
    """Các dòng trong Result.Data của /Charts/SearchBusiness."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select(".data-item"):
        link = row.select_one("a.title")
        if not link or not link.get("href"):
            continue
        href = urljoin(BASE_URL, link["href"].split("#")[0])
        source_id, year = parse_profile_url(href)
        rank_txt = _text(row.select_one(".stt"))
        img = row.select_one("img")
        logo = img.get("src", "") if img else ""
        if "Default" in logo:  # ảnh mặc định của trang, không phải logo thật
            logo = ""
        info: dict[str, str] = {}
        for col in row.select(".row > div"):
            label = _text(col.select_one("span")).rstrip(":").strip().lower()
            value = _text(col)
            value = value.split(":", 1)[1].strip() if ":" in value else ""
            if label:
                info[label] = value
        items.append(
            {
                "name": _text(link),
                "source_url": href,
                "source_id": source_id,
                "rank_year": year,
                "rank": int(rank_txt) if rank_txt.isdigit() else None,
                "logo_url": logo,
                "ceo_name": info.get("ceo", ""),
                "tax_code": info.get("mst", ""),
                "industry": info.get("ngành nghề", ""),
            }
        )
    return items


def parse_profile_html(html: str) -> dict:
    """Phần "Giới thiệu chung" của trang hồ sơ → dict theo khoá LABEL_MAP (+ 'extra')."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#GeneralIntroduction") or soup
    out: dict = {"extra": {}}

    title = soup.select_one("h4.title")
    if title:
        out["name"] = _text(title)

    for row in root.select(".info-row"):
        label = _text(row.select_one(".info-label")).rstrip(":").strip()
        value_el = row.select_one(".info-value")
        if not label or value_el is None:
            continue
        cf = value_el.select_one("[data-cfemail]")
        if cf is not None:
            value = decode_cfemail(cf["data-cfemail"])
        else:
            a = value_el.select_one("a[href^='http']")
            value = _text(value_el) or (a["href"] if a else "")
        key = LABEL_MAP.get(label.lower())
        if key:
            out[key] = value
        elif value:
            out["extra"][label] = value

    intro = root.select_one(".dn-gioi-thieu")
    if intro:
        for h in intro.select("h1, h2, h3, .intro-title"):
            h.decompose()
        lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in intro.get_text("\n").splitlines()]
        text = "\n".join(ln for ln in lines if ln)
        out["description"] = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Chuẩn hoá
    if "stock_code" in out and out["stock_code"].strip().lower() in NOT_LISTED:
        out["stock_code"] = ""
    if "founded_year" in out:
        m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", out["founded_year"])
        out["founded_year"] = int(m.group(1)) if m else None
    if "rank_label" in out:
        out["rank_label"] = out["rank_label"].replace(" ", "")
        m = re.match(r"(\d+)", out["rank_label"])
        if m:
            out["rank"] = int(m.group(1))
    if out.get("website") and not re.match(r"https?://", out["website"]):
        out["website"] = "http://" + out["website"]
    if out.get("address"):
        out["province"] = province_from_address(out["address"])
    return out


# ------------------------------------------------------------------ gọi trang


class Profit500Client:
    def __init__(self, delay: float = 1.0, timeout: float = 30.0, retries: int = 3, client: httpx.Client | None = None):
        self.delay = delay
        self.retries = retries
        self.http = client or httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.8"},
        )
        self._last = 0.0

    def _get(self, url: str, **kw) -> httpx.Response:
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.http.get(url, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                return r
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if attempt == self.retries:
                    raise
                log.warning("Lỗi tải %s (lần %d): %s — thử lại", url, attempt, e)
                time.sleep(self.delay * 2 * attempt)
        raise RuntimeError("unreachable")

    def list_page(self, chart: int, year: int, page: int, page_size: int = 50) -> tuple[int, list[dict]]:
        r = self._get(
            "/Charts/SearchBusiness",
            params={"Year": year, "ChartId": chart, "PageSize": page_size, "BusinessName": "", "PageNumber": page},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        data = r.json()
        if not data.get("Succeeded"):
            raise RuntimeError(f"Trang trả lỗi khi lấy danh sách: {data}")
        result = data.get("Result") or {}
        return int(result.get("TotalItems") or 0), parse_list_html(result.get("Data") or "")

    def profile(self, url: str) -> dict:
        return parse_profile_html(self._get(url).text)

    def close(self):
        self.http.close()


# ------------------------------------------------------------------ ghi vào phân hệ làm giàu


@dataclass
class CrawlStats:
    created: int = 0  # MST mới vào phân hệ
    updated: int = 0  # MST đã có, ghi thêm bằng chứng PROFIT500
    skipped: int = 0  # đã có bằng chứng PROFIT500 và không --update
    no_mst: int = 0  # không có MST hợp lệ → không vào được phân hệ
    errors: list[str] = field(default_factory=list)
    batch_id: int | None = None


def _merge(list_item: dict, profile: dict, chart: int) -> dict:
    """Ghép dòng danh sách + hồ sơ. Hồ sơ ưu tiên hơn, trừ hạng/năm lấy theo bảng đang quét."""
    data = {**list_item, **{k: v for k, v in profile.items() if v not in (None, "", {})}}
    data["rank"] = list_item.get("rank") or profile.get("rank")
    data["rank_year"] = list_item.get("rank_year")
    data["rank_list"] = f"PROFIT500 – {CHARTS.get(chart, f'chart {chart}')}"
    return data


def enrich_row(data: dict, *, row_no: int) -> Row | None:
    """Dữ liệu một doanh nghiệp (khoá LABEL_MAP) → dòng của lô làm giàu. Không có MST hợp lệ → None.

    Không lấy: tên CEO (dữ liệu cá nhân), logo. Ngành → "nhóm ngành" (phân loại của bảng xếp hạng, không phải ngành ĐKKD).
    """
    mst = parse_mst(data.get("tax_code")).mst if data.get("tax_code") else None
    if not mst:
        return None
    extra: dict[str, object] = {}
    for src_key, field_ in (
        ("name_en", "ten_tieng_anh"), ("address", "dia_chi"), ("province", "tinh"), ("website", "website"),
        ("industry", "nhom_nganh"), ("founded_year", "nam_thanh_lap"), ("description", "mo_ta"),
    ):  # fmt: skip
        if data.get(src_key) not in (None, ""):
            extra[field_] = data[src_key]
    for src_key, field_ in (("phone", "dien_thoai"), ("fax", "fax")):
        if data.get(src_key) and (nums := split_phones(data[src_key])[0]):
            extra[field_] = nums
    if data.get("email") and (emails := split_emails(data["email"])):
        extra["email"] = emails
    if data.get("stock_code"):
        extra["ma_ck"] = data["stock_code"]
        extra["niem_yet"] = True
    signals = []
    if data.get("rank") or data.get("rank_label"):
        payload = {"bang": data.get("rank_list") or "PROFIT500", "nam": data.get("rank_year"), "hang": data.get("rank"), "nhan": data.get("rank_label") or ""}
        signals.append(SignalFact("xep_hang", payload))
    rank = f" · {data.get('rank_list') or 'PROFIT500'} {data.get('rank_year') or ''} — hạng {data.get('rank_label') or data.get('rank')}" if signals else ""
    name = " ".join(str(data.get("name") or "").split())[:400]
    digest = {"name": name, **extra, "rank": [s.payload for s in signals]}
    return Row(
        row_no=row_no,
        mst=mst,
        name=name,
        raw="",
        extra=extra,
        url=data.get("source_url") or "",
        excerpt=f"PROFIT500{rank}: {name} — Nguồn: Vietnam Report",
        content_hash=hashlib.sha256(json.dumps(digest, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest(),
        signals=signals,
    )


def _profit500_msts(db: Session) -> set[str]:
    return set(db.scalars(select(CompanyEvidence.mst).where(CompanyEvidence.source_code == sources.PROFIT500).distinct()))


def report_for(rows: list[Row], *, skipped: int = 0, no_mst: int = 0, errors: list[str] | None = None) -> dict:
    """Biên bản lô theo cùng dạng nhập file (trang Lô MST hiện được)."""
    from app.enrich.importer import EXTRA_LABELS

    filled: dict[str, int] = {}
    for r in rows:
        for k in r.extra:
            if k in EXTRA_LABELS:
                filled[k] = filled.get(k, 0) + 1
    phones = sum(len(r.extra.get("dien_thoai") or []) for r in rows)
    return {
        "total_rows": len(rows) + skipped + no_mst + len(errors or []),
        "valid": len(rows),
        "duplicate_in_file": 0,
        "invalid": 0,
        "zero_padded": 0,
        "has_header": True,
        "has_name_column": True,
        "invalid_rows": [],
        "duplicate_rows": [],
        "columns": [{"header": EXTRA_LABELS[k], "field": k, "label": EXTRA_LABELS[k], "filled": n} for k, n in filled.items()],
        "ignored_columns": [],
        "sensitive_columns": [],
        "phones": {"ok": phones, "bad": 0, "bad_rows": []},
        "no_tax_code": no_mst,
        "skipped_existing": skipped,
        "errors": (errors or [])[:200],
    }


def save_rows(db: Session, user: AdminUser | None, rows: list[Row], report: dict, *, name: str, list_source: str, purposes: list[str], file_name: str) -> EnrichBatch:
    return save_batch(
        db, user, rows, report,
        name=name, list_source=list_source, purposes=purposes, note="", file_name=file_name,
        file_sha256=hashlib.sha256(json.dumps(sorted(r.content_hash for r in rows)).encode()).hexdigest(),
        source_code=sources.PROFIT500, method="cau_truc",
    )


def crawl(
    db: Session,
    *,
    chart: int = 12,
    year: int,
    purposes: list[str],
    user: AdminUser | None = None,
    limit: int = 0,
    page_size: int = 50,
    update: bool = False,
    delay: float = 1.0,
    client: Profit500Client | None = None,
    progress: Callable[[str], None] = print,
) -> CrawlStats:
    """Quét bảng xếp hạng `chart` năm `year` vào một lô mới của phân hệ làm giàu. limit=0 → quét hết.

    Không --update: doanh nghiệp đã có bằng chứng PROFIT500 thì không tải lại trang hồ sơ.
    Lỗi giữa chừng: những doanh nghiệp đã tải vẫn được ghi thành lô.
    """
    own = client is None
    client = client or Profit500Client(delay=delay)
    stats = CrawlStats()
    have = _profit500_msts(db)
    rows: list[Row] = []
    in_run: set[str] = set()
    done = 0
    try:
        page = 1
        while True:
            total, items = client.list_page(chart, year, page, page_size)
            if page == 1:
                progress(f"{CHARTS.get(chart, chart)} {year}: {total} doanh nghiệp")
            if not items:
                break
            for item in items:
                if limit and done >= limit:
                    return stats
                done += 1
                label = f"[{done}] #{item.get('rank') or '?'} {item['name']}"
                try:
                    listed = parse_mst(item.get("tax_code")).mst if item.get("tax_code") else None
                    if listed and listed in have and not update:
                        stats.skipped += 1
                        progress(f"{label} — đã có, bỏ qua")
                        continue
                    row = enrich_row(_merge(item, client.profile(item["source_url"]), chart), row_no=done)
                    if row is None:
                        stats.no_mst += 1
                        progress(f"{label} — không có MST, bỏ qua")
                        continue
                    if row.mst in in_run:
                        stats.skipped += 1
                        continue
                    in_run.add(row.mst)
                    rows.append(row)
                    progress(f"{label} — {row.mst}")
                except Exception as e:  # 1 doanh nghiệp lỗi không dừng cả lượt quét
                    stats.errors.append(f"{item.get('name')}: {e}")
                    progress(f"{label} — LỖI: {e}")
            if page * page_size >= total:
                break
            page += 1
    finally:
        if own:
            client.close()
        if rows:
            known = existing_msts(db, [r.mst for r in rows])
            stats.created = sum(r.mst not in known for r in rows)
            stats.updated = len(rows) - stats.created
            title = f"{CHARTS.get(chart, chart)} {year}"
            batch = save_rows(
                db, user, rows, report_for(rows, skipped=stats.skipped, no_mst=stats.no_mst, errors=stats.errors),
                name=f"PROFIT500 – {title}", list_source=f"profit500.vn (Vietnam Report) – {title}",
                purposes=purposes, file_name=f"profit500:chart={chart}&year={year}",
            )
            stats.batch_id = batch.id
    return stats
