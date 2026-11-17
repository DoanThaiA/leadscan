"""Hợp nhất theo độ tin cậy nguồn (B04): chọn giá trị hiển thị từ bằng chứng, không xoá bằng chứng nào.

Thứ tự chọn cho mỗi trường:
  1. Quyết định của biên tập viên (method "thu_cong") mới nhất — không bị vòng chạy sau đè (B09).
  2. Nguồn có độ tin cậy cao hơn; bằng nhau thì bằng chứng mới hơn.
Các giá trị khác nhau giữa các bằng chứng → đánh dấu xung đột.
Giá trị hiển thị đổi (và trước đó đã có giá trị) → ghi CompanyChange (C07).
"""

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enrich.normalize import bo_dau, company_type
from app.enrich.sources import all_sources
from app.models_enrich import COMPANY_FIELDS, CompanyChange, CompanyEvidence, EnrichCompany

LIST_FIELDS = {"nganh_nghe", "nhom_san_pham", "ma_hs"}
DATE_FIELDS = {"ngay_thanh_lap"}
INT_FIELDS = {"von", "nam_thanh_lap"}
BOOL_FIELDS = {"niem_yet"}
CHUNK = 500


def encode(field: str, v) -> str:
    """Giá trị → chữ để lưu trong evidence.value."""
    if field in LIST_FIELDS:
        return json.dumps(list(v), ensure_ascii=False)
    if field in DATE_FIELDS and isinstance(v, date):
        return v.isoformat()
    if field in BOOL_FIELDS:
        return "true" if v else "false"
    return str(v)


def decode(field: str, s: str | None):
    if s is None:
        return None
    try:
        if field in LIST_FIELDS:
            return list(json.loads(s))
        if field in DATE_FIELDS:
            return date.fromisoformat(s)
        if field in INT_FIELDS:
            return int(s)
        if field in BOOL_FIELDS:
            return s.lower() in ("true", "1", "co", "có")
    except (ValueError, TypeError):
        return None
    return s


@dataclass
class FieldView:
    chosen: CompanyEvidence
    count: int  # số bằng chứng cho trường này
    agree: int  # số NGUỒN khác nhau đồng thuận với giá trị được chọn
    conflict: bool


def same_key(value: str) -> str:
    """Khoá so sánh đồng thuận: bỏ dấu, chữ thường, bỏ ký tự phân cách — 'CÔNG TY CP ĐẠI VIỆT' ≡ 'Công ty CP Đại Việt'."""
    return re.sub(r"[^a-z0-9]", "", bo_dau(value))


def choose(evs: Sequence[CompanyEvidence], trust: dict[str, float]) -> FieldView | None:
    if not evs:
        return None
    manual = [e for e in evs if e.method == "thu_cong"]
    if manual:
        chosen = max(manual, key=lambda e: (e.fetched_at, e.id))
    else:
        chosen = max(evs, key=lambda e: (trust.get(e.source_code, 0.0), e.fetched_at, e.id))
    key = same_key(chosen.value)
    agreeing = {e.source_code for e in evs if same_key(e.value) == key}
    return FieldView(chosen=chosen, count=len(evs), agree=len(agreeing), conflict=len({same_key(e.value) for e in evs}) > 1)


STALE_FACTOR = 0.7  # bằng chứng quá hạn tái thu thập: điểm nhân hệ số này
AGREE_BONUS = 0.05  # mỗi nguồn đồng thuận thêm


def field_score(view: FieldView, trust: dict[str, float], recrawl_days: int, now: datetime) -> tuple[int, bool]:
    """B08: điểm tin cậy 0–100 của một trường = độ tin cậy nguồn được chọn + thưởng đồng thuận, nhân hệ số độ mới.

    B13: quá `recrawl_days` kể từ lần thu thập gần nhất của giá trị đang dùng → cũ (stale).
    Quyết định của biên tập viên luôn 100 điểm và không bị coi là cũ.
    """
    e = view.chosen
    if e.method == "thu_cong":
        return 100, False
    base = trust.get(e.source_code, 0.0) + AGREE_BONUS * max(0, view.agree - 1)
    stale = recrawl_days > 0 and (now - e.fetched_at) > timedelta(days=recrawl_days)
    if stale:
        base *= STALE_FACTOR
    return round(min(1.0, base) * 100), stale


def views_for(evs: Iterable[CompanyEvidence], trust: dict[str, float]) -> dict[str, FieldView]:
    by_field: dict[str, list[CompanyEvidence]] = defaultdict(list)
    for e in evs:
        by_field[e.field].append(e)
    out = {}
    for field, items in by_field.items():
        v = choose(items, trust)
        if v:
            out[field] = v
    return out


def recompute_companies(db: Session, msts: Iterable[str]) -> int:
    """Tính lại giá trị hiển thị cho các MST. Trả về số thay đổi đã ghi nhật ký."""
    trust = {code: s.trust for code, s in all_sources(db).items()}
    msts = list(dict.fromkeys(msts))
    changes = 0
    for i in range(0, len(msts), CHUNK):
        part = msts[i : i + CHUNK]
        evs: dict[str, list[CompanyEvidence]] = defaultdict(list)
        for e in db.scalars(select(CompanyEvidence).where(CompanyEvidence.mst.in_(part))):
            evs[e.mst].append(e)
        for c in db.scalars(select(EnrichCompany).where(EnrichCompany.mst.in_(part))):
            views = views_for(evs.get(c.mst, []), trust)
            for field in COMPANY_FIELDS:
                if field == "mst":
                    continue
                view = views.get(field)
                new = decode(field, view.chosen.value) if view else None
                old = getattr(c, field)
                if old == new:
                    continue
                if old is not None:
                    db.add(
                        CompanyChange(
                            mst=c.mst,
                            field=field,
                            old_value=encode(field, old),
                            new_value=None if new is None else encode(field, new),
                            source_code=view.chosen.source_code if view else "",
                        )
                    )
                    changes += 1
                setattr(c, field, new)
            c.ten_khong_dau = bo_dau(c.ten)
            c.loai_hinh = company_type(c.ten)
        db.flush()
    return changes
