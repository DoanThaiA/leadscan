"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { CopyField, Skeleton } from "@/components/admin/ui";
import { fmtVnd, type PaymentInfo } from "@/lib/commerce";
import { errMsg, mapi } from "@/lib/member/api";

/** Thanh toán qua cổng MCV: QR vẽ từ qr_data (MCV cấp), đếm ngược tới hạn QR, tạo QR mới khi hết hạn.
 *  Trạng thái do trang cha hỏi backend LeadScan định kỳ — trình duyệt không bao giờ gọi MCV trực tiếp. */
export function McvPayPanel({ code, payment: p, onChange, onCancel }: { code: string; payment: PaymentInfo; onChange: () => Promise<void> | void; onCancel: () => void }) {
  const [qr, setQr] = useState("");
  const [busy, setBusy] = useState<"" | "renew" | "sim">("");
  const [error, setError] = useState("");
  const left = useCountdown(p.expires_at);

  useEffect(() => {
    setQr("");
    // Chuỗi VietQR do MCV cấp — vẽ nguyên văn, mức sửa lỗi M; không tự sinh QR từ số tài khoản
    if (p.qr_payload) QRCode.toDataURL(p.qr_payload, { width: 456, margin: 1, errorCorrectionLevel: "M" }).then(setQr);
  }, [p.qr_payload]);

  async function act(kind: "renew" | "sim") {
    setBusy(kind);
    setError("");
    try {
      await mapi.post(kind === "renew" ? `/orders/${code}/mcv` : `/orders/${code}/simulate-paid`);
      await onChange();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy("");
    }
  }

  const renewBtn = (label: string) => (
    <button className="adm-btn primary" onClick={() => act("renew")} disabled={busy !== ""}>{busy === "renew" ? "Đang tạo mã…" : label}</button>
  );
  const errBox = error || p.error ? <div className="adm-alert">{error || p.error}</div> : null;

  if (!p.configured) {
    return <div className="adm-alert">Cổng thanh toán chưa được cấu hình. Vui lòng liên hệ LeadScan để được hỗ trợ thanh toán.</div>;
  }
  if (!p.payment_code || p.mcv_status === "failed") {
    return (
      <div style={{ display: "grid", gap: 12, justifyItems: "start" }}>
        {errBox}
        {p.mcv_status === "failed" ? <p className="muted">Cổng thanh toán báo lỗi khi tạo mã. Vui lòng thử lại.</p> : null}
        {renewBtn(p.mcv_status === "failed" ? "Thử lại" : "Tạo mã QR thanh toán")}
      </div>
    );
  }
  if (p.mcv_status === "needs_attention") {
    return (
      <div className="adm-alert warn">
        <b>LeadScan đã nhận được tiền nhưng số tiền chưa khớp với đơn.</b> Bộ phận kế toán sẽ đối soát và liên hệ bạn — bạn không cần chuyển thêm.
      </div>
    );
  }

  const expired = p.mcv_status === "expired" || left === 0;
  if (expired) {
    return (
      <div style={{ display: "grid", gap: 12, justifyItems: "start" }}>
        {errBox}
        <p><b>Mã QR đã hết hạn.</b> Tạo mã mới để tiếp tục thanh toán đơn này.</p>
        <p className="muted" style={{ fontSize: 13 }}>Nếu bạn đã chuyển khoản theo mã cũ, đừng lo — hệ thống vẫn ghi nhận khi nhận được tiền, không cần chuyển lại.</p>
        <div className="adm-actions" style={{ justifyContent: "flex-start" }}>
          {renewBtn("Tạo mã QR mới")}
          <button className="adm-btn ghost danger" onClick={onCancel}>Huỷ đơn</button>
        </div>
      </div>
    );
  }

  return (
    <div className="adm-pay">
      <div className="adm-qr">
        {p.qr_payload ? (
          qr ? <img src={qr} alt={`Mã VietQR chuyển ${fmtVnd(p.amount)} cho ${p.account_name}`} /> : <Skeleton h={228} w={228} />
        ) : (
          <div style={{ width: 228, height: 228, display: "grid", placeItems: "center", textAlign: "center", fontSize: 13 }} className="muted">
            {p.test_mode ? "Khoá thử nghiệm: không có QR thật. Dùng nút giả lập hoặc trang thanh toán MCV." : "Đang lấy mã QR…"}
          </div>
        )}
        <span className="muted" style={{ fontSize: 12 }}>Mở app ngân hàng → Quét QR</span>
        <b style={{ fontVariantNumeric: "tabular-nums" }} aria-live="polite">Còn {fmtLeft(left)}</b>
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        <CopyField label="Số tiền" value={p.amount.toLocaleString("vi-VN")} />
        <CopyField label="Chủ tài khoản nhận" value={p.account_name || "—"} />
        {p.bank_name || p.account_no ? <CopyField label={`Số tài khoản${p.bank_name ? ` · ${p.bank_name}` : ""}`} value={p.account_no || "—"} /> : null}
        {p.transfer_content ? <CopyField label="Nội dung chuyển khoản" value={p.transfer_content} /> : null}
        <div className="adm-alert warn" style={{ fontSize: 13 }}>
          <b>Không sửa nội dung chuyển khoản và số tiền</b> — hệ thống dựa vào đó để tự xác nhận. Chuyển thiếu tiền sẽ không được ghi nhận tự động.
        </div>
        {errBox}
        <div className="adm-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
          <span className="muted" style={{ fontSize: 12.5, alignSelf: "center" }}>● Đang chờ thanh toán…</span>
          {p.checkout_url ? <a className="adm-btn sm" href={p.checkout_url}>Mở trang thanh toán MCV</a> : null}
          <button className="adm-btn sm ghost danger" onClick={onCancel}>Huỷ đơn</button>
          {p.can_simulate ? (
            <button className="adm-btn sm" onClick={() => act("sim")} disabled={busy !== ""} title="Chỉ có khi dùng khoá thử nghiệm MCV">
              {busy === "sim" ? "Đang giả lập…" : "Giả lập: đã thanh toán"}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** Số giây còn lại tới `iso` (null nếu không có hạn), cập nhật mỗi giây. */
function useCountdown(iso: string | null | undefined): number | null {
  const calc = () => (iso ? Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000)) : null);
  const [left, setLeft] = useState<number | null>(calc);
  useEffect(() => {
    setLeft(calc());
    if (!iso) return;
    const t = setInterval(() => setLeft(calc()), 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [iso]);
  return left;
}

function fmtLeft(s: number | null): string {
  if (s === null) return "—";
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}
