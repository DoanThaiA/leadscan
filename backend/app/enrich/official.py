"""Nhập file từ nguồn chính thức: dữ liệu mua từ Cổng ĐKKD (A03), danh sách nợ thuế, kết quả đấu thầu.

• Chỉ ghi cho MST đã có trong hệ thống (danh sách đầu vào) — MST lạ trong file bị bỏ qua, không tạo hồ sơ mới.
• Cột nhận diện theo tiêu đề (không dấu). Cột dữ liệu cá nhân nhạy cảm (CCCD, ngày sinh, địa chỉ cá nhân…)
  bị BỎ QUA và liệt kê trong biên bản — hệ thống không có chỗ để lưu chúng (T09).
• File gốc lưu thành SourcePage (A09); mỗi giá trị là một bằng chứng trỏ về file + dòng.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enrich import merge, raw_store, sources
from app.enrich.apply import Applied, Origin, apply_facts
from app.enrich.connectors.base import CompanyFact, Facts, PersonFact, SignalFact
from app.enrich.importer import ImportError_, _cell, read_table
from app.enrich.normalize import bo_dau, clean_text, parse_date, parse_money, parse_mst
from app.models import AdminUser
from app.models_enrich import EnrichCompany, EnrichImport

KINDS = {
    "dkkd_mua": "Dữ liệu mua từ Cổng ĐKKD",
    "no_thue": "Danh sách nợ thuế",
    "dau_thau": "Kết quả lựa chọn nhà thầu",
    "ds_niem_yet": "Danh sách niêm yết (HOSE, HNX, UPCoM)",
}

# trường → các tiêu đề cột chấp nhận (không dấu, chữ thường); khớp nguyên văn hoặc bắt đầu bằng
COLUMNS: dict[str, dict[str, list[str]]] = {
    "dkkd_mua": {
        "mst": ["ma so doanh nghiep", "ma so thue", "mst", "ma doanh nghiep", "ma so dn"],
        "ten": ["ten doanh nghiep", "ten cong ty", "ten tieng viet", "ten"],
        "dia_chi": ["dia chi tru so chinh", "dia chi tru so", "dia chi"],
        "trang_thai": ["tinh trang hoat dong", "tinh trang", "trang thai"],
        "nganh_nghe": ["nganh nghe kinh doanh chinh", "nganh nghe chinh", "nganh kinh doanh chinh", "nganh chinh", "nganh nghe"],
        "ngay_thanh_lap": ["ngay thanh lap", "ngay cap giay chung nhan lan dau", "ngay dang ky lan dau", "ngay bat dau hoat dong", "ngay cap"],
        "von": ["von dieu le", "von dau tu", "von"],
        "website": ["website", "trang web"],
        "nguoi_dai_dien": ["nguoi dai dien theo phap luat", "nguoi dai dien phap luat", "ten nguoi dai dien", "dai dien phap luat", "nguoi dai dien"],
        "chuc_danh_dai_dien": ["chuc danh nguoi dai dien", "chuc danh"],
    },
    "no_thue": {
        "mst": ["ma so thue", "mst", "ma so doanh nghiep"],
        "ten": ["ten nguoi nop thue", "ten doanh nghiep", "ten don vi", "ten"],
        "so_tien": ["tong so tien thue no", "tong so no", "so tien no", "so no thue", "tien thue no", "so thue no", "tong no"],
        "ky": ["no den ngay", "thoi diem", "ky", "den ngay"],
        "co_quan": ["co quan thue quan ly", "co quan thue", "chi cuc thue", "co quan quan ly"],
    },
    "dau_thau": {
        "mst": ["ma so thue nha thau", "mst nha thau", "ma so thue", "mst", "ma dinh danh nha thau"],
        "ten": ["ten nha thau trung thau", "ten nha thau", "nha thau trung thau", "nha thau"],
        "goi_thau": ["ten goi thau", "goi thau"],
        "gia": ["gia trung thau", "gia hop dong", "gia trung"],
        "ben_moi_thau": ["ben moi thau", "chu dau tu", "don vi moi thau"],
        "ngay": ["ngay phe duyet ket qua", "ngay phe duyet", "ngay dang tai", "ngay"],
        "ma_tbmt": ["so tbmt", "ma tbmt", "so thong bao moi thau", "ma goi thau"],
    },
}
COLUMNS["ds_niem_yet"] = {
    "mst": ["ma so thue", "mst", "ma so doanh nghiep"],
    "ma_ck": ["ma chung khoan", "ma ck", "ma cp", "ma co phieu", "ticker", "symbol"],
    "ten": ["ten cong ty", "ten doanh nghiep", "ten to chuc phat hanh", "ten"],
    "san": ["san giao dich", "san niem yet", "noi niem yet", "san"],
}
REQUIRED = {"dkkd_mua": ["mst", "ten"], "no_thue": ["mst", "so_tien"], "dau_thau": ["mst", "goi_thau"], "ds_niem_yet": ["mst", "ma_ck"]}
SENSITIVE = (
    "cccd", "cmnd", "can cuoc", "chung minh", "ho chieu", "giay to tuy than", "ngay sinh", "nam sinh", "noi sinh",
    "thuong tru", "cho o hien tai", "dia chi lien lac", "dia chi nguoi dai dien", "gioi tinh", "dan toc", "quoc tich",
    "so dien thoai nguoi dai dien", "email nguoi dai dien", "tai khoan ngan hang",
)
MAX_LISTED = 200


@dataclass
class Parsed:
    kind: str
    header: dict[str, int]  # trường → chỉ số cột
    header_names: dict[str, str]
    ignored: list[str] = field(default_factory=list)
    sensitive: list[str] = field(default_factory=list)
    rows: list[tuple[int, str, dict]] = field(default_factory=list)  # (dòng, MST, giá trị thô theo trường)
    invalid: list[dict] = field(default_factory=list)
    invalid_count: int = 0
    total: int = 0


def _match_header(kind: str, first: list) -> tuple[dict[str, int], dict[str, str], list[str], list[str]]:
    heads = [bo_dau(_cell(c)) for c in first]
    cols: dict[str, int] = {}
    names: dict[str, str] = {}
    sensitive: list[str] = []
    for i, h in enumerate(heads):
        if not h:
            continue
        if any(w in h for w in SENSITIVE):
            sensitive.append(_cell(first[i]))
            continue
        for target, syns in COLUMNS[kind].items():
            if target in cols:
                continue
            if any(h == s or (len(s) >= 8 and h.startswith(s)) for s in syns):  # tiêu đề ngắn (mst, ten, von) phải khớp đúng
                cols[target] = i
                names[target] = _cell(first[i])
                break
    ignored = [_cell(first[i]) for i, h in enumerate(heads) if h and i not in cols.values() and _cell(first[i]) not in sensitive]
    return cols, names, ignored, sensitive


def parse_file(kind: str, file_name: str, data: bytes) -> Parsed:
    if kind not in KINDS:
        raise ImportError_("Loại nguồn không hợp lệ.")
    table = read_table(file_name, data)
    # dòng tiêu đề có thể nằm dưới vài dòng tiêu đề văn bản (file công bố thường có quốc hiệu, tên bảng…)
    for idx, row in enumerate(table[:15]):
        cols, names, ignored, sensitive = _match_header(kind, row)
        if all(r in cols for r in REQUIRED[kind]):
            break
    else:
        need = ", ".join(COLUMNS[kind][r][0] for r in REQUIRED[kind])
        raise ImportError_(f"Không thấy dòng tiêu đề có đủ cột bắt buộc ({need}).")
    p = Parsed(kind=kind, header=cols, header_names=names, ignored=ignored, sensitive=sensitive)
    for i in range(idx + 1, len(table)):
        row = table[i]
        if not any(_cell(c) for c in row):
            continue
        p.total += 1
        raw = row[cols["mst"]] if cols["mst"] < len(row) else None
        res = parse_mst(raw)
        if not res.mst:
            p.invalid_count += 1
            if len(p.invalid) < MAX_LISTED:
                p.invalid.append({"row": i + 1, "value": _cell(raw)[:60], "reason": res.error})
            continue
        values = {t: (row[c] if c < len(row) else None) for t, c in cols.items() if t != "mst"}
        p.rows.append((i + 1, res.mst, values))
    return p


def _facts(kind: str, values: dict, data_date: date | None, excerpt: str) -> Facts:
    f = Facts()
    if kind == "dkkd_mua":
        for key in ("ten", "dia_chi", "trang_thai", "nganh_nghe", "ngay_thanh_lap", "von", "website"):
            if values.get(key) not in (None, ""):
                f.company.append(CompanyFact(key, values[key], excerpt))
        reps = _cell(values.get("nguoi_dai_dien"))
        title = _cell(values.get("chuc_danh_dai_dien")) or "Người đại diện theo pháp luật"
        for name in [x.strip() for x in reps.replace("\n", ";").split(";") if x.strip()]:
            f.people.append(PersonFact(name, title, excerpt))
    elif kind == "ds_niem_yet":
        code = clean_text(values.get("ma_ck"), 20)
        if code:
            f.company.append(CompanyFact("ma_ck", code.upper(), excerpt))
            f.company.append(CompanyFact("niem_yet", True, excerpt))
    elif kind == "no_thue":
        amount = parse_money(values.get("so_tien"))
        if amount:
            f.signals.append(
                SignalFact(
                    "no_thue",
                    {
                        "so_tien": amount,
                        "ky": clean_text(values.get("ky"), 60) or (data_date.isoformat() if data_date else None),
                        "co_quan": clean_text(values.get("co_quan"), 200),
                        "ten_tren_danh_sach": clean_text(values.get("ten"), 300),
                    },
                    parse_date(values.get("ky")) or data_date,
                    excerpt,
                )
            )
    elif kind == "dau_thau":
        goi = clean_text(values.get("goi_thau"), 500)
        if goi:
            f.signals.append(
                SignalFact(
                    "trung_thau",
                    {
                        "goi_thau": goi,
                        "gia_trung_thau": parse_money(values.get("gia")),
                        "ben_moi_thau": clean_text(values.get("ben_moi_thau"), 300),
                        "ma_tbmt": clean_text(values.get("ma_tbmt"), 60),
                        "ten_nha_thau": clean_text(values.get("ten"), 300),
                    },
                    parse_date(values.get("ngay")) or data_date,
                    excerpt,
                )
            )
    return f


def _known(db: Session, msts: list[str]) -> set[str]:
    out: set[str] = set()
    for i in range(0, len(msts), 1000):
        out.update(db.scalars(select(EnrichCompany.mst).where(EnrichCompany.mst.in_(msts[i : i + 1000]))))
    return out


def _report(p: Parsed, known: set[str]) -> dict:
    msts = [m for _, m, _ in p.rows]
    outside = [m for m in dict.fromkeys(msts) if m not in known]
    return {
        "kind": p.kind,
        "total_rows": p.total,
        "valid": len(p.rows),
        "matched": sum(1 for m in msts if m in known),
        "not_in_system": len(outside),
        "not_in_system_sample": outside[:20],
        "invalid": p.invalid_count,
        "invalid_rows": p.invalid,
        "columns": p.header_names,
        "ignored_columns": p.ignored,
        "sensitive_columns": p.sensitive,
    }


def preview(db: Session, kind: str, file_name: str, data: bytes) -> dict:
    p = parse_file(kind, file_name, data)
    rep = _report(p, _known(db, [m for _, m, _ in p.rows]))
    rep["sample"] = [{"row": r, "mst": m, **{k: _cell(v)[:120] for k, v in vals.items()}} for r, m, vals in p.rows[:5]]
    return rep


def import_file(
    db: Session,
    user: AdminUser,
    *,
    kind: str,
    file_name: str,
    data: bytes,
    source_url: str,
    data_date: date | None,
    note: str,
) -> EnrichImport:
    p = parse_file(kind, file_name, data)
    known = _known(db, [m for _, m, _ in p.rows])
    report = _report(p, known)
    if not report["matched"]:
        raise ImportError_("Không dòng nào khớp MST đang có trong hệ thống — kiểm tra lại file hoặc nhập lô MST trước.")
    src = sources.ensure(db, kind)
    if not src.enabled:
        raise ImportError_(f"Nguồn “{src.name}” đang tắt.")
    page, _ = raw_store.save_page(db, src.code, source_url, data, file_name.rsplit(".", 1)[-1])
    total = Applied()
    touched: list[str] = []
    for row_no, mst, values in p.rows:
        if mst not in known:
            continue
        excerpt = f"{file_name} — dòng {row_no}: " + " | ".join(f"{p.header_names.get(k, k)}: {_cell(v)}" for k, v in values.items() if _cell(v))
        facts = _facts(kind, values, data_date, excerpt[:2000])
        if facts.empty():
            continue
        # B12: khoá khử trùng theo NỘI DUNG DÒNG (không theo byte file — xuất lại cùng dữ liệu thì Excel vẫn đổi metadata)
        row_hash = hashlib.sha256(
            json.dumps([kind, mst, {k: _cell(v) for k, v in sorted(values.items())}], ensure_ascii=False).encode()
        ).hexdigest()
        origin = Origin(
            source=src,
            source_url=source_url,
            content_hash=row_hash,
            method="cau_truc",
            source_page_id=page.id,
            actor_id=user.id,
        )
        total.add(apply_facts(db, mst, facts, origin, recompute=False))
        touched.append(mst)
    changes = merge.recompute_companies(db, touched)
    report.update({"evidence": total.evidence, "duplicates": total.duplicates, "people": total.people, "signals": total.signals, "changes": changes})
    imp = EnrichImport(
        source_code=src.code,
        file_name=file_name[:255],
        source_url=source_url[:1000],
        data_date=data_date,
        note=note,
        report=report,
        source_page_id=page.id,
        created_by_id=user.id,
    )
    db.add(imp)
    db.commit()
    db.refresh(imp)
    return imp


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
