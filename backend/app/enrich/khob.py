"""Lối duy nhất để đọc kho B (dữ liệu cá nhân).

Mỗi hàm: kiểm quyền → truy vấn → lọc trường theo vai trò (N04) → loại người / liên hệ trong danh sách từ chối (C10)
→ ghi AccessLog (N06, chỉ ghi thêm — T08). Route KHÔNG được truy vấn bảng kho B trực tiếp.
"""

from fastapi import HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.enrich import permissions as perm
from app.enrich.normalize import bo_dau
from app.models import AdminUser
from app.models_enrich import AccessLog, EnrichContact, EnrichPerson, EntityOp, OptOut, PersonEvidence, PersonRole
from app.security import client_ip


def log_access(db: Session, user: AdminUser, request: Request | None, action: str, target: str, row_count: int) -> None:
    db.add(
        AccessLog(
            user_id=user.id,
            action=action,
            target=target[:200],
            row_count=row_count,
            ip=client_ip(request, get_settings())[:64] if request is not None else "",
        )
    )
    db.commit()


def _need(user: AdminUser, cap: str) -> None:
    if not perm.has(user, cap):
        raise HTTPException(403, perm.FORBIDDEN)


def _optouts(db: Session) -> tuple[set[int], set[str]]:
    """(id người đã từ chối, email/điện thoại đã từ chối — chữ thường)."""
    persons: set[int] = set()
    values: set[str] = set()
    for kind, value in db.execute(select(OptOut.kind, OptOut.value)):
        if kind == "person":
            if value.isdigit():
                persons.add(int(value))
        else:
            values.add(value.strip().lower())
    return persons, values


def company_people(db: Session, user: AdminUser, mst: str, request: Request | None = None) -> list[dict]:
    """Người liên quan của một doanh nghiệp (hồ sơ doanh nghiệp, tab "Người liên quan")."""
    _need(user, "b.read")
    blocked_people, blocked_values = _optouts(db)
    rows = db.execute(
        select(PersonRole, EnrichPerson)
        .join(EnrichPerson, EnrichPerson.id == PersonRole.person_id)
        .where(PersonRole.company_mst == mst)
        .order_by(PersonRole.la_nguoi_quyet_dinh.desc(), PersonRole.den_ngay.is_not(None), EnrichPerson.ho_ten)
    ).all()
    rows = [(r, p) for r, p in rows if p.id not in blocked_people]
    ids = list({p.id for _, p in rows})

    contacts: dict[int, list[dict]] = {}
    evidence: dict[int, list[dict]] = {}
    if ids:
        for c in db.scalars(
            select(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id.in_([str(i) for i in ids]))
        ):
            if c.value.strip().lower() in blocked_values:
                continue
            contacts.setdefault(int(c.owner_id), []).append(
                {"kind": c.kind, "value": c.value, "is_inferred": c.is_inferred, "verify_status": c.verify_status}
            )
        if perm.has(user, "b.evidence"):
            for e in db.scalars(select(PersonEvidence).where(PersonEvidence.person_id.in_(ids)).order_by(PersonEvidence.fetched_at.desc())):
                evidence.setdefault(e.person_id, []).append(
                    {
                        "field": e.field,
                        "value": e.value,
                        "source_code": e.source_code,
                        "source_url": e.source_url,
                        "excerpt": e.excerpt,
                        "method": e.method,
                        "is_inferred": e.is_inferred,
                        "fetched_at": e.fetched_at.isoformat() + "Z",
                    }
                )

    out = []
    for r, p in rows:
        out.append(
            perm.filter_person(
                user,
                {
                    "id": p.id,
                    "ho_ten": p.ho_ten,
                    "chuc_danh": r.chuc_danh,
                    "chuc_danh_chuan": r.chuc_danh_chuan,
                    "la_nguoi_quyet_dinh": r.la_nguoi_quyet_dinh,
                    "tu_ngay": r.tu_ngay.isoformat() if r.tu_ngay else None,
                    "den_ngay": r.den_ngay.isoformat() if r.den_ngay else None,
                    "lien_he": contacts.get(p.id, []),
                    "nam_sinh": p.nam_sinh,
                    "mst_ca_nhan": p.mst_ca_nhan,
                    "bang_chung": evidence.get(p.id, []),
                },
            )
        )
    log_access(db, user, request, "read", f"company:{mst}/people", len(out))
    return out


