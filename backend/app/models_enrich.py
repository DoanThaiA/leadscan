"""Hệ thống làm giàu dữ liệu doanh nghiệp theo mã số thuế (tài liệu "Yêu cầu nghiệp vụ", mục 8).

Ba schema PostgreSQL tách biệt để sau này cấp quyền DB riêng cho từng kho (T01):
  kho_a     dữ liệu doanh nghiệp — không chứa dữ liệu cá nhân
              EnrichCompany (khoá MST) · CompanyEvidence · CompanyChange · EnrichSignal
  kho_b     dữ liệu cá nhân — mọi truy cập đi qua app/enrich/khob.py (kiểm quyền + ghi nhật ký)
              EnrichPerson · PersonRole · EnrichContact · PersonEvidence · PersonChange · OptOut · AccessLog
  thu_thap  vận hành thu thập
              EnrichSource (nguồn/connector + độ tin cậy) · EnrichBatch/EnrichBatchItem (lô MST + mục đích)
              SourcePage (bản gốc đã lưu) · CrawlJob (hàng đợi MST × connector)

SQLite (dev/test) không có schema → app/db.py bỏ tên schema qua schema_translate_map, nên tên bảng phải
duy nhất trên toàn bộ CSDL (tiền tố enrich_).

Nguyên tắc (mục 6, 8):
  • Giá trị không bao giờ ghi đè: mỗi lần một nguồn nói một điều là một dòng evidence. Cột trên
    EnrichCompany chỉ là giá trị hiển thị do app/enrich/merge.py chọn lại từ evidence.
  • Trường không có evidence thì không hiển thị.
  • T09: kho B KHÔNG có cột cho CCCD, hộ khẩu, tài khoản ngân hàng, sức khoẻ, quan hệ gia đình
    (tests/test_enrich.py kiểm tra tên cột).
"""

from datetime import date, datetime

