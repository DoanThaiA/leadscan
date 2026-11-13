"""API cổng đối tác: /api/partner/*  (tách hẳn /api/member — xem app/partner_auth.py)."""

import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.models import (
    PARTNER_KINDS,
    PARTNER_TIERS,
    SUBMISSION_CERTAINTY,
    SUBMISSION_KINDS,
    SUBMISSION_OPEN,
    SUBMISSION_SOURCES,
    SUBMISSION_STATUSES,
    PartnerEvent,
    PartnerPasswordReset,
    PartnerSubmission,
    PartnerUser,
)
from app import accounts
from app.partner_auth import create_session, current_partner, verified_partner
from app.registration_form import _EMAIL, AREAS, INDUSTRIES, clean1, pick_list
from app.schemas import LoginIn
from app.security import add_hit, client_ip, hash_password, origin_allowed, rate_limited, sha256, verify_password
from app.services import otp
from app.services import partner_submissions as subs
from app.services import partner_attachments, partner_wallet
from app.worker import enqueue, send_partner_password_reset_task, send_partner_welcome_task

router = APIRouter(prefix="/api/partner")

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ I, O, 0, 1 cho khỏi nhầm khi đọc qua điện thoại


def new_partner_code() -> str:
    return "DT-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def norm_phone(raw: object) -> str:
    """"+84 901 234 567" / "0901.234.567" → "0901234567"."""
    s = re.sub(r"[\s.\-()]", "", str(raw or ""))[:20]
    if s.startswith("+84"):
        s = "0" + s[3:]
    elif s.startswith("84") and len(s) >= 11:
        s = "0" + s[2:]
    return s


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def me_out(p: PartnerUser) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "email": p.email,
        "full_name": p.full_name,
        "phone": p.phone,
        "email_verified": bool(p.email_verified_at),
        "email_verified_at": _iso(p.email_verified_at),
        "kind": p.kind,
        "kind_label": PARTNER_KINDS.get(p.kind, p.kind),
        "org_name": p.org_name,
        "org_tax_code": p.org_tax_code,
        "industries": p.industries or [],
        "regions": p.regions or [],
        "tier": p.tier,
        "tier_label": PARTNER_TIERS.get(p.tier, p.tier),
        "created_at": _iso(p.created_at),
        "portals": accounts.portals_of(p),  # cùng email dùng được cổng nào (hiện nút chuyển cổng)
    }


def _fail(status: int, message: str, fields: dict | None = None) -> JSONResponse:
    return JSONResponse({"detail": message, "fields": fields or {}}, status_code=status)


# ================================================================== đăng ký


def normalize_signup(raw: dict) -> tuple[dict, dict[str, str]]:
    """Form đăng ký đối tác (7 trường — brief mục 7.2). Không hỏi CCCD/ngân hàng/MST cá nhân, không có mã giới thiệu."""
    d = {
        "full_name": clean1(raw.get("full_name"), 100),
        "phone": norm_phone(raw.get("phone")),
        "email": clean1(raw.get("email"), 150).lower(),
        "password": raw.get("password") if isinstance(raw.get("password"), str) else "",
        "kind": raw.get("kind") if raw.get("kind") in PARTNER_KINDS else "",
        "org_name": clean1(raw.get("org_name"), 200),
        "org_tax_code": re.sub(r"[^0-9\-]", "", clean1(raw.get("org_tax_code"), 20)),
        "industries": pick_list(raw.get("industries"), INDUSTRIES),
        "regions": pick_list(raw.get("regions"), AREAS),
    }
    e: dict[str, str] = {}
    if len(d["full_name"]) < 2:
        e["full_name"] = "Vui lòng nhập họ và tên."
    if not re.fullmatch(r"0\d{9,10}", d["phone"]):
        e["phone"] = "Số điện thoại chưa đúng định dạng."
    if not _EMAIL.match(d["email"]):
        e["email"] = "Email chưa đúng định dạng."
    if len(d["password"]) < 8 or len(d["password"]) > 200:
        e["password"] = "Mật khẩu cần ít nhất 8 ký tự."
    if not d["kind"]:
        e["kind"] = "Vui lòng chọn Cá nhân hoặc Tổ chức."
    if d["kind"] == "org":
        if not d["org_name"]:
            e["org_name"] = "Vui lòng nhập tên tổ chức."
        if not re.fullmatch(r"\d{10}(-?\d{3})?", d["org_tax_code"]):
            e["org_tax_code"] = "Mã số thuế gồm 10 hoặc 13 chữ số."
    else:
        d["org_name"] = d["org_tax_code"] = ""
    if raw.get("agree") is not True:
        e["agree"] = "Bạn cần đồng ý Điều khoản đối tác và Chính sách bảo mật."
    return d, e