def list_persons(
    db: Session, user: AdminUser, q: str, page: int, page_size: int, request: Request | None = None
) -> dict:
    """Truy vấn trực tiếp kho B — chỉ biên tập, thẩm định, quản trị (T01: nhân viên kinh doanh bị từ chối)."""
    _need(user, "b.list")
    blocked_people, _ = _optouts(db)
    stmt = select(EnrichPerson).where(EnrichPerson.merged_into_id.is_(None))  # bỏ hồ sơ đã gộp (B07)
    if blocked_people:
        stmt = stmt.where(EnrichPerson.id.not_in(blocked_people))
    q = q.strip()
    if q:
        like = f"%{bo_dau(q)}%"
        conds = [EnrichPerson.ho_ten_khong_dau.like(like)]
        if perm.has(user, "b.personal"):
            conds.append(EnrichPerson.mst_ca_nhan == q)
        stmt = stmt.where(or_(*conds))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    people = db.scalars(stmt.order_by(EnrichPerson.ho_ten_khong_dau).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        perm.filter_person(user, {"id": p.id, "ho_ten": p.ho_ten, "nam_sinh": p.nam_sinh, "mst_ca_nhan": p.mst_ca_nhan})
        for p in people
    ]
    log_access(db, user, request, "list", f"persons?q={q}"[:200], len(items))
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def decision_maker_company_count(db: Session) -> int:
    """Số doanh nghiệp có ít nhất một người ra quyết định đang tại vị — số tổng hợp, không chứa dữ liệu cá nhân
    nên không ghi nhật ký (mục tiêu ≥ 70%)."""
    return (
        db.scalar(
            select(func.count(func.distinct(PersonRole.company_mst))).where(
                PersonRole.la_nguoi_quyet_dinh.is_(True), PersonRole.den_ngay.is_(None)
            )
        )
        or 0
    )


BOARD_CODES = ("chu_tich_hdqt", "pho_chu_tich_hdqt", "thanh_vien_hdqt", "chu_tich_hdtv")
EXEC_CODES = ("tong_giam_doc", "pho_tong_giam_doc", "giam_doc", "pho_giam_doc", "giam_doc_khoi", "thanh_vien_bdh")


def board_counts(db: Session, msts: list[str]) -> dict[str, dict[str, int]]:
    """Số người đang tại vị theo nhóm (HĐQT / Ban điều hành) cho từng MST — chỉ là số đếm, không có tên."""
    out: dict[str, dict[str, int]] = {m: {"board": 0, "exec": 0} for m in msts}
    for i in range(0, len(msts), 1000):
        part = msts[i : i + 1000]
        rows = db.execute(
            select(PersonRole.company_mst, PersonRole.chuc_danh_chuan, func.count(func.distinct(PersonRole.person_id)))
            .where(PersonRole.company_mst.in_(part), PersonRole.den_ngay.is_(None))
            .group_by(PersonRole.company_mst, PersonRole.chuc_danh_chuan)
        ).all()
        for mst, code, n in rows:
            if code in BOARD_CODES:
                out[mst]["board"] += n
            elif code in EXEC_CODES:
                out[mst]["exec"] += n
    return out


def listed_full_board_count(db: Session) -> tuple[int, int]:
    """(số DN niêm yết, số DN niêm yết có đủ HĐQT + Ban điều hành) — mục tiêu giai đoạn 3: ≥ 90%."""
    from app.models_enrich import EnrichCompany

    listed = list(db.scalars(select(EnrichCompany.mst).where(EnrichCompany.niem_yet.is_(True))))
    counts = board_counts(db, listed)
    return len(listed), sum(1 for c in counts.values() if c["board"] and c["exec"])


# ------------------------------------------------------------------ giai đoạn 4: hồ sơ người, đồ thị quan hệ, bên liên quan


