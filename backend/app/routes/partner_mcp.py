"""Kết nối AI cho đối tác: MCP server (Streamable HTTP) để đăng & theo dõi cơ hội qua Claude, ChatGPT…

- Đối tác tạo URL kết nối trong cổng (/doi-tac/ket-noi-ai): https://<site>/api/mcp/<khoá>. Khoá nằm trong URL vì Claude.ai và
  ChatGPT chỉ nhận URL (không cho thêm header). Ứng dụng nhận header (Claude Code, Cursor…) dùng /api/mcp + "Authorization: Bearer <khoá>".
- DB chỉ lưu sha256 của khoá; URL hiện đúng 1 lần khi tạo. Tạo URL mới = thu hồi URL cũ.
- Server không giữ phiên: mỗi POST là 1 thông điệp JSON-RPC, trả application/json. GET (luồng SSE) → 405 theo đặc tả.
- Công cụ dùng lại đúng logic form cổng (partner_submissions.normalize / create): cùng kiểm tra, giới hạn/ngày, lọc trùng, chấm điểm.
"""

import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.models import (
    SUBMISSION_CERTAINTY,
    SUBMISSION_KINDS,
    SUBMISSION_OPEN,
    SUBMISSION_SOURCES,
    SUBMISSION_STATUSES,
    PartnerEvent,
    PartnerMcpToken,
    PartnerSubmission,
    PartnerUser,
)
from app.partner_auth import verified_partner
from app.registration_form import AREAS, INDUSTRIES
from app.security import origin_allowed, sha256
from app.services import partner_submissions as subs
from app.services import partner_wallet

portal = APIRouter(prefix="/api/partner/mcp")  # quản lý URL kết nối trong cổng (cookie đối tác)
router = APIRouter(prefix="/api/mcp")  # MCP server (khoá trong URL hoặc Bearer)

TOKEN_PREFIX = "lsm_"
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "leadscan-doi-tac", "title": "LeadScan – Đối tác", "version": "1.0.0"}
VIA = "kết nối AI"


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def mcp_url(token: str) -> str:
    return f"{get_settings().site_url.rstrip('/')}/api/mcp/{token}"


# ================================================================== cổng đối tác: tạo / thu hồi URL


def _active(db: Session, partner_id: int) -> PartnerMcpToken | None:
    return db.scalar(
        select(PartnerMcpToken).where(PartnerMcpToken.partner_id == partner_id, PartnerMcpToken.revoked_at.is_(None))
        .order_by(PartnerMcpToken.id.desc())
    )


def _token_out(t: PartnerMcpToken | None) -> dict:
    if not t:
        return {"active": False}
    return {"active": True, "hint": t.hint, "created_at": _iso(t.created_at), "last_used_at": _iso(t.last_used_at), "last_client": t.last_client}


def _revoke_all(db: Session, partner_id: int) -> int:
    rows = db.scalars(select(PartnerMcpToken).where(PartnerMcpToken.partner_id == partner_id, PartnerMcpToken.revoked_at.is_(None))).all()
    for t in rows:
        t.revoked_at = utcnow()
    return len(rows)


@portal.get("")
def mcp_status(p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    return {**_token_out(_active(db, p.id)), "endpoint": f"{get_settings().site_url.rstrip('/')}/api/mcp"}


@portal.post("/token", status_code=201)
def mcp_create(p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    """Tạo URL kết nối mới (thu hồi URL cũ nếu có). URL đầy đủ chỉ trả về 1 lần này."""
    replaced = _revoke_all(db, p.id)
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    t = PartnerMcpToken(partner_id=p.id, token_hash=sha256(token), hint=token[-4:], created_at=utcnow())
    db.add(t)
    db.add(PartnerEvent(partner_id=p.id, kind="mcp_token", content="Tạo URL kết nối AI mới" + (" (URL cũ đã bị thu hồi)" if replaced else "")))
    db.commit()
    db.refresh(t)
    return {**_token_out(t), "url": mcp_url(token), "token": token}


@portal.delete("/token", status_code=204)
def mcp_revoke(p: PartnerUser = Depends(verified_partner), db: Session = Depends(get_db)):
    if _revoke_all(db, p.id):
        db.add(PartnerEvent(partner_id=p.id, kind="mcp_token", content="Thu hồi URL kết nối AI"))
        db.commit()
    return Response(status_code=204)


# ================================================================== công cụ MCP

_KIND_DESC = "; ".join(f"{k} = {v}" for k, v in SUBMISSION_KINDS.items())
_SOURCE_DESC = "; ".join(f"{k} = {v}" for k, v in SUBMISSION_SOURCES.items())
_CERT_DESC = "; ".join(f"{k} = {v}" for k, v in SUBMISSION_CERTAINTY.items())

_SUBMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Tiêu đề ngắn (10–150 ký tự), vd: Nhà máy điện tử Quế Võ cần 20.000 thùng carton 5 lớp/tháng."},
        "company_name": {"type": "string", "description": "Tên doanh nghiệp có nhu cầu mua (bên mua)."},
        "tax_code": {"type": "string", "description": "Mã số thuế bên mua, 10 hoặc 13 số. Để trống nếu chưa biết — không đoán."},
        "province": {"type": "string", "description": "Tỉnh/thành hoặc khu vực, vd: " + ", ".join(AREAS[:12]) + "…"},
        "industry": {"type": "string", "enum": INDUSTRIES, "description": "Ngành hàng của nhu cầu (chọn đúng 1 giá trị trong danh sách)."},
        "kind": {"type": "string", "enum": list(SUBMISSION_KINDS), "description": "Loại cơ hội: " + _KIND_DESC},
        "need": {"type": "string", "description": "Mô tả nhu cầu cụ thể (≥ 30 ký tự): mặt hàng/dịch vụ, quy cách, quy mô, thời điểm, yêu cầu nhà cung cấp. Không dán danh sách SĐT/email."},
        "scale": {"type": "string", "description": "Quy mô / số lượng / giá trị ước tính, vd: 20.000 thùng/tháng."},
        "timing": {"type": "string", "description": "Thời điểm cần, vd: Từ tháng 1/2027."},
        "source_type": {"type": "string", "enum": list(SUBMISSION_SOURCES), "description": "Nguồn biết tin: " + _SOURCE_DESC + ". Nguồn công khai bắt buộc có source_url."},
        "source_url": {"type": "string", "description": "Link nguồn (http/https) nếu có."},
        "certainty": {"type": "string", "enum": list(SUBMISSION_CERTAINTY), "description": "Độ chắc chắn: " + _CERT_DESC},
        "evidence": {"type": "string", "description": "Bằng chứng / ghi chú thêm cho người duyệt (không bắt buộc)."},
        "contact_name": {"type": "string", "description": "Người liên hệ bên mua — CHỈ điền khi người đó đồng ý được giới thiệu hoặc là liên hệ công khai."},
        "contact_title": {"type": "string", "description": "Chức danh người liên hệ."},
        "contact_phone": {"type": "string", "description": "SĐT người liên hệ (0xxxxxxxxx hoặc +84…)."},
        "contact_email": {"type": "string", "description": "Email người liên hệ."},
        "contact_consent": {"type": "boolean", "description": "true khi người liên hệ đồng ý được giới thiệu / là liên hệ công khai. Bắt buộc true nếu có điền người liên hệ."},
        "can_connect": {"type": "string", "enum": ["yes", "no"], "description": "Đối tác có thể giới thiệu trực tiếp LeadScan/nhà cung cấp với bên mua không."},
        "commitment": {
            "type": "boolean",
            "description": "Cam kết của đối tác: thông tin hợp pháp, không vi phạm bảo mật nơi làm việc, không phải dữ liệu mua bán. "
                           "Chỉ đặt true khi chính người dùng đã xác nhận cam kết này trong cuộc trò chuyện.",
        },
    },
    "required": ["title", "company_name", "province", "industry", "kind", "need", "source_type", "certainty", "commitment"],
    "additionalProperties": False,
}

