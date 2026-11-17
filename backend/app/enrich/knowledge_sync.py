"""Chuyển MỘT LẦN dữ liệu từ "Kho doanh nghiệp" cũ (bảng knowledge_companies) sang phân hệ làm giàu theo MST.

Kho doanh nghiệp đã bỏ: phân hệ làm giàu là nơi duy nhất chứa doanh nghiệp, crawler PROFIT500 ghi thẳng vào đây
(app/services/profit500.py). Bảng cũ còn giữ trong CSDL tới khi kiểm tra xong trên máy chủ; một migration sau sẽ xoá
bảng, model KnowledgeCompany và module này.

  • Doanh nghiệp quét từ PROFIT500 → nguồn "profit500" (0,7), bằng chứng trỏ về trang hồ sơ profit500.vn.
  • Doanh nghiệp admin nhập tay vào kho → nguồn "nhập lô" (0,5), bằng chứng trỏ về bản ghi kho cũ.
  • Trường chuyển sang như crawler (profit500.enrich_row): tên, tên tiếng Anh, địa chỉ, tỉnh, điện thoại, fax, email,
    website, ngành → nhóm ngành, năm thành lập, giới thiệu, mã CK + niêm yết, xếp hạng (tín hiệu). Không lấy tên CEO, logo.
  • Doanh nghiệp không có MST / MST sai không vào được phân hệ → liệt kê để xuất CSV giữ lại (missing_csv).
Chạy lại an toàn: nội dung không đổi thì không sinh bằng chứng mới.

Chạy:  python -m app.cli enrich-from-knowledge --purposes ban_hang_b2b --missing-csv thieu-mst.csv [--dry-run]
"""

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.enrich import sources
from app.enrich.importer import ImportError_, Row, existing_msts, save_batch
from app.models import KNOWLEDGE_SOURCES, AdminUser, KnowledgeCompany
from app.services import profit500

ENRICH_SOURCE = {"profit500": sources.PROFIT500, "manual": sources.IMPORT}
MISSING_COLUMNS = ["id", "source", "name", "tax_code", "industry", "address", "phone", "email", "website", "stock_code", "source_url", "ly_do"]


@dataclass
class Plan:
    by_source: dict[str, list[Row]] = field(default_factory=dict)
    missing: list[dict] = field(default_factory=list)  # không vào được phân hệ — xuất CSV
    duplicate: int = 0
    total: int = 0

    @property
    def valid(self) -> int:
        return sum(len(r) for r in self.by_source.values())


def table_exists(db: Session) -> bool:
    return inspect(db.get_bind()).has_table(KnowledgeCompany.__tablename__)


def _data(k: KnowledgeCompany) -> dict:
    return {
        "name": k.name, "name_en": k.name_en, "tax_code": k.tax_code, "stock_code": k.stock_code, "industry": k.industry,
        "address": k.address, "province": k.province, "phone": k.phone, "fax": k.fax, "email": k.email, "website": k.website,
        "founded_year": k.founded_year, "description": k.description, "rank": k.rank, "rank_label": k.rank_label,
        "rank_list": k.rank_list, "rank_year": k.rank_year, "source_url": k.source_url,
    }  # fmt: skip


def plan(db: Session, kinds: list[str]) -> Plan:
    bad = [k for k in kinds if k not in ENRICH_SOURCE]
    if bad or not kinds:
        raise ImportError_("Nguồn trong kho cũ: " + ", ".join(f"{k} ({v})" for k, v in KNOWLEDGE_SOURCES.items()))
    if not table_exists(db):
        raise ImportError_("Không còn bảng kho doanh nghiệp cũ (knowledge_companies) — không có gì để chuyển.")
    out = Plan()
    seen: set[str] = set()
    for k in db.scalars(select(KnowledgeCompany).where(KnowledgeCompany.source.in_(kinds)).order_by(KnowledgeCompany.id)):
        out.total += 1
        row = profit500.enrich_row(_data(k), row_no=k.id)
        if row is None:
            out.missing.append({c: getattr(k, c, "") for c in MISSING_COLUMNS[:-1]} | {"ly_do": "Chưa có MST" if not k.tax_code else "MST sai định dạng"})
            continue
        if row.mst in seen:
            out.duplicate += 1
            continue
        seen.add(row.mst)
        if k.source != "profit500":  # nhập tay vào kho: không phải dữ liệu PROFIT500
            row.excerpt = f"Kho doanh nghiệp cũ #{k.id} (nhập tay): {row.name}"
            row.url = f"kho-doanh-nghiep#{k.id}"
        out.by_source.setdefault(k.source, []).append(row)
    return out


def missing_csv(p: Plan) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=MISSING_COLUMNS)
    w.writeheader()
    for m in p.missing:
        w.writerow({c: "" if m.get(c) is None else m.get(c) for c in MISSING_COLUMNS})
    return "﻿" + buf.getvalue()


def preview(db: Session, kinds: list[str]) -> dict:
    p = plan(db, kinds)
    msts = [r.mst for rs in p.by_source.values() for r in rs]
    existing = len(existing_msts(db, msts))
    return {"total": p.total, "valid": p.valid, "new": p.valid - existing, "existing": existing, "missing": len(p.missing), "duplicate": p.duplicate}


def sync(db: Session, user: AdminUser | None, *, kinds: list[str], purposes: list[str], name: str = "Chuyển từ Kho doanh nghiệp") -> tuple[list, Plan]:
    """Ghi mỗi nguồn của kho cũ thành một lô. Trả về (các lô, kế hoạch — có danh sách thiếu MST)."""
    p = plan(db, kinds)
    batches = []
    for kind, rows in p.by_source.items():
        label = KNOWLEDGE_SOURCES.get(kind, kind)
        rep = profit500.report_for(rows, no_mst=sum(1 for m in p.missing if m["source"] == kind))
        if kind == "profit500":
            batches.append(
                profit500.save_rows(
                    db, user, rows, rep, name=f"{name} — {label}", list_source="Kho doanh nghiệp cũ — PROFIT500 (Vietnam Report)",
                    purposes=purposes, file_name="kho-doanh-nghiep:profit500",
                )
            )
        else:
            batches.append(
                save_batch(
                    db, user, rows, rep, name=f"{name} — {label}", list_source=f"Kho doanh nghiệp cũ — {label}", purposes=purposes,
                    note="", file_name=f"kho-doanh-nghiep:{kind}",
                    file_sha256=hashlib.sha256(json.dumps(sorted(r.content_hash for r in rows)).encode()).hexdigest(),
                    source_code=ENRICH_SOURCE[kind], method="nhap_lo",
                )
            )
    return batches, p