@router.post("/auth/register", status_code=201)
def register(request: Request, response: Response, raw: dict | None = Body(None), db: Session = Depends(get_db)):
    cfg = get_settings()
    if not origin_allowed(request, cfg):
        return _fail(403, "Yêu cầu không hợp lệ.")
    if not isinstance(raw, dict):
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")
    if str(raw.get("website_url") or "").strip():  # honeypot: bot điền ô ẩn
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")
    try:
        elapsed = int(raw.get("elapsed_ms") or 0)
    except (TypeError, ValueError):
        elapsed = 0
    if elapsed < cfg.min_fill_ms:
        return _fail(429, "Bạn thao tác quá nhanh, vui lòng thử lại.")

    d, errors = normalize_signup(raw)
    if errors:
        return _fail(422, "Vui lòng kiểm tra lại thông tin.", errors)

    ip = client_ip(request, cfg)
    rl_key = "preg:" + sha256(ip)
    if rate_limited(db, rl_key, cfg.rate_limit_per_hour, timedelta(hours=1)):
        return _fail(429, "Bạn đã gửi quá nhiều lần. Vui lòng thử lại sau ít phút.")

    def taken_email():
        return _fail(409, "Email này đã có tài khoản đối tác. Vui lòng đăng nhập hoặc dùng email khác.", {"email": "Email đã có tài khoản đối tác."})

    def taken_phone():
        return _fail(409, "Số điện thoại này đã đăng ký đối tác. Mỗi số điện thoại chỉ dùng cho 1 tài khoản.", {"phone": "Số điện thoại đã đăng ký."})

    if db.scalar(select(PartnerUser.id).where(PartnerUser.email == d["email"])):
        return taken_email()
    if db.scalar(select(PartnerUser.id).where(PartnerUser.phone == d["phone"])):
        return taken_phone()

    # Email đã là thành viên → cùng 1 tài khoản: phải nhập đúng mật khẩu đang dùng, hồ sơ đối tác dùng chung mật khẩu đó
    password = d.pop("password")
    try:
        pw_hash = accounts.other_hash_for_signup(db, accounts.member_by_email(db, d["email"]), password) or hash_password(password)
    except ValueError:
        add_hit(db, rl_key)  # chặn dò mật khẩu qua form đăng ký
        db.commit()
        msg = "Email này đã có tài khoản thành viên LeadScan. Nhập đúng mật khẩu của tài khoản đó để dùng chung cho cổng đối tác."
        return _fail(409, msg, {"password": "Mật khẩu chưa khớp với tài khoản thành viên của email này."})
    p = None
    for _ in range(5):
        p = PartnerUser(
            code=new_partner_code(),
            password_hash=pw_hash,
            terms_version=cfg.partner_terms_version,
            terms_accepted_at=utcnow(),
            signup_ip=ip,
            signup_ua=request.headers.get("user-agent", "")[:300],
            **d,
        )
        db.add(p)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            p = None
            # Unique constraint chặn 2 request đồng thời cùng email/SĐT
            if db.scalar(select(PartnerUser.id).where(PartnerUser.email == d["email"])):
                return taken_email()
            if db.scalar(select(PartnerUser.id).where(PartnerUser.phone == d["phone"])):
                return taken_phone()
            continue  # trùng mã đối tác → sinh mã khác
        db.add(PartnerEvent(partner_id=p.id, kind="created", content=f"Đăng ký đối tác ({PARTNER_KINDS[p.kind]}) trên trang /doi-tac"))
        add_hit(db, rl_key)
        db.commit()
        break
    if p is None:
        return _fail(500, "Hệ thống bận, vui lòng thử lại.")

    create_session(db, p, request, response)  # đăng nhập luôn để nhập mã OTP (gửi qua email) ngay
    enqueue(send_partner_welcome_task, p.email, p.full_name, p.code)
    try:
        sent = otp.send(db, cfg, p)
    except HTTPException:
        sent = {"sent": False}
    return {"me": me_out(p), "otp": sent}


