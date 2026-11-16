"""Khớp người (B06), gộp / tách thủ công có hoàn tác (B07), nhập MST cá nhân nội bộ (giai đoạn 4).

Thứ tự khớp khi một nguồn nói "người X giữ chức Y ở doanh nghiệp Z":
  1. MST cá nhân (nếu nguồn có) — chắc chắn là một người.
  2. Cùng doanh nghiệp + cùng tên chuẩn hoá — coi là một người (điểm 0,9 ≥ ngưỡng tự gộp).
  3. Không khớp → tạo hồ sơ mới. Nếu ở doanh nghiệp khác có người cùng tên → tạo cặp "nghi trùng" (điểm < ngưỡng)
     cho biên tập viên quyết — KHÔNG tự gộp (rủi ro "Trùng tên người", mục 12).
Chỉ gộp tự động khi MST cá nhân chứng minh hai hồ sơ là một.
"""

from dataclasses import dataclass

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.db import utcnow
from app.enrich.normalize import bo_dau, parse_mst
from app.models import AdminUser
from app.models_enrich import (
    AccessLog,
    EnrichContact,
    EnrichPerson,
    EntityOp,
    MergeCandidate,
    PersonEvidence,
    PersonRole,
)

AUTO_MERGE_SCORE = 0.85


class PeopleError(ValueError):
    pass


def active(stmt):
    """Bỏ các hồ sơ đã gộp vào người khác."""
    return stmt.where(EnrichPerson.merged_into_id.is_(None))


def by_mst(db: Session, mst_ca_nhan: str) -> EnrichPerson | None:
    return db.scalar(active(select(EnrichPerson).where(EnrichPerson.mst_ca_nhan == mst_ca_nhan)))


def at_company(db: Session, company_mst: str, name_key: str) -> EnrichPerson | None:
    return db.scalar(
        active(
            select(EnrichPerson)
            .join(PersonRole, PersonRole.person_id == EnrichPerson.id)
            .where(PersonRole.company_mst == company_mst, EnrichPerson.ho_ten_khong_dau == name_key)
            .order_by(EnrichPerson.id)
            .limit(1)
        )
    )


def _score(db: Session, a: EnrichPerson, b: EnrichPerson) -> tuple[float, list[str]]:
    reasons = ["Cùng họ tên chuẩn hoá"]
    score = 0.5
    if a.nam_sinh and b.nam_sinh:
        if a.nam_sinh == b.nam_sinh:
            score += 0.2
            reasons.append("Cùng năm sinh")
        else:
            score -= 0.3
            reasons.append("Khác năm sinh")
    ca = set(db.scalars(select(PersonRole.chuc_danh_chuan).where(PersonRole.person_id == a.id)))
    cb = set(db.scalars(select(PersonRole.chuc_danh_chuan).where(PersonRole.person_id == b.id)))
    if ca & cb - {"khac"}:
        score += 0.1
        reasons.append("Cùng chức danh chuẩn")
    return round(min(score, AUTO_MERGE_SCORE - 0.01), 2), reasons


def suggest_duplicates(db: Session, person: EnrichPerson) -> int:
    """Tạo cặp nghi trùng với mọi hồ sơ khác cùng tên (chưa có cặp). Trả về số cặp mới."""
    others = db.scalars(
        active(select(EnrichPerson).where(EnrichPerson.ho_ten_khong_dau == person.ho_ten_khong_dau, EnrichPerson.id != person.id))
    ).all()
    n = 0
    for o in others:
        if person.mst_ca_nhan and o.mst_ca_nhan and person.mst_ca_nhan != o.mst_ca_nhan:
            continue  # khác MST cá nhân → chắc chắn hai người
        a, b = sorted((person.id, o.id))
        if db.scalar(select(MergeCandidate.id).where(MergeCandidate.person_a_id == a, MergeCandidate.person_b_id == b)):
            continue
        score, reasons = _score(db, db.get(EnrichPerson, a), db.get(EnrichPerson, b))
        db.add(MergeCandidate(person_a_id=a, person_b_id=b, score=score, reasons=reasons))
        n += 1
    return n