def _get_person(db: Session, pid: int) -> EnrichPerson:
    p = db.get(EnrichPerson, pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy người này.")
    return p


def _companies(db: Session, msts) -> dict:
    from app.models_enrich import EnrichCompany

    msts = list(set(msts))
    if not msts:
        return {}
    return {c.mst: c for c in db.scalars(select(EnrichCompany).where(EnrichCompany.mst.in_(msts)))}


def person_profile(db: Session, user: AdminUser, pid: int, request: Request | None = None) -> dict:
    """C02: tên, chức danh hiện tại và trước đây, doanh nghiệp liên quan. MST cá nhân chỉ hiện với vai trò được phép."""
    _need(user, "b.read")
    p = _get_person(db, pid)
    if p.merged_into_id:
        return {"id": p.id, "merged_into_id": p.merged_into_id}
    blocked_people, blocked_values = _optouts(db)
    if p.id in blocked_people:
        raise HTTPException(404, "Người này đã yêu cầu không xử lý dữ liệu (danh sách từ chối).")
    roles = db.scalars(
        select(PersonRole).where(PersonRole.person_id == p.id).order_by(PersonRole.den_ngay.is_not(None), PersonRole.tu_ngay.desc())
    ).all()
    comps = _companies(db, [r.company_mst for r in roles])
    contacts = [
        {"id": c.id, "kind": c.kind, "value": c.value, "is_inferred": c.is_inferred, "verify_status": c.verify_status, "source_code": c.source_code}
        for c in db.scalars(select(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id == str(p.id)))
        if c.value.strip().lower() not in blocked_values
    ]
    evidence = []
    if perm.has(user, "b.evidence"):
        for e in db.scalars(select(PersonEvidence).where(PersonEvidence.person_id == p.id).order_by(PersonEvidence.fetched_at.desc())):
            value = e.value if e.field != "mst_ca_nhan" or perm.has(user, "b.personal") else "••••••••••"
            evidence.append(
                {
                    "field": e.field,
                    "value": value,
                    "source_code": e.source_code,
                    "source_url": e.source_url,
                    "excerpt": e.excerpt,
                    "method": e.method,
                    "is_inferred": e.is_inferred,
                    "fetched_at": e.fetched_at.isoformat() + "Z",
                }
            )
    out = perm.filter_person(
        user,
        {"id": p.id, "ho_ten": p.ho_ten, "nam_sinh": p.nam_sinh, "mst_ca_nhan": p.mst_ca_nhan, "lien_he": contacts, "bang_chung": evidence},
    )
    out["roles"] = [
        {
            "id": r.id,
            "company_mst": r.company_mst,
            "company_ten": comps[r.company_mst].ten if r.company_mst in comps else None,
            "ma_ck": comps[r.company_mst].ma_ck if r.company_mst in comps else None,
            "chuc_danh": r.chuc_danh,
            "chuc_danh_chuan": r.chuc_danh_chuan,
            "la_nguoi_quyet_dinh": r.la_nguoi_quyet_dinh,
            "tu_ngay": r.tu_ngay.isoformat() if r.tu_ngay else None,
            "den_ngay": r.den_ngay.isoformat() if r.den_ngay else None,
            "source_code": r.source_code,
        }
        for r in roles
    ]
    if perm.has(user, "b.list"):
        out["candidates"] = merge_candidates(db, user, person_id=p.id, log=False)
        out["ops"] = [
            {
                "id": o.id,
                "op": o.op,
                "person_id": o.person_id,
                "other_person_id": o.other_person_id,
                "note": o.note,
                "created_at": o.created_at.isoformat() + "Z",
                "undone_at": o.undone_at.isoformat() + "Z" if o.undone_at else None,
            }
            for o in db.scalars(
                select(EntityOp).where((EntityOp.person_id == p.id) | (EntityOp.other_person_id == p.id)).order_by(EntityOp.id.desc()).limit(50)
            )
        ]
    p.last_used_at = utcnow()  # T07: hồ sơ còn được dùng
    log_access(db, user, request, "read", f"person:{p.id}", 1)
    return out


def person_graph(db: Session, user: AdminUser, pid: int, request: Request | None = None) -> dict:
    """C03: từ một người → mọi pháp nhân họ giữ vai trò → những người khác đang giữ vai trò ở các pháp nhân đó."""
    _need(user, "b.read")
    p = _get_person(db, pid)
    blocked_people, _ = _optouts(db)
    my_roles = db.scalars(select(PersonRole).where(PersonRole.person_id == p.id)).all()
    msts = {r.company_mst for r in my_roles}
    comps = _companies(db, msts)
    nodes = {f"p{p.id}": {"id": f"p{p.id}", "type": "person", "label": p.ho_ten, "person_id": p.id, "center": True}}
    edges = []
    for m in msts:
        c = comps.get(m)
        label = (c.ma_ck + " · " if c and c.ma_ck else "") + (c.ten if c and c.ten else m)
        nodes[f"c{m}"] = {"id": f"c{m}", "type": "company", "label": label, "mst": m}
    for r in my_roles:
        edges.append({"from": f"p{p.id}", "to": f"c{r.company_mst}", "label": r.chuc_danh, "active": r.den_ngay is None})
    if msts:
        others = db.execute(
            select(PersonRole, EnrichPerson)
            .join(EnrichPerson, EnrichPerson.id == PersonRole.person_id)
            .where(
                PersonRole.company_mst.in_(msts),
                PersonRole.person_id != p.id,
                PersonRole.den_ngay.is_(None),
                EnrichPerson.merged_into_id.is_(None),
            )
        ).all()
        for r, o in others:
            if o.id in blocked_people:
                continue
            nodes.setdefault(f"p{o.id}", {"id": f"p{o.id}", "type": "person", "label": o.ho_ten, "person_id": o.id, "center": False})
            edges.append({"from": f"p{o.id}", "to": f"c{r.company_mst}", "label": r.chuc_danh, "active": True})
    if request is not None:
        log_access(db, user, request, "read", f"person:{p.id}/graph", len(nodes))
    return {"nodes": list(nodes.values()), "edges": edges}


def related_rows(db: Session, user: AdminUser, pid: int, purpose: str, include_inferred: bool, request: Request | None = None) -> list[dict]:
    """C03: danh sách bên liên quan để xuất. Không bao giờ có cột MST cá nhân (T04); email suy luận chỉ khi chọn (B11)."""
    _need(user, "b.list")
    g = person_graph(db, user, pid, None)
    by_id = {n["id"]: n for n in g["nodes"]}
    pids = [n["person_id"] for n in g["nodes"] if n["type"] == "person"]
    _, blocked_values = _optouts(db)
    contacts: dict[int, list[str]] = {}
    for c in db.scalars(
        select(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id.in_([str(i) for i in pids]))
    ):
        if c.value.strip().lower() in blocked_values or (c.is_inferred and not include_inferred):
            continue
        contacts.setdefault(int(c.owner_id), []).append(c.value + (" (suy luận)" if c.is_inferred else ""))
    rows = []
    for e in g["edges"]:
        pn, cn = by_id[e["from"]], by_id[e["to"]]
        rows.append(
            {
                "nguoi": pn["label"],
                "nguoi_dang_xem": "x" if pn.get("center") else "",
                "chuc_danh": e["label"],
                "dang_giu": "x" if e["active"] else "",
                "doanh_nghiep": cn["label"],
                "mst_doanh_nghiep": cn["mst"],
                "lien_he_cong_viec": "; ".join(contacts.get(pn["person_id"], [])),
            }
        )
    log_access(db, user, request, "export", f"person:{pid}/related?purpose={purpose}", len(rows))
    return rows


def merge_candidates(
    db: Session, user: AdminUser, status: str = "pending", person_id: int | None = None, request: Request | None = None, log: bool = True
) -> list[dict]:
    """B06: cặp hồ sơ nghi trùng chờ biên tập viên quyết."""
    _need(user, "b.list")
    from app.models_enrich import MergeCandidate

    stmt = select(MergeCandidate).where(MergeCandidate.status == status)
    if person_id:
        stmt = stmt.where((MergeCandidate.person_a_id == person_id) | (MergeCandidate.person_b_id == person_id))
    cands = db.scalars(stmt.order_by(MergeCandidate.score.desc(), MergeCandidate.id).limit(200)).all()
    ids = {i for c in cands for i in (c.person_a_id, c.person_b_id)}
    people = {p.id: p for p in db.scalars(select(EnrichPerson).where(EnrichPerson.id.in_(ids)))} if ids else {}
    roles: dict[int, list[PersonRole]] = {}
    if ids:
        for r in db.scalars(select(PersonRole).where(PersonRole.person_id.in_(ids))):
            roles.setdefault(r.person_id, []).append(r)
    comps = _companies(db, [r.company_mst for rs in roles.values() for r in rs])

    def side(pid: int) -> dict:
        p = people.get(pid)
        base = perm.filter_person(
            user, {"id": pid, "ho_ten": p.ho_ten if p else "?", "nam_sinh": p.nam_sinh if p else None, "mst_ca_nhan": p.mst_ca_nhan if p else None}
        )
        base["roles"] = [
            {
                "chuc_danh": r.chuc_danh,
                "company_mst": r.company_mst,
                "company_ten": comps[r.company_mst].ten if r.company_mst in comps else None,
                "den_ngay": r.den_ngay.isoformat() if r.den_ngay else None,
            }
            for r in roles.get(pid, [])
        ]
        return base

    out = [{"id": c.id, "score": c.score, "reasons": c.reasons, "status": c.status, "a": side(c.person_a_id), "b": side(c.person_b_id)} for c in cands]
    if log:
        log_access(db, user, request, "list", f"merge-candidates?status={status}", len(out))
    return out