TOOLS = [
    {
        "name": "get_submission_guide",
        "title": "Hướng dẫn đăng cơ hội",
        "description": "Xem quy định đăng cơ hội lên sàn LeadScan: cơ hội nào được nhận, danh mục ngành/khu vực/loại/nguồn, mức thưởng hiện hành "
                       "và số cơ hội còn được đăng hôm nay. Gọi trước khi đăng cơ hội đầu tiên.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"title": "Hướng dẫn đăng cơ hội", "readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "submit_opportunity",
        "title": "Đăng cơ hội lên LeadScan",
        "description": "Đăng 1 cơ hội kinh doanh B2B (một doanh nghiệp đang có nhu cầu mua) lên sàn LeadScan dưới tên đối tác đang kết nối. "
                       "LeadScan kiểm trùng, xác minh và chấm điểm trong khoảng 2 ngày làm việc; cơ hội đạt được mở bán cho người mua và đối tác nhận thưởng. "
                       "QUY TẮC: chỉ dùng thông tin người dùng cung cấp, không tự bịa hay đoán (MST, người liên hệ…); thiếu trường bắt buộc thì hỏi lại. "
                       "Trước khi gọi, tóm tắt lại toàn bộ nội dung sẽ gửi và hỏi người dùng xác nhận cùng lời cam kết. "
                       "Nếu kết quả báo lỗi theo từng trường, sửa đúng các trường đó (hỏi người dùng nếu cần) rồi gọi lại.",
        "inputSchema": _SUBMIT_SCHEMA,
        "annotations": {"title": "Đăng cơ hội lên LeadScan", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "list_my_opportunities",
        "title": "Cơ hội của tôi",
        "description": "Liệt kê các cơ hội đối tác đã đăng, mới nhất trước: mã, tiêu đề, trạng thái xác minh, điểm, số lượt bán và tiền thưởng đã ghi.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["", "open", *SUBMISSION_STATUSES], "description": "Lọc trạng thái: open = đang chờ/đang xác minh; " + "; ".join(f"{k} = {v}" for k, v in SUBMISSION_STATUSES.items()) + ". Bỏ trống = tất cả."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Số cơ hội tối đa (mặc định 10)."},
            },
            "additionalProperties": False,
        },
        "annotations": {"title": "Cơ hội của tôi", "readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "get_opportunity",
        "title": "Chi tiết cơ hội",
        "description": "Xem chi tiết và lịch sử trạng thái của 1 cơ hội đối tác đã đăng, theo mã GT-xxxxxx.",
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Mã cơ hội, vd: GT-000123."}},
            "required": ["code"],
            "additionalProperties": False,
        },
        "annotations": {"title": "Chi tiết cơ hội", "readOnlyHint": True, "openWorldHint": False},
    },
]

INSTRUCTIONS = (
    "Máy chủ này thuộc sàn LeadScan (leadscan.net) — sàn kết nối cơ hội kinh doanh B2B. Người dùng là ĐỐI TÁC: họ biết doanh nghiệp đang có "
    "nhu cầu mua và đăng lên sàn; LeadScan xác minh rồi kết nối với người mua, đối tác nhận ít nhất 1 ly cafe cho mỗi cơ hội đạt xác minh "
    "và hoa hồng khi phiếu được bán. Giúp người dùng soạn cơ hội đủ thông tin, hỏi lại phần còn thiếu, không bịa dữ liệu, "
    "và luôn xin xác nhận trước khi gọi submit_opportunity. Trả lời bằng tiếng Việt."
)


class ToolError(Exception):
    """Lỗi nghiệp vụ trả về cho AI (isError=true) để nó sửa và thử lại."""


def _portal_link(s: PartnerSubmission) -> str:
    return f"{get_settings().site_url.rstrip('/')}/doi-tac/co-hoi/{s.id}"


def _brief(item: dict) -> dict:
    keys = ("code", "title", "company_name", "province", "status", "status_label", "score", "sold_count", "earned", "created_at", "decided_at", "published_at")
    return {k: item[k] for k in keys}


