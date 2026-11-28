"""Các trang chạy chung hệ thống sự kiện: LeadScan và 2 cổng sự kiện riêng c89.leadscan.net, epc.leadscan.net.

Mỗi sự kiện / đăng ký / tài khoản cổng sự kiện thuộc đúng 1 trang (cột `site`).

Trang của 1 request lấy từ header X-LeadScan-Site:
  - Production: Nginx đặt header này ở từng khối server (deploy/nginx.conf) và XOÁ header khách tự gửi ở leadscan.net.
  - Dev / web render phía máy chủ: Next.js tự đặt (web/proxy.ts, web/lib/events-server.ts).
Header thiếu / sai → trang chính LeadScan. Header chỉ quyết định trang công khai hiển thị sự kiện nào và cổng nào
được đăng nhập; quyền xem dữ liệu admin luôn theo tài khoản (AdminUser.site), không theo header.
"""

from __future__ import annotations

from fastapi import Request

from app.config import Settings, get_settings

MAIN = "leadscan"
HEADER = "x-leadscan-site"

NAMES = {
    "leadscan": "LeadScan",
    "c89": "CLB CEO 1989",
    "epc": "EPC",
}
KEYS = tuple(NAMES)
PORTALS = tuple(k for k in KEYS if k != MAIN)  # cổng chỉ đăng sự kiện


def valid(key: str | None) -> bool:
    return key in NAMES


def request_site(request: Request) -> str:
    v = (request.headers.get(HEADER) or "").strip().lower()
    return v if v in NAMES else MAIN


def url(key: str, cfg: Settings | None = None) -> str:
    cfg = cfg or get_settings()
    return {
        "leadscan": cfg.site_url,
        "c89": cfg.c89_url,
        "epc": cfg.epc_url,
    }.get(key, cfg.site_url).rstrip("/")


def admin_url(key: str, cfg: Settings | None = None) -> str:
    """Trang quản trị của từng trang (LeadScan dùng LEADSCAN_ADMIN_URL như cũ)."""
    cfg = cfg or get_settings()
    return cfg.admin_url.rstrip("/") if key == MAIN else url(key, cfg) + "/admin"


def info(cfg: Settings | None = None) -> dict[str, dict]:
    return {k: {"name": n, "url": url(k, cfg)} for k, n in NAMES.items()}
