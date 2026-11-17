"""Lọc nhiều điều kiện trên hồ sơ doanh nghiệp (C04): mọi trường, kết hợp AND/OR, biểu thức chính quy.

Định nghĩa bộ lọc (lưu được — C05):
    {"op": "and" | "or", "q": "tìm nhanh không dấu", "conditions": [{"field": "tinh", "cmp": "eq", "value": "Hà Nội"}, …]}
Mỗi điều kiện có thể là một nhóm con {"op": …, "conditions": […]} (lồng tối đa 3 tầng).
"""

import re
from datetime import timedelta

from sqlalchemy import String, and_, cast, exists, false, not_, or_, select, true
from sqlalchemy.sql import ColumnElement

from app.db import utcnow
from app.enrich.normalize import bo_dau, parse_date
from app.models_enrich import EnrichBatch, EnrichBatchItem, EnrichCompany, EnrichSignal, PersonRole

TEXT = {"mst", "ten", "dia_chi", "tinh", "trang_thai", "website", "domain", "ma_ck", "loai_hinh", "nhom_nganh"}
FIELDS = {
    "mst": ("Mã số thuế", "text"),
    "ten": ("Tên doanh nghiệp", "text"),
    "loai_hinh": ("Loại hình", "text"),
    "dia_chi": ("Địa chỉ", "text"),
    "tinh": ("Tỉnh/thành", "text"),
    "trang_thai": ("Tình trạng hoạt động", "text"),
    "nganh_nghe": ("Ngành nghề", "list"),
    "nhom_nganh": ("Nhóm ngành (theo danh sách)", "text"),
    "nhom_san_pham": ("Nhóm sản phẩm", "list"),
    "ma_hs": ("Mã HS", "list"),
    "ngay_thanh_lap": ("Ngày thành lập", "date"),
    "von": ("Vốn điều lệ (đồng)", "number"),
    "website": ("Website", "text"),
    "domain": ("Tên miền", "text"),
    "ma_ck": ("Mã chứng khoán", "text"),
    "niem_yet": ("Niêm yết", "bool"),
    "co_nguoi_quyet_dinh": ("Có người ra quyết định", "bool"),
    "tin_hieu": ("Có tín hiệu (trong N ngày)", "signal"),
    "lo": ("Thuộc lô", "batch"),
    "muc_dich": ("Được phép dùng cho mục đích", "purpose"),
}
CMPS = {
    "text": ["contains", "not_contains", "eq", "ne", "starts", "regex", "empty", "not_empty", "in"],
    "list": ["contains", "not_contains", "regex", "empty", "not_empty"],
    "date": ["gte", "lte", "empty", "not_empty"],
    "number": ["gte", "lte", "eq", "empty", "not_empty"],
    "bool": ["is_true", "is_false"],
    "signal": ["has"],
    "batch": ["eq"],
    "purpose": ["eq"],
}
MAX_CONDITIONS = 40


class FilterError(ValueError):
    pass


def _col(field: str):
    return getattr(EnrichCompany, field)


def _regex(value: str) -> str:
    if not value or len(value) > 200:
        raise FilterError("Biểu thức chính quy rỗng hoặc quá dài.")
    try:
        re.compile(value)
    except re.error as e:
        raise FilterError(f"Biểu thức chính quy không hợp lệ: {e}") from e
    return value