@dataclass
class Resolved:
    person: EnrichPerson
    created: bool
    how: str  # mst | company_name | new


def resolve(db: Session, company_mst: str, name: str, mst_ca_nhan: str | None = None) -> Resolved:
    key = bo_dau(name)
    if mst_ca_nhan:
        p = by_mst(db, mst_ca_nhan)
        if p:
            return Resolved(p, False, "mst")
    p = at_company(db, company_mst, key)
    if p and (not mst_ca_nhan or not p.mst_ca_nhan or p.mst_ca_nhan == mst_ca_nhan):
        if mst_ca_nhan and not p.mst_ca_nhan:
            p.mst_ca_nhan = mst_ca_nhan
        return Resolved(p, False, "company_name")
    p = EnrichPerson(ho_ten=name, ho_ten_khong_dau=key, mst_ca_nhan=mst_ca_nhan or None)
    db.add(p)
    db.flush()
    # cặp nghi trùng được tạo SAU khi người gọi ghi vai trò (điểm khớp cần biết chức danh) — xem apply_facts
    return Resolved(p, True, "new")


# ------------------------------------------------------------------ gộp / tách / hoàn tác (B07)


def _log(db: Session, user_id: int | None, action: str, target: str, n: int) -> None:
    db.add(AccessLog(user_id=user_id, action=action, target=target[:200], row_count=n))


def merge(db: Session, user: AdminUser | None, keep_id: int, drop_id: int, note: str = "") -> EntityOp:
    if keep_id == drop_id:
        raise PeopleError("Chọn hai hồ sơ khác nhau.")
    keep, drop = db.get(EnrichPerson, keep_id), db.get(EnrichPerson, drop_id)
    if not keep or not drop or keep.merged_into_id or drop.merged_into_id:
        raise PeopleError("Hồ sơ không tồn tại hoặc đã được gộp trước đó.")
    if keep.mst_ca_nhan and drop.mst_ca_nhan and keep.mst_ca_nhan != drop.mst_ca_nhan:
        raise PeopleError("Hai hồ sơ có MST cá nhân khác nhau — là hai người khác nhau, không gộp được.")
    roles = list(db.scalars(select(PersonRole.id).where(PersonRole.person_id == drop.id)))
    contacts = list(db.scalars(select(EnrichContact.id).where(EnrichContact.owner_type == "person", EnrichContact.owner_id == str(drop.id))))
    evidence = list(db.scalars(select(PersonEvidence.id).where(PersonEvidence.person_id == drop.id)))
    payload = {"roles": roles, "contacts": contacts, "evidence": evidence, "mst_moved": None, "nam_sinh_moved": None}
    if roles:
        db.execute(update(PersonRole).where(PersonRole.id.in_(roles)).values(person_id=keep.id))
    if contacts:
        db.execute(update(EnrichContact).where(EnrichContact.id.in_(contacts)).values(owner_id=str(keep.id)))
    if evidence:
        db.execute(update(PersonEvidence).where(PersonEvidence.id.in_(evidence)).values(person_id=keep.id))
    if drop.mst_ca_nhan and not keep.mst_ca_nhan:
        payload["mst_moved"] = drop.mst_ca_nhan
        drop.mst_ca_nhan = None
        db.flush()  # bỏ giá trị duy nhất ở hồ sơ cũ trước khi gán sang hồ sơ giữ lại
        keep.mst_ca_nhan = payload["mst_moved"]
    if drop.nam_sinh and not keep.nam_sinh:
        payload["nam_sinh_moved"] = drop.nam_sinh
        keep.nam_sinh = drop.nam_sinh
    drop.merged_into_id = keep.id
    a, b = sorted((keep.id, drop.id))
    cand = db.scalar(select(MergeCandidate).where(MergeCandidate.person_a_id == a, MergeCandidate.person_b_id == b))
    if cand:
        cand.status, cand.decided_by_id, cand.decided_at = "merged", user.id if user else None, utcnow()
        payload["candidate"] = cand.id
    # cặp nghi trùng khác của hồ sơ bị gộp không còn ý nghĩa
    db.execute(
        update(MergeCandidate)
        .where(MergeCandidate.status == "pending", or_(MergeCandidate.person_a_id == drop.id, MergeCandidate.person_b_id == drop.id))
        .values(status="rejected", decided_at=utcnow())
    )
    op = EntityOp(op="merge", person_id=keep.id, other_person_id=drop.id, payload=payload, note=note[:2000], user_id=user.id if user else None)
    db.add(op)
    _log(db, user.id if user else None, "edit", f"person:{drop.id}->merge->{keep.id}", len(roles) + len(contacts))
    db.commit()
    db.refresh(op)
    return op


