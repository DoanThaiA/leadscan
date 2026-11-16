"""Danh mục nguồn dữ liệu, độ tin cậy (0–1) và cấu hình từng connector (A04).

Nguồn = connector trong connectors/registry.py hoặc nguồn nội bộ (nhập lô, biên tập viên). Bản ghi EnrichSource
được tạo khi cần lần đầu; sau đó quản trị sửa độ tin cậy / tốc độ / bật tắt trên giao diện mà không cần deploy.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enrich.connectors import registry
from app.models_enrich import EnrichSource

IMPORT = "nhap_lo"
EDITOR = "bien_tap"

MIN_INTERVAL_S = 2.0  # A08: tối thiểu 1 request mỗi 2 giây cho mỗi tên miền — cấu hình không được thấp hơn

INTERNAL: dict[str, dict] = {
    IMPORT: {
        "name": "Danh sách MST nhập theo lô",
        "trust": 0.5,
        "legal_basis": "Danh sách MST do doanh nghiệp tự thu thập hợp pháp; mục đích sử dụng khai khi nhập từng lô.",
        "enabled": True,
        "config": {"kind": "internal"},
    },
    "suy_luan_email": {
        "name": "Suy luận email theo mẫu tên miền",
        "trust": 0.4,
        "legal_basis": "Email công việc suy luận từ mẫu đặt tên của chính doanh nghiệp (đã có email thật cùng tên miền), xác minh MX trước khi lưu; luôn gắn cờ suy luận.",
        "enabled": True,
        "config": {"kind": "internal"},
    },
    "mst_ca_nhan_noi_bo": {
        "name": "Danh sách MST cá nhân nội bộ",
        "trust": 0.95,
        "legal_basis": "Dữ liệu doanh nghiệp đang nắm giữ hợp pháp, chỉ dùng đối soát nội bộ (T04); không phải dữ liệu cá nhân mua từ bên thứ ba (T03).",
        "enabled": True,
        "config": {"kind": "internal"},
    },
    EDITOR: {
        "name": "Biên tập viên",
        "trust": 1.0,
        "legal_basis": "Biên tập viên xác minh và nhập tay từ nguồn công khai.",
        "enabled": True,
        "config": {"kind": "internal"},
    },
}


def _defaults(code: str) -> dict | None:
    if code in INTERNAL:
        return INTERNAL[code]
    c = registry.get(code)
    if not c:
        return None
    return {
        "name": c.name,
        "trust": c.default_trust,
        "legal_basis": c.legal_basis,
        # connector tự động (http) mặc định TẮT — quản trị bật sau khi kiểm tra; thủ công / file thì bật sẵn
        "enabled": c.kind in ("manual", "file", "document") and bool(c.legal_basis.strip()),
        "config": {"kind": c.kind, "domain": c.domain, **c.defaults},
    }


def ensure(db: Session, code: str) -> EnrichSource:
    """Lấy nguồn; chưa có trong DB thì tạo từ khai báo mặc định."""
    src = db.get(EnrichSource, code)
    if src:
        return src
    d = _defaults(code)
    if d is None:
        raise KeyError(f"Nguồn chưa khai báo: {code}")
    src = EnrichSource(code=code, name=d["name"], trust=d["trust"], legal_basis=d["legal_basis"], enabled=d["enabled"], config=dict(d["config"]))
    db.add(src)
    db.flush()
    return src


def ensure_all(db: Session) -> list[EnrichSource]:
    out = [ensure(db, code) for code in [*INTERNAL, *registry.CONNECTORS]]
    db.commit()
    return out


def all_sources(db: Session) -> dict[str, EnrichSource]:
    return {s.code: s for s in db.scalars(select(EnrichSource))}


def setting(src: EnrichSource, key: str, fallback=None):
    """Giá trị cấu hình của nguồn (DB đè mặc định của connector)."""
    c = registry.get(src.code)
    base = dict(c.defaults) if c else {}
    base.update(src.config or {})
    v = base.get(key, fallback)
    if key == "min_interval_s":
        return max(float(v or MIN_INTERVAL_S), MIN_INTERVAL_S)
    return v


def can_enable(src: EnrichSource) -> str:
    """'' nếu được bật; ngược lại là lý do (T12)."""
    if not (src.legal_basis or "").strip():
        return "Chưa khai cơ sở pháp lý của nguồn nên không được bật."
    return ""