from sqlalchemy import (
    DDL,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import ENRICH_SCHEMAS, Base, utcnow
from app.enrich.crypto import EncryptedMst

KHO_A = "kho_a"
KHO_B = "kho_b"
THU_THAP = "thu_thap"

# Vai trò trong phân hệ làm giàu dữ liệu (mục 3) — quyền chi tiết ở app/enrich/permissions.py
ENRICH_ROLES = {
    "quan_tri": "Quản trị hệ thống",
    "bien_tap": "Biên tập dữ liệu",
    "kinh_doanh": "Nhân viên kinh doanh",
    "tham_dinh": "Thẩm định / pháp chế",
    "phan_tich": "Phân tích thị trường",
}

# Mục đích sử dụng được phép gắn cho từng lô (mục 1, A02, T02)
PURPOSES = {
    "ban_hang_b2b": "Bán hàng & tiếp thị B2B",
    "tham_dinh_kyc": "Thẩm định rủi ro đối tác (KYC)",
    "nghien_cuu_thi_truong": "Nghiên cứu thị trường",
    "lam_giau_khach_hang": "Làm giàu hồ sơ khách hàng hiện hữu",
}

# Cách lấy ra giá trị (B01 bóc tách ba tầng + nhập lô + sửa tay)
METHODS = {
    "nhap_lo": "Nhập từ lô MST",
    "cau_truc": "Dữ liệu có cấu trúc",
    "luat": "Luật bóc tách theo nguồn",
    "mo_hinh": "Mô hình ngôn ngữ",
    "nhap_tay": "Nhân viên tra cứu và nhập từ nguồn",
    "suy_luan": "Suy luận theo mẫu (không phải thu thập)",
    "thu_cong": "Biên tập viên quyết định",  # luôn thắng khi hợp nhất (B09)
}

# Trạng thái công việc thu thập (A06)
JOB_STATUSES = {
    "pending": "Chờ chạy",
    "queued": "Đã xếp lượt",
    "running": "Đang chạy",
    "done": "Xong",
    "not_found": "Nguồn không có MST này",
    "failed": "Lỗi",
    "manual": "Chờ xử lý thủ công",
    "skipped": "Bỏ qua",
}
RUN_STATUSES = {"running": "Đang chạy", "paused": "Tạm dừng", "done": "Hoàn tất", "cancelled": "Đã huỷ"}

# Tài liệu công bố thông tin của doanh nghiệp niêm yết (giai đoạn 3)
DOC_TYPES = {
    "bao_cao_quan_tri": "Báo cáo tình hình quản trị công ty",
    "bao_cao_thuong_nien": "Báo cáo thường niên",
    "nghi_quyet": "Nghị quyết / quyết định bổ nhiệm, miễn nhiệm",
    "khac": "Tài liệu khác",
}
DOC_STATUSES = {
    "pending": "Chờ tải",
    "fetched": "Đã tải, chờ bóc tách",
    "parsed": "Đã bóc tách, tự ghi vào kho",
    "needs_review": "Chờ duyệt",
    "approved": "Đã duyệt",
    "rejected": "Đã từ chối",
    "failed": "Lỗi",
}
# Nhóm chức danh trong báo cáo quản trị
PERSON_GROUPS = {
    "hdqt": "Hội đồng quản trị / Hội đồng thành viên",
    "bks": "Ban kiểm soát / Uỷ ban kiểm toán",
    "bdh": "Ban điều hành",
    "ktt": "Kế toán trưởng",
    "khac": "Khác",
}

# Loại cảnh báo của danh sách theo dõi (C06)
ALERT_KINDS = {
    "nguoi_dai_dien": "Đổi người đại diện / người ra quyết định",
    "dia_chi": "Đổi địa chỉ",
    "trang_thai": "Đổi tình trạng MST",
    "no_thue": "Nợ thuế",
    "trung_thau": "Trúng thầu",
    "bo_nhiem": "Bổ nhiệm",
    "khac": "Thay đổi khác",
}

# Tín hiệu (mục 3)
SIGNAL_KINDS = {
    "no_thue": "Nợ thuế",
    "trung_thau": "Trúng thầu",
    "bo_nhiem": "Bổ nhiệm",
    "thay_doi_dang_ky": "Thay đổi đăng ký",
    "xep_hang": "Xếp hạng (PROFIT500…)",
}

# Trường hồ sơ doanh nghiệp (kho A) — thứ tự hiển thị trên hồ sơ
COMPANY_FIELDS = {
    "mst": "Mã số thuế",
    "ten": "Tên doanh nghiệp",
    "ten_tieng_anh": "Tên tiếng Anh",
    "dia_chi": "Địa chỉ trụ sở",
    "tinh": "Tỉnh/thành",
    "trang_thai": "Tình trạng hoạt động",
    "nganh_nghe": "Ngành nghề",
    "nhom_nganh": "Nhóm ngành (theo danh sách)",
    "nhom_san_pham": "Nhóm sản phẩm",
    "ma_hs": "Mã HS",
    "ngay_thanh_lap": "Ngày thành lập",
    "nam_thanh_lap": "Năm thành lập",
    "von": "Vốn điều lệ (đồng)",
    "website": "Website",
    "domain": "Tên miền",
    "ma_ck": "Mã chứng khoán",
    "niem_yet": "Niêm yết",
    "mo_ta": "Giới thiệu",
}
# Trường bắt buộc để tính độ phủ hồ sơ (mục 1: ≥ 95% MST có đủ)
REQUIRED_FIELDS = ("ten", "dia_chi", "trang_thai", "nganh_nghe")


# ================================================================== thu_thap


class EnrichSource(Base):
    """Một nguồn dữ liệu (connector hoặc nguồn nhập). Độ tin cậy 0–1 dùng khi hợp nhất (B04).

    T12: chưa khai cơ sở pháp lý thì không được bật — kiểm tra ở app/enrich/sources.py.
    """

    __tablename__ = "enrich_sources"
    __table_args__ = {"schema": THU_THAP}

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    trust: Mapped[float] = mapped_column(Float, default=0.5)
    legal_basis: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # A04: min_interval_s (giây giữa 2 request cùng tên miền, ≥ 2), timeout_s, max_retries, recrawl_days
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    paused_reason: Mapped[str] = mapped_column(Text, default="")  # A13: tự tạm dừng vì tỷ lệ lỗi cao
    paused_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EnrichBatch(Base):
    """Một lô MST nhập vào (A01, A02): nguồn danh sách + mục đích sử dụng được phép."""

    __tablename__ = "enrich_batches"
    __table_args__ = {"schema": THU_THAP}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    list_source: Mapped[str] = mapped_column(String(300))  # danh sách lấy từ đâu
    purposes: Mapped[list] = mapped_column(JSON, default=list)  # khoá trong PURPOSES
    note: Mapped[str] = mapped_column(Text, default="")
    file_name: Mapped[str] = mapped_column(String(255), default="")
    file_sha256: Mapped[str] = mapped_column(String(64), default="")
    report: Mapped[dict] = mapped_column(JSON, default=dict)  # số dòng hợp lệ / trùng / sai định dạng + chi tiết lỗi
    mst_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class EnrichBatchItem(Base):
    """MST thuộc lô nào (một MST có thể nằm trong nhiều lô → mục đích = hợp các lô)."""

    __tablename__ = "enrich_batch_items"
    __table_args__ = (UniqueConstraint("batch_id", "mst", name="uq_enrich_batch_item"), {"schema": THU_THAP})

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_batches.id", ondelete="CASCADE"), index=True)
    mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"), index=True)
    row_no: Mapped[int] = mapped_column(Integer)  # dòng trong file gốc
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)  # MST lần đầu vào hệ thống


