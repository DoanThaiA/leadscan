"""Lệnh quản trị LeadScan.

    python -m app.cli create-admin --email a@b.vn --name "Nguyễn Văn A"   # tạo/đặt lại tài khoản quản trị
    python -m app.cli diagnose                                          # kiểm tra DB, Redis, SMTP
    python -m app.cli import-legacy DIR                                 # nhập hồ sơ JSON từ bản PHP cũ
    python -m app.cli crawl-profit500 --chart 12 --year 2026            # quét PROFIT500 vào kho doanh nghiệp

Mật khẩu lấy từ biến môi trường LEADSCAN_ADMIN_PASSWORD nếu có, nếu không sẽ hỏi khi chạy.
"""

import argparse
import getpass
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text

from app.config import get_settings
from app.db import get_engine, new_session, utcnow
from app.models import Activity, AdminUser, Company, Contact, Profile
from app.registration_form import tax_key
from app.security import hash_password


def cmd_create_admin(args) -> int:
    email = args.email.strip().lower()
    password = os.environ.get("LEADSCAN_ADMIN_PASSWORD") or getpass.getpass("Mật khẩu (tối thiểu 10 ký tự): ")
    if len(password) < 10:
        print("Mật khẩu phải có ít nhất 10 ký tự.")
        return 1
    with new_session() as db:
        user = db.scalar(select(AdminUser).where(AdminUser.email == email))
        if user:
            user.password_hash, user.role, user.is_active = hash_password(password), "admin", True
            if args.name:
                user.full_name = args.name
            action = "Đã đặt lại mật khẩu và quyền quản trị cho"
        else:
            db.add(AdminUser(email=email, full_name=args.name or email, role="admin", password_hash=hash_password(password)))
            action = "Đã tạo tài khoản quản trị"
        db.commit()
    print(f"{action} {email}")
    return 0


def _line(ok: bool, label: str, detail: str = "") -> None:
    print(("[ OK ] " if ok else "[LỖI] ") + label + (f" — {detail}" if detail else ""))


def cmd_diagnose(_args) -> int:
    cfg = get_settings()
    _line(sys.version_info >= (3, 12), f"Python {sys.version.split()[0]}", "cần 3.12 trở lên")

    db_url = cfg.database_url.split("@")[-1]
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        _line(True, "Kết nối cơ sở dữ liệu", db_url)
    except Exception as e:  # noqa: BLE001
        _line(False, "Kết nối cơ sở dữ liệu", f"{db_url}: {e}")
        return 1

    try:
        import redis

        redis.Redis.from_url(cfg.redis_url, socket_connect_timeout=2).ping()
        _line(True, "Kết nối Redis", cfg.redis_url.split("@")[-1])
    except Exception as e:  # noqa: BLE001
        _line(False, "Kết nối Redis", str(e))

    from app.services.notify import mail_provider

    prov = mail_provider(cfg)
    _line(bool(prov), "Gửi email", f"qua {prov}, từ {cfg.mail_from_name} <{cfg.notify_from}>" if prov else "chưa cấu hình Resend/SMTP — không gửi được email")
    _line(bool(cfg.invoice_email), "Email nhận yêu cầu xuất hoá đơn", cfg.invoice_email)
    _line(True, "Email báo đăng ký mới", cfg.notify_email or "(để trống — không gửi)")
    _line(cfg.cookie_secure, "Cookie đăng nhập chỉ qua HTTPS", "" if cfg.cookie_secure else "đang tắt (chỉ nên tắt khi chạy local)")

    with new_session() as db:
        admins = db.scalar(select(func.count()).select_from(AdminUser).where(AdminUser.role == "admin", AdminUser.is_active))
        _line(bool(admins), f"Tài khoản quản trị đang hoạt động: {admins}", "" if admins else "chạy create-admin để tạo")
        counts = dict(db.execute(select(Company.status, func.count()).group_by(Company.status)).all())
        print("Khách hàng theo trạng thái: " + (", ".join(f"{k}={v}" for k, v in counts.items()) or "(chưa có)"))
    return 0


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    dt = datetime.fromisoformat(v)  # PHP date('c') luôn có múi giờ, phòng hờ thì coi là giờ VN
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    return dt.astimezone(UTC).replace(tzinfo=None)


