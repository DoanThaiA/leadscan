"""Lệnh quản trị LeadScan.

    python -m app.cli create-admin --email a@b.vn --name "Nguyễn Văn A"   # tạo/đặt lại tài khoản quản trị
    python -m app.cli diagnose                                          # kiểm tra DB, Redis, SMTP
    python -m app.cli send-test-mail [--to a@b.vn]                      # gửi thử 1 email (mặc định tới NOTIFY_EMAIL)
    python -m app.cli import-legacy DIR                                 # nhập hồ sơ JSON từ bản PHP cũ
    python -m app.cli crawl-profit500 --chart 12 --year 2026            # quét PROFIT500 vào kho doanh nghiệp
    python -m app.cli import-opportunities FILE.json [--publish]        # nhập cơ hội từ file JSON (mặc định: nháp)

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


def cmd_send_test_mail(args) -> int:
    from app.services.notify import mail_provider, send_mail

    cfg = get_settings()
    to = (args.to or cfg.notify_email).strip()
    prov = mail_provider(cfg)
    if not prov:
        print("Chưa cấu hình gửi email: đặt LEADSCAN_RESEND_API_KEY (hoặc LEADSCAN_SMTP_*) trong .env")
        return 1
    if not to:
        print("Chưa có người nhận: thêm --to email@... hoặc đặt LEADSCAN_NOTIFY_EMAIL trong .env")
        return 1
    print(f"Gửi thử qua {prov}, từ {cfg.mail_from_name} <{cfg.notify_from}> tới {to} ...")
    ok = send_mail(cfg, "[LeadScan] Email thử", "Đây là email thử từ hệ thống LeadScan. Nhận được email này nghĩa là cấu hình gửi mail đã đúng.", to=to)
    print("Đã gửi — kiểm tra hộp thư (cả mục Spam/Quảng cáo)." if ok else "Gửi KHÔNG thành công — xem lý do ở dòng log phía trên.")
    return 0 if ok else 1


def cmd_import_opportunities(args) -> int:
    """Nhập cơ hội từ file JSON (danh sách object theo đúng trường của form admin).

    Kiểm tra bằng cùng schema với form admin (OppIn). Chạy lại không nhân đôi:
    bỏ qua cơ hội đã có cùng tiêu đề + bên có nhu cầu. Mặc định lưu dạng nháp để admin
    duyệt giá/điểm rồi mới mở bán; --publish để mở bán ngay.
    """
    from pydantic import ValidationError

    from app.models import Opportunity
    from app.routes.admin_commerce import _apply_opp, _next_opp_code
    from app.schemas_commerce import OppIn

    path = Path(args.file)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Không đọc được {path}: {e}")
        return 1
    items = raw.get("opportunities") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        print('File phải là danh sách cơ hội hoặc {"opportunities": [...]}')
        return 1

    bodies: list[OppIn] = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            print(f"#{i}: không phải object")
            return 1
        it = {k: v for k, v in it.items() if not k.startswith("_")}  # trường "_..." chỉ là ghi chú trong file
        if args.publish:
            it["status"] = "published"
        try:
            bodies.append(OppIn.model_validate(it))
        except ValidationError as e:
            print(f"#{i} {it.get('title', '')!r} không hợp lệ:")
            for err in e.errors():
                print(f"   - {'.'.join(str(x) for x in err['loc'])}: {err['msg']}")
            return 1

    added = skipped = 0
    with new_session() as db:
        admin_id = db.scalar(select(AdminUser.id).where(AdminUser.email == args.by)) if args.by else None
        for b in bodies:
            dup = db.scalar(select(Opportunity.code).where(Opportunity.title == b.title, Opportunity.buyer_name == b.buyer_name))
            if dup:
                print(f"  bỏ qua (đã có {dup}): {b.title}")
                skipped += 1
                continue
            o = Opportunity(code=_next_opp_code(db), title=b.title, created_by_id=admin_id)
            _apply_opp(o, b)
            db.add(o)
            db.flush()
            print(f"  + {o.code} [{o.status}] {o.title}")
            added += 1
        if args.dry_run:
            db.rollback()
            print(f"Chạy thử: hợp lệ {len(bodies)} cơ hội, sẽ thêm {added}, bỏ qua {skipped}. Chưa lưu gì.")
        else:
            from app.services import matching

            for o in db.scalars(select(Opportunity).where(Opportunity.status == "published")).unique():
                if not o.embedding:
                    matching.match_opportunity(db, o)  # cơ hội mới mở bán → so khớp với các phiếu tìm cơ hội đã có
            db.commit()
            print(f"Đã thêm {added}, bỏ qua {skipped}.")
    return 0


def cmd_rematch(args) -> int:
    """Tính lại toàn bộ điểm phù hợp (sau khi đổi thuật toán hoặc mô hình embedding)."""
    from app.services import matching

    with new_session() as db:
        reqs, pairs = matching.rematch_all(db)
        db.commit()
    print(f"Đã so khớp lại {reqs} phiếu tìm cơ hội, tổng {pairs} cặp cơ hội phù hợp.")
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
    t = sub.add_parser("send-test-mail", help="Gửi thử 1 email để kiểm tra cấu hình Resend/SMTP")
    t.add_argument("--to", default="", help="Người nhận (mặc định LEADSCAN_NOTIFY_EMAIL)")
    t.set_defaults(fn=cmd_send_test_mail)
    o = sub.add_parser("import-opportunities", help="Nhập cơ hội từ file JSON (mặc định lưu nháp)")
    o.add_argument("file")
    o.add_argument("--publish", action="store_true", help="Mở bán ngay thay vì lưu nháp")
    o.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra, không lưu")
    o.add_argument("--by", default="", help="Email quản trị ghi là người tạo (không bắt buộc)")
    o.set_defaults(fn=cmd_import_opportunities)
    sub.add_parser("rematch", help="Tính lại điểm phù hợp giữa phiếu tìm cơ hội và phiếu cơ hội").set_defaults(fn=cmd_rematch)
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
