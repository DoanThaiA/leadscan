"""Suy luận email công việc theo mẫu tên miền (B10, B11).

Quy tắc (tài liệu yêu cầu):
  • Chỉ suy luận cho một tên miền khi đã có ÍT NHẤT MỘT email THẬT (không suy luận) của một người cùng tên miền,
    và email thật đó khớp một mẫu đặt tên → học mẫu từ đó.
  • Xác minh MX của tên miền TRƯỚC khi lưu; không có MX (hoặc không tra được) → không lưu.
  • Email suy luận luôn có cờ is_inferred + trạng thái xác minh ("mx_ok"); không xuất nếu người dùng không chọn (B11).
  • Không suy luận cho người / email trong danh sách từ chối (C10).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.enrich.normalize import bo_dau
from app.models_enrich import AccessLog, EnrichCompany, EnrichContact, EnrichPerson, OptOut, PersonEvidence, PersonRole

log = logging.getLogger("leadscan.enrich.emails")

SOURCE = "suy_luan_email"


def name_parts(ho_ten: str) -> tuple[str, list[str], str] | None:
    """'Nguyễn Văn An' → ('nguyen', ['van'], 'an'): họ, tên đệm, tên."""
    toks = [t for t in re.sub(r"[^a-z ]", "", bo_dau(ho_ten)).split() if t]
    if len(toks) < 2:
        return None
    return toks[0], toks[1:-1], toks[-1]


# mẫu → hàm sinh phần trước @ (họ f, đệm m[], tên g)
PATTERNS = {
    "ten.ho": lambda f, m, g: f"{g}.{f}",                         # an.nguyen
    "ho.ten": lambda f, m, g: f"{f}.{g}",                         # nguyen.an
    "tenho": lambda f, m, g: f"{g}{f}",                           # annguyen
    "ten+chu_dau_ho_dem": lambda f, m, g: g + f[0] + "".join(x[0] for x in m),   # annv
    "ten.chu_dau_ho_dem": lambda f, m, g: g + "." + f[0] + "".join(x[0] for x in m),  # an.nv
    "chu_dau_ho_dem+ten": lambda f, m, g: f[0] + "".join(x[0] for x in m) + g,   # nvan
    "hodemten": lambda f, m, g: f + "".join(m) + g,               # nguyenvanan
    "ten": lambda f, m, g: g,                                     # an
    "chu_dau_ten+ho": lambda f, m, g: g[0] + f,                   # anguyen
}


def candidates(ho_ten: str) -> dict[str, str]:
    p = name_parts(ho_ten)
    if not p:
        return {}
    f, m, g = p
    return {k: fn(f, m, g) for k, fn in PATTERNS.items()}


def pattern_of(email: str, ho_ten: str) -> str | None:
    local = email.split("@")[0].lower()
    for k, v in candidates(ho_ten).items():
        if v == local:
            return k
    return None


def email_matches_name(email: str, ho_ten: str) -> bool:
    """Email đứng cạnh tên trên website có phải của người đó? (khớp một mẫu, hoặc một phần trùng tên / họ)."""
    if pattern_of(email, ho_ten):
        return True
    p = name_parts(ho_ten)
    if not p:
        return False
    parts = [x for x in re.split(r"[._\-0-9]+", email.split("@")[0].lower()) if x]
    return any(x in (p[0], p[2]) for x in parts if len(x) >= 2)


@lru_cache(maxsize=4096)
def _mx_cached(domain: str) -> bool | None:
    import dns.exception
    import dns.resolver

    try:
        ans = dns.resolver.resolve(domain, "MX", lifetime=5.0)
        return any(str(r.exchange).strip(".") for r in ans)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return False
    except dns.exception.DNSException:
        return None  # không tra được (mạng / timeout) → chưa biết


def has_mx(domain: str) -> bool | None:
    """True: tên miền nhận thư · False: không có MX · None: không tra được. Tách hàm để test thay thế."""
    return _mx_cached(domain.lower())


def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def learn_pattern(db: Session, domain: str) -> tuple[str | None, int]:
    """Mẫu phổ biến nhất trong các email THẬT của người ở tên miền này. (mẫu, số email thật khớp)."""
    rows = db.execute(
        select(EnrichContact.value, EnrichPerson.ho_ten)
        .join(EnrichPerson, EnrichContact.owner_id == EnrichPerson.id.cast(EnrichContact.owner_id.type))
        .where(
            EnrichContact.owner_type == "person",
            EnrichContact.kind == "email",
            EnrichContact.is_inferred.is_(False),
            EnrichContact.value.like(f"%@{domain}"),
            EnrichPerson.merged_into_id.is_(None),
        )
    ).all()
    counts = Counter(p for p in (pattern_of(e, n) for e, n in rows) if p)
    if not counts:
        return None, 0
    pat, n = counts.most_common(1)[0]
    return pat, n


def infer_company(db: Session, mst: str, actor_id: int | None = None) -> dict:
    """Suy luận email cho người ra quyết định đang tại vị của một doanh nghiệp. Trả về biên bản."""
    c = db.get(EnrichCompany, mst)
    out = {"mst": mst, "domain": None, "pattern": None, "created": 0, "skipped": None}
    if not c or not c.domain:
        out["skipped"] = "Chưa có tên miền"
        return out
    domain = c.domain.lower()
    out["domain"] = domain
    pat, n = learn_pattern(db, domain)
    if not pat:
        out["skipped"] = "Chưa có email thật nào của người ở tên miền này khớp mẫu đặt tên"
        return out
    out["pattern"] = pat
    mx = has_mx(domain)
    if mx is not True:
        out["skipped"] = "Tên miền không có bản ghi MX" if mx is False else "Không tra được MX — thử lại sau"
        return out
    from app.enrich import sources  # trễ: tránh vòng import (sources → registry → website → emails)

    src = sources.ensure(db, SOURCE)
    blocked_people = {int(v) for (v,) in db.execute(select(OptOut.value).where(OptOut.kind == "person")) if v.isdigit()}
    blocked_values = {v.strip().lower() for (v,) in db.execute(select(OptOut.value).where(OptOut.kind == "email"))}
    persons = db.scalars(
        select(EnrichPerson)
        .join(PersonRole, PersonRole.person_id == EnrichPerson.id)
        .where(
            PersonRole.company_mst == mst,
            PersonRole.la_nguoi_quyet_dinh.is_(True),
            PersonRole.den_ngay.is_(None),
            EnrichPerson.merged_into_id.is_(None),
        )
        .distinct()
    ).all()
    now = utcnow()
    for p in persons:
        if p.id in blocked_people:
            continue
        has_email = db.scalar(
            select(EnrichContact.id).where(
                EnrichContact.owner_type == "person", EnrichContact.owner_id == str(p.id), EnrichContact.value.like(f"%@{domain}")
            )
        )
        if has_email:
            continue
        local = candidates(p.ho_ten).get(pat)
        if not local:
            continue
        email = f"{local}@{domain}"
        if email in blocked_values:
            continue
        db.add(
            EnrichContact(
                owner_type="person", owner_id=str(p.id), kind="email", value=email, is_inferred=True,
                verify_status="mx_ok", source_code=src.code, last_checked_at=now,
            )
        )
        db.add(
            PersonEvidence(
                person_id=p.id, field="email", value=email, source_code=src.code, source_url=f"mx:{domain}",
                excerpt=f"Suy luận theo mẫu “{pat}” học từ {n} email thật cùng tên miền; tên miền có bản ghi MX ({now:%d/%m/%Y}).",
                method="suy_luan", is_inferred=True, content_hash=f"{pat}:{domain}", fetched_at=now,
            )
        )
        out["created"] += 1
    if out["created"]:
        db.add(AccessLog(user_id=actor_id, action="write", target=f"company:{mst}/emails<-suy_luan", row_count=out["created"]))
    db.commit()
    return out


def infer_all(db: Session, actor_id: int | None = None, limit: int = 5000) -> dict:
    msts = list(db.scalars(select(EnrichCompany.mst).where(EnrichCompany.domain.is_not(None)).limit(limit)))
    created, done, reasons = 0, 0, Counter()
    for m in msts:
        r = infer_company(db, m, actor_id)
        done += 1
        created += r["created"]
        if r["skipped"]:
            reasons[r["skipped"]] += 1
    return {"companies": done, "created": created, "skipped": dict(reasons)}
