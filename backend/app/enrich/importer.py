"""Nhập danh sách MST từ file CSV hoặc Excel thành một lô (A01, A02).

File: cột MST bắt buộc (nhận tiêu đề "MST", "Mã số thuế", "tax code"…; không có dòng tiêu đề thì lấy cột đầu),
cột tên doanh nghiệp tuỳ chọn. Các cột khác được nhận theo tiêu đề (EXTRA_HEADERS): địa chỉ, tỉnh/thành, điện thoại,
email, website, ngành nghề, nhóm ngành, nhóm sản phẩm, mã HS, tình trạng, ngày thành lập, vốn. Mỗi MST hợp lệ:
  • tạo hồ sơ kho A nếu chưa có (khoá MST — B05),
  • gắn vào lô (mục đích sử dụng được phép đi theo lô),
  • ghi bằng chứng cho mọi trường nhận được, trỏ về file + số dòng. Nguồn "nhập lô" có độ tin cậy thấp (0,5)
    nên dữ liệu ĐKKD / nguồn chính thức nhập sau tự được ưu tiên hiển thị; giá trị từ lô vẫn giữ làm bằng chứng.
  • điện thoại / email chung của doanh nghiệp → bảng liên hệ (như liên hệ chung lấy từ website).
Cột dữ liệu cá nhân nhạy cảm (CCCD, ngày sinh…) bị bỏ qua và liệt kê trong biên bản; cột không nhận ra chỉ nằm trong
trích đoạn của bằng chứng. MST trùng trong file chỉ lấy lần đầu; MST đã có trong hệ thống vẫn gắn vào lô mới.
"""

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.enrich import merge, sources
from app.enrich.connectors.base import CompanyFact
from app.enrich.normalize import bo_dau, normalize_phone, parse_mst
from app.models import AdminUser
from app.models_enrich import COMPANY_FIELDS, CompanyEvidence, EnrichBatch, EnrichBatchItem, EnrichCompany, EnrichContact, EnrichSignal, OptOut

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_LISTED = 500  # số dòng lỗi / trùng liệt kê chi tiết trong biên bản

MST_HEADERS = {"mst", "ma so thue", "masothue", "ma_so_thue", "tax code", "tax_code", "taxcode", "ma so thue doanh nghiep"}
NAME_HEADERS = {"ten", "ten doanh nghiep", "ten cong ty", "ten dn", "ten_doanh_nghiep", "company", "company name", "name"}

