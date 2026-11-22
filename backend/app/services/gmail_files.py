"""Đọc chữ trong tệp đính kèm của thư Gmail (Apps Script gửi base64) để AI đọc cùng thân thư.

Đọc được: PDF (có lớp chữ), Word .docx, Excel .xlsx/.xlsm, PowerPoint .pptx, .txt/.csv, .html, thư đính kèm .eml
(thư chuyển tiếp dạng tệp đính kèm — đọc cả thân thư và tệp đính kèm bên trong).
Không đọc: ảnh, PDF scan (không có lớp chữ), .doc/.xls/.ppt đời cũ, .zip, .msg → chỉ ghi chú, admin mở Gmail xem.

Tệp là dữ liệu không tin cậy: giới hạn số trang / số dòng / dung lượng giải nén (chống zip bomb), lỗi tệp nào chỉ ghi chú tệp đó.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re
import zipfile
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from xml.etree import ElementTree

log = logging.getLogger("leadscan.gmail")

MAX_FILES = 20
MAX_FILE_TEXT = 15_000  # ký tự chữ lưu cho mỗi tệp
MAX_PDF_PAGES = 30
MAX_SHEET_ROWS = 400
MAX_UNZIPPED = 60 * 1024 * 1024  # tổng dung lượng giải nén của docx/xlsx/pptx
MAX_EML_DEPTH = 2

_CTRL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "heic"}
OLD_OFFICE_EXT = {"doc", "xls", "ppt", "msg", "rtf", "odt", "ods"}


class Unreadable(Exception):
    """Tệp không đọc được chữ — thông điệp là ghi chú hiện cho admin."""


def _clean(text: str) -> str:
    text = _CTRL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def kind(name: str, ctype: str) -> str:
    """Loại tệp theo đuôi tên (ưu tiên) rồi tới content type: pdf / docx / xlsx / pptx / text / html / eml / image / old / ""."""
    ext, ctype = _ext(name), (ctype or "").lower().split(";")[0].strip()
    if ext == "pdf" or ctype == "application/pdf":
        return "pdf"
    if ext == "docx" or ctype.endswith("wordprocessingml.document"):
        return "docx"
    if ext in ("xlsx", "xlsm") or ctype.endswith("spreadsheetml.sheet"):
        return "xlsx"
    if ext == "pptx" or ctype.endswith("presentationml.presentation"):
        return "pptx"
    if ext in ("txt", "csv", "tsv", "md") or ctype in ("text/plain", "text/csv"):
        return "text"
    if ext in ("html", "htm") or ctype == "text/html":
        return "html"
    if ext == "eml" or ctype == "message/rfc822":
        return "eml"
    if ext in IMAGE_EXT or ctype.startswith("image/"):
        return "image"
    if ext in OLD_OFFICE_EXT or ctype in ("application/msword", "application/vnd.ms-excel", "application/vnd.ms-outlook"):
        return "old"
    return ""


READABLE = {"pdf", "docx", "xlsx", "pptx", "text", "html", "eml"}


# ------------------------------------------------------------------ từng loại tệp


def _zip(data: bytes) -> zipfile.ZipFile:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise Unreadable("Tệp hỏng hoặc sai định dạng.") from e
    if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED:
        raise Unreadable("Tệp giải nén quá lớn, không đọc.")
    return z


def _xml(z: zipfile.ZipFile, name: str) -> ElementTree.Element | None:
    try:
        return ElementTree.fromstring(z.read(name))
    except KeyError:
        return None


def read_pdf(data: bytes) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        total = len(pdf.pages)
        for page in pdf.pages[:MAX_PDF_PAGES]:
            pages.append(page.extract_text() or "")
    text = _clean("\n\n".join(pages))
    if len(text) < 30:
        raise Unreadable("PDF dạng ảnh scan (không có lớp chữ) — mở Gmail để xem.")
    if total > MAX_PDF_PAGES:
        text += f"\n[… chỉ đọc {MAX_PDF_PAGES}/{total} trang đầu]"
    return text


def read_docx(data: bytes) -> str:
    z = _zip(data)
    parts = ["word/document.xml"] + sorted(n for n in z.namelist() if re.fullmatch(r"word/(header|footer)\d*\.xml", n))
    out = []
    for part in parts:
        root = _xml(z, part)
        if root is None:
            continue
        # Đoạn văn; bảng → mỗi dòng các ô cách nhau " | "
        body = root.find(f"{_W}body") if part == "word/document.xml" else root
        for el in (body if body is not None else root):
            if el.tag == f"{_W}p":
                out.append(_wtext(el))
            elif el.tag == f"{_W}tbl":
                for tr in el.iter(f"{_W}tr"):
                    cells = [" ".join(_wtext(p) for p in tc.iter(f"{_W}p")).strip() for tc in tr.iter(f"{_W}tc")]
                    if any(cells):
                        out.append(" | ".join(cells))
    return _clean("\n".join(out))


def _wtext(p: ElementTree.Element) -> str:
    bits = []
    for t in p.iter():
        if t.tag == f"{_W}t" and t.text:
            bits.append(t.text)
        elif t.tag == f"{_W}tab":
            bits.append("\t")
        elif t.tag in (f"{_W}br", f"{_W}cr"):
            bits.append("\n")
    return "".join(bits)


def read_xlsx(data: bytes) -> str:
    _zip(data)  # kiểm tra dung lượng giải nén trước khi openpyxl mở
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 — tệp Excel hỏng có nhiều loại lỗi
        raise Unreadable("Tệp Excel hỏng hoặc sai định dạng.") from e
    out = []
    try:
        for ws in wb.worksheets[:10]:
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= MAX_SHEET_ROWS:
                    rows.append(f"[… chỉ đọc {MAX_SHEET_ROWS} dòng đầu]")
                    break
                cells = ["" if v is None else str(v).strip() for v in row]
                while cells and not cells[-1]:
                    cells.pop()
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                out.append(f"[Trang tính: {ws.title}]\n" + "\n".join(rows))
    finally:
        wb.close()
    return _clean("\n\n".join(out))


def read_pptx(data: bytes) -> str:
    z = _zip(data)
    slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.sub(r"\D", "", n)))
    out = []
    for i, name in enumerate(slides, 1):
        root = _xml(z, name)
        if root is None:
            continue
        paras = ["".join(t.text or "" for t in p.iter(f"{_A}t")) for p in root.iter(f"{_A}p")]
        text = "\n".join(x for x in paras if x.strip())
        if text:
            out.append(f"[Trang chiếu {i}]\n{text}")
    return _clean("\n\n".join(out))


def decode_text(data: bytes) -> str:
    enc = "utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        return data.decode(enc)
    except UnicodeDecodeError:
        return data.decode("cp1258", errors="replace")


def html_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "head"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    return _clean(soup.get_text("\n"))


def _eml_body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, ValueError):
        content = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
    return html_text(content) if part.get_content_type() == "text/html" else _clean(content)


def read_eml(data: bytes, depth: int = 0) -> tuple[str, list[dict]]:
    """Thư .eml → (chữ: tiêu đề thư gốc + thân thư, tệp đính kèm bên trong đã đọc)."""
    msg = BytesParser(policy=policy.default).parsebytes(data)
    head = [f"{k}: {msg[k]}" for k in ("From", "Date", "To", "Cc", "Subject") if msg[k]]
    text = "\n".join(head) + "\n\n" + _eml_body(msg)
    inner = []
    if depth < MAX_EML_DEPTH:
        for i, att in enumerate(msg.iter_attachments()):
            if i >= MAX_FILES:
                break
            name = att.get_filename() or ("thu-dinh-kem.eml" if att.get_content_type() == "message/rfc822" else f"tep-{i + 1}")
            if att.get_content_type() == "message/rfc822":
                payload = att.get_payload()
                raw = payload[0].as_bytes() if isinstance(payload, list) and payload else b""
            else:
                raw = att.get_payload(decode=True) or b""
            inner.append(extract_one(name, att.get_content_type(), raw, depth + 1))
    return _clean(text), inner


# ------------------------------------------------------------------ điểm vào


def extract_one(name: str, ctype: str, data: bytes | None, depth: int = 0, skipped: str = "") -> dict:
    """1 tệp → {name, type, size, text, note}. text rỗng + note = không đọc được (lý do)."""
    k = kind(name, ctype)
    item = {"name": name[:200], "type": (ctype or "")[:100], "size": len(data) if data else 0, "text": "", "note": ""}
    if skipped == "too_large":
        item["note"] = "Tệp quá lớn, chưa gửi nội dung — mở Gmail để xem."
        return item
    if k not in READABLE:
        item["note"] = {
            "image": "Ảnh — chưa đọc được chữ trong ảnh, mở Gmail để xem.",
            "old": "Định dạng cũ (.doc/.xls/.ppt/.msg…) chưa đọc được — mở Gmail để xem.",
        }.get(k, "Định dạng chưa hỗ trợ đọc — mở Gmail để xem.")
        return item
    if not data:
        item["note"] = "Không nhận được nội dung tệp — mở Gmail để xem."
        return item
    try:
        if k == "eml":
            text, inner = read_eml(data, depth)
            for f in inner:  # chữ của tệp bên trong thư đính kèm nối vào sau thân thư
                if f["text"]:
                    text += f"\n\n[Tệp đính kèm trong thư: {f['name']}]\n{f['text']}"
                elif f["note"]:
                    text += f"\n\n[Tệp đính kèm trong thư: {f['name']} — {f['note']}]"
        else:
            text = {
                "pdf": read_pdf, "docx": read_docx, "xlsx": read_xlsx, "pptx": read_pptx,
                "text": lambda b: _clean(decode_text(b)), "html": lambda b: html_text(decode_text(b)),
            }[k](data)
    except Unreadable as e:
        item["note"] = str(e)
        return item
    except Exception as e:  # noqa: BLE001 — tệp hỏng không được làm hỏng cả thư
        log.warning("Không đọc được tệp %r: %s", name, e)
        item["note"] = "Tệp hỏng hoặc không đọc được — mở Gmail để xem."
        return item
    if not text:
        item["note"] = "Tệp không có chữ."
    if len(text) > MAX_FILE_TEXT:
        text = text[:MAX_FILE_TEXT] + "\n[… đã cắt bớt]"
    item["text"] = text
    return item


def extract_payload(items: list[dict]) -> list[dict]:
    """attachments từ Apps Script ({name, type, size, data base64, skipped}) → danh sách đã đọc chữ."""
    out = []
    for f in items[:MAX_FILES]:
        data = None
        if f.get("data"):
            try:
                data = base64.b64decode(f["data"], validate=False)
            except (binascii.Error, ValueError):
                out.append({"name": f["name"], "type": f["type"], "size": 0, "text": "", "note": "Nội dung tệp gửi lên bị lỗi."})
                continue
        out.append(extract_one(f["name"], f["type"], data, skipped=f.get("skipped", "")))
    return out