# ================================================================== đăng nhập


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    cfg = get_settings()
    if not origin_allowed(request, cfg):
        raise HTTPException(403, "Yêu cầu không hợp lệ.")
    key = "plogin:" + sha256(client_ip(request, cfg))
    if rate_limited(db, key, cfg.login_attempts_per_15min, timedelta(minutes=15)):
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.")
    # 1 tài khoản cho cả 2 cổng: mở phiên đối tác + phiên thành viên (nếu email có hồ sơ thành viên)
    member, p = accounts.authenticate(db, body.email, body.password)
    if not member and not p:
        add_hit(db, key)
        db.commit()
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    if p and not accounts.partner_usable(p):
        raise HTTPException(403, "Tài khoản đối tác đang bị khoá. Vui lòng liên hệ LeadScan.")
    if not p and not accounts.member_usable(member):
        raise HTTPException(403, "Tài khoản đang bị khoá. Vui lòng liên hệ LeadScan.")
    accounts.open_sessions(db, member, p, request, response)
    if not p:  # chỉ có hồ sơ thành viên → trang đăng nhập cho chọn vào cổng thành viên hoặc đăng ký đối tác
        return {"portals": {"member": True, "partner": False}, "redirect": accounts.MEMBER_HOME}
    return me_out(p)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    accounts.logout_all(db, request, response)  # đăng xuất cả cổng thành viên (cùng 1 tài khoản)


@router.get("/auth/me")
def me(p: PartnerUser = Depends(current_partner), db: Session = Depends(get_db)):
    out = me_out(p)
    out["otp_resend_after"] = 0 if p.email_verified_at else otp.resend_after(db, get_settings(), p.id)
    return out


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)  # khớp form đăng ký đối tác (brief: tối thiểu 8 ký tự)


@router.post("/auth/password", status_code=204)
def change_password(body: PasswordChangeIn, p: PartnerUser = Depends(current_partner), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, p.password_hash):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")
    accounts.sync_password(db, p.email, hash_password(body.new_password), end_sessions=False)  # áp dụng cả cổng thành viên
    db.add(PartnerEvent(partner_id=p.id, kind="password", content="Đối tác đổi mật khẩu"))
    db.commit()


class ForgotIn(BaseModel):
    email: str = Field(max_length=150)


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=200)


