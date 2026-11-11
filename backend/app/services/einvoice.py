"""Hoá đơn điện tử qua IAM Invoice (iamsoftware.com.vn) — tự xuất sau khi thanh toán.

Luồng:
  1. Đơn được ghi nhận đã thanh toán (mark_paid) → nếu bật iam_issue_on_payment, tạo InvoiceRequest từ thông tin
     doanh nghiệp đã đăng ký (tên, MST, địa chỉ). Thiếu địa chỉ → chờ khách gửi form "Thông tin xuất hoá đơn".
  2. issue(): đăng nhập IAM lấy accessToken → POST create-from-3rd (isSigned=Y + chứng thư IntrustCA + PIN) → IAM cấp số HĐ.
  3. Lỗi → ghi einvoice_error; worker thử lại khi lỗi mạng, hết lượt thì email kế toán xuất thủ công. Admin bấm
     "Phát hành HĐĐT" ở trang Hoá đơn để thử lại.

Chống xuất trùng: mã đơn (LSP…) gửi làm thirdPartyCode. Trước khi tạo luôn hỏi IAM theo mã này; IAM cũng không tạo
hoá đơn thứ 2 cho cùng thirdPartyCode (nháp → cập nhật, đã ký → báo lỗi "đã được tạo và ký phát hành").

Yêu cầu của IAM: với các method KHÁC GET phải gửi request KHÔNG kèm cookie (IAM trả Set-Cookie JSESSIONID/moqui.visitor
mỗi lần gọi) → _call() xoá cookie trước mỗi request không phải GET.
"""

import logging
import re
import threading
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import InvoiceRequest, MemberUser, PaymentOrder

log = logging.getLogger("leadscan.einvoice")

API = "/api/rest/s1"
NOT_ISSUED = "InvNotIssued"  # issueStatusId của hoá đơn nháp (chưa ký)
NO_TAX_RATES = {"0", "KCT", "KKKNT"}


class IamError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


# ------------------------------------------------------------------ đọc số tiền bằng chữ

_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_UNITS = ["", " nghìn", " triệu"]  # trên nữa: lặp " tỷ" (nghìn tỷ, triệu tỷ…)


def _read_3(n: int, full: bool) -> str:
    """Đọc 1 nhóm 3 chữ số. full=True: không phải nhóm đầu → đọc cả "không trăm", "linh"."""
    h, t, u = n // 100, n // 10 % 10, n % 10
    out = []
    if h or full:
        out.append(f"{_DIGITS[h]} trăm")
    if t == 0:
        if u and (h or full):
            out.append("linh")
    elif t == 1:
        out.append("mười")
    else:
        out.append(f"{_DIGITS[t]} mươi")
    if u:
        if u == 1 and t > 1:
            out.append("mốt")
        elif u == 5 and t > 0:
            out.append("lăm")
        else:
            out.append(_DIGITS[u])
    return " ".join(out)


