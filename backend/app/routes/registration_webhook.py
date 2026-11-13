"""Webhook nhận đăng ký thành viên từ hệ thống ngoài: POST /api/registrations/webhook

Dùng khi khách đăng ký ở nơi khác (landing page riêng, form quảng cáo qua n8n / Zapier / Make, CRM…) và cần tạo
hồ sơ thành viên LeadScan giống như đăng ký trên web.

Xác thực: header  Authorization: Bearer <LEADSCAN_REGISTRATION_WEBHOOK_SECRET>   (khoá trống = webhook tắt → 404).

Body JSON (cùng tên trường với form đăng ký trên web):
  bắt buộc : company_name, tax_code (10 hoặc 13 số), contact_name, email, phone
  tuỳ chọn : position, province, address, website, company_size, industries [..], notes,
             password (≥ 8 ký tự — không gửi thì khách nhận email tự đặt mật khẩu),
             source (tên nguồn, vd "facebook-ads" — lưu vào hồ sơ để biết khách đến từ đâu)
  Bên gửi chịu trách nhiệm đã có sự đồng ý của khách (không cần trường agree).

Kết quả:
  201 {"ok": true, "code", "company_id", "account": "created" | "shared_with_partner", "password_setup_email": bool}
  200 {"ok": true, "duplicate": true, "code", "company_id"}  gửi lại đúng đăng ký đã có (cùng MST + email) — an toàn khi retry
  401 sai khoá · 409 MST / email đã thuộc khách khác · 422 dữ liệu sai (fields: {trường: lỗi})
"""

import hmac
import json
import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app import accounts
from app.config import Settings, get_settings
from app.db import new_session, utcnow
from app.models import Company, Contact, MemberUser, PasswordReset
from app.registration_form import SIZES, normalize, tax_key
from app.routes.public import MAX_BODY, ApiError, fail, insert_member
from app.security import add_hit, client_ip, hash_password, rate_limited, sha256, verify_password
from app.worker import enqueue, notify_new_registration_task, send_account_setup_task, send_welcome_task

router = APIRouter(prefix="/api/registrations")

# Webhook không bắt buộc các trường chỉ có trên form web (ngành, quy mô, tỉnh, đồng ý điều khoản)
OPTIONAL_HERE = {"industries", "company_size", "province", "agree"}


def _authorized(request: Request, secret: str) -> bool:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
    return bool(token) and hmac.compare_digest(token.encode(), secret.encode())


def _source(raw: object) -> str:
    name = re.sub(r"[^a-z0-9_.-]+", "-", str(raw or "").strip().lower()).strip("-")[:30]
    return f"webhook:{name}" if name else "webhook"


@router.post("/webhook")
async def registration_webhook(request: Request):
    cfg = get_settings()
    if not cfg.registration_webhook_secret:
        return fail(404, "Webhook đăng ký chưa được bật.")
    ip = client_ip(request, cfg)
    denied = await run_in_threadpool(_auth_gate, ip, _authorized(request, cfg.registration_webhook_secret))
    if denied:
        return denied
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        return fail(413, "Dữ liệu gửi lên quá lớn.")
    body = await request.body()
    try:
        data = json.loads(body[:MAX_BODY] or b"null")
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return fail(400, "Body phải là JSON object.")

    ua = request.headers.get("user-agent", "")[:300]
    try:
        out = await run_in_threadpool(_save, data, ip, ua, cfg)
    except ApiError as e:
        return fail(e.status, e.message, e.fields)
    if out.get("duplicate"):
        return JSONResponse(out, status_code=200, headers={"Cache-Control": "no-store"})
    return JSONResponse(out, status_code=201, headers={"Cache-Control": "no-store"})


def _auth_gate(ip: str, ok: bool) -> JSONResponse | None:
    """IP sai khoá quá 20 lần / 15 phút → 429 (kể cả khi lần này đúng khoá) để chặn dò khoá."""
    key = "rwh:" + sha256(ip)
    with new_session() as db:
        if rate_limited(db, key, 20, timedelta(minutes=15)):
            return fail(429, "Sai khoá quá nhiều lần. Vui lòng thử lại sau 15 phút.")
        if not ok:
            add_hit(db, key)
            db.commit()
            return fail(401, "Sai hoặc thiếu khoá webhook (Authorization: Bearer <khoá>).")
    return None


def _save(data: dict, ip: str, ua: str, cfg: Settings) -> dict:
    d, errors = normalize({**data, "agree": True})
    for f in OPTIONAL_HERE:
        errors.pop(f, None)
    if d["company_size"] not in SIZES:
        d["company_size"] = ""
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    if password and not 8 <= len(password) <= 200:
        errors["password"] = "Mật khẩu cần ít nhất 8 ký tự (hoặc bỏ trống để khách tự đặt qua email)."
    if errors:
        raise ApiError(422, "Vui lòng kiểm tra lại thông tin.", errors)
    source = _source(data.get("source"))

    with new_session() as db:
        tkey = tax_key(d["tax_code"])
        existing = db.scalar(select(Company).where(Company.tax_key == tkey))
        if existing:
            # retry của bên gửi: cùng MST + cùng email → trả lại đăng ký cũ, không tạo trùng
            emails = {c.email for c in db.scalars(select(Contact).where(Contact.company_id == existing.id))}
            emails |= set(db.scalars(select(MemberUser.email).where(MemberUser.company_id == existing.id)))
            if d["email"] in emails:
                return {"ok": True, "duplicate": True, "code": existing.code, "company_id": existing.id}
            raise ApiError(409, "Mã số thuế này đã được đăng ký.", {"tax_code": "Mã số thuế đã được đăng ký."})
        if accounts.member_by_email(db, d["email"]):
            raise ApiError(409, "Email này đã có tài khoản thành viên LeadScan.", {"email": "Email đã có tài khoản."})

        # Cùng email với đối tác = cùng 1 tài khoản (app/accounts.py): dùng mật khẩu đối tác đang dùng
        partner = accounts.partner_by_email(db, d["email"])
        setup_token = ""
        if partner:
            if password and not verify_password(password, partner.password_hash):
                raise ApiError(409, "Email này đã là đối tác LeadScan với mật khẩu khác — bỏ trống password để dùng chung tài khoản.",
                               {"password": "Mật khẩu không khớp tài khoản đối tác của email này."})
            pw_hash = partner.password_hash
        elif password:
            pw_hash = hash_password(password)
        else:
            pw_hash = hash_password(secrets.token_urlsafe(32))  # mật khẩu ngẫu nhiên không ai biết → khách tự đặt qua email
            setup_token = secrets.token_urlsafe(32)

        label = source.removeprefix("webhook").lstrip(":")
        company = insert_member(db, d, pw_hash, ip, ua, source=source,
                                activity="Đăng ký thành viên qua webhook" + (f" (nguồn: {label})" if label else ""))
        if setup_token:
            user = db.scalar(select(MemberUser).where(MemberUser.company_id == company.id))
            db.add(PasswordReset(token_hash=sha256(setup_token), user_id=user.id,
                                 expires_at=utcnow() + timedelta(days=cfg.registration_setup_days)))
            db.commit()
        company_id, code = company.id, company.code

    enqueue(notify_new_registration_task, company_id)  # email báo quản trị như đăng ký trên web
    if setup_token:
        enqueue(send_account_setup_task, company_id, setup_token)  # chào mừng + link đặt mật khẩu
    else:
        enqueue(send_welcome_task, company_id)
    return {
        "ok": True,
        "code": code,
        "company_id": company_id,
        "account": "shared_with_partner" if partner else "created",
        "password_setup_email": bool(setup_token),
    }
