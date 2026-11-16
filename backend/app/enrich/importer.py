"""Nhập danh sách MST từ file CSV hoặc Excel thành một lô (A01, A02).

File: cột MST bắt buộc (nhận tiêu đề "MST", "Mã số thuế", "tax code"…; không có dòng tiêu đề thì lấy cột đầu),
cột tên doanh nghiệp tuỳ chọn. Mỗi MST hợp lệ:
  • tạo hồ sơ kho A nếu chưa có (khoá MST — B05),
  • gắn vào lô (mục đích sử dụng được phép đi theo lô),
  • ghi bằng chứng cho trường mst (và tên, nếu file có) trỏ về file + số dòng.
MST trùng trong file chỉ lấy lần đầu; MST đã có trong hệ thống vẫn gắn vào lô mới.
"""

import csv
import hashlib
import io
from dataclasses import dataclass, field

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.enrich import merge, sources
from app.enrich.normalize import bo_dau, parse_mst
from app.models import AdminUser
from app.models_enrich import CompanyEvidence, EnrichBatch, EnrichBatchItem, EnrichCompany

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_LISTED = 500  # số dòng lỗi / trùng liệt kê chi tiết trong biên bản

MST_HEADERS = {"mst", "ma so thue", "masothue", "ma_so_thue", "tax code", "tax_code", "taxcode", "ma so thue doanh nghiep"}
NAME_HEADERS = {"ten", "ten doanh nghiep", "ten cong ty", "ten dn", "ten_doanh_nghiep", "company", "company name", "name"}


class ImportError_(ValueError):
    """Lỗi file nhập — thông báo hiển thị thẳng cho người dùng."""


@dataclass
class Row:
    row_no: int
    mst: str
    name: str
    raw: str


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

    def report(self) -> dict:
        return {
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


def analyze(file_name: str, data: bytes) -> Analysis:
    table = read_table(file_name, data)
    while table and not any(_cell(c) for c in table[-1]):
        table.pop()
    if not table:
        raise ImportError_("File trống.")
    an = Analysis()
    an.has_header, mst_col, name_col = _detect(table[0])
    an.has_name = name_col is not None
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
        an.rows.append(
            Row(row_no=row_no, mst=res.mst, name=" ".join(name.split())[:400], raw=" | ".join(_cell(c) for c in row)[:500])
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
    rep["sample"] = [{"row": r.row_no, "mst": r.mst, "name": r.name} for r in an.rows[:10]]
    return rep


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
    msts = [r.mst for r in an.rows]
    existing = existing_msts(db, msts)
    now = utcnow()
    src = sources.ensure(db, sources.IMPORT)

    report = an.report()
    report["existing"] = len(existing)
    report["new"] = len(msts) - len(existing)
    batch = EnrichBatch(
        name=name,
        list_source=list_source,
        purposes=purposes,
        note=note,
        file_name=file_name[:255],
        file_sha256=hashlib.sha256(data).hexdigest(),
        report=report,
        mst_count=len(msts),
        new_count=report["new"],
        created_by_id=user.id,
        created_at=now,
    )
    db.add(batch)
    db.flush()

    new_rows = [r for r in an.rows if r.mst not in existing]
    if new_rows:
        db.execute(
            insert(EnrichCompany),
            [{"mst": r.mst, "ten_khong_dau": "", "created_at": now, "updated_at": now} for r in new_rows],
        )
    db.execute(
        insert(EnrichBatchItem),
        [{"batch_id": batch.id, "mst": r.mst, "row_no": r.row_no, "is_new": r.mst not in existing} for r in an.rows],
    )
    # B12: cùng một file nhập lại → không sinh bằng chứng lặp (khoá: MST, trường, giá trị, mã băm file)
    seen: set[tuple[str, str, str]] = set()
    for i in range(0, len(msts), 1000):
        seen.update(
            db.execute(
                select(CompanyEvidence.mst, CompanyEvidence.field, CompanyEvidence.value).where(
                    CompanyEvidence.source_code == src.code,
                    CompanyEvidence.content_hash == batch.file_sha256,
                    CompanyEvidence.mst.in_(msts[i : i + 1000]),
                )
            ).all()
        )
    evidence = []
    for r in an.rows:
        common = {
            "mst": r.mst,
            "source_code": src.code,
            "source_url": f"{batch.file_name}#dong={r.row_no}",
            "excerpt": f"Dòng {r.row_no}: {r.raw}",
            "method": "nhap_lo",
            "is_inferred": False,
            "content_hash": batch.file_sha256,
            "batch_id": batch.id,
            "fetched_at": now,
        }
        for field_, value in (("mst", r.mst), ("ten", r.name)):
            if value and (r.mst, field_, value) not in seen:
                evidence.append({**common, "field": field_, "value": value})
    for i in range(0, len(evidence), 5000):
        db.execute(insert(CompanyEvidence), evidence[i : i + 5000])
    merge.recompute_companies(db, msts)
    db.commit()
    db.refresh(batch)
    return batch
