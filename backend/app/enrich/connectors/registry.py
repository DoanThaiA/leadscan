"""Danh mục connector giai đoạn 2 (A05). Cơ sở pháp lý (T12) là bản nháp — pháp chế cần duyệt trước khi dùng thật."""

from app.enrich.connectors.base import Connector, ManualField

STATUS_OPTIONS = [
    "Đang hoạt động",
    "Tạm ngừng kinh doanh",
    "Đang làm thủ tục giải thể",
    "Đã giải thể",
    "Ngừng hoạt động, đã đóng MST",
    "Không hoạt động tại địa chỉ đã đăng ký",
    "Bị thu hồi giấy chứng nhận",
]


class DkkdLookup(Connector):
    """Tra cứu trên Cổng thông tin quốc gia về đăng ký doanh nghiệp — có captcha nên chỉ tra thủ công."""

    code = "dkkd_tra_cuu"
    name = "Cổng ĐKKD — tra cứu thủ công"
    kind = "manual"
    domain = "dangkykinhdoanh.gov.vn"
    default_trust = 0.9
    legal_basis = (
        "Thông tin doanh nghiệp công khai trên Cổng thông tin quốc gia về đăng ký doanh nghiệp. "
        "Nhân viên tra cứu thủ công từng MST; hệ thống không tự vượt captcha."
    )
    # mục tiêu "phát hiện đổi người đại diện / địa chỉ / tình trạng trong 30 ngày" → 30 ngày (A12 ghi 90 cho hồ sơ pháp lý)
    defaults = {"recrawl_days": 30}
    manual_fields = [
        ManualField("ten", "Tên doanh nghiệp"),
        ManualField("dia_chi", "Địa chỉ trụ sở chính", "textarea"),
        ManualField("trang_thai", "Tình trạng hoạt động", "select", STATUS_OPTIONS),
        ManualField("nganh_nghe", "Ngành nghề kinh doanh chính"),
        ManualField("ngay_thanh_lap", "Ngày thành lập", "date"),
        ManualField("nguoi_dai_dien", "Người đại diện theo pháp luật (họ tên)"),
    ]

    def manual_url(self, mst: str) -> str:
        return "https://dangkykinhdoanh.gov.vn/vn/Pages/Trangchu.aspx"

    def manual_hint(self, mst: str) -> str:
        return f"Nhập MST {mst} vào ô tìm kiếm trên Cổng, chọn doanh nghiệp rồi chép thông tin vào form."


class TaxpayerLookup(Connector):
    """Tra cứu thông tin người nộp thuế của cơ quan thuế — có captcha nên chỉ tra thủ công."""

    code = "tracuu_nnt"
    name = "Tra cứu người nộp thuế — thủ công"
    kind = "manual"
    domain = "tracuunnt.gdt.gov.vn"
    default_trust = 0.85
    legal_basis = (
        "Thông tin người nộp thuế công khai trên trang tra cứu của cơ quan thuế. "
        "Nhân viên tra cứu thủ công từng MST; hệ thống không tự vượt captcha."
    )
    defaults = {"recrawl_days": 30}
    manual_fields = [
        ManualField("ten", "Tên người nộp thuế"),
        ManualField("dia_chi", "Địa chỉ trụ sở", "textarea"),
        ManualField("trang_thai", "Trạng thái MST", "select", STATUS_OPTIONS),
    ]

    def manual_url(self, mst: str) -> str:
        return "https://tracuunnt.gdt.gov.vn/tcnnt/mstdn.jsp"

    def manual_hint(self, mst: str) -> str:
        return f"Nhập MST {mst}, gõ mã xác nhận rồi chép tên, địa chỉ, trạng thái vào form."


class DkkdPurchased(Connector):
    """A03: dữ liệu mua hợp pháp từ Cổng ĐKKD — độ tin cậy cao nhất."""

    code = "dkkd_mua"
    name = "Dữ liệu mua từ Cổng ĐKKD"
    kind = "file"
    domain = "dangkykinhdoanh.gov.vn"
    default_trust = 0.95
    legal_basis = (
        "Dữ liệu doanh nghiệp mua hợp pháp từ Cổng thông tin quốc gia về đăng ký doanh nghiệp theo hợp đồng "
        "cung cấp thông tin; số hợp đồng ghi ở mỗi lần nhập. Chỉ nhận tên, chức danh người đại diện — "
        "không nhận CCCD, ngày sinh, địa chỉ cá nhân."
    )
    defaults = {"recrawl_days": 90}


class TaxDebtList(Connector):
    code = "no_thue"
    name = "Danh sách nợ thuế công khai"
    kind = "file"
    domain = "gdt.gov.vn"
    default_trust = 0.9
    legal_basis = "Danh sách người nộp thuế nợ thuế do cơ quan thuế công khai theo Luật Quản lý thuế."
    defaults = {"recrawl_days": 7}


class ProcurementResults(Connector):
    code = "dau_thau"
    name = "Kết quả lựa chọn nhà thầu"
    kind = "file"
    domain = "muasamcong.mpi.gov.vn"
    default_trust = 0.9
    legal_basis = "Kết quả lựa chọn nhà thầu công khai trên Hệ thống mạng đấu thầu quốc gia theo Luật Đấu thầu."
    defaults = {"recrawl_days": 7}


class ListedCompanies(Connector):
    """Danh sách chứng khoán niêm yết / đăng ký giao dịch (HOSE, HNX, UPCoM) — gắn mã CK cho MST."""

    code = "ds_niem_yet"
    name = "Danh sách niêm yết (HOSE, HNX, UPCoM)"
    kind = "file"
    domain = ""
    default_trust = 0.9
    legal_basis = "Danh sách chứng khoán niêm yết, đăng ký giao dịch do Sở Giao dịch Chứng khoán công bố công khai."
    defaults = {"recrawl_days": 90}


class Disclosures(Connector):
    """Tài liệu công bố thông tin của doanh nghiệp niêm yết (báo cáo tình hình quản trị, báo cáo thường niên, nghị quyết).

    Không tự dò toàn bộ trang công bố: mỗi tài liệu được nhân viên tải lên hoặc khai đường dẫn (theo mã CK);
    hệ thống tải từng đường dẫn qua cùng giới hạn tốc độ + robots.txt như connector tự động.
    """

    code = "cbtt"
    name = "Công bố thông tin doanh nghiệp niêm yết"
    kind = "document"
    domain = ""
    default_trust = 0.9
    legal_basis = (
        "Thông tin doanh nghiệp niêm yết bắt buộc công bố công khai theo pháp luật chứng khoán (báo cáo tình hình "
        "quản trị công ty, báo cáo thường niên, nghị quyết). Chỉ lấy họ tên + chức danh thành viên HĐQT, BKS, Ban điều hành; "
        "phần danh sách người nội bộ / người có liên quan bị cắt bỏ trước khi bóc tách."
    )
    defaults = {"min_interval_s": 2.0, "timeout_s": 60, "max_retries": 2, "recrawl_days": 180}


CONNECTORS: dict[str, Connector] = {}


def register(c: Connector) -> Connector:
    CONNECTORS[c.code] = c
    return c


def unregister(code: str) -> None:
    CONNECTORS.pop(code, None)


from app.enrich.connectors.website import CompanyWebsite  # noqa: E402

for _cls in (DkkdPurchased, DkkdLookup, TaxpayerLookup, TaxDebtList, ProcurementResults, ListedCompanies, Disclosures, CompanyWebsite):
    register(_cls())


def get(code: str) -> Connector | None:
    return CONNECTORS.get(code)
