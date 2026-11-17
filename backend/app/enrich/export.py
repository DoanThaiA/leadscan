"""Xuất dữ liệu theo bộ lọc (C08, C09) và báo cáo tổng hợp thị trường (C11).

Quy tắc:
  • Bắt buộc khai mục đích (T11). Doanh nghiệp mà không lô nào cho phép mục đích đó → dòng bị CHẶN và đếm vào
    nhật ký (T02); nếu mọi dòng bị chặn thì cả lần xuất bị chặn.
  • Cột kho B (người ra quyết định, email công việc) chỉ cho vai trò được xuất kho B; vai trò khác bị tự loại (C08).
  • KHÔNG BAO GIỜ có cột MST cá nhân, kể cả quản trị (T04) — danh mục cột không có cột này.
  • Email suy luận chỉ khi người dùng chọn "kèm giá trị suy luận" (B11), và luôn ghi chú "(suy luận)".
  • Người / email / điện thoại trong danh sách từ chối bị loại (C10).
  • Mỗi lần xuất ghi enrich_exports (ai, lúc nào, bao nhiêu dòng, cột gì, mục đích, hạn dùng file) — kể cả lần bị chặn.
"""

import csv
import hashlib
import io
from collections import Counter, defaultdict
from datetime import timedelta

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.enrich import khob, search
from app.enrich import permissions as perm
from app.enrich.merge import encode
from app.models import AdminUser
from app.models_enrich import (
    PURPOSES,
    REQUIRED_FIELDS,
    EnrichBatch,
    EnrichBatchItem,
    EnrichCompany,
    EnrichContact,
    EnrichPerson,
    ExportRecord,
    PersonRole,
)

MAX_ROWS = 50_000

COLUMNS_A = {
    "mst": "Mã số thuế",
    "ten": "Tên doanh nghiệp",
    "loai_hinh": "Loại hình",
    "dia_chi": "Địa chỉ",
    "tinh": "Tỉnh/thành",
    "trang_thai": "Tình trạng",
    "nganh_nghe": "Ngành nghề",
    "nhom_nganh": "Nhóm ngành (theo danh sách)",
    "nhom_san_pham": "Nhóm sản phẩm",
    "ma_hs": "Mã HS",
    "ngay_thanh_lap": "Ngày thành lập",
    "von": "Vốn điều lệ",
    "website": "Website",
    "ma_ck": "Mã CK",
    "email_dn": "Email chung doanh nghiệp",
    "dien_thoai_dn": "Điện thoại doanh nghiệp",
}
COLUMNS_B = {
    "nguoi_quyet_dinh": "Người ra quyết định (họ tên — chức danh)",
    "email_nguoi": "Email công việc người ra quyết định",
}
# T04: không có "mst_ca_nhan" trong bất kỳ danh mục nào ở trên


def columns_for(user: AdminUser) -> dict[str, str]:
    cols = dict(COLUMNS_A)
    if perm.has(user, "b.export"):
        cols.update(COLUMNS_B)
    return cols


def _allowed_purposes(db: Session, msts: list[str]) -> dict[str, set[str]]:
    batches = {b.id: set(b.purposes or []) for b in db.scalars(select(EnrichBatch))}
    out: dict[str, set[str]] = defaultdict(set)
    for i in range(0, len(msts), 1000):
        for mst, bid in db.execute(select(EnrichBatchItem.mst, EnrichBatchItem.batch_id).where(EnrichBatchItem.mst.in_(msts[i : i + 1000]))):
            out[mst] |= batches.get(bid, set())
    return out