def _condition(c: dict) -> ColumnElement:
    field, cmp, value = c.get("field"), c.get("cmp"), c.get("value")
    if field not in FIELDS:
        raise FilterError(f"Trường không hợp lệ: {field}")
    kind = FIELDS[field][1]
    if cmp not in CMPS[kind]:
        raise FilterError(f"Phép so sánh “{cmp}” không dùng được cho {FIELDS[field][0]}.")
    if kind == "text":
        col = _col(field)
        v = str(value or "").strip()
        if cmp == "empty":
            return or_(col.is_(None), col == "")
        if cmp == "not_empty":
            return and_(col.is_not(None), col != "")
        if cmp == "regex":
            return col.regexp_match(_regex(v), flags="i")
        if cmp == "in":
            items = [x.strip() for x in (value if isinstance(value, list) else str(v).split(",")) if str(x).strip()]
            return col.in_(items) if items else false()
        if field == "ten" and cmp in ("contains", "not_contains", "starts"):
            col, v = EnrichCompany.ten_khong_dau, bo_dau(v)  # tên: không dấu (N12)
        if cmp == "contains":
            return col.ilike(f"%{v}%")
        if cmp == "not_contains":
            return or_(col.is_(None), not_(col.ilike(f"%{v}%")))
        if cmp == "starts":
            return col.ilike(f"{v}%")
        if cmp == "eq":
            return col == v
        return or_(col.is_(None), col != v)
    if kind == "list":
        col = cast(_col(field), String)
        if cmp == "empty":
            return or_(_col(field).is_(None), col == "[]")
        if cmp == "not_empty":
            return and_(_col(field).is_not(None), col != "[]")
        if cmp == "regex":
            return col.regexp_match(_regex(str(value or "")), flags="i")
        like = col.ilike(f"%{str(value or '').strip()}%")
        return like if cmp == "contains" else or_(_col(field).is_(None), not_(like))
    if kind == "date":
        col = _col(field)
        if cmp in ("empty", "not_empty"):
            return col.is_(None) if cmp == "empty" else col.is_not(None)
        d = parse_date(value)
        if not d:
            raise FilterError("Ngày không hợp lệ.")
        return col >= d if cmp == "gte" else col <= d
    if kind == "number":
        col = _col(field)
        if cmp in ("empty", "not_empty"):
            return col.is_(None) if cmp == "empty" else col.is_not(None)
        try:
            n = int(float(value))
        except (TypeError, ValueError) as e:
            raise FilterError("Giá trị số không hợp lệ.") from e
        return {"gte": col >= n, "lte": col <= n, "eq": col == n}[cmp]
    if kind == "bool":
        if field == "co_nguoi_quyet_dinh":
            cond = exists().where(
                PersonRole.company_mst == EnrichCompany.mst, PersonRole.la_nguoi_quyet_dinh.is_(True), PersonRole.den_ngay.is_(None)
            )
        else:
            cond = _col(field).is_(True)
        return cond if cmp == "is_true" else not_(cond)
    if kind == "signal":
        v = value if isinstance(value, dict) else {"kind": value}
        days = int(v.get("days") or 365)
        conds = [EnrichSignal.mst == EnrichCompany.mst, EnrichSignal.created_at >= utcnow() - timedelta(days=days)]
        if v.get("kind"):
            conds.append(EnrichSignal.kind == v["kind"])
        return exists().where(*conds)
    if kind == "batch":
        return exists().where(EnrichBatchItem.mst == EnrichCompany.mst, EnrichBatchItem.batch_id == int(value))
    if kind == "purpose":
        # mục đích nằm trong JSON của lô → lọc theo danh sách lô có mục đích đó (tính sẵn ở build)
        raise AssertionError("xử lý ở build()")
    raise FilterError("Điều kiện không hợp lệ.")


def _purpose_batches(db, purpose: str) -> list[int]:
    return [b.id for b in db.scalars(select(EnrichBatch)) if purpose in (b.purposes or [])]


def _group(db, g: dict, depth: int, counter: list[int]) -> ColumnElement:
    if depth > 3:
        raise FilterError("Lồng nhóm điều kiện tối đa 3 tầng.")
    parts = []
    for c in g.get("conditions") or []:
        counter[0] += 1
        if counter[0] > MAX_CONDITIONS:
            raise FilterError(f"Tối đa {MAX_CONDITIONS} điều kiện.")
        if "conditions" in c:
            parts.append(_group(db, c, depth + 1, counter))
        elif c.get("field") == "muc_dich":
            ids = _purpose_batches(db, str(c.get("value")))
            parts.append(exists().where(EnrichBatchItem.mst == EnrichCompany.mst, EnrichBatchItem.batch_id.in_(ids)) if ids else false())
        else:
            parts.append(_condition(c))
    if not parts:
        return true()
    return or_(*parts) if g.get("op") == "or" else and_(*parts)


def build(db, definition: dict | None) -> ColumnElement:
    """Điều kiện WHERE cho EnrichCompany từ định nghĩa bộ lọc."""
    d = definition or {}
    where = _group(db, d, 1, [0])
    q = str(d.get("q") or "").strip()
    if q:
        digits = re.sub(r"[^\d-]", "", q)
        quick = [EnrichCompany.ten_khong_dau.like(f"%{bo_dau(q)}%")]
        if len(digits) >= 3:
            quick.append(EnrichCompany.mst.like(f"{digits}%"))
        if len(q) <= 10:
            quick.append(EnrichCompany.ma_ck == q.upper())
        where = and_(where, or_(*quick))
    return where


def meta() -> dict:
    return {"fields": {k: {"label": v[0], "type": v[1], "cmps": CMPS[v[1]]} for k, v in FIELDS.items()}}
