"""Quét danh sách doanh nghiệp từ bảng xếp hạng PROFIT500 (profit500.vn) vào kho knowledge_companies.

Nguồn (Vietnam Report):
  • Danh sách: GET /Charts/SearchBusiness?ChartId=&Year=&PageSize=&PageNumber=  → JSON, Result.Data là HTML các dòng
    (hạng, logo, tên + link hồ sơ, CEO, MST, ngành nghề).
  • Hồ sơ:     /Thong-tin-doanh-nghiep/<TEN>-Chart--<MÃ DN>-<NĂM>.html → tab "Giới thiệu chung" (#GeneralIntroduction):
    bảng thông tin (tên tiếng Anh, xếp hạng, MST, mã CK, trụ sở, tel, fax, email, website, năm thành lập, ngành)
    và đoạn "Giới thiệu".

robots.txt của trang cho phép 2 đường dẫn trên. Script đi chậm (mặc định nghỉ 1 giây giữa các request),
có User-Agent riêng và ghi nguồn (source_url) cho từng doanh nghiệp — trang yêu cầu ghi rõ nguồn
"Vietnam Report" khi dùng lại thông tin.

Chạy:  python -m app.cli crawl-profit500 --chart 12 --year 2026 [--limit 20] [--update]
"""

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

from app.db import utcnow
from app.models import KnowledgeCompany
from app.schemas_knowledge import normalize_tax_code

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

# Nhãn trong bảng "Giới thiệu chung" → cột của KnowledgeCompany. Nhãn khác lưu vào `extra`.
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
    """Phần "Giới thiệu chung" của trang hồ sơ → dict theo cột KnowledgeCompany (+ 'extra')."""
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


# ------------------------------------------------------------------ ghi vào DB


@dataclass
class CrawlStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


FIELDS = [
    "name", "name_en", "tax_code", "stock_code", "industry", "address", "province", "phone", "fax", "email",
    "website", "founded_year", "ceo_name", "description", "logo_url", "rank", "rank_label", "rank_list", "rank_year",
]  # fmt: skip
NULLABLE = {"tax_code", "founded_year", "rank", "rank_year"}
LIMITS = {
    "name": 300, "name_en": 300, "tax_code": 20, "stock_code": 20, "industry": 200, "address": 500, "province": 80,
    "phone": 100, "fax": 100, "email": 200, "website": 300, "ceo_name": 150, "logo_url": 500, "rank_label": 100,
    "rank_list": 200,
}  # fmt: skip


def _merge(list_item: dict, profile: dict, chart: int) -> dict:
    """Ghép dòng danh sách + hồ sơ. Hồ sơ ưu tiên hơn, trừ hạng/năm lấy theo bảng đang quét."""
    data = {**list_item, **{k: v for k, v in profile.items() if v not in (None, "", {})}}
    data["rank"] = list_item.get("rank") or profile.get("rank")
    data["rank_year"] = list_item.get("rank_year")
    data["rank_list"] = f"PROFIT500 – {CHARTS.get(chart, f'chart {chart}')}"
    data["tax_code"] = normalize_tax_code(data.get("tax_code"))
    for k, n in LIMITS.items():
        if isinstance(data.get(k), str):
            data[k] = data[k][:n]
    return data


def upsert(db: Session, data: dict, *, update: bool) -> str:
    """Thêm/cập nhật 1 doanh nghiệp. Trả về 'created' | 'updated' | 'skipped'.

    Tìm bản ghi cũ theo (source, source_id), không có thì theo MST. Khi cập nhật chỉ ghi đè các trường
    lấy từ nguồn; trạng thái AI và ghi chú nội bộ giữ nguyên.
    """
    k = None
    if data.get("source_id"):
        k = db.scalar(select(KnowledgeCompany).where(KnowledgeCompany.source == SOURCE, KnowledgeCompany.source_id == data["source_id"]))
    if k is None and data.get("tax_code"):
        k = db.scalar(select(KnowledgeCompany).where(KnowledgeCompany.tax_code == data["tax_code"]))
    if k is not None and not update:
        return "skipped"

    created = k is None
    if created:
        k = KnowledgeCompany(source=SOURCE, source_id=data.get("source_id"))
        db.add(k)
    elif k.source == SOURCE and not k.source_id:
        k.source_id = data.get("source_id")
    for f in FIELDS:
        v = data.get(f)
        if v in (None, "") and not created:
            continue  # nguồn không có giá trị → giữ dữ liệu cũ
        if v is None and f not in NULLABLE:
            v = ""
        setattr(k, f, v)
    k.source_url = data.get("source_url") or k.source_url
    k.extra = {**(k.extra or {}), **(data.get("extra") or {})}
    k.crawled_at = utcnow()
    db.commit()
    return "created" if created else "updated"


def crawl(
    db: Session,
    *,
    chart: int = 12,
    year: int,
    limit: int = 0,
    page_size: int = 50,
    update: bool = False,
    delay: float = 1.0,
    client: Profit500Client | None = None,
    progress: Callable[[str], None] = print,
) -> CrawlStats:
    """Quét bảng xếp hạng `chart` năm `year`. limit=0 → quét hết."""
    own = client is None
    client = client or Profit500Client(delay=delay)
    stats = CrawlStats()
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
                    # Đã có và không cập nhật → khỏi tải trang hồ sơ
                    if not update and item.get("source_id") and db.scalar(
                        select(KnowledgeCompany.id).where(KnowledgeCompany.source == SOURCE, KnowledgeCompany.source_id == item["source_id"])
                    ):
                        stats.skipped += 1
                        progress(f"{label} — đã có, bỏ qua")
                        continue
                    profile = client.profile(item["source_url"])
                    result = upsert(db, _merge(item, profile, chart), update=update)
                    setattr(stats, result, getattr(stats, result) + 1)
                    progress(f"{label} — {({'created': 'thêm mới', 'updated': 'cập nhật', 'skipped': 'đã có, bỏ qua'})[result]}")
                except Exception as e:  # 1 doanh nghiệp lỗi không dừng cả lượt quét
                    db.rollback()
                    stats.errors.append(f"{item.get('name')}: {e}")
                    progress(f"{label} — LỖI: {e}")
            if page * page_size >= total:
                break
            page += 1
    finally:
        if own:
            client.close()
    return stats
