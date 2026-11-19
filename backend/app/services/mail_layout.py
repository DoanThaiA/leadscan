"""Giao diện email HTML của LeadScan — dùng chung cho MỌI email hệ thống gửi.

• wrap(): khung email (logo, nội dung, chân trang) theo nhận diện LeadScan: xanh #004b87, vàng #ffcd00.
  Viết bằng bảng + style inline để hiển thị đúng trên Gmail, Outlook, Apple Mail, điện thoại.
• text_to_html(): chuyển nội dung chữ thuần của các email cũ sang HTML gọn gàng (đoạn văn, danh sách, bảng
  "Nhãn : giá trị", tiêu đề viết hoa, link bấm được) — send_mail tự gọi khi email không có bản HTML riêng.
• button(), info_table(), note_box(): khối dựng sẵn cho email viết HTML riêng (vd. email gửi cơ hội cho khách).

Mọi chuỗi đưa vào đều được escape; chỉ khối HTML do chính các hàm ở đây tạo ra mới được chèn thẳng.
"""

import html
import re

from app.config import Settings, get_settings

BRAND = "#004b87"
BRAND_DARK = "#00355f"
BRAND_SOFT = "#eef4fa"
ACCENT = "#ffcd00"
INK = "#1d262e"
MUTED = "#5b6570"
LINE = "#e6e9ec"
BG = "#f3f5f7"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

_URL = re.compile(r"(https?://[^\s<>\"')]+)")
_KV = re.compile(r"^\s{0,4}([^:\n]{2,32}?)\s+:\s+(.+)$")  # "Mã đơn            : DH-001"
_BULLET = re.compile(r"^\s*(?:[•\-*]|\d+\.)\s+(.+)$")
_RULE = re.compile(r"^\s*[=\-_]{4,}\s*$")


def esc(s: object) -> str:
    return html.escape(str(s or ""), quote=True)


def linkify(escaped: str) -> str:
    """Biến URL trong chuỗi ĐÃ escape thành link."""
    return _URL.sub(lambda m: f'<a href="{m.group(1)}" style="color:{BRAND};text-decoration:underline;word-break:break-all">{m.group(1)}</a>', escaped)


def _is_heading(line: str) -> bool:
    s = line.strip()
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 4 and len(s) <= 80 and all(c.isupper() for c in letters)


def text_to_html(text: str) -> str:
    """Nội dung chữ thuần → HTML (đặt vào wrap())."""
    blocks: list[str] = []
    para: list[str] = []
    items: list[str] = []
    rows: list[tuple[str, str]] = []

    def flush() -> None:
        if para:
            blocks.append(f'<p style="margin:0 0 14px;line-height:1.6">{"<br>".join(para)}</p>')
            para.clear()
        if items:
            lis = "".join(f'<li style="margin:0 0 6px;line-height:1.55">{x}</li>' for x in items)
            blocks.append(f'<ul style="margin:0 0 14px;padding-left:20px">{lis}</ul>')
            items.clear()
        if rows:
            blocks.append(info_table(rows, raw=True))
            rows.clear()

    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if _RULE.match(line):
            continue
        kv = _KV.match(line)
        bullet = _BULLET.match(line)
        if kv and not bullet:
            if para or items:
                flush()
            rows.append((linkify(esc(kv.group(1).strip())), linkify(esc(kv.group(2).strip()))))
        elif bullet:
            if para or rows:
                flush()
            items.append(linkify(esc(bullet.group(1))))
        elif _is_heading(line) and not para:
            flush()
            blocks.append(f'<h3 style="margin:18px 0 10px;font-size:13px;letter-spacing:.04em;color:{BRAND}">{esc(line.strip())}</h3>')
        else:
            if items or rows:
                flush()
            para.append(linkify(esc(line.strip())))
    flush()
    return "".join(blocks)


def info_table(rows: list[tuple[str, str]], raw: bool = False) -> str:
    """Bảng 2 cột "nhãn — giá trị". raw=True: giá trị đã là HTML an toàn (đã escape)."""
    tr = "".join(
        f'<tr><td style="padding:7px 12px 7px 0;color:{MUTED};font-size:13px;vertical-align:top;white-space:nowrap;border-bottom:1px solid {LINE}">'
        f'{k if raw else esc(k)}</td><td style="padding:7px 0;font-size:14px;color:{INK};vertical-align:top;border-bottom:1px solid {LINE}">'
        f'{v if raw else esc(v)}</td></tr>'
        for k, v in rows
    )
    return f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;margin:0 0 16px">{tr}</table>'


def button(label: str, url: str) -> str:
    """Nút bấm chính (vàng chữ xanh) — dùng bảng để hiện đúng trên Outlook."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:6px 0 18px"><tr>'
        f'<td style="background:{ACCENT};border-radius:8px">'
        f'<a href="{esc(url)}" style="display:inline-block;padding:13px 26px;font-weight:700;font-size:15px;color:{BRAND_DARK};text-decoration:none">{esc(label)}</a>'
        "</td></tr></table>"
    )


def note_box(title: str, text: str) -> str:
    body = "<br>".join(linkify(esc(x)) for x in text.strip().split("\n"))
    return (
        f'<div style="margin:0 0 18px;padding:14px 16px;background:{BRAND_SOFT};border-left:4px solid {BRAND};border-radius:6px">'
        f'<div style="font-size:12px;font-weight:700;color:{BRAND};text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px">{esc(title)}</div>'
        f'<div style="font-size:14px;line-height:1.6;color:{INK}">{body}</div></div>'
    )


def wrap(subject: str, inner: str, preheader: str = "", footer_note: str = "", cfg: Settings | None = None) -> str:
    """Khung email hoàn chỉnh. inner: HTML nội dung (đã an toàn)."""
    cfg = cfg or get_settings()
    site = cfg.site_url.rstrip("/")
    logo = f"{site}/brand/leadscan-logo-reverse-1200.png"
    pre = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{esc(preheader)}</div>' if preheader else ""
    )
    note = f'<p style="margin:0 0 8px">{footer_note}</p>' if footer_note else ""
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{esc(subject)}</title></head>
<body style="margin:0;padding:0;background:{BG};font-family:{FONT};color:{INK};-webkit-text-size-adjust:100%">
{pre}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:24px 12px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid {LINE}">
    <tr><td style="background:{BRAND};padding:18px 28px">
      <a href="{esc(site)}" style="text-decoration:none"><img src="{esc(logo)}" alt="LeadScan" width="150" style="display:block;border:0;width:150px;height:auto;color:#ffffff;font-size:20px;font-weight:700"></a>
    </td></tr>
    <tr><td style="height:4px;background:{ACCENT};line-height:4px;font-size:0">&nbsp;</td></tr>
    <tr><td style="padding:28px 28px 12px;font-size:15px;line-height:1.6;color:{INK}">
{inner}
    </td></tr>
    <tr><td style="padding:18px 28px 24px;border-top:1px solid {LINE};font-size:12px;line-height:1.6;color:{MUTED}">
      {note}<p style="margin:0">LeadScan — Sàn cơ hội B2B: tìm khách hàng doanh nghiệp đang cần mua · <a href="{esc(site)}" style="color:{BRAND}">{esc(site.split('//')[-1])}</a></p>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""


def from_text(subject: str, body: str, cfg: Settings | None = None) -> str:
    """Email chữ thuần → email HTML có giao diện LeadScan (dùng cho mọi email chưa có bản HTML riêng)."""
    first = next((x.strip() for x in (body or "").split("\n") if x.strip() and not _RULE.match(x)), "")
    return wrap(subject, text_to_html(body), preheader=first[:140], cfg=cfg)