class SourcePage(Base):
    """Bản gốc đã tải (HTML, PDF) — lưu nén trên kho tệp, khoá theo mã băm nội dung (A09, B12)."""

    __tablename__ = "enrich_source_pages"
    __table_args__ = {"schema": THU_THAP}

    id: Mapped[int] = mapped_column(primary_key=True)
    source_code: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"), index=True)
    mst: Mapped[str | None] = mapped_column(String(14), index=True)  # trang tải cho MST nào (None = file nhập nhiều MST)
    url: Mapped[str] = mapped_column(String(1000))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), default="")
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CrawlJob(Base):
    """Một MST chạy qua một connector (A06). Trạng thái lưu DB để dừng/chạy lại không mất tiến độ."""

    __tablename__ = "enrich_crawl_jobs"
    __table_args__ = (Index("ix_enrich_crawl_jobs_queue", "connector", "status"), {"schema": THU_THAP})

    id: Mapped[int] = mapped_column(primary_key=True)
    mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"), index=True)
    connector: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # khoá trong JOB_STATUSES
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    run_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_runs.id", ondelete="CASCADE"), index=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)  # lùi dần khi lỗi
    handled_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))  # hàng đợi thủ công
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EnrichRun(Base):
    """Vòng thu thập: một lượt chạy danh sách MST (toàn bộ hoặc một lô) qua các connector được chọn."""

    __tablename__ = "enrich_runs"
    __table_args__ = {"schema": THU_THAP}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    connectors: Mapped[list] = mapped_column(JSON, default=list)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_batches.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(12), default="running", index=True)
    job_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class FetchLog(Base):
    """Mỗi request ra ngoài một dòng — chứng minh không tên miền nào bị vượt ngưỡng tốc độ (A08), tính tỷ lệ lỗi (A13)."""

    __tablename__ = "enrich_fetch_logs"
    __table_args__ = (Index("ix_enrich_fetch_logs_domain_at", "domain", "at"), {"schema": THU_THAP})

    id: Mapped[int] = mapped_column(primary_key=True)
    source_code: Mapped[str] = mapped_column(String(40), index=True)
    domain: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000))
    http_status: Mapped[int | None] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(String(500), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DomainSlot(Base):
    """Lượt được phép gọi tiếp theo của từng tên miền — đặt chỗ nguyên tử để nhiều worker cùng tôn trọng giới hạn (A08)."""

    __tablename__ = "enrich_domain_slots"
    __table_args__ = {"schema": THU_THAP}

    domain: Mapped[str] = mapped_column(String(200), primary_key=True)
    next_at: Mapped[datetime] = mapped_column(DateTime)


class EnrichSetting(Base):
    """Cấu hình vận hành chung (A07): paused (dừng khẩn cấp), window {start,end} giờ chạy, max_running."""

    __tablename__ = "enrich_settings"
    __table_args__ = {"schema": THU_THAP}

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Watchlist(Base):
    """Danh sách theo dõi (C06): thay đổi / tín hiệu của doanh nghiệp trong danh sách sinh cảnh báo cho người sở hữu
    (và cả nhóm nếu chia sẻ)."""

    __tablename__ = "enrich_watchlists"
    __table_args__ = {"schema": THU_THAP}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    kinds: Mapped[list] = mapped_column(JSON, default=list)  # loại cảnh báo bật; rỗng = tất cả (ALERT_KINDS)
    email_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WatchItem(Base):
    __tablename__ = "enrich_watch_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "mst", name="uq_enrich_watch_item"), {"schema": THU_THAP})

    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_watchlists.id", ondelete="CASCADE"), index=True)
    mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EnrichAlert(Base):
    """Một cảnh báo cho một người dùng. Nội dung không chứa tên người (chỉ chức danh) — xem chi tiết trên hồ sơ."""

    __tablename__ = "enrich_alerts"
    __table_args__ = (Index("ix_enrich_alerts_user_unread", "user_id", "read_at"), {"schema": THU_THAP})

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"))
    watchlist_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_watchlists.id", ondelete="CASCADE"))
    mst: Mapped[str] = mapped_column(String(14), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # khoá ALERT_KINDS
    summary: Mapped[str] = mapped_column(String(500))
    ref: Mapped[str] = mapped_column(String(60), default="")  # change:<id> | signal:<id>
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SavedFilter(Base):
    """Bộ lọc đã lưu (C05) — dùng lại được, chia sẻ trong nhóm."""

    __tablename__ = "enrich_saved_filters"
    __table_args__ = {"schema": THU_THAP}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), index=True)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    definition: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ExportRecord(Base):
    """Nhật ký xuất dữ liệu (C09): ai xuất, lúc nào, bao nhiêu dòng, cột gì, mục đích, hạn dùng file (T11)."""

    __tablename__ = "enrich_exports"
    __table_args__ = {"schema": THU_THAP}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    filter: Mapped[dict] = mapped_column(JSON, default=dict)
    columns: Mapped[list] = mapped_column(JSON, default=list)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)  # dòng bị chặn vì lô không cho phép mục đích (T02)
    optout_count: Mapped[int] = mapped_column(Integer, default=0)  # liên hệ / người bị loại vì từ chối (C10)
    include_inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    includes_kho_b: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12), default="ok")  # ok | blocked
    expires_on: Mapped[date | None] = mapped_column(Date)
    file_sha256: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class EnrichImport(Base):
    """Một lần nhập file từ nguồn chính thức (dữ liệu mua ĐKKD, danh sách nợ thuế, kết quả đấu thầu).

    File gốc lưu như một SourcePage (A09) — bằng chứng trỏ về đó, bóc tách lại được mà không cần file.
    """

    __tablename__ = "enrich_imports"
    __table_args__ = {"schema": THU_THAP}

    id: Mapped[int] = mapped_column(primary_key=True)
    source_code: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(1000))  # nơi công bố / số hợp đồng mua dữ liệu
    data_date: Mapped[date | None] = mapped_column(Date)  # dữ liệu tính đến ngày
    note: Mapped[str] = mapped_column(Text, default="")
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    source_page_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_source_pages.id", ondelete="SET NULL"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ================================================================== kho A — doanh nghiệp