def amount_in_words(n: int) -> str:
    """89000 → "Tám mươi chín nghìn đồng"; 1702000 → "Một triệu bảy trăm linh hai nghìn đồng"."""
    n = int(n)
    if n <= 0:
        return "Không đồng"
    groups = []  # (thứ tự nhóm từ phải sang, giá trị 3 chữ số)
    i = 0
    while n:
        n, g = divmod(n, 1000)
        if g:
            groups.append((i, g))
        i += 1
    top = groups[-1][0]
    words = [_read_3(g, full=i != top) + _UNITS[i % 3] + " tỷ" * (i // 3) for i, g in reversed(groups)]
    s = " ".join(words) + " đồng"
    return s[0].upper() + s[1:]


# ------------------------------------------------------------------ gọi API IAM

_token_lock = threading.Lock()
_token: dict = {}  # {"key", "access", "exp", "refresh", "rexp"} — dùng chung trong 1 tiến trình worker/api


class IamClient:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.base = cfg.iam_base_url.rstrip("/") + API
        self._http = httpx.Client(timeout=cfg.iam_timeout_seconds)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- HTTP

    def _call(self, method: str, path: str, *, json: dict | None = None, auth: bool = True, _retry_auth: bool = True) -> dict:
        headers = {"Accept": "application/json"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            headers["sso_access_token"] = self.access_token()
        if method.upper() != "GET":
            self._http.cookies.clear()  # IAM yêu cầu: method khác GET không gửi cookie
        try:
            r = self._http.request(method, self.base + path, json=json, headers=headers)
        except httpx.HTTPError as e:
            raise IamError(f"Không kết nối được IAM: {e.__class__.__name__}", retryable=True) from e
        try:
            data = r.json()
        except ValueError:
            data = None
        code = (data or {}).get("errorCode") if isinstance(data, dict) else None
        if auth and _retry_auth and (r.status_code == 401 or code == 401):
            _drop_token()  # token hết hạn / bị thu hồi → đăng nhập lại 1 lần
            return self._call(method, path, json=json, auth=auth, _retry_auth=False)
        if r.status_code >= 500 or not isinstance(data, dict):
            raise IamError(f"IAM lỗi HTTP {r.status_code}", retryable=r.status_code >= 500 or r.status_code == 429)
        if r.status_code >= 400 and not code:
            code = r.status_code
        if code not in (None, 0, "0"):
            raise IamError(_msg(data) or f"IAM trả mã lỗi {code}", retryable=False)
        return data

    # --- token

    def access_token(self) -> str:
        key = (self.cfg.iam_base_url, self.cfg.iam_username)
        with _token_lock:
            now = time.time()
            if _token.get("key") == key and _token.get("exp", 0) > now + 60:
                return _token["access"]
            data = None
            if _token.get("key") == key and _token.get("rexp", 0) > now + 30:
                try:
                    data = self._call("PUT", "/iam-sso/keycloak-oidc/refresh-access-token", json={"refreshToken": _token["refresh"]}, auth=False)
                except IamError:
                    data = None  # refresh hỏng → đăng nhập lại
            if not data or not data.get("accessToken"):
                if not (self.cfg.iam_username and self.cfg.iam_password):
                    raise IamError("Chưa cấu hình tài khoản IAM (LEADSCAN_IAM_USERNAME / LEADSCAN_IAM_PASSWORD).")
                data = self._call(
                    "POST",
                    "/iam-sso/keycloak-oidc/fetch-access-token",
                    json={"username": self.cfg.iam_username, "password": self.cfg.iam_password},
                    auth=False,
                )
            if not data.get("accessToken"):
                raise IamError("IAM không trả accessToken.")
            _token.clear()
            _token.update(
                key=key,
                access=data["accessToken"],
                exp=now + int(data.get("expiresIn") or 300),
                refresh=data.get("refreshToken") or "",
                rexp=now + int(data.get("refreshExpiresIn") or 0),
            )
            return _token["access"]

    # --- nghiệp vụ

    def certificates(self) -> list[dict]:
        return self._call("GET", "/iam-invoice/invoices/intrust-signed-3rd").get("listData") or []

    def detail_by_code(self, code: str) -> dict | None:
        """Hoá đơn gắn với thirdPartyCode; None nếu chưa có / đã xoá."""
        try:
            d = self._call("GET", f"/iam-invoice/invoices/3rdCode/{code}/detail")
        except IamError as e:
            if not e.retryable and ("không tồn tại" in e.message.lower() or "không tìm thấy" in e.message.lower()):
                return None
            raise
        return d if d.get("invoiceId") else None

    def create(self, payload: dict) -> dict:
        return self._call("POST", "/iam-invoice/invoices/create-from-3rd", json=payload)

    def delete_draft(self, code: str) -> dict:
        return self._call("DELETE", f"/iam-invoice/invoices/3rdCode/{code}/delete")


def _drop_token() -> None:
    with _token_lock:
        _token.clear()


def _msg(d: dict) -> str:
    m = d.get("message") or d.get("errorMsg") or d.get("errors") or ""
    return str(m).strip()


# ------------------------------------------------------------------ dựng hoá đơn


def split_vat(total: int, rate: str) -> tuple[int, int]:
    """Tách tổng tiền đã gồm thuế → (tiền trước thuế, tiền thuế)."""
    if rate.upper() in NO_TAX_RATES:
        return total, 0
    r = float(rate)
    pre = round(total * 100 / (100 + r))
    return pre, total - pre


def item_name(order: PaymentOrder, cfg: Settings) -> str:
    if order.kind == "membership":
        return f"Phí thành viên LeadScan B2B ({cfg.membership_days} ngày)"
    return f"Nạp điểm tài khoản LeadScan B2B ({order.points:,} điểm)".replace(",", ".")


def build_payload(inv: InvoiceRequest, cfg: Settings, cert_sn: str = "") -> dict:
    o = inv.order
    total = int(o.amount)
    rate = cfg.iam_vat_rate.strip().upper() if cfg.iam_vat_rate.strip().upper() in NO_TAX_RATES else cfg.iam_vat_rate.strip()
    pre, tax = split_vat(total, rate)
    name = item_name(o, cfg)
    payload = {
        "invoiceDate": None,  # IAM lấy ngày hiện tại
        "invoiceForm": int(cfg.iam_invoice_form) if cfg.iam_invoice_form.isdigit() else cfg.iam_invoice_form,
        "invoiceSerial": cfg.iam_invoice_serial,
        "discountTypeEnumId": None,
        "currencyUomId": "VND",
        "exchangeRate": 1,
        "paymentInstrumentEnumId": cfg.iam_payment_method,
        "applyVatTaxExempt": "N",
        "saleTaxExemptEnumId": "",
        "thirdPartyCode": o.code,
        "accountNumber": "",
        "bankName": "",
        "toAddress": inv.address,
        "toEmailAddress": inv.receive_email,
        "toName": inv.buyer_name,
        "toPartyName": inv.company_name,
        "toPartyTaxId": inv.tax_code,
        "toTelecomNumber": "",
        "productItems": [
            {
                "quantity": 1,
                "amount": pre,  # đơn giá chưa thuế
                "amountTotal": pre,  # thành tiền chưa thuế
                "taxRate": rate,
                "taxAmount": tax,
                "itemName": name,
                "description": name,
                "quantityUomDesc": cfg.iam_unit,
                "isPromotion": "N",
                "itemClassTypeEnumId": "IiclsProduct",
                "discountPercent": 0,
                "discountAmount": 0,
                "tableColumnExtraFields": [],
            }
        ],
        "grandTotal": pre,
        "taxTotalPayments": [{"taxRate": rate, "taxAmount": tax, "amountExcludeTax": pre, "amountTotal": total}],
        "vatExemptAmount": 0,
        "feeFields": [],
        "invoiceTotal": total,
        "invoiceDiscountPercent": 0,
        "exciseDutyRate": 0,
        "exciseDutyAmount": 0,
        "includeExciseDuty": "N",
        "invoiceDiscountTotal": 0,
        "amountInWords": amount_in_words(total),
        "isSigned": "Y" if cfg.iam_sign else "N",
    }
    if cfg.iam_sign:
        payload["certSn"] = cert_sn
        payload["pinCode"] = cfg.iam_pin_code
    return payload


def _is_issued(d: dict) -> bool:
    no = str(d.get("invoiceNo") or "")
    return bool(re.search(r"[1-9]", no)) and d.get("issueStatusId") != NOT_ISSUED


def _apply(inv: InvoiceRequest, d: dict, cfg: Settings) -> str:
    """Ghi kết quả IAM vào yêu cầu hoá đơn. Trả 'issued' hoặc 'draft'."""
    inv.einvoice_id = str(d.get("invoiceId") or inv.einvoice_id)
    inv.einvoice_serial = f"{d.get('invoiceForm') or cfg.iam_invoice_form}{d.get('invoiceSerial') or cfg.iam_invoice_serial}"[:20]
    inv.einvoice_status = str(d.get("issueStatusId") or ("InvIssued" if _is_issued(d) else NOT_ISSUED))[:40]
    inv.einvoice_error = ""
    inv.einvoice_at = utcnow()
    if _is_issued(d):
        inv.invoice_number = str(d["invoiceNo"])[:50]
        inv.status = "issued"
        inv.issued_at = inv.issued_at or utcnow()
        return "issued"
    return "draft"


def record_error(db: Session, inv: InvoiceRequest, err: IamError) -> None:
    inv.einvoice_error = err.message[:500]
    inv.einvoice_at = utcnow()
    db.commit()


def issue(db: Session, cfg: Settings, inv: InvoiceRequest) -> str:
    """Xuất HĐĐT cho 1 yêu cầu hoá đơn. Trả 'issued' | 'draft' và commit. Lỗi → IamError (chưa ghi vào DB)."""
    if inv.status == "issued":
        return "issued"
    if inv.order.status != "paid":
        raise IamError("Đơn chưa thanh toán.")
    if not cfg.iam_invoice_serial:
        raise IamError("Chưa cấu hình ký hiệu hoá đơn (LEADSCAN_IAM_INVOICE_SERIAL).")
    if cfg.iam_sign and not cfg.iam_pin_code:
        raise IamError("Chưa cấu hình mã PIN ký số (LEADSCAN_IAM_PIN_CODE).")

    with IamClient(cfg) as iam:
        existing = iam.detail_by_code(inv.order.code)  # đã tạo ở lần trước (vd. lần trước bị timeout)?
        if existing and (_is_issued(existing) or not cfg.iam_sign):
            result = _apply(inv, existing, cfg)
            db.commit()
            return result

        cert = ""
        if cfg.iam_sign:
            cert = cfg.iam_cert_sn
            if not cert:
                certs = iam.certificates()
                if not certs:
                    raise IamError("Tài khoản IAM chưa có chứng thư số IntrustCA để ký.")
                cert = certs[0].get("idValue") or ""

        res = iam.create(build_payload(inv, cfg, cert))
        if str(res.get("success", "")).upper() != "Y":
            msg = _msg(res) or "IAM từ chối tạo hoá đơn."
            if "đã được tạo và ký" in msg.lower():  # đã phát hành ở lần gọi trước
                d = iam.detail_by_code(inv.order.code)
                if d:
                    result = _apply(inv, d, cfg)
                    db.commit()
                    return result
            raise IamError(msg)
        # Phản hồi tạo hoá đơn chưa có issueStatusId → hỏi lại để biết đã ký/gửi CQT chưa
        d = {**res, **(iam.detail_by_code(inv.order.code) or {})}
        result = _apply(inv, d, cfg)
        db.commit()
    log.info("HĐĐT đơn %s: %s %s số %s", inv.order.code, result, inv.einvoice_serial, inv.invoice_number or "—")
    return result


def auto_request(db: Session, order: PaymentOrder) -> InvoiceRequest | None:
    """Tạo yêu cầu hoá đơn từ thông tin doanh nghiệp đã đăng ký. None nếu đã có hoặc thiếu tên/MST/địa chỉ."""
    if order.invoice:
        return None
    c = order.company
    if not (c.name.strip() and c.tax_code.strip() and c.address.strip()):
        return None
    u = db.get(MemberUser, order.created_by_id) if order.created_by_id else None
    if not u:
        u = db.scalar(select(MemberUser).where(MemberUser.company_id == c.id, MemberUser.is_active).order_by(MemberUser.id))
    if not u:
        return None
    inv = InvoiceRequest(
        order_id=order.id,
        company_name=c.name.strip()[:200],
        tax_code=c.tax_code.strip()[:20],
        address=c.address.strip()[:300],
        buyer_name=u.full_name[:100],
        receive_email=u.email,
        source="auto",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv
