"""Hoá đơn điện tử IAM Invoice (giả lập bằng respx): tự xuất sau khi thanh toán, chống xuất trùng, lỗi → email kế toán."""

import json

import httpx
import pytest
import respx
from sqlalchemy import select

from app.db import new_session
from app.models import Company, InvoiceRequest
from app.services import einvoice
from tests.test_member import member_client, pay_membership
from tests.conftest import register

IAM = "https://iam.test/api/rest/s1"
CERT = "1665312DDD39B7779F19AB4129E4ED52"


@pytest.fixture(autouse=True)
def iam_env(monkeypatch):
    monkeypatch.setenv("LEADSCAN_IAM_ENABLED", "true")
    monkeypatch.setenv("LEADSCAN_IAM_BASE_URL", "https://iam.test")
    monkeypatch.setenv("LEADSCAN_IAM_USERNAME", "0312303803-999")
    monkeypatch.setenv("LEADSCAN_IAM_PASSWORD", "12345678")
    monkeypatch.setenv("LEADSCAN_IAM_INVOICE_SERIAL", "C26TYY")
    monkeypatch.setenv("LEADSCAN_IAM_PIN_CODE", "000000")
    from app.config import get_settings

    get_settings.cache_clear()
    einvoice._drop_token()
    yield
    einvoice._drop_token()


class FakeIam:
    """IAM giả: lưu hoá đơn theo thirdPartyCode, đặt cookie mỗi phản hồi như IAM thật."""

    def __init__(self, mock: respx.MockRouter):
        self.invoices: dict[str, dict] = {}
        self.created: list[dict] = []
        self.fail_message = ""
        self.non_get_cookies: list[str] = []
        self.logins = 0
        cookie = {"set-cookie": "JSESSIONID=abc; Path=/"}

        def track(req):
            if req.method != "GET" and req.headers.get("cookie"):
                self.non_get_cookies.append(req.headers["cookie"])

        def login(req):
            track(req)
            self.logins += 1
            return httpx.Response(200, headers=cookie, json={"errorCode": 0, "accessToken": "AT", "refreshToken": "RT", "expiresIn": 1800, "refreshExpiresIn": 1800})

        def certs(req):
            assert req.headers["sso_access_token"] == "AT"
            return httpx.Response(200, headers=cookie, json={"listData": [{"idValue": CERT, "issuedBy": "IntrustCA Remote Signing"}]})

        def detail(req, code):
            d = self.invoices.get(code)
            if not d:
                return httpx.Response(200, headers=cookie, json={"errorCode": 400, "errors": "Không tồn tại hóa đơn tìm kiếm hoặc đã bị xóa\n"})
            return httpx.Response(200, headers=cookie, json=d)

        def create(req):
            track(req)
            assert req.headers["sso_access_token"] == "AT"
            body = json.loads(req.content)
            self.created.append(body)
            if self.fail_message:
                return httpx.Response(200, json={"success": "N", "error": True, "message": self.fail_message})
            code = body["thirdPartyCode"]
            old = self.invoices.get(code)
            if old and old["issueStatusId"] != "InvNotIssued":
                return httpx.Response(200, json={"success": "N", "error": True, "invoiceId": old["invoiceId"], "message": f"Hóa đơn mã {code} đã được tạo và ký phát hành không thể cập nhật"})
            signed = body["isSigned"] == "Y"
            no = f"{len(self.invoices) + 1:08d}" if signed else "--------"
            self.invoices[code] = {
                "invoiceSerial": body["invoiceSerial"],
                "invoiceForm": str(body["invoiceForm"]),
                "invoiceId": str(108000 + len(self.invoices)),
                "invoiceNo": no,
                "issueStatusId": "InvTaxAuthSent" if signed else "InvNotIssued",
            }
            return httpx.Response(200, headers=cookie, json={"success": "Y", "message": "Thành công", **{k: v for k, v in self.invoices[code].items() if k != "issueStatusId"}})

        mock.post(f"{IAM}/iam-sso/keycloak-oidc/fetch-access-token").mock(side_effect=login)
        mock.get(f"{IAM}/iam-invoice/invoices/intrust-signed-3rd").mock(side_effect=certs)
        mock.get(url__regex=rf"{IAM}/iam-invoice/invoices/3rdCode/(?P<code>[^/]+)/detail").mock(side_effect=detail)
        mock.post(f"{IAM}/iam-invoice/invoices/create-from-3rd").mock(side_effect=create)


@pytest.fixture
def iam():
    with respx.mock(assert_all_called=False) as mock:
        yield FakeIam(mock)


def _inv() -> InvoiceRequest:
    with new_session() as db:
        inv = db.scalar(select(InvoiceRequest))
        db.expunge_all()
        return inv


def test_doc_so_tien_bang_chu():
    assert einvoice.amount_in_words(89_000) == "Tám mươi chín nghìn đồng"
    assert einvoice.amount_in_words(1_702_000) == "Một triệu bảy trăm linh hai nghìn đồng"
    assert einvoice.amount_in_words(10_000_000) == "Mười triệu đồng"
    assert einvoice.amount_in_words(1_050_000) == "Một triệu không trăm năm mươi nghìn đồng"
    assert einvoice.amount_in_words(21_515) == "Hai mươi mốt nghìn năm trăm mười lăm đồng"
    assert einvoice.split_vat(89_000, "10") == (80_909, 8_091)
    assert einvoice.split_vat(89_000, "KCT") == (89_000, 0)