class EnrichCompany(Base):
    """Hồ sơ doanh nghiệp, khoá chính là MST (B05: không có MST thì không tạo hồ sơ).

    Các cột dưới đây là giá trị HIỂN THỊ do merge.recompute_companies chọn từ CompanyEvidence —
    không sửa trực tiếp. ten_khong_dau là cột phụ để tìm kiếm không dấu.
    """

    __tablename__ = "enrich_companies"
    __table_args__ = {"schema": KHO_A}

    mst: Mapped[str] = mapped_column(String(14), primary_key=True)  # 10 số, hoặc 0101234567-001
    ten: Mapped[str | None] = mapped_column(String(400))
    ten_khong_dau: Mapped[str] = mapped_column(String(400), default="", index=True)
    ten_tieng_anh: Mapped[str | None] = mapped_column(String(300))
    loai_hinh: Mapped[str | None] = mapped_column(String(60))  # tách từ tên (B02): Công ty TNHH, Công ty cổ phần…
    dia_chi: Mapped[str | None] = mapped_column(String(600))
    tinh: Mapped[str | None] = mapped_column(String(80), index=True)
    nganh_nghe: Mapped[list | None] = mapped_column(JSON)
    # phân loại do danh sách nhập lô cung cấp (không phải ngành nghề ĐKKD) — vd "Dệt may", nhóm hàng xuất khẩu, mã HS
    nhom_nganh: Mapped[str | None] = mapped_column(String(200), index=True)
    nhom_san_pham: Mapped[list | None] = mapped_column(JSON)
    ma_hs: Mapped[list | None] = mapped_column(JSON)
    ngay_thanh_lap: Mapped[date | None] = mapped_column(Date)
    nam_thanh_lap: Mapped[int | None] = mapped_column(Integer)  # khi nguồn chỉ có năm (vd PROFIT500)
    von: Mapped[int | None] = mapped_column(BigInteger)
    trang_thai: Mapped[str | None] = mapped_column(String(120), index=True)
    website: Mapped[str | None] = mapped_column(String(300))
    domain: Mapped[str | None] = mapped_column(String(200), index=True)
    ma_ck: Mapped[str | None] = mapped_column(String(20))
    niem_yet: Mapped[bool | None] = mapped_column(Boolean)
    mo_ta: Mapped[str | None] = mapped_column(Text)  # đoạn giới thiệu doanh nghiệp tại nguồn

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CompanyEvidence(Base):
    """Bằng chứng: một nguồn nói trường X của doanh nghiệp có giá trị Y, lấy từ đâu, lúc nào."""

    __tablename__ = "enrich_company_evidence"
    __table_args__ = (Index("ix_enrich_company_evidence_field", "mst", "field"), {"schema": KHO_A})

    id: Mapped[int] = mapped_column(primary_key=True)
    mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"))
    field: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(Text)  # dạng chữ; danh sách lưu JSON
    source_code: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"), index=True)
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")  # trích đoạn
    method: Mapped[str] = mapped_column(String(16))  # khoá trong METHODS
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=False)  # B11
    content_hash: Mapped[str] = mapped_column(String(64), default="")  # mã băm nội dung gốc — khử trùng (B12)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_batches.id", ondelete="SET NULL"))
    source_page_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_source_pages.id", ondelete="SET NULL"))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CompanyChange(Base):
    """Nhật ký thay đổi giá trị hiển thị (C07) — nguồn sinh cảnh báo (C06)."""

    __tablename__ = "enrich_company_changes"
    __table_args__ = {"schema": KHO_A}

    id: Mapped[int] = mapped_column(primary_key=True)
    mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    source_code: Mapped[str] = mapped_column(String(40))
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class EnrichSignal(Base):
    """Tín hiệu gắn với doanh nghiệp: nợ thuế, trúng thầu, bổ nhiệm, thay đổi đăng ký."""

    __tablename__ = "enrich_signals"
    __table_args__ = {"schema": KHO_A}

    id: Mapped[int] = mapped_column(primary_key=True)
    mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    day: Mapped[date | None] = mapped_column(Date)
    source_code: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"))
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    dedupe_key: Mapped[str] = mapped_column(String(64), default="", index=True)  # băm (loại, nội dung, nguồn) — B12
    source_page_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_source_pages.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ================================================================== kho B — dữ liệu cá nhân