def split(db: Session, user: AdminUser, person_id: int, role_ids: list[int], note: str = "") -> EntityOp:
    """Tách các vai trò đã chọn sang một hồ sơ mới cùng tên (khi hai người trùng tên bị gộp nhầm)."""
    p = db.get(EnrichPerson, person_id)
    if not p or p.merged_into_id:
        raise PeopleError("Không tìm thấy hồ sơ.")
    own = set(db.scalars(select(PersonRole.id).where(PersonRole.person_id == p.id)))
    role_ids = [r for r in dict.fromkeys(role_ids)]
    if not role_ids or not set(role_ids) <= own:
        raise PeopleError("Chọn vai trò thuộc hồ sơ này để tách.")
    if set(role_ids) == own:
        raise PeopleError("Phải giữ lại ít nhất một vai trò ở hồ sơ hiện tại.")
    new = EnrichPerson(ho_ten=p.ho_ten, ho_ten_khong_dau=p.ho_ten_khong_dau)
    db.add(new)
    db.flush()
    db.execute(update(PersonRole).where(PersonRole.id.in_(role_ids)).values(person_id=new.id))
    # họ tên của hồ sơ mới cũng phải có bằng chứng → sao chép bằng chứng họ tên
    copied = []
    for e in db.scalars(select(PersonEvidence).where(PersonEvidence.person_id == p.id, PersonEvidence.field == "ho_ten")).all():
        c = PersonEvidence(
            person_id=new.id, field=e.field, value=e.value, source_code=e.source_code, source_url=e.source_url,
            excerpt=e.excerpt, method=e.method, is_inferred=e.is_inferred, content_hash=e.content_hash,
            source_page_id=e.source_page_id, fetched_at=e.fetched_at,
        )
        db.add(c)
        db.flush()
        copied.append(c.id)
    op = EntityOp(op="split", person_id=p.id, other_person_id=new.id, payload={"roles": role_ids, "copied_evidence": copied}, note=note[:2000], user_id=user.id)
    db.add(op)
    _log(db, user.id, "edit", f"person:{p.id}->split->{new.id}", len(role_ids))
    db.commit()
    db.refresh(op)
    return op


def undo(db: Session, user: AdminUser, op_id: int) -> EntityOp:
    op = db.get(EntityOp, op_id)
    if not op or op.undone_at:
        raise PeopleError("Thao tác không tồn tại hoặc đã được hoàn tác.")
    pl = op.payload or {}
    if op.op == "merge":
        keep, drop = db.get(EnrichPerson, op.person_id), db.get(EnrichPerson, op.other_person_id)
        if not drop or drop.merged_into_id != keep.id:
            raise PeopleError("Hồ sơ đã thay đổi sau khi gộp — không hoàn tác tự động được.")
        roles, contacts, evidence = pl.get("roles", []), pl.get("contacts", []), pl.get("evidence", [])
        moved = db.scalars(select(PersonRole.person_id).where(PersonRole.id.in_(roles))).all() if roles else []
        if any(pid != keep.id for pid in moved):
            raise PeopleError("Vai trò đã bị chuyển tiếp sau khi gộp — không hoàn tác tự động được.")
        if roles:
            db.execute(update(PersonRole).where(PersonRole.id.in_(roles)).values(person_id=drop.id))
        if contacts:
            db.execute(update(EnrichContact).where(EnrichContact.id.in_(contacts)).values(owner_id=str(drop.id)))
        if evidence:
            db.execute(update(PersonEvidence).where(PersonEvidence.id.in_(evidence)).values(person_id=drop.id))
        if pl.get("mst_moved"):
            keep.mst_ca_nhan = None
            db.flush()
            drop.mst_ca_nhan = pl["mst_moved"]
        if pl.get("nam_sinh_moved"):
            keep.nam_sinh = None
        drop.merged_into_id = None
        if pl.get("candidate"):
            cand = db.get(MergeCandidate, pl["candidate"])
            if cand:
                cand.status, cand.decided_at = "pending", None
    elif op.op == "split":
        orig, new = db.get(EnrichPerson, op.person_id), db.get(EnrichPerson, op.other_person_id)
        if not new or new.merged_into_id:
            raise PeopleError("Hồ sơ tách ra đã thay đổi — không hoàn tác tự động được.")
        extra = db.scalar(select(PersonRole.id).where(PersonRole.person_id == new.id, PersonRole.id.not_in(pl.get("roles", []))))
        if extra:
            raise PeopleError("Hồ sơ tách ra đã có thêm vai trò mới — gộp lại thủ công thay vì hoàn tác.")
        db.execute(update(PersonRole).where(PersonRole.id.in_(pl.get("roles", []))).values(person_id=orig.id))
        db.execute(update(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id == str(new.id)).values(owner_id=str(orig.id)))
        db.execute(update(PersonEvidence).where(PersonEvidence.person_id == new.id, PersonEvidence.id.not_in(pl.get("copied_evidence", []))).values(person_id=orig.id))
        new.merged_into_id = orig.id  # ẩn hồ sơ tách (giữ để truy vết)
    op.undone_at, op.undone_by_id = utcnow(), user.id
    _log(db, user.id, "edit", f"undo-op:{op.id}", 1)
    db.commit()
    db.refresh(op)
    return op


def decide_candidate(db: Session, user: AdminUser, cand_id: int, action: str, keep: str = "a") -> MergeCandidate:
    cand = db.get(MergeCandidate, cand_id)
    if not cand or cand.status != "pending":
        raise PeopleError("Cặp này đã được xử lý.")
    if action == "reject":
        cand.status, cand.decided_by_id, cand.decided_at = "rejected", user.id, utcnow()
        _log(db, user.id, "edit", f"merge-candidate:{cand.id}/reject", 1)
        db.commit()
    elif action == "merge":
        k, d = (cand.person_a_id, cand.person_b_id) if keep == "a" else (cand.person_b_id, cand.person_a_id)
        merge(db, user, k, d, note=f"Từ cặp nghi trùng #{cand.id}")
        db.refresh(cand)
    else:
        raise PeopleError("Thao tác không hợp lệ.")
    return cand


def personal_mst_ok(raw: str) -> str | None:
    """MST cá nhân: 10 chữ số (không có dạng chi nhánh)."""
    r = parse_mst(raw)
    return r.mst if r.mst and "-" not in r.mst else None


# ------------------------------------------------------------------ nhập MST cá nhân nội bộ (dữ liệu đang có — mục 1)

PERSONAL_COLUMNS = {
    "mst_ca_nhan": ["ma so thue ca nhan", "mst ca nhan", "mst cn", "mstcn"],
    "ho_ten": ["ho va ten", "ho ten", "ten nguoi", "ten"],
    "mst_dn": ["ma so thue doanh nghiep", "mst doanh nghiep", "mst dn", "ma so doanh nghiep", "mst cong ty", "ma so thue cong ty"],
    "chuc_danh": ["chuc danh", "chuc vu"],
}


def import_personal_mst(db: Session, user: AdminUser, *, file_name: str, data: bytes, source_note: str, confirmed: bool) -> dict:
    """Nhập danh sách MST cá nhân của người ra quyết định mà doanh nghiệp đang nắm giữ.

    T03: không có luồng nhập dữ liệu cá nhân MUA từ bên thứ ba — người nhập phải xác nhận nguồn là dữ liệu nội bộ.
    T04: MST cá nhân chỉ dùng đối soát (khớp người), không bao giờ có trong bản xuất.
    """
    import hashlib
    import json

    from app.enrich import sources
    from app.enrich.apply import Origin, apply_facts
    from app.enrich.connectors.base import Facts, PersonFact
    from app.enrich.governance import clean_name
    from app.enrich.importer import ImportError_, _cell, read_table
    from app.models_enrich import EnrichCompany

    if not confirmed:
        raise PeopleError("Phải xác nhận đây là dữ liệu doanh nghiệp đang nắm giữ hợp pháp, không mua từ bên thứ ba.")
    if len((source_note or "").strip()) < 3:
        raise PeopleError("Ghi rõ nguồn của danh sách (vd: hồ sơ khách hàng ký hợp đồng).")
    try:
        table = read_table(file_name, data)
    except ImportError_ as e:
        raise PeopleError(str(e)) from e
    header_idx, cols = None, {}
    for i, row in enumerate(table[:10]):
        heads = [bo_dau(_cell(c)) for c in row]
        found = {}
        for target, syns in PERSONAL_COLUMNS.items():
            for c, h in enumerate(heads):
                if c not in found.values() and h and any(h == s or (len(s) >= 6 and h.startswith(s)) for s in syns):
                    found[target] = c
                    break
        if {"mst_ca_nhan", "ho_ten", "mst_dn"} <= set(found):
            header_idx, cols = i, found
            break
    if header_idx is None:
        raise PeopleError("Cần các cột: MST cá nhân, Họ và tên, MST doanh nghiệp (tuỳ chọn: Chức danh).")

    src = sources.ensure(db, "mst_ca_nhan_noi_bo")
    rep = {"rows": 0, "by_mst": 0, "by_company_name": 0, "created": 0, "auto_merged": 0, "skipped": []}
    for i in range(header_idx + 1, len(table)):
        row = table[i]
        get = lambda k: _cell(row[cols[k]]) if k in cols and cols[k] < len(row) else ""  # noqa: E731
        if not any(_cell(c) for c in row):
            continue
        rep["rows"] += 1
        mcn = personal_mst_ok(get("mst_ca_nhan"))
        name = clean_name(" ".join(w.capitalize() for w in get("ho_ten").split()))  # file nội bộ hay viết thường
        company = parse_mst(get("mst_dn")).mst
        reason = None
        if not mcn:
            reason = "MST cá nhân phải gồm 10 chữ số"
        elif not name:
            reason = "Họ tên không hợp lệ"
        elif not company or not db.get(EnrichCompany, company):
            reason = "MST doanh nghiệp không có trong hệ thống"
        if reason:
            if len(rep["skipped"]) < 200:
                rep["skipped"].append({"row": i + 1, "reason": reason})
            continue
        a = by_mst(db, mcn)
        b = at_company(db, company, bo_dau(name))
        if a and b and a.id != b.id:
            if b.mst_ca_nhan and b.mst_ca_nhan != mcn:
                rep["skipped"].append({"row": i + 1, "reason": "Người cùng tên ở doanh nghiệp này đã có MST cá nhân khác"})
                continue
            merge(db, user, a.id, b.id, note=f"Tự gộp: cùng MST cá nhân (nhập {file_name}, dòng {i + 1})")
            rep["auto_merged"] += 1
        elif b and b.mst_ca_nhan and b.mst_ca_nhan != mcn and not a:
            pass  # khác MST → người khác cùng tên: resolve sẽ tạo hồ sơ mới
        rep["by_mst" if a else ("by_company_name" if b and not b.mst_ca_nhan else "created")] += 1
        title = get("chuc_danh") or "Không rõ chức danh"
        h = hashlib.sha256(json.dumps([mcn, name, company, title], ensure_ascii=False).encode()).hexdigest()
        apply_facts(
            db, company, Facts(people=[PersonFact(name, title, f"{source_note.strip()} — {file_name}, dòng {i + 1}", mst_ca_nhan=mcn)]),
            Origin(source=src, source_url=f"{file_name}#dong={i + 1}", content_hash=h, method="cau_truc", actor_id=user.id),
            recompute=False,
        )
    db.commit()
    return rep
