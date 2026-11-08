"""Gửi email (Resend hoặc SMTP). Lỗi gửi mail chỉ ghi log, không làm hỏng luồng chính."""

import logging
import smtplib
import ssl
from datetime import UTC
from email.message import EmailMessage
from email.utils import formataddr
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.models import Company

log = logging.getLogger("leadscan.notify")


def _sender(cfg: Settings) -> str:
    return formataddr((cfg.mail_from_name, cfg.notify_from)) if cfg.mail_from_name else cfg.notify_from


def _send_resend(cfg: Settings, to: str, subject: str, body: str) -> bool:
    """Gửi qua Resend HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {cfg.resend_api_key}"},
            json={"from": _sender(cfg), "to": [to], "subject": subject, "text": body},
            timeout=15,
        )
    except httpx.HTTPError as e:
        log.error("Không gửi được email qua Resend: %s", e)
        return False
    if 200 <= r.status_code < 300:
        log.info("Đã gửi email qua Resend tới %s (id %s)", to, r.json().get("id") if r.content else "?")
        return True
    log.error("Resend từ chối email tới %s: HTTP %s %s", to, r.status_code, r.text[:300])
    return False


def _send_smtp(cfg: Settings, to: str, subject: str, body: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _sender(cfg)
    msg["To"] = to
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        if cfg.smtp_ssl:
            server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=15, context=ctx)
        else:
            server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15)
            server.starttls(context=ctx)
        with server:
            if cfg.smtp_user:
                server.login(cfg.smtp_user, cfg.smtp_password)
            server.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as e:
        log.error("Không gửi được email qua SMTP: %s", e)
        return False


def mail_provider(cfg: Settings) -> str | None:
    """resend nếu có RESEND API key, smtp nếu có SMTP host, None nếu chưa cấu hình."""
    if cfg.mail_mailer == "resend" or (cfg.mail_mailer == "auto" and cfg.resend_api_key):
        return "resend" if cfg.resend_api_key else None
    return "smtp" if cfg.smtp_host else None


def send_mail(cfg: Settings, subject: str, body: str, to: str | None = None) -> bool:
    to = to or cfg.notify_email
    provider = mail_provider(cfg)
    if not to or not provider:
        return False
    return (_send_resend if provider == "resend" else _send_smtp)(cfg, to, subject, body)


def notify_new_registration(cfg: Settings, c: Company) -> bool:
    contact = c.contacts[0] if c.contacts else None
    body = (
        f"Mã đăng ký: {c.code}\n"
        f"Doanh nghiệp: {c.name}\n"
        f"MST: {c.tax_code}\n"
        f"Ngành hàng: {c.industry} · {c.province}\n"
        + (f"Liên hệ: {contact.full_name} - {contact.phone} - {contact.email}\n" if contact else "")
        + f"\nXem và xử lý: {cfg.admin_url.rstrip('/')}/khach-hang/{c.id}\n"
    )
    return send_mail(cfg, f"[LeadScan] Đăng ký mới: {c.name} ({c.code})", body)


def _vn(dt) -> str:
    if not dt:
        return "—"
    return dt.replace(tzinfo=UTC).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%d/%m/%Y %H:%M")


def _vnd(n: int | None) -> str:
    return f"{(n or 0):,}đ".replace(",", ".")


def send_invoice_request(cfg: Settings, inv) -> bool:
    """Gửi thông tin xuất hoá đơn tới kế toán (cfg.invoice_email) để xuất thủ công."""
    o = inv.order
    c = o.company
    body = (
        "YÊU CẦU XUẤT HOÁ ĐƠN — LeadScan B2B\n"
        "=====================================\n\n"
        f"Mã đơn thanh toán : {o.code}\n"
        f"Nội dung          : {'Phí thành viên LeadScan' if o.kind == 'membership' else 'Nạp điểm LeadScan'}\n"
        f"Số tiền           : {_vnd(o.paid_amount or o.amount)}\n"
        f"Thanh toán lúc    : {_vn(o.paid_at)}\n\n"
        "THÔNG TIN XUẤT HOÁ ĐƠN\n"
        f"Tên đơn vị        : {inv.company_name}\n"
        f"Mã số thuế        : {inv.tax_code}\n"
        f"Địa chỉ           : {inv.address}\n"
        f"Người mua hàng    : {inv.buyer_name or '—'}\n"
        f"Email nhận HĐ     : {inv.receive_email}\n"
        f"Ghi chú           : {inv.note or '—'}\n\n"
        f"Khách hàng trên hệ thống: {c.name} ({c.code})\n"
        f"Sau khi xuất, cập nhật số hoá đơn tại: {cfg.admin_url.rstrip('/')}/hoa-don\n"
    )
    return send_mail(cfg, f"[LeadScan] Yêu cầu xuất hoá đơn {o.code} — {inv.company_name}", body, to=cfg.invoice_email)


def send_password_reset(cfg: Settings, email: str, name: str, token: str) -> bool:
    link = f"{cfg.member_url.rstrip('/')}/dat-lai-mat-khau?token={token}"
    body = (
        f"Chào {name},\n\n"
        "Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu tài khoản LeadScan B2B.\n"
        f"Mở liên kết sau trong 60 phút để đặt mật khẩu mới:\n\n{link}\n\n"
        "Nếu không phải bạn, hãy bỏ qua email này — mật khẩu hiện tại vẫn giữ nguyên.\n"
    )
    return send_mail(cfg, "[LeadScan] Đặt lại mật khẩu", body, to=email)


def _member_base(cfg: Settings) -> str:
    return cfg.member_url.rstrip("/")


def send_welcome(cfg: Settings, c: Company, email: str, name: str) -> bool:
    """Gửi khách vừa đăng ký: xác nhận đã nhận hồ sơ + bước tiếp theo."""
    base = _member_base(cfg)
    body = (
        f"Chào {name},\n\n"
        f"Cảm ơn bạn đã đăng ký LeadScan cho {c.name}.\n"
        f"Mã đăng ký: {c.code}\n\n"
        "Tài khoản thành viên của bạn đã được tạo:\n"
        f"  • Đăng nhập: {base}/dang-nhap\n"
        f"  • Email đăng nhập: {email}\n"
        "  • Mật khẩu: mật khẩu bạn đã đặt khi đăng ký\n\n"
        "Bước tiếp theo:\n"
        f"  1. Thanh toán phí thành viên {_vnd(cfg.membership_fee)}/năm trong cổng thành viên ({base}/nap-tien).\n"
        f"     Toàn bộ số tiền được cộng thành {cfg.membership_points:,} điểm để mua phiếu cơ hội.\n".replace(",", ".")
        + "  2. Cập nhật chân dung cơ hội để AI tìm đúng khách hàng bạn cần.\n"
        "  3. Đội ngũ LeadScan sẽ liên hệ xác nhận và hỗ trợ bạn bắt đầu.\n\n"
        f"Quên mật khẩu? Đặt lại tại {base}/quen-mat-khau\n\n"
        "Trân trọng,\nĐội ngũ LeadScan\n"
    )
    return send_mail(cfg, f"[LeadScan] Chào mừng {c.name} — đăng ký thành công", body, to=email)


def send_payment_success(cfg: Settings, order, email: str, name: str) -> bool:
    """Gửi thành viên khi đơn thanh toán được ghi nhận (phí thành viên hoặc nạp điểm)."""
    c = order.company
    base = _member_base(cfg)
    is_membership = order.kind == "membership"
    lines = [
        f"Chào {name},\n",
        f"LeadScan đã nhận thanh toán {'phí thành viên' if is_membership else 'nạp điểm'} của {c.name}.\n",
        f"Mã đơn            : {order.code}",
        f"Số tiền           : {_vnd(order.paid_amount or order.amount)}",
        f"Thời gian         : {_vn(order.paid_at)}",
        f"Điểm được cộng    : {order.points:,}".replace(",", "."),
        f"Số dư hiện tại    : {c.points_balance:,} điểm".replace(",", "."),
    ]
    if c.membership_expires_at:
        lines.append(f"Thành viên đến    : {_vn(c.membership_expires_at)[:10]}")
    lines += [
        "",
        f"Bắt đầu xem kho cơ hội: {base}/co-hoi",
        f"Cần xuất hoá đơn? Nhập thông tin tại: {base}/nap-tien/{order.code}",
        "",
        "Trân trọng,\nĐội ngũ LeadScan",
    ]
    subject = "[LeadScan] Kích hoạt thành viên thành công" if is_membership else f"[LeadScan] Nạp điểm thành công — {order.code}"
    return send_mail(cfg, subject, "\n".join(lines) + "\n", to=email)


def notify_payment_admin(cfg: Settings, order) -> bool:
    """Báo quản trị (LEADSCAN_NOTIFY_EMAIL) khi có thanh toán được ghi nhận."""
    c = order.company
    how = f"xác nhận thủ công bởi {order.confirmed_by.full_name}" if order.confirmed_by else "tự động"
    body = (
        f"Khách hàng   : {c.name} ({c.code})\n"
        f"Loại         : {'Phí thành viên' if order.kind == 'membership' else 'Nạp điểm'}\n"
        f"Mã đơn       : {order.code}\n"
        f"Số tiền      : {_vnd(order.paid_amount or order.amount)}\n"
        f"Ghi nhận     : {_vn(order.paid_at)} ({how})\n"
        f"Số dư sau    : {c.points_balance:,} điểm\n".replace(",", ".")
        + f"\nXem khách hàng: {cfg.admin_url.rstrip('/')}/khach-hang/{c.id}\n"
    )
    kind = "phí thành viên" if order.kind == "membership" else "nạp điểm"
    return send_mail(cfg, f"[LeadScan] Đã nhận thanh toán {kind}: {c.name} — {_vnd(order.paid_amount or order.amount)}", body)


def _criteria_lines(c: dict) -> list[str]:
    join = lambda v: ", ".join(v) if v else "(không giới hạn)"  # noqa: E731
    return [
        f"Ngành hàng        : {join(c.get('industries') or [])}",
        f"Khu vực           : {join(c.get('regions') or [])}",
        f"Quy mô khách hàng : {join(c.get('sizes') or [])}",
        f"Loại cơ hội       : {join(c.get('sources') or [])}",
        f"Điểm tối thiểu    : {('≥ ' + str(c['min_score'])) if c.get('min_score') else 'Mọi mức'}",
    ]


def notify_search_request(cfg: Settings, req) -> bool:
    """Báo quản trị (LEADSCAN_NOTIFY_EMAIL) khi thành viên gửi yêu cầu Enrich tìm kiếm cơ hội."""
    c = req.company
    u = req.member_user
    contact = next((x for x in c.contacts if x.is_primary), c.contacts[0] if c.contacts else None)
    lines = [
        "YÊU CẦU ENRICH TÌM KIẾM CƠ HỘI — LeadScan B2B",
        "==============================================",
        "",
        f"Khách hàng        : {c.name} ({c.code})",
        f"Ngành của khách   : {c.industry or '—'} · {c.province or '—'}",
        f"Người gửi         : {u.full_name + ' <' + u.email + '>' if u else '—'}",
    ]
    if contact:
        lines.append(f"Liên hệ chính     : {contact.full_name} · {contact.phone or '—'} · {contact.email or '—'}")
    lines += [
        f"Gửi lúc           : {_vn(req.created_at)}",
        "",
        "TIÊU CHÍ",
        *_criteria_lines(req.criteria or {}),
        "",
        "MÔ TẢ YÊU CẦU",
        req.note or "—",
        "",
        f"Xử lý và trả lời khách: {cfg.admin_url.rstrip('/')}/yeu-cau-tim-co-hoi",
        f"Hồ sơ khách hàng      : {cfg.admin_url.rstrip('/')}/khach-hang/{c.id}",
    ]
    return send_mail(cfg, f"[LeadScan] Yêu cầu tìm cơ hội #{req.id}: {c.name}", "\n".join(lines) + "\n")