class EnrichPerson(Base):
    """Người ra quyết định. Không lưu CCCD, địa chỉ nhà, thông tin gia đình (T09)."""

    __tablename__ = "enrich_persons"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    # chỉ dùng đối soát nội bộ (T04); lưu bản mã AES-SIV tất định (N05) — app/enrich/crypto.py
    mst_ca_nhan: Mapped[str | None] = mapped_column(EncryptedMst(), unique=True)
    ho_ten: Mapped[str] = mapped_column(String(200))
    ho_ten_khong_dau: Mapped[str] = mapped_column(String(200), default="", index=True)
    nam_sinh: Mapped[int | None] = mapped_column(Integer)
    # B07: đã gộp vào người khác → hồ sơ này ẩn khỏi mọi truy vấn; giữ lại để hoàn tác được
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="SET NULL"), index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)  # T07: 24 tháng không dùng → rà soát xoá
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PersonRole(Base):
    """Vai trò của người tại doanh nghiệp theo thời gian (nhiều–nhiều)."""

    __tablename__ = "enrich_person_roles"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="CASCADE"), index=True)
    company_mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"), index=True)
    chuc_danh: Mapped[str] = mapped_column(String(200))
    chuc_danh_chuan: Mapped[str] = mapped_column(String(60), default="")
    la_nguoi_quyet_dinh: Mapped[bool] = mapped_column(Boolean, default=False)
    tu_ngay: Mapped[date | None] = mapped_column(Date)
    den_ngay: Mapped[date | None] = mapped_column(Date)
    source_code: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"))
    trust: Mapped[float] = mapped_column(Float, default=0.5)


