"""Gửi email (Resend hoặc SMTP). Lỗi gửi mail chỉ ghi log, không làm hỏng luồng chính."""

import base64
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


# Tệp đính kèm: (tên file, mime, nội dung)
Attachment = tuple[str, str, bytes]


def _send_resend(
    cfg: Settings, to: str, subject: str, body: str, reply_to: str = "", attachments: list[Attachment] | None = None
) -> bool:
    """Gửi qua Resend HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""
    payload: dict = {"from": _sender(cfg), "to": [to], "subject": subject, "text": body}
    if reply_to:
        payload["reply_to"] = reply_to
    if attachments:
        payload["attachments"] = [
            {"filename": name, "content": base64.b64encode(data).decode(), "content_type": mime} for name, mime, data in attachments
        ]
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {cfg.resend_api_key}"},
            json=payload,
            timeout=30 if attachments else 15,
        )
    except httpx.HTTPError as e:
        log.error("Không gửi được email qua Resend: %s", e)
        return False
    if 200 <= r.status_code < 300:
        log.info("Đã gửi email qua Resend tới %s (id %s)", to, r.json().get("id") if r.content else "?")
        return True
    log.error("Resend từ chối email tới %s: HTTP %s %s", to, r.status_code, r.text[:300])
    return False


def _send_smtp(
    cfg: Settings, to: str, subject: str, body: str, reply_to: str = "", attachments: list[Attachment] | None = None
) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _sender(cfg)
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    for name, mime, data in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype or "application", subtype=subtype or "octet-stream", filename=name)
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


def send_mail(
    cfg: Settings,
    subject: str,
    body: str,
    to: str | None = None,
    reply_to: str = "",
    attachments: list[Attachment] | None = None,
) -> bool:
    to = to or cfg.notify_email
    provider = mail_provider(cfg)
    if not to or not provider:
        return False
    send = _send_resend if provider == "resend" else _send_smtp
    if reply_to or attachments:
        return send(cfg, to, subject, body, reply_to=reply_to, attachments=attachments)
    return send(cfg, to, subject, body)


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
    failed = (
        f"!! Hệ thống CHƯA tự xuất được hoá đơn điện tử qua IAM: {inv.einvoice_error}\n"
        "   Kiểm tra lại trên IAM (mã tra cứu = mã đơn) rồi bấm \"Phát hành HĐĐT\" ở trang Hoá đơn, hoặc xuất thủ công.\n\n"
        if inv.einvoice_error
        else ""
    )
    body = (
        "YÊU CẦU XUẤT HOÁ ĐƠN — LeadScan B2B\n"
        "=====================================\n\n"
        + failed
        + f"Mã đơn thanh toán : {o.code}\n"
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


def send_partner_password_reset(cfg: Settings, email: str, name: str, token: str) -> bool:
    link = f"{cfg.partner_url.rstrip('/')}/dat-lai-mat-khau?token={token}"
    body = (
        f"Chào {name},\n\n"
        "Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu tài khoản Đối tác LeadScan.\n"
        f"Mở liên kết sau trong 60 phút để đặt mật khẩu mới:\n\n{link}\n\n"
        "Nếu không phải bạn, hãy bỏ qua email này — mật khẩu hiện tại vẫn giữ nguyên.\n"
    )
    return send_mail(cfg, "[Đối tác LeadScan] Đặt lại mật khẩu", body, to=email)


def send_partner_welcome(cfg: Settings, email: str, name: str, code: str) -> bool:
    base = cfg.partner_url.rstrip("/")
    body = (
        f"Chào {name},\n\n"
        "Cảm ơn bạn đã đăng ký Đối tác LeadScan.\n"
        f"Mã đối tác của bạn: {code}\n\n"
        f"  • Đăng nhập cổng đối tác: {base}/dang-nhap\n"
        f"  • Email đăng nhập: {email}\n\n"
        "Bước tiếp theo: xác thực số điện thoại bằng mã OTP để kích hoạt tài khoản, rồi gửi cơ hội đầu tiên.\n"
        "Mỗi cơ hội đạt xác minh nhận ít nhất 1 ly cafe cảm ơn; khi phiếu được bán, bạn nhận hoa hồng theo từng lượt bán.\n\n"
        f"Quên mật khẩu? Đặt lại tại {base}/quen-mat-khau\n\n"
        "Trân trọng,\nĐội ngũ LeadScan\n"
    )
    return send_mail(cfg, "[Đối tác LeadScan] Chào mừng bạn", body, to=email)


def send_partner_submission_update(cfg: Settings, s) -> bool:
    """Báo đối tác kết quả xác minh 1 cơ hội đã gửi (Đạt / Trùng / Không đạt / Đóng góp bổ sung)."""
    from app.models import REJECT_REASONS, SUBMISSION_STATUSES

    p = s.partner
    link = f"{cfg.partner_url.rstrip('/')}/co-hoi/{s.id}"
    status = SUBMISSION_STATUSES.get(s.status, s.status)
    lines = [f"Chào {p.full_name},\n", f"Cơ hội {s.code} ({s.company_name}) đã có kết quả xác minh: {status}."]
    if s.status == "rejected" and s.reject_reason:
        lines.append(f"Lý do: {REJECT_REASONS.get(s.reject_reason, s.reject_reason)}.")
    if s.status == "verified":
        lines.append("LeadScan sẽ hoàn thiện và mở bán phiếu cơ hội; bạn theo dõi số lượt bán trong cổng đối tác.")
    if s.partner_note:
        lines.append(f"\nGhi chú từ LeadScan:\n{s.partner_note}")
    lines.append(f"\nXem chi tiết: {link}\n\nTrân trọng,\nĐội ngũ LeadScan\n")
    return send_mail(cfg, f"[Đối tác LeadScan] {s.code}: {status}", "\n".join(lines), to=p.email)


def send_partner_withdrawal_update(cfg: Settings, w) -> bool:
    """Báo đối tác: lệnh rút được duyệt / đã chi / bị từ chối."""
    p = w.partner
    link = f"{cfg.partner_url.rstrip('/')}/rut-tien"
    vnd = lambda n: f"{n:,}đ".replace(",", ".")  # noqa: E731
    head = {
        "approved": f"Lệnh rút {w.code} ({vnd(w.amount)}) đã được duyệt và sẽ chi trong lô gần nhất.",
        "paid": f"LeadScan đã chuyển {vnd(w.net_amount)} cho lệnh rút {w.code} về tài khoản {w.payee.get('bank_name', '')} ••••{w.payee.get('account_last4', '')}.",
        "rejected": f"Lệnh rút {w.code} ({vnd(w.amount)}) không được duyệt. Lý do: {w.reject_reason}. Số tiền đã trở lại số dư Khả dụng.",
    }.get(w.status)
    if not head:
        return False
    lines = [f"Chào {p.full_name},\n", head]
    if w.status == "paid" and w.tax_withheld:
        lines.append(f"Thuế TNCN đã khấu trừ: {vnd(w.tax_withheld)} — LeadScan sẽ cấp chứng từ khấu trừ thuế.")
    lines.append(f"\nXem chi tiết: {link}\n\nTrân trọng,\nĐội ngũ LeadScan\n")
    return send_mail(cfg, f"[Đối tác LeadScan] Lệnh rút {w.code}", "\n".join(lines), to=p.email)


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


def notify_search_request(cfg: Settings, req, match_count: int | None = None) -> bool:
    """Báo quản trị (LEADSCAN_NOTIFY_EMAIL) khi thành viên gửi yêu cầu Enrich tìm kiếm cơ hội.

    Hệ thống đã tự so khớp và trả kết quả cho khách ngay; email chỉ để quản trị nắm tình hình / bổ sung khi cần.
    """
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
        "KẾT QUẢ TỰ ĐỘNG",
        (f"Hệ thống đã tìm thấy {match_count} cơ hội phù hợp — khách đã thấy ngay trong cổng thành viên."
         if match_count is not None else "Hệ thống đang so khớp tự động — khách sẽ thấy kết quả trong cổng thành viên."),
        "",
        f"Xem / trả lời khách (nếu cần): {cfg.admin_url.rstrip('/')}/yeu-cau-tim-co-hoi",
        f"Hồ sơ khách hàng      : {cfg.admin_url.rstrip('/')}/khach-hang/{c.id}",
    ]
    return send_mail(cfg, f"[LeadScan] Yêu cầu tìm cơ hội #{req.id}: {c.name}", "\n".join(lines) + "\n")


def send_match_digest(cfg: Settings, email: str, name: str, groups: list[tuple]) -> bool:
    """Báo thành viên: có cơ hội mới phù hợp với phiếu tìm cơ hội (tìm kiếm liên tục). Gộp nhiều cơ hội trong 1 email.

    groups: [(phiếu tìm, [(phiếu cơ hội, điểm), ...]), ...]
    """
    base = _member_base(cfg)
    total = sum(len(items) for _, items in groups)
    lines = [f"Chào {name},", "", f"LeadScan vừa tìm thấy {total} cơ hội mới phù hợp với yêu cầu tìm cơ hội của bạn.", ""]
    for req, items in groups:
        note = " ".join((req.note or "").split())
        lines.append(f"YÊU CẦU #{req.id}: {note[:90]}{'…' if len(note) > 90 else ''}")
        for o, score in items[:10]:
            lines.append(f"  • {o.title} — {score} điểm phù hợp")
            lines.append(f"    {base}/co-hoi/{o.id}")
        if len(items) > 10:
            lines.append(f"  … và {len(items) - 10} cơ hội khác")
        lines.append(f"  Xem tất cả: {base}/phu-hop?yeu-cau={req.id}")
        lines.append("")
    lines += [
        "Các cơ hội này đã được chấm điểm riêng cho bạn và thêm vào Tất cả cơ hội + Kho của tôi.",
        "Yêu cầu của bạn vẫn đang tìm kiếm liên tục — có cơ hội mới phù hợp LeadScan sẽ báo tiếp.",
        "",
        "Trân trọng,",
        "Đội ngũ LeadScan",
    ]
    subject = f"[LeadScan] {total} cơ hội mới phù hợp với yêu cầu của bạn"
    return send_mail(cfg, subject, "\n".join(lines) + "\n", to=email)


# ------------------------------------------------------------------ tuyển dụng


def recruit_inbox(cfg: Settings, job=None) -> str:
    """Hộp thư nhận hồ sơ: email riêng của bài → LEADSCAN_RECRUIT_EMAIL → LEADSCAN_NOTIFY_EMAIL."""
    return (getattr(job, "apply_email", "") or cfg.recruit_email or cfg.notify_email or "").strip()


def _size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


def send_job_application(cfg: Settings, a, cv_data: bytes | None = None) -> bool:
    """Gửi hồ sơ ứng viên về hộp thư tuyển dụng (Reply-To = email ứng viên, đính kèm file CV nếu có)."""
    to = recruit_inbox(cfg, a.job)
    if not to:
        log.warning("Chưa cấu hình email nhận hồ sơ (LEADSCAN_RECRUIT_EMAIL) — hồ sơ #%s chỉ lưu trong hệ thống", a.id)
        return False
    job_link = f"{cfg.site_url.rstrip('/')}/tuyen-dung/{a.job.slug}" if a.job else "—"
    lines = [
        "HỒ SƠ ỨNG TUYỂN MỚI — LeadScan",
        "===============================",
        "",
        f"Vị trí            : {a.job_title}",
        f"Họ và tên         : {a.full_name}",
        f"Số điện thoại     : {a.phone}",
        f"Email             : {a.email}",
        f"Link CV           : {a.cv_url or '—'}",
        f"File CV           : {f'{a.cv_filename} ({_size(a.cv_size)}) — đính kèm email này' if a.cv_filename else '—'}",
        f"Portfolio / SP    : {a.portfolio_url or '—'}",
        f"Gửi lúc           : {_vn(a.created_at)}",
        "",
        "GIỚI THIỆU NGẮN",
        a.intro or "—",
        "",
        f"Bài tuyển dụng    : {job_link}",
        f"Quản lý hồ sơ     : {cfg.admin_url.rstrip('/')}/tuyen-dung/ho-so?id={a.id}",
        "",
        "Trả lời email này để liên hệ trực tiếp với ứng viên.",
    ]
    attachments = [(a.cv_filename, a.cv_mime or "application/octet-stream", cv_data)] if a.cv_filename and cv_data else None
    return send_mail(
        cfg,
        f"[Tuyển dụng] {a.job_title} — {a.full_name}",
        "\n".join(lines) + "\n",
        to=to,
        reply_to=a.email,
        attachments=attachments,
    )


def send_application_receipt(cfg: Settings, a) -> bool:
    """Xác nhận cho ứng viên: LeadScan đã nhận hồ sơ."""
    lines = [
        f"Chào {a.full_name},",
        "",
        f"Cảm ơn bạn đã quan tâm và ứng tuyển vị trí {a.job_title} tại LeadScan.",
        "Chúng tôi đã nhận được hồ sơ của bạn. Bộ phận tuyển dụng sẽ xem xét và liên hệ với bạn",
        "qua số điện thoại hoặc email này trong vòng 3–5 ngày làm việc nếu hồ sơ phù hợp.",
        "",
        "Thông tin bạn đã gửi:",
        f"  • Số điện thoại : {a.phone}",
        f"  • Email         : {a.email}",
        f"  • CV            : {a.cv_filename or a.cv_url or '—'}",
        "",
        f"Xem các vị trí khác: {cfg.site_url.rstrip('/')}/tuyen-dung",
        "",
        "Trân trọng,",
        "Bộ phận Tuyển dụng LeadScan",
    ]
    return send_mail(cfg, f"[LeadScan] Đã nhận hồ sơ ứng tuyển {a.job_title}", "\n".join(lines) + "\n", to=a.email)
