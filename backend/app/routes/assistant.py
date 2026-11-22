"""Trợ lý LeadScan (chatbot hỏi đáp về hệ thống) — 3 cửa theo đối tượng, mỗi cửa dùng đúng cookie của cổng đó:

  POST /api/public/assistant         khách chưa đăng nhập (giới hạn theo IP)
  POST /api/member/assistant         thành viên (cookie ls_member) — có công cụ đọc dữ liệu của chính doanh nghiệp
  POST /api/partner/assistant        đối tác đã kích hoạt (cookie ls_partner) — có công cụ đọc dữ liệu của chính đối tác
  POST …/assistant/feedback          người dùng bấm hữu ích / chưa đúng (ghi log để rà soát kiến thức)

Body: {"messages": [{"role": "user"|"assistant", "content": "..."}], "page": "/duong-dan-dang-xem"}
Trả: {"id", "reply", "tools"}
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.assistant import engine
from app.assistant.tools import Ctx
from app.config import get_settings
from app.db import get_db
from app.member_auth import current_member
from app.models import MemberUser, PartnerUser
from app.partner_auth import verified_partner
from app.security import add_hit, client_ip, origin_allowed, rate_limited

log = logging.getLogger("leadscan.assistant")

public = APIRouter(prefix="/api/public/assistant")
member = APIRouter(prefix="/api/member/assistant")
partner = APIRouter(prefix="/api/partner/assistant")


def _guard(db: Session, request: Request, key: str, per_hour: int, monthly_key: str, monthly_limit: int) -> None:
    from app.services import usage

    cfg = get_settings()
    if not cfg.assistant_enabled:
        raise HTTPException(503, "Trợ lý đang tạm tắt.")
    if not origin_allowed(request, cfg):
        raise HTTPException(403, "Yêu cầu không hợp lệ.")
    if rate_limited(db, key, per_hour, timedelta(hours=1)):
        raise HTTPException(429, "Bạn hỏi hơi nhiều trong 1 giờ qua, nghỉ chút rồi hỏi tiếp nhé.")
    if not usage.reserve_call(monthly_key, monthly_limit):
        raise HTTPException(503, "Trợ lý đã hết lượt trả lời của tháng. Bạn vui lòng liên hệ LeadScan để được hỗ trợ trực tiếp.")
    add_hit(db, key)
    db.commit()


def _answer(ctx: Ctx, raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(400, "Dữ liệu gửi lên không hợp lệ.")
    try:
        history = engine.clean_history(raw.get("messages"))
        ans = engine.ask(ctx, history, engine.clean_page(raw.get("page")))
    except engine.AssistantError as e:
        raise HTTPException(e.status, str(e)) from None
    return {"id": ans.id, "reply": ans.text, "tools": ans.tools}


def _feedback(who: str, raw: dict | None) -> None:
    if not isinstance(raw, dict):
        raise HTTPException(400, "Dữ liệu gửi lên không hợp lệ.")
    log.info("assistant-feedback who=%s id=%s helpful=%s note=%s", who, str(raw.get("id") or "")[:20],
             bool(raw.get("helpful")), str(raw.get("note") or "")[:300].replace("\n", " "))


@public.post("")
def ask_public(request: Request, raw: dict | None = Body(None), db: Session = Depends(get_db)):
    cfg = get_settings()
    if not cfg.assistant_guest_enabled:
        raise HTTPException(503, "Trợ lý đang tạm tắt.")
    _guard(db, request, f"asst:ip:{client_ip(request, cfg)}", cfg.assistant_guest_per_hour, "assistant-guest", cfg.assistant_guest_monthly_limit)
    return _answer(Ctx(db, "guest"), raw)


@public.post("/feedback", status_code=204)
def feedback_public(request: Request, raw: dict | None = Body(None)):
    _feedback(f"ip:{client_ip(request, get_settings())}", raw)


@member.post("")
def ask_member(request: Request, raw: dict | None = Body(None), user: MemberUser = Depends(current_member), db: Session = Depends(get_db)):
    cfg = get_settings()
    _guard(db, request, f"asst:m:{user.id}", cfg.assistant_per_hour, "assistant", cfg.assistant_monthly_limit)
    return _answer(Ctx(db, "member", member=user), raw)


@member.post("/feedback", status_code=204)
def feedback_member(raw: dict | None = Body(None), user: MemberUser = Depends(current_member)):
    _feedback(f"m{user.id}", raw)


@partner.post("")
def ask_partner(request: Request, raw: dict | None = Body(None), p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    cfg = get_settings()
    _guard(db, request, f"asst:p:{p.id}", cfg.assistant_per_hour, "assistant", cfg.assistant_monthly_limit)
    return _answer(Ctx(db, "partner", partner=p), raw)


@partner.post("/feedback", status_code=204)
def feedback_partner(raw: dict | None = Body(None), p: PartnerUser = Depends(verified_partner)):
    _feedback(f"p{p.id}", raw)