def cmd_import_legacy(args) -> int:
    files = sorted(Path(args.dir).glob("LS-*.json"))
    if not files:
        print(f"Không thấy file LS-*.json trong {args.dir}")
        return 1
    added = skipped = 0
    with new_session() as db:
        for f in files:
            rec = json.loads(f.read_text(encoding="utf-8"))
            d = rec.get("data") or {}
            tkey = tax_key(d.get("tax_code", ""))
            if db.scalar(select(Company.id).where((Company.code == rec["code"]) | (Company.tax_key == tkey))):
                skipped += 1
                continue
            c = Company(
                code=rec["code"],
                name=d.get("company_name", ""),
                tax_code=d.get("tax_code", ""),
                tax_key=tkey,
                industry=d.get("industry", ""),
                company_size=d.get("company_size", ""),
                province=d.get("province", ""),
                address=d.get("address", ""),
                website=d.get("website", ""),
                source="landing-php",
                ip=rec.get("ip", ""),
                created_at=_parse_dt(rec.get("created_at")) or utcnow(),
            )
            c.contacts.append(
                Contact(
                    full_name=d.get("contact_name", ""), position=d.get("position", ""),
                    email=d.get("email", ""), phone=d.get("phone", ""), is_primary=True,
                )
            )
            c.profile = Profile(
                offering=d.get("offering", ""), target_customers=d.get("target_customers", ""),
                target_regions=d.get("target_regions", []), opp_types=d.get("opp_types", []),
                expected_tickets=d.get("expected_tickets", ""), notes=d.get("notes", ""),
            )
            c.activities.append(Activity(kind="created", content="Nhập từ hệ thống đăng ký cũ (PHP)", created_at=c.created_at))
            db.add(c)
            added += 1
        db.commit()
    print(f"Đã nhập {added} hồ sơ, bỏ qua {skipped} hồ sơ đã có.")
    return 0


def cmd_crawl_profit500(args) -> int:
    from app.services import profit500

    if args.chart not in profit500.CHARTS:
        print("Bảng xếp hạng không hợp lệ. Chọn: " + ", ".join(f"{k} = {v}" for k, v in profit500.CHARTS.items()))
        return 1
    with new_session() as db:
        stats = profit500.crawl(
            db, chart=args.chart, year=args.year, limit=args.limit, page_size=args.page_size, update=args.update, delay=args.delay
        )
    print()
    print(f"Xong: thêm mới {stats.created}, cập nhật {stats.updated}, bỏ qua {stats.skipped}, lỗi {len(stats.errors)}")
    for e in stats.errors[:20]:
        print("  - " + e)
    return 1 if stats.errors and not (stats.created or stats.updated or stats.skipped) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli", description="Lệnh quản trị LeadScan")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("create-admin", help="Tạo hoặc đặt lại tài khoản quản trị")
    a.add_argument("--email", required=True)
    a.add_argument("--name", default="")
    a.set_defaults(fn=cmd_create_admin)
    sub.add_parser("diagnose", help="Kiểm tra cấu hình và kết nối").set_defaults(fn=cmd_diagnose)
    i = sub.add_parser("import-legacy", help="Nhập hồ sơ JSON từ bản PHP cũ")
    i.add_argument("dir")
    i.set_defaults(fn=cmd_import_legacy)
    c = sub.add_parser("crawl-profit500", help="Quét doanh nghiệp từ bảng xếp hạng PROFIT500 vào kho doanh nghiệp")
    c.add_argument("--chart", type=int, default=12, help="12 = Top 500 lợi nhuận tốt nhất, 13 = Top 500 tư nhân, 17 = Top 50 xuất sắc")
    c.add_argument("--year", type=int, default=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).year)
    c.add_argument("--limit", type=int, default=0, help="Số doanh nghiệp tối đa (0 = tất cả)")
    c.add_argument("--page-size", type=int, default=50)
    c.add_argument("--delay", type=float, default=1.0, help="Số giây nghỉ giữa các lần tải trang (lịch sự với trang nguồn)")
    c.add_argument("--update", action="store_true", help="Cập nhật cả doanh nghiệp đã có (mặc định chỉ thêm mới)")
    c.set_defaults(fn=cmd_crawl_profit500)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