def export_companies(
    db: Session,
    user: AdminUser,
    *,
    definition: dict,
    columns: list[str],
    purpose: str,
    include_inferred: bool,
    request: Request | None = None,
) -> tuple[bytes, ExportRecord]:
    if purpose not in PURPOSES:
        raise HTTPException(422, "Khai mục đích sử dụng của bản xuất.")
    allowed_cols = columns_for(user)
    columns = [c for c in dict.fromkeys(columns) if c in allowed_cols] or ["mst", "ten"]  # cột không được phép tự bị loại
    wants_b = any(c in COLUMNS_B for c in columns)

    rows = db.scalars(select(EnrichCompany).where(search.build(db, definition)).order_by(EnrichCompany.mst).limit(MAX_ROWS + 1)).all()
    if len(rows) > MAX_ROWS:
        raise HTTPException(422, f"Bộ lọc trả về hơn {MAX_ROWS:,} doanh nghiệp — thu hẹp bộ lọc.".replace(",", "."))
    allowed = _allowed_purposes(db, [c.mst for c in rows])
    ok_rows = [c for c in rows if purpose in allowed.get(c.mst, set())]
    blocked = len(rows) - len(ok_rows)
    msts = [c.mst for c in ok_rows]
    blocked_people, blocked_values = khob._optouts(db)  # noqa: SLF001
    optout_count = 0

    company_contacts: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    if {"email_dn", "dien_thoai_dn"} & set(columns) and msts:
        for i in range(0, len(msts), 1000):
            for ct in db.scalars(select(EnrichContact).where(EnrichContact.owner_type == "company", EnrichContact.owner_id.in_(msts[i : i + 1000]))):
                if ct.value.strip().lower() in blocked_values:
                    optout_count += 1
                    continue
                company_contacts[ct.owner_id][ct.kind].append(ct.value)

    people: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    person_emails: dict[int, list[str]] = defaultdict(list)
    used_people: set[int] = set()
    if wants_b and msts:
        for i in range(0, len(msts), 1000):
            for role, p in db.execute(
                select(PersonRole, EnrichPerson)
                .join(EnrichPerson, EnrichPerson.id == PersonRole.person_id)
                .where(
                    PersonRole.company_mst.in_(msts[i : i + 1000]),
                    PersonRole.la_nguoi_quyet_dinh.is_(True),
                    PersonRole.den_ngay.is_(None),
                    EnrichPerson.merged_into_id.is_(None),
                )
            ):
                if p.id in blocked_people:
                    optout_count += 1
                    continue
                people[role.company_mst].append((p.id, p.ho_ten, role.chuc_danh))
                used_people.add(p.id)
        if "email_nguoi" in columns and used_people:
            ids = [str(i) for i in used_people]
            for i in range(0, len(ids), 1000):
                for ct in db.scalars(select(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id.in_(ids[i : i + 1000]), EnrichContact.kind == "email")):
                    if ct.value.strip().lower() in blocked_values:
                        optout_count += 1
                        continue
                    if ct.is_inferred and not include_inferred:
                        continue  # B11
                    person_emails[int(ct.owner_id)].append(ct.value + (" (suy luận)" if ct.is_inferred else ""))

    expires = (utcnow() + timedelta(days=int(get_settings().enrich_export_valid_days))).date()
    rec = ExportRecord(
        user_id=user.id,
        purpose=purpose,
        filter=definition or {},
        columns=columns,
        row_count=len(ok_rows),
        blocked_count=blocked,
        optout_count=optout_count,
        include_inferred=include_inferred,
        includes_kho_b=wants_b,
        status="ok" if ok_rows or not rows else "blocked",
        expires_on=expires,
    )
    db.add(rec)
    db.flush()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        f"Mã xuất #{rec.id} · Mục đích: {PURPOSES[purpose]} · Hạn sử dụng đến {expires:%d/%m/%Y} · "
        f"Chỉ dùng cho mục đích đã khai, không chia sẻ ra ngoài · Người xuất: {user.full_name}"
    ])
    w.writerow([allowed_cols[c] for c in columns])
    for c in ok_rows:
        out = []
        for col in columns:
            if col == "email_dn":
                out.append("; ".join(company_contacts[c.mst]["email"]))
            elif col == "dien_thoai_dn":
                out.append("; ".join(company_contacts[c.mst]["phone"]))
            elif col == "nguoi_quyet_dinh":
                out.append("; ".join(f"{n} — {t}" for _, n, t in people.get(c.mst, [])))
            elif col == "email_nguoi":
                out.append("; ".join(e for pid, _, _ in people.get(c.mst, []) for e in person_emails.get(pid, [])))
            else:
                v = getattr(c, col)
                out.append("" if v is None else (", ".join(v) if isinstance(v, list) else encode(col, v) if col in ("ngay_thanh_lap", "niem_yet") else str(v)))
        w.writerow(out)
    data = ("﻿" + buf.getvalue()).encode("utf-8")
    rec.file_sha256 = hashlib.sha256(data).hexdigest()
    if used_people:
        db.execute(update(EnrichPerson).where(EnrichPerson.id.in_(used_people)).values(last_used_at=utcnow()))  # T07
    db.commit()
    if wants_b:
        khob.log_access(db, user, request, "export", f"export:{rec.id}?purpose={purpose}", len(ok_rows))
    if rec.status == "blocked":
        raise HTTPException(403, f"Không doanh nghiệp nào trong bộ lọc được phép dùng cho mục đích “{PURPOSES[purpose]}” — lần xuất bị chặn và đã ghi nhật ký (mã #{rec.id}).")
    return data, rec


def market_report(db: Session) -> dict:
    """C11: phân bổ theo tỉnh, ngành, quy mô vốn, tình trạng và độ phủ dữ liệu — không có dữ liệu cá nhân."""
    companies = db.execute(
        select(EnrichCompany.tinh, EnrichCompany.nganh_nghe, EnrichCompany.von, EnrichCompany.trang_thai, *[getattr(EnrichCompany, f) for f in REQUIRED_FIELDS])
    ).all()
    total = len(companies)
    by_tinh, by_nganh, by_von, by_tt = Counter(), Counter(), Counter(), Counter()
    coverage = Counter()
    for row in companies:
        tinh, nganh, von, tt = row[0], row[1], row[2], row[3]
        by_tinh[tinh or "Chưa rõ"] += 1
        by_nganh[(nganh or ["Chưa rõ"])[0]] += 1
        by_tt[tt or "Chưa rõ"] += 1
        if von is None:
            by_von["Chưa rõ"] += 1
        elif von < 10_000_000_000:
            by_von["Dưới 10 tỷ"] += 1
        elif von < 100_000_000_000:
            by_von["10 – 100 tỷ"] += 1
        elif von < 1_000_000_000_000:
            by_von["100 – 1.000 tỷ"] += 1
        else:
            by_von["Trên 1.000 tỷ"] += 1
        for f, v in zip(REQUIRED_FIELDS, row[4:]):
            if v not in (None, "", []):
                coverage[f] += 1
    top = lambda c, n=30: [{"key": k, "count": v} for k, v in c.most_common(n)]  # noqa: E731
    return {
        "total": total,
        "by_tinh": top(by_tinh, 40),
        "by_nganh": top(by_nganh),
        "by_von": [{"key": k, "count": by_von[k]} for k in ("Dưới 10 tỷ", "10 – 100 tỷ", "100 – 1.000 tỷ", "Trên 1.000 tỷ", "Chưa rõ") if by_von[k]],
        "by_trang_thai": top(by_tt),
        "coverage": {f: coverage[f] for f in REQUIRED_FIELDS},
        "decision_maker": khob.decision_maker_company_count(db),
    }
