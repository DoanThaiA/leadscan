"""API backend LeadScan (landing/admin giao diện do Next.js trong web/ phục vụ).

Chạy dev:   uv run uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routes import admin, admin_commerce, admin_jobs, admin_knowledge, admin_partner_payouts, admin_partner_reports, admin_partner_submissions, admin_partners, careers, mcv, member, partner, payments, public

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="LeadScan B2B", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(admin_commerce.router)
app.include_router(admin_knowledge.router)
app.include_router(admin_jobs.router)
app.include_router(careers.router)
app.include_router(member.router)
app.include_router(partner.router)
app.include_router(admin_partners.router)
app.include_router(admin_partners.settings_router)
app.include_router(admin_partner_submissions.router)
app.include_router(admin_partner_payouts.router)
app.include_router(admin_partner_payouts.batches)
app.include_router(admin_partner_reports.router)
app.include_router(payments.router)
app.include_router(mcv.router)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    """Lỗi dữ liệu → {"detail": ..., "fields": {tên_trường: thông báo}} để form hiển thị cạnh từng ô."""
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
        msg = str(err.get("msg", "Không hợp lệ")).removeprefix("Value error, ")
        fields.setdefault(".".join(loc) or "_", msg)
    return JSONResponse({"detail": "Vui lòng kiểm tra lại thông tin.", "fields": fields}, status_code=422)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if request.url.path.startswith(("/api/admin", "/api/member", "/api/partner")):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp
