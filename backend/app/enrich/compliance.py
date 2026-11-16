"""Công cụ tuân thủ (mục 10): danh sách từ chối (C10), yêu cầu của chủ thể dữ liệu (T05, T06), rà soát thời hạn lưu (T07),
báo cáo đánh giá tác động xử lý dữ liệu cá nhân (T10).

Đây là công cụ kỹ thuật để thực hiện yêu cầu — diễn giải pháp lý (khi nào phải xoá, thời hạn trả lời…) cần pháp chế duyệt.
"""

from collections import Counter
from datetime import date, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.enrich import crypto, khob
from app.enrich.normalize import bo_dau, normalize_phone
from app.enrich.sources import all_sources
from app.models import AdminUser
from app.models_enrich import (
    ENRICH_ROLES,
    PURPOSES,
    AccessLog,
    EnrichBatch,
    EnrichContact,
    EnrichPerson,
    ExportRecord,
    OptOut,
    PersonEvidence,
    PersonRole,
)

OPTOUT_KINDS = {"email": "Email", "phone": "Điện thoại", "person": "Người (mã hồ sơ)"}


class ComplianceError(ValueError):
    pass


# ------------------------------------------------------------------ C10: danh sách từ chối


def normalize_optout(kind: str, value: str) -> str:
    v = (value or "").strip()
    if kind == "email":
        v = v.lower()
        if "@" not in v:
            raise ComplianceError("Email không hợp lệ.")
    elif kind == "phone":
        n = normalize_phone(v)
        if not n:
            raise ComplianceError("Số điện thoại không hợp lệ.")
        v = n
    elif kind == "person":
        if not v.isdigit():
            raise ComplianceError("Mã hồ sơ người phải là số.")
    else:
        raise ComplianceError("Loại không hợp lệ.")
    return v


def add_optout(db: Session, user: AdminUser, kind: str, value: str, reason: str) -> OptOut:
    v = normalize_optout(kind, value)
    existing = db.scalar(select(OptOut).where(OptOut.kind == kind, OptOut.value == v))
    if existing:
        return existing
    o = OptOut(kind=kind, value=v, reason=reason[:2000], created_by_id=user.id)
    db.add(o)
    db.add(AccessLog(user_id=user.id, action="edit", target=f"optout:{kind}", row_count=1))
    db.commit()
    db.refresh(o)
    return o


def list_optouts(db: Session, q: str = "") -> list[dict]:
    stmt = select(OptOut).where(OptOut.kind.in_(tuple(OPTOUT_KINDS)))
    if q.strip():
        stmt = stmt.where(OptOut.value.ilike(f"%{q.strip().lower()}%"))
    return [
        {"id": o.id, "kind": o.kind, "value": o.value, "day": o.day.isoformat(), "reason": o.reason}
        for o in db.scalars(stmt.order_by(OptOut.id.desc()).limit(500))
    ]


def hashed_block(db: Session) -> set[str]:
    """Khoá băm của người đã xoá dữ liệu (mst_cn, ten_dn) — apply_facts dùng để không thu thập lại (T05)."""
    return {v for (v,) in db.execute(select(OptOut.value).where(OptOut.kind.in_(("mst_cn", "ten_dn"))))}


def name_company_key(name: str, company_mst: str) -> str:
    return crypto.blind_index(f"{bo_dau(name)}|{company_mst}", "ten_dn")


def mst_key(mst_ca_nhan: str) -> str:
    return crypto.blind_index(mst_ca_nhan, "mst_cn")


# ------------------------------------------------------------------ T05, T06: yêu cầu của chủ thể dữ liệu


def find_subject(db: Session, user: AdminUser, q: str, request: Request | None = None) -> list[dict]:
    """Tìm theo tên, email hoặc MST cá nhân."""
    q = (q or "").strip()
    if len(q) < 3:
        raise ComplianceError("Nhập ít nhất 3 ký tự (tên, email hoặc MST cá nhân).")
    ids: set[int] = set()
    if "@" in q:
        ids |= {int(o) for (o,) in db.execute(select(EnrichContact.owner_id).where(EnrichContact.owner_type == "person", EnrichContact.value == q.lower())) if o.isdigit()}
    elif q.replace(" ", "").isdigit():
        p = db.scalar(select(EnrichPerson).where(EnrichPerson.mst_ca_nhan == q.replace(" ", "")))
        if p:
            ids.add(p.id)
    else:
        ids |= set(db.scalars(select(EnrichPerson.id).where(EnrichPerson.ho_ten_khong_dau.like(f"%{bo_dau(q)}%")).limit(100)))
    people = db.scalars(select(EnrichPerson).where(EnrichPerson.id.in_(ids), EnrichPerson.merged_into_id.is_(None))).all() if ids else []
    out = []
    for p in people:
        roles = db.execute(select(PersonRole.company_mst, PersonRole.chuc_danh).where(PersonRole.person_id == p.id)).all()
        out.append({"id": p.id, "ho_ten": p.ho_ten, "roles": [{"company_mst": m, "chuc_danh": t} for m, t in roles]})
    khob.log_access(db, user, request, "list", "subject-search", len(out))
    return out