def tool_guide(db: Session, p: PartnerUser) -> dict:
    cfg = get_settings()
    st = partner_wallet.settings(db)
    used = db.scalar(
        select(func.count()).select_from(PartnerSubmission)
        .where(PartnerSubmission.partner_id == p.id, PartnerSubmission.created_at > utcnow() - timedelta(hours=24))
    ) or 0
    cafe, rate, months = f'{st["cafe_amount"]:,}'.replace(",", "."), st["rate_new"], st["share_months"]
    reward = (
        f"1 ly cafe ({cafe}đ) cho mỗi cơ hội đạt xác minh, cộng {rate}% doanh thu mỗi lượt bán phiếu trong {months} tháng."
        if st["reward_mode"] == "sum" else
        f"Mức cao hơn giữa 1 ly cafe ({cafe}đ) và {rate}% doanh thu phiếu trong {months} tháng — luôn có ít nhất 1 ly cafe cho mỗi cơ hội đạt xác minh."
    )
    return {
        "partner": {"code": p.code, "name": p.full_name},
        "accepted": [
            "Nhu cầu cụ thể: mặt hàng/dịch vụ, quy mô, thời điểm cần",
            "Có doanh nghiệp (tên hoặc mã số thuế) đứng sau nhu cầu",
            "Có thời điểm: sắp mua, đang tìm nhà cung cấp, sắp khởi công",
        ],
        "rejected": [
            "Tin đồn, thông tin chung chung chép từ báo",
            "Danh sách số điện thoại, email cá nhân (dữ liệu cá nhân)",
            "Thông tin mật của nơi đối tác đang làm việc",
        ],
        "industries": INDUSTRIES,
        "regions_examples": AREAS,
        "kinds": SUBMISSION_KINDS,
        "sources": SUBMISSION_SOURCES,
        "certainty": SUBMISSION_CERTAINTY,
        "reward": reward,
        "review": f"Xác minh trong khoảng {cfg.partner_sla_workdays} ngày làm việc; đạt khi điểm ≥ {cfg.partner_min_score}/100.",
        "daily_limit": cfg.partner_submit_per_day,
        "remaining_today": max(0, cfg.partner_submit_per_day - used),
        "images": "Ảnh minh chứng thêm trong cổng đối tác khi cơ hội còn trạng thái Đã gửi.",
    }


def tool_submit(db: Session, p: PartnerUser, args: dict, client: str) -> dict:
    d, errors = subs.normalize(args)
    if errors:
        raise ToolError("Chưa gửi được — cần sửa các trường sau rồi gọi lại:\n" + "\n".join(f"- {k}: {v}" for k, v in errors.items()))
    try:
        s = subs.create(db, get_settings(), p, d, via=f"{VIA}{' · ' + client if client else ''}")
    except HTTPException as e:
        raise ToolError(str(e.detail)) from e
    return {
        "ok": True,
        "code": s.code,
        "status_label": SUBMISSION_STATUSES.get(s.status, s.status),
        "message": f"Đã đăng cơ hội {s.code}. LeadScan sẽ xác minh trong khoảng {get_settings().partner_sla_workdays} ngày làm việc và báo kết quả qua email.",
        "portal_url": _portal_link(s),
        "next": "Có thể sửa hoặc thêm ảnh trong cổng đối tác khi cơ hội còn trạng thái Đã gửi.",
    }


def tool_list(db: Session, p: PartnerUser, args: dict) -> dict:
    status = args.get("status") or ""
    try:
        limit = max(1, min(50, int(args.get("limit") or 10)))
    except (TypeError, ValueError):
        limit = 10
    stmt = select(PartnerSubmission).where(PartnerSubmission.partner_id == p.id)
    if status == "open":
        stmt = stmt.where(PartnerSubmission.status.in_(SUBMISSION_OPEN))
    elif status:
        if status not in SUBMISSION_STATUSES:
            raise ToolError("Trạng thái không hợp lệ.")
        stmt = stmt.where(PartnerSubmission.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PartnerSubmission.id.desc()).limit(limit)).unique().all()
    items = [_brief(subs.partner_out(s, money=m, until=u)) for s, m, u in subs.with_money(db, rows)]
    return {"total": total, "shown": len(items), "items": items}


