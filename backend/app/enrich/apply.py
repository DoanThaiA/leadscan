"""Ghi kết quả bóc tách (Facts) vào kho: chuẩn hoá (B02), khử trùng (B12), bằng chứng, người (kho B), tín hiệu.

Mọi nguồn — connector tự động, hàng đợi thủ công, file chính thức — đều đi qua đây, nên quy tắc chỉ nằm một chỗ.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.enrich import merge, people
from app.enrich.connectors.base import CompanyFact, Facts
from app.enrich.normalize import (
    bo_dau,
    clean_text,
    normalize_status,
    normalize_website,
    parse_date,
    parse_money,
    province_of,
)
from app.enrich.titles import TITLES, normalize_title
from app.models_enrich import (
    COMPANY_FIELDS,
    SIGNAL_KINDS,
    AccessLog,
    CompanyEvidence,
    EnrichContact,
    EnrichPerson,
    EnrichSignal,
    EnrichSource,
    OptOut,
    PersonChange,
    PersonEvidence,
    PersonRole,
)


@dataclass
class Origin:
    """Một lần nguồn "nói": ở đâu, lúc nào, cách nào."""

    source: EnrichSource
    source_url: str
    content_hash: str
    method: str  # khoá METHODS
    fetched_at: datetime = field(default_factory=utcnow)
    source_page_id: int | None = None
    batch_id: int | None = None
    actor_id: int | None = None  # người thao tác (nhập file / hàng đợi thủ công) — ghi nhật ký kho B


@dataclass
class Applied:
    evidence: int = 0
    duplicates: int = 0
    people: int = 0
    signals: int = 0

    def add(self, o: "Applied") -> None:
        self.evidence += o.evidence
        self.duplicates += o.duplicates
        self.people += o.people
        self.signals += o.signals


def normalize_fact(f: CompanyFact) -> list[CompanyFact]:
    """Một fact thô → các fact đã chuẩn hoá (địa chỉ sinh thêm tỉnh/thành, website sinh thêm tên miền)."""
    v = f.value
    if v is None or v == "" or f.field not in COMPANY_FIELDS or f.field == "mst":
        return []
    out: list[CompanyFact] = []
    if f.field == "ten":
        v = clean_text(v, 400)
    elif f.field == "dia_chi":
        v = clean_text(v, 600)
        p = province_of(v)
        if p:
            out.append(CompanyFact("tinh", p, f"Tách từ địa chỉ: {v}", f.is_inferred))
    elif f.field == "tinh":
        v = province_of(str(v)) or clean_text(v, 80)
    elif f.field == "trang_thai":
        v = normalize_status(str(v))
    elif f.field == "nganh_nghe":
        items = v if isinstance(v, list) else [x for x in str(v).replace("\n", ";").split(";")]
        v = [" ".join(str(x).split()) for x in items if str(x).strip()][:20] or None
    elif f.field == "nhom_nganh":
        v = clean_text(v, 200)
    elif f.field == "ten_tieng_anh":
        v = clean_text(v, 300)
    elif f.field == "mo_ta":
        lines = [" ".join(ln.split()) for ln in str(v).splitlines()]
        v = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()[:5000] or None
    elif f.field == "nam_thanh_lap":
        m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", str(int(v) if isinstance(v, float) and v.is_integer() else v))
        v = int(m.group(1)) if m else None
    elif f.field == "nhom_san_pham":
        items = v if isinstance(v, list) else str(v).replace("\n", ";").split(";")
        v = list(dict.fromkeys(" ".join(str(x).split()) for x in items if str(x).strip()))[:20] or None
    elif f.field == "ma_hs":
        items = v if isinstance(v, list) else re.split(r"[,;/\s]+", str(v))
        codes = [re.sub(r"\D", "", str(x)) for x in items]
        v = list(dict.fromkeys(c for c in codes if 2 <= len(c) <= 10))[:50] or None
    elif f.field == "ngay_thanh_lap":
        v = parse_date(v)
    elif f.field == "von":
        v = parse_money(v)
    elif f.field == "website":
        site, dom = normalize_website(str(v))
        v = site
        if dom:
            out.append(CompanyFact("domain", dom, f"Tách từ website: {site}", f.is_inferred))
    elif f.field == "domain":
        v = normalize_website(str(v))[1]
    elif f.field == "ma_ck":
        v = clean_text(v, 20).upper()
    elif f.field == "niem_yet":
        v = bool(v)
    else:
        v = clean_text(v)
    if v is None or v == "" or v == []:
        return out
    return [CompanyFact(f.field, v, f.excerpt, f.is_inferred), *out]


def _excerpt(f: CompanyFact) -> str:
    return (f.excerpt or "")[:2000]


def _blocked_values(db: Session) -> set[str]:
    """C10: email / điện thoại trong danh sách từ chối — không ghi lại."""
    return {v.strip().lower() for (v,) in db.execute(select(OptOut.value).where(OptOut.kind.in_(("email", "phone"))))}


def add_contact(
    db: Session, owner_type: str, owner_id: str, kind: str, value: str, source_code: str, *, inferred: bool, verify_status: str = "unverified"
) -> EnrichContact | None:
    """Thêm liên hệ nếu chưa có (cùng chủ + cùng giá trị). Trả về bản ghi mới, hoặc None nếu đã có."""
    if db.scalar(
        select(EnrichContact.id).where(EnrichContact.owner_type == owner_type, EnrichContact.owner_id == owner_id, EnrichContact.value == value)
    ):
        return None
    c = EnrichContact(
        owner_type=owner_type, owner_id=owner_id, kind=kind, value=value[:200], is_inferred=inferred,
        verify_status=verify_status, source_code=source_code, last_checked_at=utcnow() if inferred else None,
    )
    db.add(c)
    db.flush()
    return c


def signal_key(kind: str, payload: dict, source_code: str) -> str:
    raw = json.dumps({"k": kind, "p": payload, "s": source_code}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def apply_facts(db: Session, mst: str, facts: Facts, origin: Origin, *, recompute: bool = True) -> Applied:
    res = Applied()
    src = origin.source

    # ---- kho A: bằng chứng doanh nghiệp
    seen = {
        (f, v, h)
        for f, v, h in db.execute(
            select(CompanyEvidence.field, CompanyEvidence.value, CompanyEvidence.content_hash).where(
                CompanyEvidence.mst == mst, CompanyEvidence.source_code == src.code
            )
        )
    }
    company_facts = list(facts.company)
    if company_facts:
        # nguồn trả về thông tin cho MST này = nguồn xác nhận MST tồn tại → thêm bằng chứng cho trường mst
        company_facts.insert(0, CompanyFact("mst", mst, company_facts[0].excerpt))
    for raw in company_facts:
        if raw.field == "mst":
            normalized = [CompanyFact("mst", mst, raw.excerpt)]
        else:
            normalized = normalize_fact(raw)
        for f in normalized:
            value = merge.encode(f.field, f.value)
            key = (f.field, value, origin.content_hash)
            if key in seen:
                res.duplicates += 1
                continue
            seen.add(key)
            db.add(
                CompanyEvidence(
                    mst=mst,
                    field=f.field,
                    value=value,
                    source_code=src.code,
                    source_url=origin.source_url[:1000],
                    excerpt=_excerpt(f),
                    method=origin.method,
                    is_inferred=f.is_inferred,
                    content_hash=origin.content_hash,
                    batch_id=origin.batch_id,
                    source_page_id=origin.source_page_id,
                    fetched_at=origin.fetched_at,
                )
            )
            res.evidence += 1

    # ---- kho A: tín hiệu
    for s in facts.signals:
        if s.kind not in SIGNAL_KINDS:
            continue
        key = signal_key(s.kind, s.payload, src.code)
        if db.scalar(select(EnrichSignal.id).where(EnrichSignal.mst == mst, EnrichSignal.dedupe_key == key)):
            res.duplicates += 1
            continue
        db.add(
            EnrichSignal(
                mst=mst,
                kind=s.kind,
                payload=s.payload,
                day=s.day,
                source_code=src.code,
                source_url=origin.source_url[:1000],
                dedupe_key=key,
                source_page_id=origin.source_page_id,
            )
        )
        res.signals += 1

    # ---- kho B: người (chỉ họ tên + chức danh; không có trường nhạy cảm nào để ghi — T09)
    if facts.people:
        blocked = {int(v) for (v,) in db.execute(select(OptOut.value).where(OptOut.kind == "person")) if v.isdigit()}
        blocked_values = _blocked_values(db)
        from app.enrich import compliance  # trễ: tránh vòng import

        erased = compliance.hashed_block(db)  # T05: người đã xoá theo yêu cầu — không thu thập lại
        # đã có người từ nguồn này trước lần ghi này → người mới xuất hiện là "bổ nhiệm" (C06), không phải lần nạp đầu
        had_people = db.scalar(
            select(PersonRole.id).where(PersonRole.company_mst == mst, PersonRole.source_code == src.code).limit(1)
        ) is not None
        for p in facts.people:
            name = clean_text(p.ho_ten, 200)
            if not name:
                continue
            code, decision = normalize_title(p.chuc_danh)
            if erased and (
                compliance.name_company_key(name, mst) in erased or (p.mst_ca_nhan and compliance.mst_key(p.mst_ca_nhan) in erased)
            ):
                continue
            # B06: MST cá nhân → cùng DN + cùng tên → hồ sơ mới (kèm cặp nghi trùng nếu nơi khác có người cùng tên)
            resolved = people.resolve(db, mst, name, p.mst_ca_nhan)
            person = resolved.person
            if person.id in blocked:
                continue
            role = db.scalar(
                select(PersonRole).where(
                    PersonRole.person_id == person.id,
                    PersonRole.company_mst == mst,
                    PersonRole.chuc_danh_chuan == code,
                    PersonRole.den_ngay.is_(None),
                )
            )
            if resolved.created:
                res.people += 1
            if role:
                role.trust = max(role.trust, src.trust)
                if p.tu_ngay and not role.tu_ngay:
                    role.tu_ngay = p.tu_ngay
                if p.den_ngay and not role.den_ngay:
                    role.den_ngay = p.den_ngay  # miễn nhiệm / từ nhiệm
                    db.add(PersonChange(person_id=person.id, field=f"vai_tro:{mst}:{code}", old_value="đang giữ", new_value=f"kết thúc {p.den_ngay.isoformat()}", source_code=src.code))
            else:
                db.add(
                    PersonRole(
                        person_id=person.id,
                        company_mst=mst,
                        chuc_danh=clean_text(p.chuc_danh, 200) or TITLES[code][0],
                        chuc_danh_chuan=code,
                        la_nguoi_quyet_dinh=decision,
                        tu_ngay=p.tu_ngay,
                        den_ngay=p.den_ngay,
                        source_code=src.code,
                        trust=src.trust,
                    )
                )
                if had_people and decision and not p.den_ngay:
                    payload = {"chuc_danh": clean_text(p.chuc_danh, 200) or TITLES[code][0], "person_id": person.id}
                    key = signal_key("bo_nhiem", payload, src.code)
                    db.add(EnrichSignal(mst=mst, kind="bo_nhiem", payload=payload, day=p.tu_ngay, source_code=src.code, source_url=origin.source_url[:1000], dedupe_key=key, source_page_id=origin.source_page_id))
                    res.signals += 1
            if resolved.created:
                db.flush()
                people.suggest_duplicates(db, person)  # B06: cùng tên ở nơi khác → chờ duyệt, không tự gộp
            person_fields = [("ho_ten", name), ("chuc_danh", clean_text(p.chuc_danh, 200) or TITLES[code][0])]
            if p.mst_ca_nhan:
                person_fields.append(("mst_ca_nhan", p.mst_ca_nhan))
            if p.email:
                email = p.email.strip().lower()
                if email not in blocked_values:
                    add_contact(db, "person", str(person.id), "email", email, src.code, inferred=False)
                    person_fields.append(("email", email))
            for fld, val in person_fields:
                exists = db.scalar(
                    select(PersonEvidence.id).where(
                        PersonEvidence.person_id == person.id,
                        PersonEvidence.field == fld,
                        PersonEvidence.value == val,
                        PersonEvidence.source_code == src.code,
                        PersonEvidence.content_hash == origin.content_hash,
                    )
                )
                if exists:
                    continue
                db.add(
                    PersonEvidence(
                        person_id=person.id,
                        field=fld,
                        value=val,
                        source_code=src.code,
                        source_url=origin.source_url[:1000],
                        excerpt=(p.excerpt or "")[:2000],
                        method=origin.method,
                        content_hash=origin.content_hash,
                        source_page_id=origin.source_page_id,
                        fetched_at=origin.fetched_at,
                    )
                )
        # N06: ghi vào kho B cũng phải có nhật ký
        db.add(AccessLog(user_id=origin.actor_id, action="write", target=f"company:{mst}/people<-{src.code}", row_count=len(facts.people)))

    # ---- liên hệ chung của doanh nghiệp (email info@, tổng đài) — bảng liên hệ nằm ở kho B
    if facts.contacts:
        blocked_values = blocked_values if facts.people else _blocked_values(db)
        for kind, value in facts.contacts:
            v = value.strip().lower() if kind == "email" else value.strip()
            if v and v not in blocked_values:
                add_contact(db, "company", mst, kind, v, src.code, inferred=False)

    db.flush()
    if recompute:
        merge.recompute_companies(db, [mst])
    return res


def today() -> date:
    return utcnow().date()
