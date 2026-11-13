"""API công khai cho landing page."""

import json
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app import accounts
from app.config import Settings, get_settings
from app.db import new_session
from app.models import Activity, Company, Contact, MemberUser, Profile
from app.registration_form import normalize, tax_key
from app.security import add_hit, client_ip, hash_password, origin_allowed, rate_limited, sha256
from app.worker import enqueue_new_registration

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
MAX_BODY = 64 * 1024

router = APIRouter(prefix="/api")


class ApiError(Exception):
    def __init__(self, status: int, message: str, fields: dict | None = None):
        self.status, self.message, self.fields = status, message, fields or {}


def fail(status: int, message: str, fields: dict | None = None) -> JSONResponse:
    return JSONResponse(
        {"ok": False, "message": message, "fields": fields or {}},
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


def new_code() -> str:
    return f"LS-{datetime.now(VN_TZ):%Y%m%d}-{secrets.token_hex(3).upper()}"


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.post("/registrations")
async def create_registration(request: Request):
    cfg = get_settings()

    if not origin_allowed(request, cfg):
        return fail(403, "Yêu cầu không hợp lệ.")
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        return fail(413, "Dữ liệu gửi lên quá lớn.")
    body = await request.body()
    try:
        data = json.loads(body[:MAX_BODY] or b"null")
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return fail(400, "Dữ liệu gửi lên không hợp lệ.")

    # Honeypot: bot điền ô ẩn → giả vờ thành công, không lưu gì
    if str(data.get("website_url") or "").strip():
        return {"ok": True, "code": f"LS-{datetime.now(VN_TZ):%Y%m%d}-000000"}
    # Thiếu hoặc quá nhanh đều coi là bot
    try:
        elapsed = int(data.get("elapsed_ms") or 0)
    except (TypeError, ValueError):
        elapsed = 0
    if elapsed < cfg.min_fill_ms:
        return fail(429, "Bạn thao tác quá nhanh, vui lòng thử lại.")

    ip = client_ip(request, cfg)
    ua = request.headers.get("user-agent", "")[:300]
    try:
        company_id, code = await run_in_threadpool(_save, data, ip, ua, cfg)
    except ApiError as e:
        return fail(e.status, e.message, e.fields)

    await run_in_threadpool(enqueue_new_registration, company_id)  # email báo quản trị (chạy nền)
    return JSONResponse({"ok": True, "code": code}, headers={"Cache-Control": "no-store"})


def _save(data: dict, ip: str, ua: str, cfg: Settings) -> tuple[int, str]:
    d, errors = normalize(data)
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    if len(password) < 8 or len(password) > 200:
        errors["password"] = "Mật khẩu cần ít nhất 8 ký tự."
    elif data.get("password_confirm") != password:
        errors["password_confirm"] = "Mật khẩu nhập lại không khớp."
    if errors:
        raise ApiError(422, "Vui lòng kiểm tra lại thông tin.", errors)
    pw_hash = hash_password(password)

    rl_key = "reg:" + sha256(ip)
    tkey = tax_key(d["tax_code"])

    with new_session() as db:
        if rate_limited(db, rl_key, cfg.rate_limit_per_hour, timedelta(hours=1)):
            raise ApiError(429, "Bạn đã gửi quá nhiều lần. Vui lòng thử lại sau ít phút.")
        if db.scalar(select(Company.id).where(Company.tax_key == tkey)):
            raise ApiError(409, *DUP_TAX)
        if db.scalar(select(MemberUser.id).where(MemberUser.email == d["email"])):
            raise ApiError(
                409,
                "Email này đã có tài khoản LeadScan. Vui lòng đăng nhập hoặc dùng email khác.",
                {"email": "Email đã có tài khoản."},
            )
        # Email đã là đối tác → cùng 1 tài khoản: phải nhập đúng mật khẩu đang dùng, hồ sơ thành viên dùng chung mật khẩu đó
        try:
            pw_hash = accounts.other_hash_for_signup(db, accounts.partner_by_email(db, d["email"]), password) or pw_hash
        except ValueError:
            add_hit(db, rl_key)  # chặn dò mật khẩu qua form đăng ký
            db.commit()
            raise ApiError(
                409,
                "Email này đã có tài khoản đối tác LeadScan. Nhập đúng mật khẩu của tài khoản đó để dùng chung cho cổng thành viên.",
                {"password": "Mật khẩu chưa khớp với tài khoản đối tác của email này."},
            ) from None

        company = insert_member(db, d, pw_hash, ip, ua, source="landing", activity="Đăng ký thành viên trên landing page",
                                before_commit=lambda: add_hit(db, rl_key))
        return company.id, company.code


DUP_TAX = ("Mã số thuế này đã được đăng ký. Nếu cần hỗ trợ, vui lòng liên hệ LeadScan.", {"tax_code": "Mã số thuế đã được đăng ký."})


def insert_member(db, d: dict, pw_hash: str, ip: str, ua: str, *, source: str, activity: str, before_commit=None) -> Company:
    """Tạo doanh nghiệp + người liên hệ chính + chân dung + tài khoản thành viên từ dữ liệu đã chuẩn hoá (normalize()).

    Dùng chung cho form đăng ký trên web và webhook nhận đăng ký (routes/registration_webhook.py).
    Trùng MST / email (kể cả 2 request đồng thời) → ApiError 409.
    """
    tkey = tax_key(d["tax_code"])
    for _ in range(5):
        company = Company(
            code=new_code(),
            name=d["company_name"],
            tax_code=d["tax_code"],
            tax_key=tkey,
            industry=d["industry"],
            company_size=d["company_size"],
            province=d["province"],
            address=d["address"],
            website=d["website"],
            source=source,
            ip=ip,
            user_agent=ua,
        )
        company.contacts.append(
            Contact(full_name=d["contact_name"], position=d["position"], email=d["email"], phone=d["phone"], is_primary=True)
        )
        company.profile = Profile(
            # ngành hàng đã chọn khi đăng ký → gợi ý sẵn cho "Tìm cơ hội phù hợp"
            search={"industries": d["industries"]},
            offering=d["offering"],
            target_customers=d["target_customers"],
            target_regions=d["target_regions"],
            opp_types=d["opp_types"],
            expected_tickets=d["expected_tickets"],
            notes=d["notes"],
        )
        company.activities.append(Activity(kind="created", content=activity[:500]))
        db.add(company)
        try:
            db.flush()
            db.add(MemberUser(company_id=company.id, email=d["email"], full_name=d["contact_name"], password_hash=pw_hash))
            if before_commit:
                before_commit()
            db.commit()
            return company
        except IntegrityError:
            db.rollback()
            # Unique constraint đảm bảo 2 request đồng thời cùng MST/email không lọt qua
            if db.scalar(select(Company.id).where(Company.tax_key == tkey)):
                raise ApiError(409, *DUP_TAX) from None
            if db.scalar(select(MemberUser.id).where(MemberUser.email == d["email"])):
                raise ApiError(409, "Email này đã có tài khoản LeadScan.", {"email": "Email đã có tài khoản."}) from None
            # còn lại là trùng mã đăng ký → sinh mã khác
    raise ApiError(500, "Hệ thống bận, vui lòng thử lại.")