class EnrichContact(Base):
    """Email / điện thoại công việc của người hoặc doanh nghiệp."""

    __tablename__ = "enrich_contacts"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(10))  # person | company
    owner_id: Mapped[str] = mapped_column(String(20), index=True)  # id người hoặc MST
    kind: Mapped[str] = mapped_column(String(10))  # email | phone
    value: Mapped[str] = mapped_column(String(200), index=True)
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=False)  # B10, B11
    verify_status: Mapped[str] = mapped_column(String(16), default="unverified")
    source_code: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)


class PersonEvidence(Base):
    """Bằng chứng cho trường của người — nằm trong kho B vì giá trị và trích đoạn là dữ liệu cá nhân."""

    __tablename__ = "enrich_person_evidence"
    __table_args__ = (Index("ix_enrich_person_evidence_field", "person_id", "field"), {"schema": KHO_B})

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="CASCADE"))
    field: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(Text)
    source_code: Mapped[str] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_sources.code"))
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(String(16))
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    source_page_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_source_pages.id", ondelete="SET NULL"))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PersonChange(Base):
    __tablename__ = "enrich_person_changes"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    source_code: Mapped[str] = mapped_column(String(40))
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OptOut(Base):
    """Danh sách từ chối liên hệ (C10): email, điện thoại hoặc người — ẩn khỏi mọi kết quả và bản xuất."""

    __tablename__ = "enrich_optouts"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    # email | phone | person (id hồ sơ) | mst_cn, ten_dn (khoá băm HMAC — người đã xoá dữ liệu, chặn thu thập lại; T05)
    kind: Mapped[str] = mapped_column(String(10))
    value: Mapped[str] = mapped_column(String(200), index=True)
    day: Mapped[date] = mapped_column(Date, default=date.today)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))