@router.post("/auth/forgot")
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Luôn trả cùng một thông báo để không lộ email nào có tài khoản."""
    cfg = get_settings()
    key = "pforgot:" + sha256(client_ip(request, cfg))
    if rate_limited(db, key, 5, timedelta(hours=1)):
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau.")
    add_hit(db, key)
    p = db.scalar(select(PartnerUser).where(PartnerUser.email == body.email.strip().lower(), PartnerUser.status == "active"))
    if p:
        token = secrets.token_urlsafe(32)
        db.add(PartnerPasswordReset(token_hash=sha256(token), partner_id=p.id, expires_at=utcnow() + timedelta(hours=1)))
        db.commit()
        enqueue(send_partner_password_reset_task, p.email, p.full_name, token)
    db.commit()
    return {"ok": True, "message": "Nếu email có tài khoản đối tác, chúng tôi đã gửi liên kết đặt lại mật khẩu (hiệu lực 60 phút)."}


@router.post("/auth/reset", status_code=204)
def reset(body: ResetIn, db: Session = Depends(get_db)):
    pr = db.scalar(select(PartnerPasswordReset).where(PartnerPasswordReset.token_hash == sha256(body.token)))
    if not pr or pr.used_at or pr.expires_at < utcnow():
        raise HTTPException(400, "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")
    p = db.get(PartnerUser, pr.partner_id)
    pr.used_at = utcnow()
    accounts.sync_password(db, p.email, hash_password(body.password), end_sessions=True)  # cả 2 cổng
    db.add(PartnerEvent(partner_id=p.id, kind="password", content="Đặt lại mật khẩu qua email"))
    db.commit()


# ================================================================== xác thực email (OTP)


class OtpVerifyIn(BaseModel):
    code: str = Field(min_length=4, max_length=10)


@router.post("/auth/otp/send")
def otp_send(request: Request, p: PartnerUser = Depends(current_partner), db: Session = Depends(get_db)):
    cfg = get_settings()
    key = "potp:" + sha256(client_ip(request, cfg))
    if rate_limited(db, key, 20, timedelta(hours=1)):
        raise HTTPException(429, "Bạn đã yêu cầu quá nhiều mã. Vui lòng thử lại sau.")
    add_hit(db, key)
    return otp.send(db, cfg, p)


@router.post("/auth/otp/verify")
def otp_verify(body: OtpVerifyIn, p: PartnerUser = Depends(current_partner), db: Session = Depends(get_db)):
    otp.verify(db, get_settings(), p, body.code)
    return me_out(p)


# ================================================================== danh mục cho form


@router.get("/options")
def options():
    """Danh mục dùng chung với cổng thành viên (ngành hàng, khu vực)."""
    return {"industries": INDUSTRIES, "regions": AREAS, "kinds": PARTNER_KINDS}


# ================================================================== cơ hội đối tác gửi (Mốc 2)


@router.get("/submission-options")
def submission_options(_: PartnerUser = Depends(verified_partner)):
    return {
        "industries": INDUSTRIES, "regions": AREAS, "kinds": SUBMISSION_KINDS, "sources": SUBMISSION_SOURCES,
        "certainty": SUBMISSION_CERTAINTY, "statuses": SUBMISSION_STATUSES,
    }


@router.post("/submissions", status_code=201)
def create_submission(raw: dict | None = Body(None), p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    if not isinstance(raw, dict):
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")
    d, errors = subs.normalize(raw)
    if errors:
        return _fail(422, "Vui lòng kiểm tra lại thông tin.", errors)
    ids = raw.get("attachment_ids") or []
    if not isinstance(ids, list):
        return _fail(422, "Danh sách ảnh không hợp lệ.")
    s = subs.create(db, get_settings(), p, d)
    if ids:
        try:
            purge = partner_attachments.link(db, p, s, ids)
        except HTTPException as e:
            # cơ hội đã lưu; ảnh lỗi thì báo nhưng không mất nội dung
            return {**_sub_out(db, s), "warning": f"Đã gửi cơ hội nhưng chưa gắn được ảnh: {e.detail}"}
        db.commit()
        _purge(purge)
    return _sub_out(db, s)


@router.put("/submissions/{sub_id}")
def update_submission(sub_id: int, raw: dict | None = Body(None), p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    """Sửa cơ hội khi LeadScan chưa bắt đầu xác minh (trạng thái Đã gửi)."""
    s = db.get(PartnerSubmission, sub_id)
    if not s or s.partner_id != p.id:
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    if not isinstance(raw, dict):
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")
    if not subs.editable(s):
        raise HTTPException(409, "LeadScan đã bắt đầu xác minh cơ hội này nên không sửa được nữa. Cần bổ sung thông tin? Liên hệ LeadScan.")
    d, errors = subs.normalize(raw)
    if errors:
        return _fail(422, "Vui lòng kiểm tra lại thông tin.", errors)
    changed = subs.update(db, get_settings(), p, s, d)
    s = db.get(PartnerSubmission, sub_id)
    if isinstance(raw.get("attachment_ids"), list):
        before = [a.id for a in partner_attachments.for_submission(db, s.id)]
        purge = partner_attachments.link(db, p, s, raw["attachment_ids"])
        if before != [int(i) for i in dict.fromkeys(raw["attachment_ids"])]:
            changed = [*changed, "Ảnh"]
            if changed == ["Ảnh"]:
                db.add(PartnerEvent(partner_id=p.id, submission_id=s.id, kind="sub_edited", content=f"Sửa cơ hội {s.code}: Ảnh"))
        db.commit()
        _purge(purge)
    return {**_sub_out(db, s), "changed": changed}


@router.get("/submissions")
def list_submissions(
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    p: PartnerUser = Depends(verified_partner),
    db: Session = Depends(get_db),
):
    stmt = select(PartnerSubmission).where(PartnerSubmission.partner_id == p.id)
    if status == "open":
        stmt = stmt.where(PartnerSubmission.status.in_(SUBMISSION_OPEN))
    elif status:
        stmt = stmt.where(PartnerSubmission.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PartnerSubmission.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    counts = dict(db.execute(select(PartnerSubmission.status, func.count()).where(PartnerSubmission.partner_id == p.id).group_by(PartnerSubmission.status)).all())
    items = [subs.partner_out(s, money=m, until=u) for s, m, u in subs.with_money(db, rows)]
    return {"total": total, "page": page, "page_size": page_size, "items": items, "counts": counts}


@router.get("/submissions/{sub_id}")
def get_submission(sub_id: int, p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    s = db.get(PartnerSubmission, sub_id)
    if not s or s.partner_id != p.id:
        raise HTTPException(404, "Không tìm thấy cơ hội.")
    events = db.scalars(select(PartnerEvent).where(PartnerEvent.submission_id == s.id).order_by(PartnerEvent.id)).unique().all()
    # Đối tác chỉ thấy các mốc trạng thái, không thấy ai giao việc cho ai
    events = [e for e in events if e.kind in ("sub_created", "sub_edited", "sub_verifying", "sub_decided", "sub_published", "credit", "cafe_quota")]
    (_, money, until), = subs.with_money(db, [s])
    return {**subs.partner_out(s, events, money=money, until=until), "images": [partner_attachments.out(a) for a in partner_attachments.for_submission(db, s.id)]}


@router.get("/dashboard")
def dashboard(p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    st = subs.partner_stats(db, p.id)
    recent = db.scalars(select(PartnerSubmission).where(PartnerSubmission.partner_id == p.id).order_by(PartnerSubmission.id.desc()).limit(5)).unique().all()
    by = st["by_status"]
    partner_wallet.release_due(db, p.id)
    money = partner_wallet.submission_money(db, list(db.scalars(select(PartnerSubmission.id).where(PartnerSubmission.partner_id == p.id))))
    return {
        "wallet": partner_wallet.wallet_summary(db, p),
        "sent": st["total"],
        "open": sum(by.get(k, 0) for k in SUBMISSION_OPEN),
        "ok": st["ok"] + by.get("supplement", 0),  # đạt xác minh (kể cả đã xuất bản, đóng góp bổ sung)
        "published": by.get("published", 0),
        "not_ok": by.get("rejected", 0) + by.get("duplicate", 0),
        "sold": sum(1 for m in money.values() if m["sold"] > 0),  # cơ hội có ≥ 1 lượt bán
        "recent": [subs.partner_out(s, money=m, until=u) for s, m, u in subs.with_money(db, recent)],
    }


# ================================================================== ví hoa hồng (Mốc 3)


@router.get("/wallet")
def wallet(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    p: PartnerUser = Depends(verified_partner),
    db: Session = Depends(get_db),
):
    from app.models import PartnerCredit

    partner_wallet.release_due(db, p.id)
    stmt = select(PartnerCredit).where(PartnerCredit.partner_id == p.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PartnerCredit.id.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {"summary": partner_wallet.wallet_summary(db, p), "total": total, "page": page, "page_size": page_size,
            "items": [partner_wallet.credit_out(c) for c in rows]}


@router.get("/reward-config")
def reward_config(db: Session = Depends(get_db)):
    """Mức thưởng hiện hành (công khai) — landing, chính sách, điều khoản hiển thị đúng cấu hình đang áp dụng."""
    st = partner_wallet.settings(db)
    return {
        "cafe": st["cafe_amount"], "mode": st["reward_mode"], "rate": st["rate_new"], "rate_silver": st["rate_silver"],
        "rate_large": st["rate_large"], "rate_max": st["rate_max"], "hold_days": st["hold_days"], "months": st["share_months"],
        "quota_new": st["cafe_quota_new"], "quota_silver": st["cafe_quota_silver"],
        "min_withdraw": st["min_withdraw"], "payout_days": st["payout_days"], "tax_threshold": st["tax_threshold"], "tax_rate": st["tax_rate"],
    }


# ================================================================== hồ sơ thanh toán & rút tiền (Mốc 4)


@router.get("/banks")
def banks(_: PartnerUser = Depends(verified_partner)):
    from app.services.partner_payouts import BANKS

    return {"banks": [{"bin": k, "name": v} for k, v in BANKS.items()]}


@router.get("/payout-profile")
def get_payout_profile(p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    from app.services import partner_payouts as pay

    return {"profile": pay.profile_out(pay.get_profile(db, p.id)), "kind": p.kind, "org_name": p.org_name, "org_tax_code": p.org_tax_code}


@router.put("/payout-profile")
def put_payout_profile(raw: dict | None = Body(None), p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    from app.services import partner_payouts as pay

    if not isinstance(raw, dict):
        return _fail(400, "Dữ liệu gửi lên không hợp lệ.")
    try:
        prof = pay.save_profile(db, p, raw)
    except pay.FieldsError as e:
        return _fail(422, e.message, e.fields)
    return {"profile": pay.profile_out(prof), "kind": p.kind, "org_name": p.org_name, "org_tax_code": p.org_tax_code}


@router.get("/withdrawals")
def list_withdrawals(p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    from app.models import PartnerWithdrawal
    from app.services import partner_payouts as pay

    partner_wallet.release_due(db, p.id)
    rows = db.scalars(select(PartnerWithdrawal).where(PartnerWithdrawal.partner_id == p.id).order_by(PartnerWithdrawal.id.desc()).limit(100)).unique().all()
    return {"summary": partner_wallet.wallet_summary(db, p), "rules": pay.rules(db, p),
            "profile": pay.profile_out(pay.get_profile(db, p.id)), "items": [pay.withdrawal_out(w) for w in rows]}


class WithdrawIn(BaseModel):
    amount: int = Field(gt=0, le=10_000_000_000)


@router.post("/withdrawals", status_code=201)
def create_withdrawal(body: WithdrawIn, p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    from app.services import partner_payouts as pay

    return pay.withdrawal_out(pay.request(db, p, body.amount))


@router.post("/withdrawals/{wid}/cancel")
def cancel_withdrawal(wid: int, p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    from app.models import PartnerWithdrawal
    from app.services import partner_payouts as pay

    w = db.get(PartnerWithdrawal, wid)
    if not w:
        raise HTTPException(404, "Không tìm thấy lệnh rút.")
    pay.cancel(db, p, w)
    return pay.withdrawal_out(w)


# ================================================================== ảnh gắn vào cơ hội gửi


def _sub_out(db: Session, s: PartnerSubmission) -> dict:
    return {**subs.partner_out(s), "images": [partner_attachments.out(a) for a in partner_attachments.for_submission(db, s.id)]}


def _purge(keys: list[str]) -> None:
    if keys:
        from app.worker import purge_files_task

        if not enqueue(purge_files_task, keys):
            purge_files_task.apply(args=[keys])


@router.get("/attachments/config")
def attachment_config(_: PartnerUser = Depends(verified_partner)):
    return partner_attachments.config()


class AttachInitIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)


@router.post("/attachments/init", status_code=201)
def attachment_init(body: AttachInitIn, p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    a, url = partner_attachments.init_upload(db, p, body.filename, body.size)
    return {"id": a.id, "upload_url": url, "content_type": a.content_type}


@router.post("/attachments/{att_id}/complete")
def attachment_complete(att_id: int, p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    from app.models import PartnerAttachment

    a = db.get(PartnerAttachment, att_id)
    if not a:
        raise HTTPException(404, "Không tìm thấy ảnh.")
    return partner_attachments.out(partner_attachments.complete_upload(db, p, a))
