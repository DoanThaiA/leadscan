"""Cấu hình đọc từ biến môi trường (tiền tố LEADSCAN_) hoặc file backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
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

    # Cổng đối tác (/doi-tac) — tài khoản, phiên, dữ liệu tách hẳn cổng thành viên
    partner_url: str = "https://leadscan.net/doi-tac"  # link trong email gửi đối tác
    partner_terms_version: str = "2026-11"  # phiên bản Điều khoản đối tác — lưu lại khi đối tác bấm đồng ý
    # Mã OTP kích hoạt tài khoản đối tác — gửi qua email (Resend/SMTP như các email khác). Chưa cấu hình gửi mail
    # thì mã chỉ ghi vào log máy chủ; admin có thể kích hoạt tay trong trang quản trị Đối tác.
    otp_ttl_minutes: int = 15
    otp_resend_seconds: int = 60  # chờ tối thiểu giữa 2 lần gửi mã
    otp_max_per_hour: int = 5  # số mã tối đa mỗi tài khoản / giờ
    otp_max_attempts: int = 5  # số lần nhập sai tối đa mỗi mã
    # Xác minh cơ hội đối tác gửi
    partner_min_score: int = 60  # điểm chất lượng tối thiểu để "Đạt xác minh"
    partner_dup_days: int = 90  # kiểm tra trùng (MST / tên + nhóm nhu cầu) trong N ngày gần nhất
    partner_sla_workdays: int = 2  # hạn xác minh, tính theo ngày làm việc (T2–T6)
    partner_submit_per_day: int = 20  # số cơ hội tối đa mỗi đối tác gửi trong 24 giờ
    # Khoá Fernet mã hoá số định danh + số tài khoản ngân hàng trong hồ sơ thanh toán đối tác.
    # Tạo: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # MẤT KHOÁ = không đọc lại được số tài khoản đã lưu. Để trống = chưa mở rút tiền.
    partner_secret_key: str = ""

    # Gói thành viên & nạp điểm (1 điểm = 1đ)
    membership_fee: int = 89_000  # phí thành viên/năm
    membership_points: int = 89_000  # số điểm nạp vào ví khi đóng phí (bằng phí)
    membership_days: int = 365
    topup_packs: list[int] = Field(default_factory=lambda: [5_000_000, 10_000_000, 20_000_000, 50_000_000])
    topup_min: int = 1_000_000
    topup_max: int = 500_000_000

    # Thanh toán: "mcv" (cổng MCV — mặc định), "infocms" (gọi thẳng InfoCMS, cần khoá RSA) hoặc
    # "mock" (giả lập tại chỗ để chạy thử — KHÔNG dùng trên production)
    payment_provider: str = "mcv"
    order_expire_hours: int = 24

    # Cổng thanh toán MCV (https://api.mcv.network). Khoá do admin MCV cấp; Secret chỉ nằm trên server.
    mcv_api_key: str = Field("", validation_alias=AliasChoices("MCV_API_KEY", "LEADSCAN_MCV_API_KEY"))  # mcvpk_test_… / mcvpk_live_…
    mcv_secret: str = Field("", validation_alias=AliasChoices("MCV_SECRET", "LEADSCAN_MCV_SECRET"))  # mcvsk_…
    mcv_base_url: str = Field("https://api.mcv.network", validation_alias=AliasChoices("MCV_BASE_URL", "LEADSCAN_MCV_BASE_URL"))
    # Nhận thanh toán test_mode (khoá test, giả lập) — CHỈ bật khi chạy thử. Production để false: webhook test bị bỏ qua.
    mcv_allow_test_mode: bool = False
    # Trang MCV đưa khách quay về sau khi trả (phải https + thuộc tên miền đã đăng ký với MCV). Không phải https → không gửi.
    mcv_return_url: str = "https://leadscan.net/thanh-vien/nap-tien/ket-qua"
    mcv_expires_minutes: int = 15  # hạn mã QR (5–60 phút); hết hạn khách bấm "Tạo mã QR mới"
    mcv_timeout_seconds: float = 15.0
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

    # Hoá đơn điện tử IAM Invoice (iamsoftware.com.vn): tự xuất HĐĐT sau khi thanh toán.
    # Tắt (mặc định) → giữ cách cũ: email kế toán xuất thủ công.
    iam_enabled: bool = False
    iam_base_url: str = "https://demo-invoice.iamsoftware.com.vn"  # production: link IAM cấp
    iam_username: str = ""  # vd 0312303803-999 (MST-mã tài khoản)
    iam_password: str = ""
    iam_invoice_form: str = "1"  # ký hiệu mẫu số (1 = HĐ GTGT)
    iam_invoice_serial: str = ""  # ký hiệu hoá đơn đã đăng ký, vd C26TYY
    # Ký số luôn khi tạo (phát hành ngay). False = chỉ tạo hoá đơn nháp trên IAM, kế toán vào IAM ký.
    iam_sign: bool = True
    iam_cert_sn: str = ""  # serial chứng thư số; trống = lấy chứng thư IntrustCA đầu tiên của tài khoản
    iam_pin_code: str = ""  # mã PIN ký số từ xa
    iam_vat_rate: str = "10"  # thuế suất GTGT: 0, 5, 8, 10, KCT, KKKNT. Số tiền đơn hàng đã GỒM thuế.
    iam_payment_method: str = "PiCashOrWireTransfer"  # TM/CK
    iam_unit: str = "Gói"  # đơn vị tính trên hoá đơn
    # Thanh toán xong → tự lấy thông tin doanh nghiệp đã đăng ký (tên, MST, địa chỉ) để xuất luôn, khách không phải điền.
    # False = chờ khách gửi form "Thông tin xuất hoá đơn" rồi mới xuất.
    iam_issue_on_payment: bool = True
    iam_timeout_seconds: float = 60.0

    # Tuyển dụng: hồ sơ ứng viên gửi về email này (từng bài có thể đặt email riêng). Trống = dùng notify_email.
    recruit_email: str = ""
    apply_rate_limit_per_hour: int = 5  # số hồ sơ tối đa mỗi IP / giờ
    apply_cv_max_mb: int = 5
    site_url: str = "https://leadscan.net"  # link bài tuyển dụng trong email

    # So khớp cơ hội ↔ yêu cầu (hybrid: tiêu chí + từ khoá + embedding ngữ nghĩa, vector lưu bằng pgvector)
    # Embedding Cohere: chỉ cần đặt COHERE_API_KEY. Không có khoá → dùng vector "hash" chạy tại chỗ (dev/test).
    cohere_api_key: str = Field("", validation_alias=AliasChoices("COHERE_API_KEY", "LEADSCAN_COHERE_API_KEY"))
    cohere_embed_url: str = "https://api.cohere.com/v2/embed"
    # Embed 5: lập chỉ mục bằng Pro, truy vấn bằng Fast (cùng không gian vector — khuyến nghị của Cohere)
    cohere_doc_model: str = "embed-v5.0-pro"
    cohere_query_model: str = "embed-v5.0-fast"
    # Khoá Trial (miễn phí) của Cohere: dùng được mọi model nhưng tối đa 1.000 lần gọi API/tháng, 2.000 văn bản/phút.
    # Hết hạn mức tháng → không gọi Cohere nữa, so khớp chỉ dùng tiêu chí + từ khoá tới tháng sau. 0 = không giới hạn.
    cohere_monthly_limit: int = 1000
    match_min_fit: int = 35  # điểm "khớp yêu cầu" tối thiểu (0–100) để cơ hội được xem là phù hợp
    match_candidates: int = 500  # số ứng viên gần nhất (pgvector) đưa vào chấm điểm hybrid mỗi lần so khớp
    # Cosine Cohere quy ra điểm ngữ nghĩa: ≤ low → 0, ≥ high → 100. Nên chỉnh lại theo dữ liệu thật.
    cohere_cos_low: float = 0.20
    cohere_cos_high: float = 0.60

    # Ảnh & tài liệu của phiếu cơ hội: Cloudflare R2 (S3-compatible). Bucket để riêng tư — trình duyệt upload
    # thẳng bằng link ký sẵn, xem/tải bằng link ký ngắn hạn. Để trống = tắt tính năng gắn tệp.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_endpoint: str = ""  # mặc định https://<account_id>.r2.cloudflarestorage.com
    attach_max_files: int = 20  # số tệp tối đa mỗi phiếu
    attach_image_max_mb: int = 10
    attach_file_max_mb: int = 25
    attach_url_ttl: int = 900  # giây — hạn của link xem/tải

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
