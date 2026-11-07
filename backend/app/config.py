"""Cấu hình đọc từ biến môi trường (tiền tố LEADSCAN_) hoặc file backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEADSCAN_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Cơ sở dữ liệu. Dev mặc định SQLite; production dùng PostgreSQL:
    #   postgresql+psycopg://user:pass@host:5432/leadscan
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'leadscan.db').as_posix()}"

    # Chống gửi chéo trang: các tên miền được phép gửi form/thao tác admin (ngoài chính host hiện tại)
    allowed_hosts: list[str] = Field(
        default_factory=lambda: [
            "leadscan.mcv.network",
            "leadscan.net",
            "www.leadscan.net",
            "leadscanb2b.com",
            "www.leadscanb2b.com",
        ]
    )

    # Header chứa IP thật khi chạy sau proxy (Nginx ghi đè X-Real-IP). Để trống = IP kết nối trực tiếp.
    # CHỈ đặt khi proxy phía trước luôn ghi đè header này.
    client_ip_header: str = ""

    # Đăng ký
    rate_limit_per_hour: int = 5
    min_fill_ms: int = 3000

    # Đăng nhập quản trị
    session_days: int = 7
    cookie_secure: bool = True  # chỉ gửi cookie qua HTTPS; đặt false khi chạy http://localhost
    login_attempts_per_15min: int = 10

    # Cổng thành viên
    member_url: str = "https://leadscan.net/thanh-vien"  # dùng cho link đặt lại mật khẩu trong email

    # Gói thành viên & nạp điểm (1 điểm = 1đ)
    membership_fee: int = 10_000_000
    membership_points: int = 10_000_000
    membership_days: int = 365
    topup_packs: list[int] = Field(default_factory=lambda: [5_000_000, 10_000_000, 20_000_000, 50_000_000])
    topup_min: int = 1_000_000
    topup_max: int = 500_000_000

    # Thanh toán: "infocms" (thật) hoặc "mock" (giả lập để chạy thử — KHÔNG dùng trên production)
    payment_provider: str = "infocms"
    order_expire_hours: int = 24
    # Tài khoản thu (InfoCMS Smart Collect cấp) để sinh mã VietQR
    payment_bank_bin: str = ""  # mã BIN ngân hàng theo NAPAS, vd 970436 = Vietcombank
    payment_bank_name: str = ""
    payment_account_no: str = ""
    payment_account_name: str = ""
    # Webhook InfoCMS báo đã nhận tiền: ký HMAC-SHA256 trên body bằng secret này
    infocms_webhook_secret: str = ""
    infocms_signature_header: str = "X-Signature"

    # Yêu cầu xuất hoá đơn được gửi tới email này (kế toán xuất thủ công)
    invoice_email: str = "vylyy9999@gmail.com"

    # Hàng đợi việc nền (Celery + Redis)
    redis_url: str = "redis://localhost:6379/0"
    celery_eager: bool = False  # True = chạy task ngay trong tiến trình (dùng cho test)

    # Gửi email: "auto" (Resend nếu có API key, ngược lại SMTP) | "resend" | "smtp"
    mail_mailer: str = "auto"
    resend_api_key: str = ""
    mail_from_name: str = "LeadScan B2B"
    # Email báo quản trị khi có đăng ký mới (để trống = không gửi)
    notify_email: str = ""
    notify_from: str = "no-reply@leadscan.net"  # địa chỉ gửi đi — tên miền phải được xác minh trên Resend
    admin_url: str = "https://leadscan.net/admin"  # link trong email thông báo
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_ssl: bool = False  # True = SMTPS (cổng 465); False = STARTTLS


@lru_cache
def get_settings() -> Settings:
    return Settings()