class EnrichDocument(Base):
    """Tài liệu công bố thông tin (báo cáo quản trị…) của một doanh nghiệp và kết quả bóc tách người + chức danh.

    Nằm trong kho B vì `extracted` chứa họ tên người. Bản gốc lưu như SourcePage (A09).
    """

    __tablename__ = "enrich_documents"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    mst: Mapped[str] = mapped_column(ForeignKey(f"{KHO_A}.enrich_companies.mst", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(30), default="bao_cao_quan_tri")
    period: Mapped[str] = mapped_column(String(40), default="")  # vd "6 tháng đầu năm 2026"
    source_url: Mapped[str] = mapped_column(String(1000))
    source_page_id: Mapped[int | None] = mapped_column(ForeignKey(f"{THU_THAP}.enrich_source_pages.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    method: Mapped[str] = mapped_column(String(16), default="")  # tầng bóc tách đã dùng: cau_truc | luat | mo_hinh
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)  # {"people": [...], "notes": [...]}
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LlmCache(Base):
    """B01: kết quả mô hình ngôn ngữ lưu đệm theo mã băm nội dung — cùng nội dung + cùng phiên bản prompt không gọi lại."""

    __tablename__ = "enrich_llm_cache"
    __table_args__ = (UniqueConstraint("content_hash", "task", "model", name="uq_enrich_llm_cache"), {"schema": KHO_B})

    id: Mapped[int] = mapped_column(primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    task: Mapped[str] = mapped_column(String(40))  # tên tác vụ + phiên bản prompt, vd "governance-v1"
    model: Mapped[str] = mapped_column(String(60))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MergeCandidate(Base):
    """B06: hai hồ sơ người nghi là một (cùng tên chuẩn hoá) nhưng điểm khớp dưới ngưỡng → chờ biên tập viên quyết, không tự gộp."""

    __tablename__ = "enrich_merge_candidates"
    __table_args__ = (UniqueConstraint("person_a_id", "person_b_id", name="uq_enrich_merge_pair"), {"schema": KHO_B})

    id: Mapped[int] = mapped_column(primary_key=True)
    person_a_id: Mapped[int] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="CASCADE"), index=True)
    person_b_id: Mapped[int] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending | merged | rejected
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EntityOp(Base):
    """B07: nhật ký gộp / tách người — ai làm, lúc nào, đã di chuyển gì (đủ để hoàn tác)."""

    __tablename__ = "enrich_entity_ops"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    op: Mapped[str] = mapped_column(String(10))  # merge | split
    person_id: Mapped[int] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="CASCADE"), index=True)
    other_person_id: Mapped[int] = mapped_column(ForeignKey(f"{KHO_B}.enrich_persons.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime)
    undone_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))


class AccessLog(Base):
    """Nhật ký mọi thao tác đọc / xuất / sửa trên kho B (N06). Chỉ ghi thêm (T08) — trigger chặn UPDATE/DELETE."""

    __tablename__ = "enrich_access_logs"
    __table_args__ = {"schema": KHO_B}

    id: Mapped[int] = mapped_column(primary_key=True)
    # Không SET NULL: xoá tài khoản sẽ phải UPDATE nhật ký (bị trigger chặn). Tài khoản đã truy cập kho B chỉ khoá, không xoá.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(16))  # read | list | export | edit | delete
    target: Mapped[str] = mapped_column(String(200))  # vd company:0101234567/people, persons?q=...
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# ------------------------------------------------------------------ DDL phụ khi tạo bảng bằng create_all (test)
# Migration tạo các đối tượng này riêng (migrations/versions/f6a1c2d3e4b5_lam_giau_mst_giai_doan_1.py).

for _schema in ENRICH_SCHEMAS:
    event.listen(
        Base.metadata, "before_create", DDL(f"CREATE SCHEMA IF NOT EXISTS {_schema}").execute_if(dialect="postgresql")
    )

ACCESS_LOG_PG_FUNC = """
CREATE OR REPLACE FUNCTION kho_b.enrich_access_logs_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Nhật ký truy cập kho B chỉ được ghi thêm';
END;
$$ LANGUAGE plpgsql
"""
ACCESS_LOG_PG_TRIGGER = """
CREATE TRIGGER enrich_access_logs_no_change BEFORE UPDATE OR DELETE ON kho_b.enrich_access_logs
FOR EACH ROW EXECUTE FUNCTION kho_b.enrich_access_logs_append_only()
"""
ACCESS_LOG_SQLITE_TRIGGERS = (
    "CREATE TRIGGER enrich_access_logs_no_update BEFORE UPDATE ON enrich_access_logs "
    "BEGIN SELECT RAISE(ABORT, 'Nhật ký truy cập kho B chỉ được ghi thêm'); END",
    "CREATE TRIGGER enrich_access_logs_no_delete BEFORE DELETE ON enrich_access_logs "
    "BEGIN SELECT RAISE(ABORT, 'Nhật ký truy cập kho B chỉ được ghi thêm'); END",
)

_log_table = AccessLog.__table__
event.listen(_log_table, "after_create", DDL(ACCESS_LOG_PG_FUNC).execute_if(dialect="postgresql"))
event.listen(_log_table, "after_create", DDL(ACCESS_LOG_PG_TRIGGER).execute_if(dialect="postgresql"))
for _sql in ACCESS_LOG_SQLITE_TRIGGERS:
    event.listen(_log_table, "after_create", DDL(_sql).execute_if(dialect="sqlite"))