def test_thanh_toan_xong_tu_xuat_hoa_don(client, iam):
    register(client)
    m = member_client()
    code = pay_membership(m)

    inv = _inv()
    assert inv.source == "auto" and inv.status == "issued"
    assert inv.invoice_number == "00000001" and inv.einvoice_serial == "1C26TYY" and not inv.einvoice_error
    assert inv.tax_code and inv.address == "KCN Quế Võ" and inv.receive_email == "a@minhan.vn"

    body = iam.created[0]
    assert body["thirdPartyCode"] == code and body["isSigned"] == "Y" and body["certSn"] == CERT and body["pinCode"] == "000000"
    assert body["invoiceTotal"] == 10_000_000 and body["taxTotalPayments"][0]["amountExcludeTax"] + body["taxTotalPayments"][0]["taxAmount"] == 10_000_000
    assert body["amountInWords"] == "Mười triệu đồng" and body["toPartyTaxId"] == inv.tax_code
    assert iam.non_get_cookies == []  # method khác GET không gửi cookie IAM đã đặt

    o = m.get("/api/member/wallet").json()["orders"][0]
    assert o["invoice"]["status"] == "issued" and o["invoice"]["invoice_number"] == "00000001"
    assert m.post(f"/api/member/orders/{code}/invoice", json={"company_name": "X", "tax_code": "0101234567", "address": "Y", "receive_email": "k@x.vn"}).status_code == 409


def test_thieu_dia_chi_cho_khach_gui_form_roi_tu_xuat(client, iam):
    cid = register(client)
    with new_session() as db:
        db.get(Company, cid).address = ""
        db.commit()
    m = member_client()
    code = pay_membership(m)
    assert _inv() is None and iam.created == []  # thiếu địa chỉ → chưa xuất

    form = {"company_name": "Công ty TNHH Minh An", "tax_code": "0101234567", "address": "KCN Quế Võ, Bắc Ninh", "receive_email": "kt@minhan.vn"}
    assert m.post(f"/api/member/orders/{code}/invoice", json=form).status_code == 201
    inv = _inv()
    assert inv.source == "member" and inv.status == "issued" and inv.invoice_number == "00000001"
    assert iam.created[0]["toAddress"] == "KCN Quế Võ, Bắc Ninh" and iam.created[0]["toEmailAddress"] == "kt@minhan.vn"


def test_loi_iam_email_ke_toan_admin_phat_hanh_lai(client, admin, iam, monkeypatch):
    sent = []
    monkeypatch.setattr("app.services.notify.send_mail", lambda cfg, subject, body, to=None: sent.append((to, body)) or True)
    iam.fail_message = "Không tìm thấy mẫu hóa đơn 1C26TYY"
    register(client)
    m = member_client()
    pay_membership(m)

    inv = _inv()
    assert inv.status == "pending" and "mẫu hóa đơn" in inv.einvoice_error
    accountant = [b for to, b in sent if to == "vylyy9999@gmail.com"]
    assert accountant and "CHƯA tự xuất được" in accountant[0] and inv.email_sent_at

    r = admin.post(f"/api/admin/invoices/{inv.id}/einvoice")
    assert r.status_code == 502 and "mẫu hóa đơn" in r.json()["detail"]

    iam.fail_message = ""
    r = admin.post(f"/api/admin/invoices/{inv.id}/einvoice")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "issued" and r.json()["invoice_number"] == "00000001" and r.json()["einvoice_error"] == ""
    assert admin.post(f"/api/admin/invoices/{inv.id}/einvoice").status_code == 409
    assert iam.logins == 1  # token dùng lại giữa các lần gọi


def test_da_ky_o_lan_truoc_khong_xuat_trung(client, iam):
    register(client)
    m = member_client()
    code = pay_membership(m)
    with new_session() as db:  # giả lập: IAM đã ký nhưng phản hồi bị mất (timeout) → DB chưa ghi số
        inv = db.scalar(select(InvoiceRequest))
        inv.status, inv.invoice_number = "pending", ""
        db.commit()
        from app.config import get_settings

        assert einvoice.issue(db, get_settings(), inv) == "issued"
        assert inv.invoice_number == "00000001"
    assert len(iam.created) == 1 and code in iam.invoices  # không gọi tạo hoá đơn lần 2


def test_tat_iam_giu_cach_cu(client, iam, monkeypatch):
    monkeypatch.setenv("LEADSCAN_IAM_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    register(client)
    m = member_client()
    code = pay_membership(m)
    assert _inv() is None
    form = {"company_name": "Minh An", "tax_code": "0101234567", "address": "Bắc Ninh", "receive_email": "kt@minhan.vn"}
    assert m.post(f"/api/member/orders/{code}/invoice", json=form).status_code == 201
    assert _inv().status == "pending" and iam.created == []
