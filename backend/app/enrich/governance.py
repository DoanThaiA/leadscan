"""Bóc tách thành viên HĐQT, Ban kiểm soát, Ban điều hành từ báo cáo quản trị / báo cáo thường niên (B01, giai đoạn 3).

Ba tầng — tầng sau chỉ chạy khi tầng trước không đủ:
  1. cau_truc  bảng trong tài liệu (mẫu Phụ lục V Thông tư 96/2020/TT-BTC: "Thành viên HĐQT | Chức vụ | Ngày bổ nhiệm…")
  2. luat      dòng văn bản trong từng mục ("Ông Nguyễn Văn A – Chủ tịch HĐQT")
  3. mo_hinh   mô hình ngôn ngữ (app/enrich/llm.py) — chỉ khi bật, lưu đệm theo mã băm nội dung

BẢO VỆ DỮ LIỆU (T09): báo cáo quản trị có mục "Danh sách người có liên quan / người nội bộ" chứa số CCCD, địa chỉ,
quan hệ gia đình. Mọi nội dung từ tiêu đề mục đó trở đi bị CẮT trước khi bóc tách (kể cả trước khi gửi cho mô hình),
và mọi bảng có cột giấy tờ / địa chỉ / quan hệ đều bị bỏ qua. Ngày sinh, trình độ không bao giờ được đọc.
"""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from app.enrich.normalize import bo_dau, parse_date
from app.enrich.titles import TITLES, normalize_title

# ------------------------------------------------------------------ nhận diện

_UP = "AÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬBCDĐEÈÉẺẼẸÊỀẾỂỄỆFGHIÌÍỈĨỊJKLMNOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢPQRSTUÙÚỦŨỤƯỪỨỬỮỰVWXYỲÝỶỸỴZ"
_LO = _UP.lower()
_WORD = f"[{_UP}][{_LO}{_UP}]*"
NAME_RE = re.compile(rf"^{_WORD}(?:\s+{_WORD}){{1,6}}$")
HONORIFIC_RE = re.compile(r"^(?:[oô]ng|b[aà]|mr\.?|mrs\.?|ms\.?)\s+", re.I)
NUMBERING_RE = re.compile(r"^\s*(?:\d+|[ivxIVX]+|[a-z])[.)/]?\s+")
_FOLD = {
    "a": "aàáảãạăằắẳẵặâầấẩẫậ", "e": "eèéẻẽẹêềếểễệ", "i": "iìíỉĩị", "o": "oòóỏõọôồốổỗộơờớởỡợ",
    "u": "uùúủũụưừứửữự", "y": "yỳýỷỹỵ", "d": "dđ",
}


def _tolerant(words: str) -> str:
    """'chu tich' → regex khớp cả 'Chủ tịch' lẫn 'Chu tich' (PDF đôi khi mất dấu khi trích chữ)."""
    out = []
    for ch in words:
        if ch == " ":
            out.append(r"\s+")
        elif ch in _FOLD:
            out.append(f"[{_FOLD[ch]}]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


_TITLE_WORDS = [
    "chu tich", "tong giam doc", "giam doc", "thanh vien", "ke toan truong", "truong ban",
    "kiem soat vien", "uy vien", "nguoi phu trach", "thu ky",
]
TITLE_RE = re.compile(
    rf"(?:{_tolerant('pho')}\s+)?(?:{'|'.join(_tolerant(w) for w in _TITLE_WORDS)})\b",
    re.I,
)
NOT_NAMES = {"thanh vien", "ho va ten", "ho ten", "tong cong", "chuc vu", "ghi chu", "stt"}

# Tiêu đề mục cần CẮT (và mọi thứ sau nó)
SENSITIVE_HEADING = re.compile(
    r"^\s*(?:[ivx]+|\d+)?[.)]?\s*(?:danh sach (?:ve )?nguoi (?:co lien quan|noi bo)|"
    r"giao dich co phieu cua nguoi noi bo|giao dich giua (?:cong ty|thanh vien).{0,40}nguoi (?:co lien quan|noi bo)|"
    r"danh sach co dong)"
)
# Cột bảng chứa dữ liệu cá nhân nhạy cảm → bỏ cả bảng
SENSITIVE_COL = re.compile(r"cmnd|cccd|can cuoc|ho chieu|so giay|ngay cap|noi cap|dia chi|moi quan he|quan he voi|so co phieu|ty le so huu")

GROUP_PATTERNS = [
    ("bks", r"ban kiem soat|\bbks\b|uy ban kiem toan|\bubkt\b|kiem soat vien"),
    ("bdh", r"ban (?:dieu hanh|tong giam doc|giam doc)|\bbdh\b|\bbgd\b|\bbtgd\b"),
    ("hdqt", r"hoi dong quan tri|\bhdqt\b|hoi dong thanh vien|\bhdtv\b"),
    ("ktt", r"ke toan truong"),
]
SECTION_RE = re.compile(r"^\s*(?:[ivx]+|\d+)[.)]?\s+")  # dòng tiêu đề mục đánh số
STOP_SECTION = re.compile(r"dai hoi dong co dong|dao tao|nghi quyet|quyet dinh cua|hoat dong cua|cac van de can luu y|thu lao")

GROUP_DEFAULT_TITLE = {
    "hdqt": "Thành viên HĐQT",
    "bks": "Thành viên Ban kiểm soát",
    "bdh": "Thành viên Ban điều hành",
    "ktt": "Kế toán trưởng",
    "khac": "Khác",
}
BOARD_CODES = {"chu_tich_hdqt", "pho_chu_tich_hdqt", "thanh_vien_hdqt", "chu_tich_hdtv"}
EXEC_CODES = {"tong_giam_doc", "pho_tong_giam_doc", "giam_doc", "pho_giam_doc", "giam_doc_khoi", "thanh_vien_bdh"}
DATE_RE = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b")
END_WORDS = re.compile(r"mien nhiem|tu nhiem|thoi (?:giu|lam)|khong con|cham dut|nghi huu")

CONFIDENCE = {"cau_truc": 0.9, "luat": 0.75, "mo_hinh": 0.7}


def group_of(text: str) -> str | None:
    key = bo_dau(text)
    for g, pat in GROUP_PATTERNS:
        if re.search(pat, key):
            return g
    return None


def clean_name(raw: str) -> str | None:
    s = " ".join(str(raw or "").replace("\n", " ").split())
    s = NUMBERING_RE.sub("", s)
    s = HONORIFIC_RE.sub("", s).strip(" .,:;-–()")
    if not s or len(s) > 60 or any(ch.isdigit() for ch in s) or bo_dau(s) in NOT_NAMES:
        return None
    if not NAME_RE.match(s):
        return None
    if s.isupper():
        s = s.title()
    return s


def _dates(text: str) -> list[date]:
    out = []
    for d, m, y in DATE_RE.findall(text or ""):
        try:
            out.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return out


def _tu_den(text: str) -> tuple[date | None, date | None]:
    """'Bổ nhiệm ngày 25/04/2023; miễn nhiệm ngày 30/06/2026' → (2023-04-25, 2026-06-30)."""
    if not text:
        return None, None
    key = bo_dau(text)
    ds = _dates(text)
    if not ds:
        return None, None
    if END_WORDS.search(key):
        if len(ds) >= 2:
            return ds[0], ds[-1]
        # chỉ một ngày, đứng sau chữ "miễn nhiệm" → ngày kết thúc
        return None, ds[0]
    return ds[0], None


@dataclass
class Person:
    ho_ten: str
    chuc_danh: str
    nhom: str
    tu_ngay: str | None = None
    den_ngay: str | None = None
    confidence: float = 0.75
    nguon_trich: str = ""  # đoạn văn bản / dòng bảng sinh ra người này (không chứa ngày sinh, giấy tờ)

    @property
    def code(self) -> str:
        return normalize_title(self.chuc_danh)[0]


@dataclass
class Extraction:
    people: list[Person] = field(default_factory=list)
    method: str = ""
    notes: list[str] = field(default_factory=list)
    text_chars: int = 0
    cut_at: str = ""  # tiêu đề mục nhạy cảm đã cắt

    @property
    def has_board(self) -> bool:
        return any(p.nhom == "hdqt" or p.code in BOARD_CODES for p in self.people if not p.den_ngay)

    @property
    def has_exec(self) -> bool:
        return any(p.nhom == "bdh" or p.code in EXEC_CODES for p in self.people if not p.den_ngay)

    @property
    def complete(self) -> bool:
        return self.has_board and self.has_exec

    def to_dict(self) -> dict:
        return {
            "people": [asdict(p) for p in self.people],
            "method": self.method,
            "notes": self.notes,
            "text_chars": self.text_chars,
            "cut_at": self.cut_at,
            "has_board": self.has_board,
            "has_exec": self.has_exec,
        }


def _person(name_cell: str, title_cell: str, group: str | None, date_text: str, method: str, raw: str) -> Person | None:
    """Ô tên có thể kèm chức danh: 'Ông Nguyễn Văn A - Tổng Giám đốc' hoặc 'Nguyễn Văn A\\nTổng Giám đốc'."""
    name_cell = str(name_cell or "")
    title = " ".join(str(title_cell or "").split())
    m = TITLE_RE.search(name_cell)
    if m and m.start() > 0:
        if not title:
            title = " ".join(name_cell[m.start():].split())
        name_cell = name_cell[: m.start()]
    name = clean_name(re.split(r"\s[-–(,]\s?|\n", name_cell.strip())[0] if name_cell.strip() else "")
    if not name:
        return None
    title = re.sub(r"\s*\(.*?\)\s*", " ", title).strip(" -–,;")  # bỏ ghi chú trong ngoặc
    title = re.split(r"\s+(?:bổ nhiệm|miễn nhiệm|từ ngày|ngày)\b", title, flags=re.I)[0].strip(" -–,;")
    g = group or group_of(title) or "khac"
    if not title:
        title = GROUP_DEFAULT_TITLE[g]
    elif normalize_title(title)[0] == "khac" and g in ("hdqt", "bks", "bdh"):
        # chức danh viết tắt kiểu "Thành viên độc lập" trong bảng HĐQT → gắn tên nhóm cho rõ
        title = f"{title} ({GROUP_DEFAULT_TITLE[g]})"
    tu, den = _tu_den(date_text)
    return Person(
        ho_ten=name,
        chuc_danh=title[:200],
        nhom=g,
        tu_ngay=tu.isoformat() if tu else None,
        den_ngay=den.isoformat() if den else None,
        confidence=CONFIDENCE[method],
        nguon_trich=raw[:300],
    )


# ------------------------------------------------------------------ đọc tài liệu


@dataclass
class Table:
    rows: list[list[str]]
    context: str  # vài dòng văn bản ngay trước bảng


@dataclass
class Doc:
    lines: list[str]
    tables: list[Table]
    cut_at: str = ""
    scanned: bool = False


def _cell(v) -> str:
    return "" if v is None else str(v).strip()


def _cut_index(lines: list[str]) -> int | None:
    for i, ln in enumerate(lines):
        if SENSITIVE_HEADING.search(bo_dau(ln)):
            return i
    return None


def load_pdf(data: bytes) -> Doc:
    import pdfplumber

    lines: list[str] = []
    tables: list[Table] = []
    cut_at = ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_lines = [ln for ln in text.split("\n") if ln.strip()]
            cut = _cut_index(page_lines)
            cut_y = None
            if cut is not None:
                cut_at = page_lines[cut].strip()
                hits = page.search(page_lines[cut].strip(), regex=False)
                cut_y = hits[0]["top"] if hits else 0
                page_lines = page_lines[:cut]
            for t in page.find_tables():
                top, bottom = t.bbox[1], t.bbox[3]
                if cut_y is not None and bottom > cut_y:
                    continue  # bảng nằm trong / sau mục nhạy cảm
                above = page.crop((0, max(0, top - 60), page.width, top)).extract_text() or ""
                rows = [[_cell(c) for c in r] for r in (t.extract() or [])]
                tables.append(Table(rows=rows, context=above))
            lines += page_lines
            if cut is not None:
                break
    scanned = sum(len(ln) for ln in lines) < 200
    return Doc(lines=lines, tables=tables, cut_at=cut_at, scanned=scanned)


def load_html(data: bytes) -> Doc:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").split("\n") if ln.strip()]
    cut = _cut_index(lines)
    cut_at = ""
    if cut is not None:
        cut_at = lines[cut]
        lines = lines[:cut]
        # bỏ mọi phần tử từ tiêu đề nhạy cảm trở đi để bảng phía sau không bị đọc
        node = soup.find(string=lambda s: s and s.strip() == cut_at)
        if node is not None:
            start = node.parent
            for el in list(start.find_all_next()):
                el.decompose()
    tables = []
    for t in soup.find_all("table"):
        rows = [[" ".join(td.get_text(" ").split()) for td in tr.find_all(["td", "th"])] for tr in t.find_all("tr")]
        prev = t.find_previous(string=lambda s: s and s.strip())
        tables.append(Table(rows=rows, context=prev.strip() if prev else ""))
    return Doc(lines=lines, tables=tables, cut_at=cut_at, scanned=False)


def load_text(data: bytes) -> Doc:
    text = data.decode("utf-8", errors="replace")
    lines = [ln for ln in text.split("\n") if ln.strip()]
    cut = _cut_index(lines)
    cut_at = ""
    if cut is not None:
        cut_at, lines = lines[cut], lines[:cut]
    return Doc(lines=lines, tables=[], cut_at=cut_at)


def load(data: bytes, content_type: str = "", file_name: str = "") -> Doc:
    ct = (content_type or "").lower()
    name = (file_name or "").lower()
    if "pdf" in ct or name.endswith(".pdf") or data[:5] == b"%PDF-":
        return load_pdf(data)
    if "html" in ct or name.endswith((".html", ".htm")) or b"<html" in data[:2000].lower():
        return load_html(data)
    return load_text(data)


# ------------------------------------------------------------------ tầng 1: bảng


def _header(rows: list[list[str]]) -> tuple[int, dict[str, list[int]]]:
    """Tìm dòng tiêu đề (có thể 2 dòng gộp). Trả về (số dòng tiêu đề, {vai trò: [chỉ số cột]})."""
    for n in (1, 2):
        if len(rows) < n:
            break
        width = max(len(r) for r in rows[:n])
        heads = [bo_dau(" ".join(rows[i][c] if c < len(rows[i]) else "" for i in range(n))) for c in range(width)]
        cols: dict[str, list[int]] = {"name": [], "title": [], "start": [], "end": [], "dates": [], "bad": []}
        for c, h in enumerate(heads):
            if not h:
                continue
            if SENSITIVE_COL.search(h):
                cols["bad"].append(c)
            elif re.search(r"thanh vien|ho va ten|ho ten|^ten\b|nguoi phu trach", h) and not re.search(r"ngay|so luong", h):
                cols["name"].append(c)
            elif re.search(r"chuc vu|chuc danh", h):
                cols["title"].append(c)
            elif re.search(r"mien nhiem|khong con", h) and not re.search(r"bo nhiem|bat dau", h):
                cols["end"].append(c)
            elif re.search(r"bo nhiem|bat dau", h) and not re.search(r"mien nhiem|khong con", h):
                cols["start"].append(c)
            elif re.search(r"bo nhiem|mien nhiem|bat dau|khong con", h):
                cols["dates"].append(c)
        if cols["name"]:
            return n, cols
    return 0, {}


def tier_tables(doc: Doc) -> list[Person]:
    out: list[Person] = []
    for t in doc.tables:
        if len(t.rows) < 2:
            continue
        n, cols = _header(t.rows)
        if not n or cols["bad"]:
            continue  # không phải bảng thành viên, hoặc bảng có cột dữ liệu nhạy cảm
        header_text = " ".join(" ".join(r) for r in t.rows[:n])
        group = group_of(header_text) or group_of(t.context)
        name_c = cols["name"][0]
        for r in t.rows[n:]:
            get = lambda cs: " ".join(r[c] for c in cs if c < len(r) and r[c])  # noqa: E731
            name_cell = r[name_c] if name_c < len(r) else ""
            start, end, both = get(cols["start"]), get(cols["end"]), get(cols["dates"])
            date_text = both or ""
            if start:
                date_text += f" bổ nhiệm {start}"
            if end and _dates(end):
                date_text += f" miễn nhiệm {end}"
            raw = " | ".join(x for x in (name_cell, get(cols["title"]), date_text.strip()) if x)
            p = _person(name_cell, get(cols["title"]), group, date_text, "cau_truc", raw)
            if p:
                out.append(p)
    return out


# ------------------------------------------------------------------ tầng 2: luật trên dòng văn bản


def tier_rules(doc: Doc) -> list[Person]:
    out: list[Person] = []
    group: str | None = None
    for ln in doc.lines:
        key = bo_dau(ln)
        m = TITLE_RE.search(ln)
        # dòng người ("1. Ông Nguyễn Văn A – Chủ tịch HĐQT") xét trước, vì nó cũng có số thứ tự giống tiêu đề mục
        p = _person(ln[: m.start()], ln[m.start():], group, ln[m.start():], "luat", ln.strip()) if m and m.start() > 0 else None
        if p:
            if group is not None:
                out.append(p)
            continue
        if SECTION_RE.match(key) and len(key) < 120:
            g = group_of(key)
            if g:
                group = g
            elif STOP_SECTION.search(key):
                group = None
    return out


# ------------------------------------------------------------------ hợp nhất


def dedupe(people: list[Person]) -> list[Person]:
    best: dict[tuple[str, str], Person] = {}
    for p in people:
        k = (bo_dau(p.ho_ten), p.code if p.code != "khac" else p.nhom)
        cur = best.get(k)
        score = (p.confidence, bool(p.tu_ngay) + bool(p.den_ngay))
        if not cur or score > (cur.confidence, bool(cur.tu_ngay) + bool(cur.den_ngay)):
            best[k] = p
    return list(best.values())


def text_for_model(doc: Doc, limit: int = 60_000) -> str:
    """Văn bản gửi tầng 3 — đã cắt mục nhạy cảm; bảng thêm dưới dạng dòng phân cách bằng |, bỏ bảng có cột nhạy cảm."""
    parts = list(doc.lines)
    for t in doc.tables:
        _, cols = _header(t.rows)
        if cols.get("bad"):
            continue
        parts.append(t.context)
        parts += [" | ".join(r) for r in t.rows]
    return "\n".join(parts)[:limit]


def extract(doc: Doc, model_fn=None) -> Extraction:
    """model_fn(text) -> list[dict] | None — tầng 3 (None = không dùng)."""
    ex = Extraction(text_chars=sum(len(ln) for ln in doc.lines), cut_at=doc.cut_at)
    if doc.cut_at:
        ex.notes.append(f"Đã cắt bỏ từ mục “{doc.cut_at[:80]}” trở đi (dữ liệu người nội bộ / người có liên quan).")
    if doc.scanned:
        ex.notes.append("Tài liệu không có lớp chữ (PDF dạng ảnh) — cần nhập tay.")
        return ex
    t1 = tier_tables(doc)
    if t1:
        ex.people, ex.method = dedupe(t1), "cau_truc"
        if ex.complete:
            return ex
    t2 = tier_rules(doc)
    if t2:
        ex.people = dedupe(ex.people + t2)
        ex.method = "luat" if not t1 else "cau_truc"
        if ex.complete:
            return ex
    if model_fn is not None:
        rows = model_fn(text_for_model(doc))
        if rows:
            model_people = []
            for r in rows:
                p = _person(r.get("ho_ten", ""), r.get("chuc_danh", ""), r.get("nhom") if r.get("nhom") in GROUP_DEFAULT_TITLE else None, "", "mo_hinh", f"Mô hình: {r.get('ho_ten', '')} — {r.get('chuc_danh', '')}")
                if p:
                    p.tu_ngay = r.get("tu_ngay") if parse_date(r.get("tu_ngay")) else None
                    p.den_ngay = r.get("den_ngay") if parse_date(r.get("den_ngay")) else None
                    model_people.append(p)
            if model_people:
                ex.people = dedupe(ex.people + model_people)
                ex.method = "mo_hinh"
    if not ex.has_board:
        ex.notes.append("Chưa tìm thấy thành viên HĐQT.")
    if not ex.has_exec:
        ex.notes.append("Chưa tìm thấy thành viên Ban điều hành.")
    return ex


def default_title(code: str) -> str:
    return TITLES.get(code, ("Khác", False))[0]
