"""Website của chính doanh nghiệp (giai đoạn 4).

Chỉ tải website đã biết của doanh nghiệp (trường website / tên miền trong hồ sơ — từ ĐKKD, công bố thông tin, nhập tay);
không tìm website qua Google (mục 2). Từ trang chủ chỉ đi tiếp tới vài trang cùng website có từ khoá giới thiệu /
liên hệ / ban lãnh đạo (tối đa max_pages trang), qua giới hạn tốc độ + robots.txt của runner.

Bóc tách:
  cau_truc  JSON-LD schema.org (Organization: điện thoại, email; Person: tên + jobTitle + email)
  luat      dòng "Ông Nguyễn Văn A – Tổng Giám đốc", "Tổng Giám đốc: Ông Nguyễn Văn A", hoặc tên rồi chức danh ở dòng kế
Chỉ nhận người khi từ đầu là họ Việt Nam phổ biến (trang web nhiễu hơn báo cáo quản trị).
Email chỉ nhận khi cùng tên miền doanh nghiệp; email đứng ngay cạnh tên người là email công việc của người đó.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from app.enrich.connectors.base import CompanyFact, Connector, Facts, PersonFact
from app.enrich.emails import email_matches_name
from app.enrich.governance import TITLE_RE, clean_name
from app.enrich.normalize import bo_dau, normalize_phone, normalize_website

SURNAMES = {
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo", "dang", "bui", "do", "ho", "ngo", "duong",
    "ly", "dinh", "dao", "doan", "truong", "lam", "mai", "trinh", "luong", "cao", "chu", "chau", "ta", "tang", "ha",
    "kieu", "khuc", "lai", "lu", "lo", "ma", "nghiem", "quach", "thai", "thach", "tieu", "tong", "to", "trieu", "van",
    "vuong", "la", "lieu", "mac", "ninh", "nong", "ong", "phi", "phung", "quan", "dam", "giang", "han", "hua", "kim",
    "lang", "luu", "mong", "nham", "ninh", "on", "tham", "thieu", "tiet", "ton", "trac", "uong", "vien", "yen", "au",
    "bach", "banh", "cung", "diep", "doan", "dong", "du", "gia", "hau", "hong", "khong", "khu", "lac", "le", "quang",
}
FOLLOW_WORDS = re.compile(
    r"gioi-?thieu|ve-?chung-?toi|about|lien-?he|contact|ban-?lanh-?dao|lanh-?dao|leadership|management|board|"
    r"doi-?ngu|nhan-?su-?chu-?chot|co-?cau-?to-?chuc|hoi-?dong-?quan-?tri|ban-?dieu-?hanh|ban-?giam-?doc"
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+84|\b0)(?:[\s.\-]?\d){9,10}\b")


def is_person_name(name: str | None) -> bool:
    if not name:
        return False
    parts = bo_dau(name).split()
    return 2 <= len(parts) <= 5 and parts[0] in SURNAMES


def _person_from_line(line: str) -> tuple[str, str] | None:
    """('Nguyễn Văn A', 'Tổng Giám đốc') từ 'Ông Nguyễn Văn A – Tổng Giám đốc' hoặc 'Tổng Giám đốc: Ông Nguyễn Văn A'."""
    m = TITLE_RE.search(line)
    if not m:
        return None
    if m.start() > 0:  # tên trước, chức danh sau
        name = clean_name(re.split(r"\s[-–(,:|]\s?", line[: m.start()].strip())[0])
        title = re.split(r"[.;|]", line[m.start():])[0].strip(" -–,:")
        if is_person_name(name):
            return name, title[:120]
    # chức danh trước, tên sau: "Chủ tịch HĐQT: Ông Nguyễn Văn A", "Tổng Giám đốc Nguyễn Văn A"
    words = [w for w in re.split(r"\s+", line[m.end():].strip()) if w and not re.fullmatch(r"[:–\-,|]+", w)]
    for k in range(0, 5):  # bỏ qua tối đa 4 từ phần đuôi chức danh ("… Phụ trách Kinh doanh")
        rest = [w.strip(":,") for w in words[k:]]
        if rest and bo_dau(rest[0]) in ("ong", "ba"):
            rest = rest[1:]
        for n in range(min(5, len(rest)), 1, -1):  # cụm tên dài nhất hợp lệ
            name = clean_name(" ".join(rest[:n]))
            if is_person_name(name):
                title = " ".join([line[m.start(): m.end()], *[w.strip(":,") for w in words[:k]]]).strip(" :–-")
                return name, title[:120]
    return None


class CompanyWebsite(Connector):
    code = "website"
    name = "Website doanh nghiệp"
    kind = "http"
    domain = ""
    default_trust = 0.7
    legal_basis = (
        "Thông tin doanh nghiệp tự công bố trên website của chính doanh nghiệp (giới thiệu, liên hệ, ban lãnh đạo). "
        "Chỉ tải website đã có trong hồ sơ, tối đa vài trang mỗi doanh nghiệp, tôn trọng robots.txt và giới hạn tốc độ."
    )
    defaults = {"min_interval_s": 2.0, "timeout_s": 20, "max_retries": 1, "recrawl_days": 180, "max_pages": 5}

    def urls(self, mst: str) -> list[str]:
        raise NotImplementedError

    def urls_for(self, mst: str, company) -> list[str]:
        site = getattr(company, "website", None) or (f"https://{company.domain}" if getattr(company, "domain", None) else None)
        if not site:
            return []
        site, _ = normalize_website(site)
        return [site + "/"] if site else []

    def parse(self, mst: str, url: str, content: bytes, content_type: str) -> Facts:
        from bs4 import BeautifulSoup

        host = (urlparse(url).hostname or "").lower()
        domain = host[4:] if host.startswith("www.") else host
        soup = BeautifulSoup(content, "html.parser")
        facts = Facts(method="luat")
        emails: set[str] = set()
        phones: set[str] = set()

        # ---- tầng cấu trúc: JSON-LD
        structured_people = 0
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
            except (ValueError, TypeError):
                continue
            stack = data if isinstance(data, list) else [data]
            while stack:
                obj = stack.pop()
                if isinstance(obj, list):
                    stack.extend(obj)
                    continue
                if not isinstance(obj, dict):
                    continue
                t = obj.get("@type")
                types = t if isinstance(t, list) else [t]
                if any(x in ("Organization", "Corporation", "LocalBusiness") for x in types):
                    if obj.get("telephone"):
                        phones.add(str(obj["telephone"]))
                    if obj.get("email"):
                        emails.add(str(obj["email"]).replace("mailto:", ""))
                if "Person" in types and obj.get("name") and obj.get("jobTitle"):
                    name = clean_name(str(obj["name"]))
                    if is_person_name(name):
                        email = str(obj.get("email") or "").replace("mailto:", "").strip().lower()
                        ok = email.endswith("@" + domain) and email_matches_name(email, name)
                        facts.people.append(PersonFact(name, str(obj["jobTitle"])[:120], f"JSON-LD: {obj.get('name')} — {obj.get('jobTitle')}", email=email if ok else None))
                        structured_people += 1
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
        if structured_people:
            facts.method = "cau_truc"

        # ---- liên kết: mailto, tel, trang nên đi tiếp
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                emails.add(href[7:].split("?")[0])
            elif href.lower().startswith("tel:"):
                phones.add(href[4:])
            else:
                full = urljoin(url, href).split("#")[0]
                path_text = bo_dau(urlparse(full).path + " " + a.get_text(" ")).replace(" ", "-")
                fh = (urlparse(full).hostname or "").lower()
                same_site = (fh[4:] if fh.startswith("www.") else fh) == domain
                if urlparse(full).scheme in ("http", "https") and same_site and FOLLOW_WORDS.search(path_text):
                    facts.follow.append(full)
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        lines = [" ".join(x.split()) for x in soup.get_text("\n").split("\n") if x.strip()]
        text = "\n".join(lines)
        emails |= set(EMAIL_RE.findall(text))
        phones |= set(PHONE_RE.findall(text))

        # ---- tầng luật: người + chức danh trong văn bản
        seen = {(bo_dau(p.ho_ten), bo_dau(p.chuc_danh)) for p in facts.people}
        for i, ln in enumerate(lines):
            if len(ln) > 160:
                continue
            got = _person_from_line(ln)
            if not got and i + 1 < len(lines) and is_person_name(clean_name(ln)):
                nxt = lines[i + 1]
                if TITLE_RE.match(nxt.strip()) and len(nxt) <= 80:
                    got = (clean_name(ln), nxt.strip(" -–,:"))
            if not got:
                continue
            name, title = got
            key = (bo_dau(name), bo_dau(title))
            if key in seen:
                continue
            seen.add(key)
            # email của người: cùng dòng hoặc dòng kế tiếp, cùng tên miền DN, và phần trước @ khớp tên người
            near = " ".join(lines[i : i + 2])
            em = next(
                (e.lower() for e in EMAIL_RE.findall(near) if e.lower().endswith("@" + domain) and email_matches_name(e, name)),
                None,
            )
            facts.people.append(PersonFact(name, title, ln[:300], email=em))

        person_emails = {p.email for p in facts.people if p.email}
        for e in sorted(emails):
            e = e.strip().lower()
            if e.endswith("@" + domain) and e not in person_emails:
                facts.contacts.append(("email", e))
        for ph in sorted(phones):
            n = normalize_phone(ph)
            if n:
                facts.contacts.append(("phone", n))
        if facts.contacts or facts.people:
            facts.company.append(CompanyFact("website", f"https://{host}", f"Trang {url}"))
        facts.follow = list(dict.fromkeys(facts.follow))[:10]
        return facts