def tool_get(db: Session, p: PartnerUser, args: dict) -> dict:
    code = str(args.get("code") or "").strip().upper()
    s = db.scalar(select(PartnerSubmission).where(PartnerSubmission.code == code, PartnerSubmission.partner_id == p.id))
    if not s:
        raise ToolError(f"Không tìm thấy cơ hội {code or '(trống)'} trong danh sách của bạn.")
    events = db.scalars(select(PartnerEvent).where(PartnerEvent.submission_id == s.id).order_by(PartnerEvent.id)).unique().all()
    events = [e for e in events if e.kind in ("sub_created", "sub_edited", "sub_verifying", "sub_decided", "sub_published", "credit", "cafe_quota")]
    (_, money, until), = subs.with_money(db, [s])
    out = subs.partner_out(s, events, money=money, until=until)
    out.pop("id", None)
    return {**out, "portal_url": _portal_link(s)}


def call_tool(db: Session, p: PartnerUser, name: str, args: dict, client: str) -> dict:
    if name == "get_submission_guide":
        return tool_guide(db, p)
    if name == "submit_opportunity":
        return tool_submit(db, p, args, client)
    if name == "list_my_opportunities":
        return tool_list(db, p, args)
    if name == "get_opportunity":
        return tool_get(db, p, args)
    raise KeyError(name)


# ================================================================== giao thức MCP (JSON-RPC 2.0 qua HTTP)


def _rpc_error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _text(obj) -> str:
    return obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1)


def handle(db: Session, p: PartnerUser, msg: dict, client: str) -> dict | None:
    """Xử lý 1 thông điệp JSON-RPC. Notification (không có id) → None."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    method, mid, params = msg["method"], msg.get("id"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if not isinstance(params, dict):
        return _rpc_error(mid, -32602, "Invalid params")
    if method == "initialize":
        asked = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if not isinstance(args, dict):
            return _rpc_error(mid, -32602, "arguments phải là object")
        try:
            data = call_tool(db, p, name, args, client)
        except KeyError:
            return _rpc_error(mid, -32602, f"Không có công cụ {name}")
        except ToolError as e:
            db.rollback()
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": str(e)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": _text(data)}], "structuredContent": data, "isError": False}}
    return _rpc_error(mid, -32601, f"Method not found: {method}")


def _partner_from_token(db: Session, token: str) -> tuple[PartnerMcpToken, PartnerUser]:
    t = db.scalar(select(PartnerMcpToken).where(PartnerMcpToken.token_hash == sha256(token), PartnerMcpToken.revoked_at.is_(None))) if token else None
    p = t.partner if t else None
    if not t or not p or p.status != "active" or not p.email_verified_at:
        raise HTTPException(401, "URL kết nối không hợp lệ hoặc đã bị thu hồi. Tạo URL mới trong cổng đối tác → Kết nối AI.")
    return t, p


def _serve(request: Request, token: str, body, db: Session) -> Response:
    if not origin_allowed(request, get_settings()):
        raise HTTPException(403, "Origin không được phép.")
    t, p = _partner_from_token(db, token)
    ua = request.headers.get("user-agent", "")[:200]
    client = ua.split("/")[0].strip()[:60] if ua else ""
    now = utcnow()
    if not t.last_used_at or now - t.last_used_at > timedelta(minutes=1) or t.last_client != ua:
        t.last_used_at, t.last_client = now, ua
        db.commit()
    if isinstance(body, list):  # batch (bản giao thức cũ)
        out = [r for r in (handle(db, p, m, client) for m in body) if r is not None]
        return JSONResponse(out) if out else Response(status_code=202)
    if not isinstance(body, dict):
        return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)
    res = handle(db, p, body, client)
    return JSONResponse(res) if res is not None else Response(status_code=202)


def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else ""


@router.post("")
def mcp_bearer(request: Request, body=Body(None), db: Session = Depends(get_db)):
    return _serve(request, _bearer(request), body, db)


@router.post("/{token}")
def mcp_url_token(token: str, request: Request, body=Body(None), db: Session = Depends(get_db)):
    return _serve(request, token, body, db)


@router.get("")
@router.get("/{token}")
def mcp_get(token: str = ""):
    """Không mở luồng SSE: server chỉ trả lời theo từng POST."""
    return Response(status_code=405, headers={"Allow": "POST"})


@router.delete("")
@router.delete("/{token}")
def mcp_delete(token: str = ""):
    return Response(status_code=405, headers={"Allow": "POST"})