def subject_report(db: Session, user: AdminUser, pid: int, request: Request | None = None) -> dict:
    """T06: mọi dữ liệu đang lưu về một người, kèm nguồn và thời điểm — để trả lời yêu cầu truy cập của chủ thể."""
    p = db.get(EnrichPerson, pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy người này.")
    roles = db.scalars(select(PersonRole).where(PersonRole.person_id == p.id)).all()
    comps = khob._companies(db, [r.company_mst for r in roles])  # noqa: SLF001
    srcs = all_sources(db)
    report = {
        "nguoi": {"ma_ho_so": p.id, "ho_ten": p.ho_ten, "nam_sinh": p.nam_sinh, "mst_ca_nhan": p.mst_ca_nhan, "tao_luc": p.created_at.isoformat() + "Z"},
        "vai_tro": [
            {
                "doanh_nghiep": (comps[r.company_mst].ten if r.company_mst in comps else None) or r.company_mst,
                "mst_doanh_nghiep": r.company_mst,
                "chuc_danh": r.chuc_danh,
                "tu_ngay": r.tu_ngay.isoformat() if r.tu_ngay else None,
                "den_ngay": r.den_ngay.isoformat() if r.den_ngay else None,
                "nguon": srcs[r.source_code].name if r.source_code in srcs else r.source_code,
            }
            for r in roles
        ],
        "lien_he": [
            {"loai": c.kind, "gia_tri": c.value, "suy_luan": c.is_inferred, "nguon": c.source_code}
            for c in db.scalars(select(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id == str(p.id)))
        ],
        "nguon_goc": [
            {
                "truong": e.field,
                "gia_tri": e.value,
                "nguon": srcs[e.source_code].name if e.source_code in srcs else e.source_code,
                "co_so_phap_ly": srcs[e.source_code].legal_basis if e.source_code in srcs else "",
                "duong_dan": e.source_url,
                "thu_thap_luc": e.fetched_at.isoformat() + "Z",
                "suy_luan": e.is_inferred,
            }
            for e in db.scalars(select(PersonEvidence).where(PersonEvidence.person_id == p.id).order_by(PersonEvidence.fetched_at))
        ],
        "muc_dich_xu_ly": sorted(
            {PURPOSES.get(x, x) for b in db.scalars(select(EnrichBatch)) for x in (b.purposes or [])}
        ),
        "lap_luc": utcnow().isoformat() + "Z",
    }
    khob.log_access(db, user, request, "read", f"subject-report:person:{p.id}", 1)
    return report


def subject_erase(db: Session, user: AdminUser, pid: int, mode: str, reason: str, request: Request | None = None) -> dict:
    """T05: 'hide' — ẩn vĩnh viễn (thêm vào danh sách từ chối); 'delete' — xoá dữ liệu kho B của người này và chặn thu thập lại.

    Khi xoá: vai trò, liên hệ, bằng chứng, lịch sử thay đổi bị xoá; email / điện thoại vào danh sách từ chối; tên + doanh
    nghiệp và MST cá nhân được lưu dưới dạng khoá băm (không phải giá trị) để không bị thu thập lại. Bản gốc trang nguồn
    vẫn giữ tới hết thời hạn lưu bản gốc (N07) — pháp chế quyết có cần xoá sớm hay không.
    """
    p = db.get(EnrichPerson, pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy người này.")
    if mode not in ("hide", "delete"):
        raise ComplianceError("Chọn ẩn vĩnh viễn hoặc xoá.")
    if len((reason or "").strip()) < 3:
        raise ComplianceError("Ghi lý do / số yêu cầu của chủ thể dữ liệu.")
    contacts = db.scalars(select(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id == str(p.id))).all()
    for c in contacts:
        kind = "email" if c.kind == "email" else "phone"
        if not db.scalar(select(OptOut.id).where(OptOut.kind == kind, OptOut.value == c.value.lower())):
            db.add(OptOut(kind=kind, value=c.value.lower(), reason=f"Yêu cầu chủ thể: {reason}"[:2000], created_by_id=user.id))
    if mode == "hide":
        if not db.scalar(select(OptOut.id).where(OptOut.kind == "person", OptOut.value == str(p.id))):
            db.add(OptOut(kind="person", value=str(p.id), reason=f"Yêu cầu chủ thể: {reason}"[:2000], created_by_id=user.id))
        db.add(AccessLog(user_id=user.id, action="edit", target=f"subject-hide:person:{p.id}", row_count=1))
        db.commit()
        return {"mode": "hide", "person_id": p.id, "contacts_blocked": len(contacts)}
    roles = db.scalars(select(PersonRole).where(PersonRole.person_id == p.id)).all()
    keys = [("ten_dn", name_company_key(p.ho_ten, r.company_mst)) for r in roles]
    if p.mst_ca_nhan:
        keys.append(("mst_cn", mst_key(p.mst_ca_nhan)))
    for kind, k in dict.fromkeys(keys):
        if not db.scalar(select(OptOut.id).where(OptOut.value == k)):
            db.add(OptOut(kind=kind, value=k, reason=f"Đã xoá theo yêu cầu: {reason}"[:2000], created_by_id=user.id))
    n_contacts = len(contacts)
    db.execute(delete(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id == str(p.id)))
    # hồ sơ đã gộp vào người này cũng là dữ liệu của họ
    merged = list(db.scalars(select(EnrichPerson.id).where(EnrichPerson.merged_into_id == p.id)))
    for mid in merged:
        db.execute(delete(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.owner_id == str(mid)))
        db.delete(db.get(EnrichPerson, mid))
    db.delete(p)  # vai trò, bằng chứng, lịch sử, cặp nghi trùng, thao tác gộp xoá theo (ON DELETE CASCADE)
    db.add(AccessLog(user_id=user.id, action="delete", target=f"subject-delete:person:{pid}", row_count=1 + len(roles) + n_contacts))
    db.commit()
    return {"mode": "delete", "person_id": pid, "roles": len(roles), "contacts": n_contacts, "blocked_keys": len(keys)}


# ------------------------------------------------------------------ T07: rà soát thời hạn lưu


def retention_due(db: Session, months: int | None = None) -> list[dict]:
    months = months or int(get_settings().enrich_retention_months)
    cutoff = utcnow() - timedelta(days=30 * months)
    rows = db.execute(
        select(EnrichPerson.id, EnrichPerson.ho_ten, EnrichPerson.created_at, EnrichPerson.last_used_at)
        .where(EnrichPerson.merged_into_id.is_(None), func.coalesce(EnrichPerson.last_used_at, EnrichPerson.created_at) < cutoff)
        .order_by(func.coalesce(EnrichPerson.last_used_at, EnrichPerson.created_at))
        .limit(1000)
    ).all()
    return [
        {"id": i, "ho_ten": n, "created_at": c.isoformat() + "Z", "last_used_at": u.isoformat() + "Z" if u else None}
        for i, n, c, u in rows
    ]


# ------------------------------------------------------------------ T10: báo cáo đánh giá tác động


def dpia(db: Session) -> dict:
    """Loại dữ liệu, nguồn, mục đích, thời hạn, ai truy cập — đầu vào cho hồ sơ đánh giá tác động xử lý dữ liệu cá nhân."""
    cfg = get_settings()
    since = utcnow() - timedelta(days=365)
    srcs = all_sources(db)
    counts = {
        "nguoi": db.scalar(select(func.count()).select_from(EnrichPerson).where(EnrichPerson.merged_into_id.is_(None))) or 0,
        "co_mst_ca_nhan": db.scalar(select(func.count()).select_from(EnrichPerson).where(EnrichPerson.mst_ca_nhan.is_not(None))) or 0,
        "vai_tro": db.scalar(select(func.count()).select_from(PersonRole)) or 0,
        "email_thu_thap": db.scalar(select(func.count()).select_from(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.kind == "email", EnrichContact.is_inferred.is_(False))) or 0,
        "email_suy_luan": db.scalar(select(func.count()).select_from(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.is_inferred.is_(True))) or 0,
        "dien_thoai": db.scalar(select(func.count()).select_from(EnrichContact).where(EnrichContact.owner_type == "person", EnrichContact.kind == "phone")) or 0,
        "tu_choi": db.scalar(select(func.count()).select_from(OptOut)) or 0,
    }
    by_source = Counter(dict(db.execute(select(PersonEvidence.source_code, func.count()).group_by(PersonEvidence.source_code)).all()))
    access = db.execute(
        select(AccessLog.user_id, AccessLog.action, func.count(), func.sum(AccessLog.row_count))
        .where(AccessLog.created_at >= since)
        .group_by(AccessLog.user_id, AccessLog.action)
    ).all()
    users = {u.id: u for u in db.scalars(select(AdminUser))}
    exports = db.execute(
        select(ExportRecord.purpose, ExportRecord.status, func.count(), func.sum(ExportRecord.row_count))
        .where(ExportRecord.created_at >= since)
        .group_by(ExportRecord.purpose, ExportRecord.status)
    ).all()
    return {
        "lap_luc": utcnow().isoformat() + "Z",
        "loai_du_lieu": {
            "kho_b_truong": ["Họ tên", "Họ tên không dấu", "Năm sinh (nếu có)", "MST cá nhân (mã hoá, chỉ đối soát)", "Chức danh, thời gian giữ chức", "Email / điện thoại công việc (thu thập hoặc suy luận)"],
            "khong_thu_thap": ["CCCD / CMND", "Hộ khẩu, địa chỉ nhà", "Tài khoản ngân hàng", "Sức khoẻ", "Quan hệ gia đình"],
            "so_luong": counts,
        },
        "nguon": [
            {
                "ma": s.code,
                "ten": s.name,
                "dang_bat": s.enabled,
                "do_tin_cay": s.trust,
                "co_so_phap_ly": s.legal_basis,
                "so_bang_chung_nguoi": by_source.get(s.code, 0),
            }
            for s in srcs.values()
        ],
        "muc_dich": [
            {"ma": k, "ten": v, "so_lo": sum(1 for b in db.scalars(select(EnrichBatch)) if k in (b.purposes or []))}
            for k, v in PURPOSES.items()
        ],
        "thoi_han": {
            "du_lieu_ca_nhan_khong_dung_thang": int(cfg.enrich_retention_months),
            "ban_goc_ngay": int(cfg.enrich_raw_retention_days),
            "nhat_ky_truy_cap": "Không xoá (chỉ ghi thêm, tối thiểu 12 tháng)",
            "han_file_xuat_ngay": int(cfg.enrich_export_valid_days),
        },
        "bao_ve": {
            "ma_hoa_mst_ca_nhan": True,
            "ma_hoa_ban_goc": True,
            "khoa_rieng_da_dat": bool(cfg.enrich_data_key),
            "mo_hinh_ngon_ngu_ngoai": bool(cfg.enrich_llm_enabled),
        },
        "truy_cap_12_thang": [
            {
                "nguoi_dung": users[u].full_name if u in users else ("Hệ thống" if u is None else f"#{u}"),
                "vai_tro": ENRICH_ROLES.get(users[u].enrich_access or "", "—") if u in users else "—",
                "hanh_dong": a,
                "so_lan": n,
                "so_dong": int(r or 0),
            }
            for u, a, n, r in access
        ],
        "xuat_12_thang": [
            {"muc_dich": PURPOSES.get(p, p), "trang_thai": s, "so_lan": n, "so_dong": int(r or 0)} for p, s, n, r in exports
        ],
        "nguoi_duoc_cap_quyen": [
            {"ho_ten": u.full_name, "vai_tro": ENRICH_ROLES.get(u.enrich_access or "", "—")}
            for u in users.values()
            if u.is_active and u.enrich_access
        ],
    }


def access_logs(db: Session, action: str = "", user_id: int | None = None, since: date | None = None, limit: int = 200) -> list[dict]:
    stmt = select(AccessLog)
    if action:
        stmt = stmt.where(AccessLog.action == action)
    if user_id:
        stmt = stmt.where(AccessLog.user_id == user_id)
    if since:
        stmt = stmt.where(AccessLog.created_at >= since)
    users = {u.id: u.full_name for u in db.scalars(select(AdminUser))}
    return [
        {"id": a.id, "user": users.get(a.user_id, "Hệ thống") if a.user_id else "Hệ thống", "action": a.action, "target": a.target, "row_count": a.row_count, "ip": a.ip, "at": a.created_at.isoformat() + "Z"}
        for a in db.scalars(stmt.order_by(AccessLog.id.desc()).limit(limit))
    ]


def export_logs(db: Session, user_id: int | None = None, limit: int = 200) -> list[dict]:
    stmt = select(ExportRecord)
    if user_id:
        stmt = stmt.where(ExportRecord.user_id == user_id)
    users = {u.id: u.full_name for u in db.scalars(select(AdminUser))}
    return [
        {
            "id": e.id, "user": users.get(e.user_id, "—"), "purpose": PURPOSES.get(e.purpose, e.purpose), "columns": e.columns,
            "row_count": e.row_count, "blocked_count": e.blocked_count, "optout_count": e.optout_count,
            "include_inferred": e.include_inferred, "includes_kho_b": e.includes_kho_b, "status": e.status,
            "expires_on": e.expires_on.isoformat() if e.expires_on else None, "at": e.created_at.isoformat() + "Z",
        }
        for e in db.scalars(stmt.order_by(ExportRecord.id.desc()).limit(limit))
    ]