# Cột phụ: trường → tiêu đề chấp nhận (không dấu, chữ thường). Tiêu đề khớp nguyên văn hoặc bắt đầu bằng một từ khoá
# (theo ranh giới từ: "mã hs (4 số)" khớp "ma hs"); nhiều từ khoá cùng khớp thì từ khoá dài nhất thắng
# ("ngành nghề kinh doanh chính" → ngành nghề ĐKKD, "ngành nghề" trơn → nhóm ngành theo danh sách).
EXTRA_HEADERS: dict[str, list[str]] = {
    "ten_tieng_anh": ["ten tieng anh", "ten giao dich quoc te", "ten quoc te", "english name", "ten nuoc ngoai"],
    "fax": ["fax", "so fax"],
    "nam_thanh_lap": ["nam thanh lap", "nam thanh lap doanh nghiep", "founded"],
    "mo_ta": ["gioi thieu", "mo ta", "gioi thieu doanh nghiep", "gioi thieu chung", "description"],
    "dia_chi": ["dia chi", "dia chi tru so", "dia chi tru so chinh", "dia chi doanh nghiep", "dia chi cong ty", "address"],
    "tinh": ["tinh", "tinh/thanh", "tinh thanh", "tinh/thanh pho", "tinh thanh pho", "province"],
    "dien_thoai": ["dien thoai", "so dien thoai", "sdt", "so dt", "dt", "phone", "tel", "telephone", "hotline"],
    "email": ["email", "e-mail", "mail", "thu dien tu", "dia chi email", "dia chi thu dien tu"],
    "website": ["website", "web", "trang web", "trang chu", "dia chi website", "dia chi web"],
    "nganh_nghe": ["nganh nghe kinh doanh", "nganh nghe kinh doanh chinh", "nganh nghe chinh", "nganh kinh doanh chinh", "nganh nghe dkkd"],
    "nhom_nganh": ["nganh nghe", "nganh", "nhom nganh", "linh vuc", "phan loai nganh", "industry"],
    "nhom_san_pham": ["phan nhom san pham", "nhom san pham", "san pham", "mat hang", "nhom hang", "nhom mat hang", "product"],
    "ma_hs": ["ma hs", "hs code", "hs"],
    "trang_thai": ["tinh trang", "trang thai", "tinh trang hoat dong"],
    "ngay_thanh_lap": ["ngay thanh lap", "ngay cap phep", "ngay dang ky"],
    "von": ["von dieu le", "von"],
}
CONTACT_FIELDS = {"dien_thoai": "phone", "fax": "fax", "email": "email"}
EXTRA_LABELS = {**COMPANY_FIELDS, "dien_thoai": "Điện thoại doanh nghiệp", "fax": "Fax doanh nghiệp", "email": "Email chung doanh nghiệp"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


class ImportError_(ValueError):
    """Lỗi file nhập — thông báo hiển thị thẳng cho người dùng."""


@dataclass
class Row:
    row_no: int
    mst: str
    name: str
    raw: str
    extra: dict[str, object] = field(default_factory=dict)  # trường phụ → giá trị thô trong ô
    url: str = ""  # nguồn riêng của dòng (vd trang hồ sơ PROFIT500); rỗng = file#dong=
    excerpt: str = ""  # trích đoạn riêng; rỗng = "Dòng N: <cả dòng>"
    content_hash: str = ""  # mã băm nội dung riêng của dòng (khử trùng khi đồng bộ lại); rỗng = mã băm file
    signals: list = field(default_factory=list)  # SignalFact — vd xếp hạng PROFIT500


@dataclass
class Analysis:
    rows: list[Row] = field(default_factory=list)  # MST hợp lệ, không trùng trong file
    total: int = 0
    invalid: list[dict] = field(default_factory=list)
    invalid_count: int = 0
    duplicates: list[dict] = field(default_factory=list)
    duplicate_count: int = 0
    padded_count: int = 0
    has_header: bool = False
    has_name: bool = False
    columns: list[dict] = field(default_factory=list)  # [{header, field, label}] — cột phụ nhận được
    ignored: list[str] = field(default_factory=list)  # tiêu đề không nhận ra (chỉ nằm trong trích đoạn)
    sensitive: list[str] = field(default_factory=list)  # cột dữ liệu cá nhân nhạy cảm — bỏ qua
    filled: dict[str, int] = field(default_factory=dict)  # trường phụ → số dòng có giá trị
    phone_ok: int = 0
    phone_bad: list[dict] = field(default_factory=list)
    phone_bad_count: int = 0

    def report(self) -> dict:
        return {
            "columns": [{**c, "filled": self.filled.get(c["field"], 0)} for c in self.columns],
            "ignored_columns": self.ignored,
            "sensitive_columns": self.sensitive,
            "phones": {"ok": self.phone_ok, "bad": self.phone_bad_count, "bad_rows": self.phone_bad},
            "total_rows": self.total,
            "valid": len(self.rows),
            "duplicate_in_file": self.duplicate_count,
            "invalid": self.invalid_count,
            "zero_padded": self.padded_count,
            "has_header": self.has_header,
            "has_name_column": self.has_name,
            "invalid_rows": self.invalid,
            "duplicate_rows": self.duplicates,
        }


def _cell(v) -> str:
    return "" if v is None else str(v).strip()


def read_table(file_name: str, data: bytes) -> list[list]:
    if len(data) > MAX_FILE_BYTES:
        raise ImportError_("File quá lớn (tối đa 10 MB).")
    name = file_name.lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001 — file hỏng / không phải Excel
            raise ImportError_("Không đọc được file Excel. Kiểm tra lại file .xlsx.") from e
        ws = wb.worksheets[0]
        rows = []
        for r in ws.iter_rows(values_only=True):
            rows.append(list(r))
            if len(rows) > MAX_ROWS + 1:
                break
        wb.close()
        return rows
    if name.endswith(".xls"):
        raise ImportError_("Định dạng .xls cũ chưa hỗ trợ — mở bằng Excel rồi lưu lại thành .xlsx hoặc .csv.")
    if name.endswith((".csv", ".txt")):
        for enc in ("utf-8-sig", "cp1258"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = data.decode("utf-8", errors="replace")
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        return [r for r in csv.reader(io.StringIO(text), dialect)]
    raise ImportError_("Chỉ nhận file .csv, .xlsx.")


def _detect(first: list) -> tuple[bool, int, int | None]:
    """(có dòng tiêu đề?, cột MST, cột tên)."""
    heads = [bo_dau(_cell(c)) for c in first]
    mst_col = next((i for i, h in enumerate(heads) if h in MST_HEADERS or h.startswith("mst")), None)
    name_col = next((i for i, h in enumerate(heads) if h in NAME_HEADERS or h.startswith("ten doanh nghiep")), None)
    if mst_col is not None:
        return True, mst_col, name_col
    if first and parse_mst(first[0]).mst:  # không có dòng tiêu đề: cột đầu là MST
        return False, 0, None
    raise ImportError_("Không thấy cột mã số thuế. Đặt tiêu đề cột là “MST” hoặc “Mã số thuế”, hoặc để MST ở cột đầu.")


def _extra_field(head: str) -> str | None:
    best, best_len = None, 0
    for target, syns in EXTRA_HEADERS.items():
        for s in syns:
            if (head == s or (head.startswith(s) and not head[len(s)].isalnum())) and len(s) > best_len:
                best, best_len = target, len(s)
    return best


def _detect_extra(first: list, skip: set[int]) -> tuple[dict[int, str], list[dict], list[str], list[str]]:
    """Cột phụ theo tiêu đề → ({chỉ số cột: trường}, mô tả cột, tiêu đề bỏ qua, tiêu đề nhạy cảm)."""
    from app.enrich.official import SENSITIVE  # trễ: official import từ module này

    cols: dict[int, str] = {}
    described: list[dict] = []
    ignored: list[str] = []
    sensitive: list[str] = []
    for i, c in enumerate(first):
        if i in skip or not _cell(c):
            continue
        head = bo_dau(_cell(c))
        if any(w in head for w in SENSITIVE):
            sensitive.append(_cell(c))
            continue
        target = _extra_field(head)
        if target is None or target in cols.values():  # trùng trường: lấy cột đầu tiên
            ignored.append(_cell(c))
            continue
        cols[i] = target
        described.append({"header": _cell(c), "field": target, "label": EXTRA_LABELS[target]})
    return cols, described, ignored, sensitive


def split_phones(raw) -> tuple[list[str], list[str]]:
    """Ô điện thoại → (số chuẩn +84…, phần không nhận được).

    Sửa lỗi Excel hay gặp: số lưu dạng số mất 0 đầu (974102195 → 0974102195; 241.3821603 → 02413821603).
    Số đã bị Excel đổi sang dạng khoa học (8.40948E+11) mất chữ số thật → không đoán, báo lại.
    """
    if raw is None or raw == "":
        return [], []
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    ok: list[str] = []
    bad: list[str] = []
    for part in re.split(r"\s*[/;,\n|]\s*|\s+-\s+", str(raw)):
        part = part.strip()
        if not part:
            continue
        if re.search(r"\d[eE]\+\d", part):
            bad.append(part)
            continue
        d = re.sub(r"[^\d+]", "", part)
        if re.fullmatch(r"1[89]00\d{4,6}", d):  # tổng đài 1800 / 1900 — không có dạng +84
            if d not in ok:
                ok.append(d)
            continue
        if d and not d.startswith(("0", "+", "84")) and len(d) in (9, 10):
            d = "0" + d
        p = normalize_phone(d)
        if p:
            if p not in ok:
                ok.append(p)
        else:
            bad.append(part)
    return ok, bad


def split_emails(raw) -> list[str]:
    return list(dict.fromkeys(m.lower() for m in _EMAIL.findall(_cell(raw))))


def analyze(file_name: str, data: bytes) -> Analysis:
    table = read_table(file_name, data)
    while table and not any(_cell(c) for c in table[-1]):
        table.pop()
    if not table:
        raise ImportError_("File trống.")
    an = Analysis()
    an.has_header, mst_col, name_col = _detect(table[0])
    an.has_name = name_col is not None
    extra_cols: dict[int, str] = {}
    if an.has_header:
        extra_cols, an.columns, an.ignored, an.sensitive = _detect_extra(table[0], {mst_col, *([name_col] if name_col is not None else [])})
    start = 1 if an.has_header else 0
    if len(table) - start > MAX_ROWS:
        raise ImportError_(f"File có hơn {MAX_ROWS:,} dòng — chia thành nhiều lô.".replace(",", "."))
    first_row_of: dict[str, int] = {}
    for idx in range(start, len(table)):
        row = table[idx]
        row_no = idx + 1  # số dòng như khi mở file
        if not any(_cell(c) for c in row):
            continue
        an.total += 1
        raw = row[mst_col] if mst_col < len(row) else None
        res = parse_mst(raw)
        if res.mst is None:
            an.invalid_count += 1
            if len(an.invalid) < MAX_LISTED:
                an.invalid.append({"row": row_no, "value": _cell(raw)[:60], "reason": res.error})
            continue
        if res.mst in first_row_of:
            an.duplicate_count += 1
            if len(an.duplicates) < MAX_LISTED:
                an.duplicates.append({"row": row_no, "mst": res.mst, "first_row": first_row_of[res.mst]})
            continue
        first_row_of[res.mst] = row_no
        if res.padded:
            an.padded_count += 1
        name = _cell(row[name_col]) if name_col is not None and name_col < len(row) else ""
        extra: dict[str, object] = {}
        for ci, target in extra_cols.items():
            v = row[ci] if ci < len(row) else None
            if v is None or _cell(v) == "":
                continue
            if target == "dien_thoai":
                phones, bad = split_phones(v)
                an.phone_ok += len(phones)
                if bad:
                    an.phone_bad_count += 1
                    if len(an.phone_bad) < MAX_LISTED:
                        an.phone_bad.append({"row": row_no, "value": _cell(v)[:80], "unreadable": bad[:5]})
                if not phones:
                    continue
                v = phones
            elif target == "fax":
                v = split_phones(v)[0]
                if not v:
                    continue
            elif target == "email":
                v = split_emails(v)
                if not v:
                    continue
            extra[target] = v
            an.filled[target] = an.filled.get(target, 0) + 1
        an.rows.append(
            Row(
                row_no=row_no, mst=res.mst, name=" ".join(name.split())[:400], raw=" | ".join(_cell(c) for c in row)[:500], extra=extra
            )
        )
    return an


def existing_msts(db: Session, msts: list[str]) -> set[str]:
    found: set[str] = set()
    for i in range(0, len(msts), 1000):
        found.update(db.scalars(select(EnrichCompany.mst).where(EnrichCompany.mst.in_(msts[i : i + 1000]))))
    return found


def preview(db: Session, file_name: str, data: bytes) -> dict:
    an = analyze(file_name, data)
    rep = an.report()
    rep["existing"] = len(existing_msts(db, [r.mst for r in an.rows]))
    rep["new"] = rep["valid"] - rep["existing"]
    rep["sample"] = [{"row": r.row_no, "mst": r.mst, "name": r.name, "extra": _sample_extra(r)} for r in an.rows[:10]]
    return rep


def _sample_extra(r: Row) -> dict[str, str]:
    return {k: "; ".join(map(str, v)) if isinstance(v, list) else _cell(v)[:200] for k, v in r.extra.items()}


def _company_facts(r: Row) -> list[CompanyFact]:
    """Trường phụ của một dòng → fact đã chuẩn hoá (địa chỉ sinh thêm tỉnh, website sinh thêm tên miền)."""
    from app.enrich.apply import normalize_fact  # trễ: apply → merge → … tránh vòng import

    out: list[CompanyFact] = []
    for k, v in r.extra.items():
        if k in CONTACT_FIELDS:
            continue
        out.extend(normalize_fact(CompanyFact(k, v, "")))
    return out


def create_batch(
    db: Session,
    user: AdminUser,
    *,
    name: str,
    list_source: str,
    purposes: list[str],
    note: str,
    file_name: str,
    data: bytes,
) -> EnrichBatch:
    an = analyze(file_name, data)
    if not an.rows:
        raise ImportError_("File không có mã số thuế hợp lệ nào.")
    return save_batch(
        db, user, an.rows, an.report(),
        name=name, list_source=list_source, purposes=purposes, note=note,
        file_name=file_name, file_sha256=hashlib.sha256(data).hexdigest(),
    )


def save_batch(
    db: Session,
    user: AdminUser | None,
    rows: list[Row],
    report: dict,
    *,
    name: str,
    list_source: str,
    purposes: list[str],
    note: str,
    file_name: str,
    file_sha256: str,
    source_code: str = sources.IMPORT,
    method: str = "nhap_lo",
) -> EnrichBatch:
    """Ghi một lô từ các dòng đã phân tích (file nhập, crawler PROFIT500 — app/services/profit500.py).

    Dòng có `url` / `content_hash` riêng (vd hồ sơ PROFIT500) thì bằng chứng trỏ về đó; không thì về file + số dòng.
    """
    msts = [r.mst for r in rows]
    existing = existing_msts(db, msts)
    now = utcnow()
    src = sources.ensure(db, source_code)

    report = dict(report)
    report["existing"] = len(existing)
    report["new"] = len(msts) - len(existing)
    batch = EnrichBatch(
        name=name,
        list_source=list_source,
        purposes=purposes,
        note=note,
        file_name=file_name[:255],
        file_sha256=file_sha256,
        report=report,
        mst_count=len(msts),
        new_count=report["new"],
        created_by_id=user.id if user else None,
        created_at=now,
    )
    db.add(batch)
    db.flush()

    new_rows = [r for r in rows if r.mst not in existing]
    if new_rows:
        db.execute(
            insert(EnrichCompany),
            [{"mst": r.mst, "ten_khong_dau": "", "created_at": now, "updated_at": now} for r in new_rows],
        )
    db.execute(
        insert(EnrichBatchItem),
        [{"batch_id": batch.id, "mst": r.mst, "row_no": r.row_no, "is_new": r.mst not in existing} for r in rows],
    )
    # B12: cùng nội dung nhập lại → không sinh bằng chứng lặp (khoá: MST, trường, giá trị, mã băm nội dung)
    seen: set[tuple[str, str, str, str]] = set()
    for i in range(0, len(msts), 1000):
        seen.update(
            db.execute(
                select(CompanyEvidence.mst, CompanyEvidence.field, CompanyEvidence.value, CompanyEvidence.content_hash).where(
                    CompanyEvidence.source_code == src.code,
                    CompanyEvidence.mst.in_(msts[i : i + 1000]),
                )
            ).all()
        )
    evidence = []
    for r in rows:
        h = r.content_hash or file_sha256
        common = {
            "mst": r.mst,
            "source_code": src.code,
            "source_url": (r.url or f"{batch.file_name}#dong={r.row_no}")[:1000],
            "excerpt": (r.excerpt or f"Dòng {r.row_no}: {r.raw}")[:2000],
            "method": method,
            "is_inferred": False,
            "content_hash": h,
            "batch_id": batch.id,
            "fetched_at": now,
        }
        pairs = [("mst", r.mst), ("ten", r.name)]
        pairs += [(f.field, merge.encode(f.field, f.value)) for f in _company_facts(r)]
        for field_, value in pairs:
            if value and (r.mst, field_, value, h) not in seen:
                seen.add((r.mst, field_, value, h))
                evidence.append({**common, "field": field_, "value": value})
    for i in range(0, len(evidence), 5000):
        db.execute(insert(CompanyEvidence), evidence[i : i + 5000])
    _add_company_contacts(db, rows, src.code)
    _add_signals(db, rows, src.code)
    merge.recompute_companies(db, msts)
    db.commit()
    db.refresh(batch)
    return batch


def _add_company_contacts(db: Session, rows: list[Row], source_code: str) -> int:
    """Điện thoại / email chung của doanh nghiệp → enrich_contacts (owner_type company). Bỏ giá trị đã có hoặc trong
    danh sách từ chối (C10)."""
    wanted = [(r.mst, CONTACT_FIELDS[k], v) for r in rows for k in CONTACT_FIELDS for v in r.extra.get(k, [])]
    if not wanted:
        return 0
    blocked = {v.strip().lower() for (v,) in db.execute(select(OptOut.value).where(OptOut.kind.in_(("email", "phone"))))}
    msts = list({m for m, _, _ in wanted})
    have: set[tuple[str, str]] = set()
    for i in range(0, len(msts), 1000):
        have.update(
            db.execute(
                select(EnrichContact.owner_id, EnrichContact.value).where(
                    EnrichContact.owner_type == "company", EnrichContact.owner_id.in_(msts[i : i + 1000])
                )
            ).all()
        )
    new = []
    for mst, kind, value in wanted:
        if (mst, value) in have or value.lower() in blocked:
            continue
        have.add((mst, value))
        new.append(
            {"owner_type": "company", "owner_id": mst, "kind": kind, "value": value[:200], "is_inferred": False, "verify_status": "unverified", "source_code": source_code}
        )
    for i in range(0, len(new), 5000):
        db.execute(insert(EnrichContact), new[i : i + 5000])
    return len(new)


def _add_signals(db: Session, rows: list[Row], source_code: str) -> int:
    """Tín hiệu đi kèm dòng (vd xếp hạng PROFIT500). Khử trùng theo khoá nội dung như apply_facts."""
    from app.enrich.apply import signal_key  # trễ: tránh vòng import

    wanted = [(r, s) for r in rows for s in r.signals]
    if not wanted:
        return 0
    keys = {(r.mst, signal_key(s.kind, s.payload, source_code)): (r, s) for r, s in wanted}
    msts = list({m for m, _ in keys})
    have: set[tuple[str, str]] = set()
    for i in range(0, len(msts), 1000):
        have.update(db.execute(select(EnrichSignal.mst, EnrichSignal.dedupe_key).where(EnrichSignal.mst.in_(msts[i : i + 1000]))).all())
    new = [
        {"mst": m, "kind": s.kind, "payload": s.payload, "day": s.day, "source_code": source_code, "source_url": (r.url or "")[:1000], "dedupe_key": k}
        for (m, k), (r, s) in keys.items()
        if (m, k) not in have
    ]
    for i in range(0, len(new), 5000):
        db.execute(insert(EnrichSignal), new[i : i + 5000])
    return len(new)
