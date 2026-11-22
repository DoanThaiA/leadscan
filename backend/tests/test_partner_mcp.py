"""Kết nối AI cho đối tác: URL MCP trong cổng + MCP server (JSON-RPC qua HTTP) để đăng & theo dõi cơ hội."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import new_session
from app.models import PartnerEvent, PartnerMcpToken, PartnerSubmission
from tests.test_partner import new_client, otp_mail  # noqa: F401
from tests.test_partner_submissions import partner, partner2, sub_form, verified_partner  # noqa: F401


def rpc(c: TestClient, url: str, method: str, params: dict | None = None, mid: int = 1, **kw):
    body = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        body["params"] = params
    return c.post(url, json=body, headers={"Accept": "application/json, text/event-stream", **kw.pop("headers", {})}, **kw)


def call(c: TestClient, url: str, name: str, args: dict | None = None) -> dict:
    r = rpc(c, url, "tools/call", {"name": name, "arguments": args or {}})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def new_url(c: TestClient) -> str:
    r = c.post("/api/partner/mcp/token")
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["url"].endswith("/api/mcp/" + j["token"]) and j["token"].startswith("lsm_")
    return "/api/mcp/" + j["token"]


def test_token_lifecycle(partner):
    assert partner.get("/api/partner/mcp").json()["active"] is False
    url = new_url(partner)
    st = partner.get("/api/partner/mcp").json()
    assert st["active"] is True and "token" not in st and "url" not in st and url.endswith(st["hint"])
    with new_session() as db:  # DB chỉ lưu hash
        t = db.scalar(select(PartnerMcpToken))
        assert t.token_hash != url.rsplit("/", 1)[1] and len(t.token_hash) == 64

    anon = new_client()  # MCP không cần cookie
    assert rpc(anon, url, "ping").json() == {"jsonrpc": "2.0", "id": 1, "result": {}}

    url2 = new_url(partner)  # tạo mới → URL cũ hết hiệu lực
    assert rpc(anon, url, "ping").status_code == 401
    assert rpc(anon, url2, "ping").status_code == 200
    assert partner.delete("/api/partner/mcp/token").status_code == 204
    assert rpc(anon, url2, "ping").status_code == 401
    assert partner.get("/api/partner/mcp").json()["active"] is False


def test_portal_requires_verified_partner(otp_mail):  # noqa: F811
    from tests.test_partner import signup_form

    c = new_client()
    assert c.post("/api/partner/mcp/token").status_code == 401
    c.post("/api/partner/auth/register", json=signup_form())
    assert c.post("/api/partner/mcp/token").status_code == 403  # chưa xác thực email


def test_handshake_and_tools(partner):
    url = new_url(partner)
    c = new_client()
    r = rpc(c, url, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})
    res = r.json()["result"]
    assert res["protocolVersion"] == "2025-06-18" and "tools" in res["capabilities"] and res["serverInfo"]["name"] == "leadscan-doi-tac"
    assert rpc(c, url, "initialize", {"protocolVersion": "1999-01-01"}).json()["result"]["protocolVersion"] == "2025-11-25"
    # notification → 202, không có nội dung
    n = c.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert n.status_code == 202 and n.content == b""
    names = [t["name"] for t in rpc(c, url, "tools/list").json()["result"]["tools"]]
    assert names == ["get_submission_guide", "submit_opportunity", "list_my_opportunities", "get_opportunity", "list_open_needs"]
    assert rpc(c, url, "nope").json()["error"]["code"] == -32601
    assert rpc(c, url, "tools/call", {"name": "nope", "arguments": {}}).json()["error"]["code"] == -32602
    assert c.get(url).status_code == 405
    # Bearer cho ứng dụng nhận header
    tok = url.rsplit("/", 1)[1]
    assert rpc(c, "/api/mcp", "ping", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert rpc(c, "/api/mcp", "ping").status_code == 401
    # Origin lạ (trang web khác gọi thẳng) bị chặn
    assert rpc(c, url, "ping", headers={"Origin": "https://evil.example"}).status_code == 403

    g = call(c, url, "get_submission_guide")
    assert g["isError"] is False and g["structuredContent"]["remaining_today"] == 20 and "Bao bì & in ấn" in g["structuredContent"]["industries"]


def test_submit_list_get(partner, partner2):
    url = new_url(partner)
    c = new_client()
    form = sub_form()
    form.pop("tax_lookup")
    res = call(c, url, "submit_opportunity", form)
    assert res["isError"] is False, res
    code = res["structuredContent"]["code"]
    assert code.startswith("GT-") and res["structuredContent"]["portal_url"].endswith("/doi-tac/co-hoi/1")
    with new_session() as db:
        s = db.scalar(select(PartnerSubmission))
        assert s.code == code and s.status == "submitted" and s.partner.email == "binh@gmail.com"
        ev = db.scalar(select(PartnerEvent).where(PartnerEvent.kind == "sub_created"))
        assert "(qua kết nối AI" in ev.content

    # gửi lại cùng cơ hội → báo trùng của chính mình
    again = call(c, url, "submit_opportunity", form)
    assert again["isError"] is True and "đã gửi cơ hội này rồi" in again["content"][0]["text"]

    lst = call(c, url, "list_my_opportunities", {"status": "open"})["structuredContent"]
    assert lst["total"] == 1 and lst["items"][0]["code"] == code and lst["items"][0]["status_label"] == "Đã gửi"
    det = call(c, url, "get_opportunity", {"code": code.lower()})["structuredContent"]
    assert det["code"] == code and det["events"][0]["kind"] == "sub_created" and "id" not in det

    # đối tác khác không xem được cơ hội của người này
    url2 = new_url(partner2)
    assert call(c, url2, "get_opportunity", {"code": code})["isError"] is True
    assert call(c, url2, "list_my_opportunities")["structuredContent"]["total"] == 0


def test_submit_validation_and_commitment(partner):
    url = new_url(partner)
    c = new_client()
    bad = call(c, url, "submit_opportunity", {"title": "ngắn", "company_name": "X", "need": "ít", "commitment": False})
    text = bad["content"][0]["text"]
    assert bad["isError"] is True
    for f in ("title", "company_name", "industry", "kind", "need", "source_type", "certainty", "commitment"):
        assert f"- {f}:" in text
    with new_session() as db:
        assert db.scalar(select(PartnerSubmission)) is None


def test_locked_partner_cannot_use_url(partner):
    url = new_url(partner)
    with new_session() as db:
        t = db.scalar(select(PartnerMcpToken))
        t.partner.status = "locked"
        db.commit()
    assert rpc(new_client(), url, "ping").status_code == 401
