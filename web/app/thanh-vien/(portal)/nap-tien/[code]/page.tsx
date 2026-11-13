"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import QRCode from "qrcode";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { CopyField, Field, Icon, Skeleton } from "@/components/admin/ui";
import { McvPayPanel } from "@/components/member/McvPayPanel";
import { type MemberMe, useMember } from "@/components/member/MemberContext";
import { fmtDateTime } from "@/lib/admin/format";
import { fmtPts, fmtVnd, ORDER_KIND, ORDER_STATUS, ORDER_STATUS_CLASS, type Order, type PaymentInfo } from "@/lib/commerce";
import { errFields, errMsg, mapi } from "@/lib/member/api";

interface Resp {
  order: Order;
  payment: PaymentInfo;
  me: MemberMe;
}

export default function OrderPage() {
  const { code } = useParams<{ code: string }>();
  const { setMe } = useMember();
  const [d, setD] = useState<Resp | null>(null);
  const [qr, setQr] = useState("");
  const [error, setError] = useState("");
  const [simBusy, setSimBusy] = useState(false);
  const status = useRef<string>("");

  const load = useCallback(async () => {
    try {
      const r = await mapi.get<Resp>(`/orders/${code}`);
      setD(r);
      if (status.current && status.current !== r.order.status) setMe(r.me); // vừa thanh toán xong → cập nhật số dư trên menu
      status.current = r.order.status;
    } catch (e) {
      setError(errMsg(e));
    }
  }, [code, setMe]);

  useEffect(() => {
    load();
  }, [load]);

  // Đang chờ thanh toán: hỏi lại trạng thái mỗi 5 giây (backend LeadScan tra MCV — trình duyệt không gọi MCV)
  useEffect(() => {
    if (d?.order.status !== "pending" || d.payment.mcv_status === "needs_attention") return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [d?.order.status, d?.payment.mcv_status, load]);

  // Đã thanh toán: hoá đơn điện tử được xuất ở việc nền → hỏi lại vài lần (tối đa ~2 phút) để hiện số hoá đơn
  const invPolls = useRef(0);
  const invWaiting = d?.order.status === "paid" && d.order.amount > 0 && (d.order.invoice ? d.order.invoice.status === "pending" && !d.order.invoice.einvoice_error : true);
  useEffect(() => {
    // chưa có yêu cầu hoá đơn: chỉ chờ ~30 giây xem hệ thống có tự tạo không (rồi để khách tự điền form)
    if (!invWaiting || invPolls.current >= (d?.order.invoice ? 24 : 6)) return;
    const t = setTimeout(() => {
      invPolls.current += 1;
      load();
    }, 5000);
    return () => clearTimeout(t);
  }, [invWaiting, d, load]);

  useEffect(() => {
    document.title = `Thanh toán ${code} · LeadScan B2B`;
    if (d?.payment.provider !== "mcv" && d?.payment.qr_payload) QRCode.toDataURL(d.payment.qr_payload, { width: 456, margin: 1, errorCorrectionLevel: "M" }).then(setQr);
  }, [d?.payment.provider, d?.payment.qr_payload, code]);

  async function simulate() {
    setSimBusy(true);
    try {
      await mapi.post(`/orders/${code}/simulate-paid`);
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSimBusy(false);
    }
  }

  async function cancel() {
    if (!confirm("Huỷ đơn thanh toán này?")) return;
    try {
      await mapi.post(`/orders/${code}/cancel`);
      load();
    } catch (e) {
      setError(errMsg(e));
    }
  }

  if (!d) return error ? <div className="adm-alert">{error}</div> : <Skeleton h={320} />;
  const { order: o, payment: p } = d;

  return (
    <>
      <Link href="/thanh-vien/vi" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}>
        <Icon name="back" size={16} /> Ví & nạp tiền
      </Link>
      <div className="adm-head">
        <div>
          <h1>Đơn {o.code}</h1>
          <p>
            {ORDER_KIND[o.kind]} · {fmtVnd(o.amount)}
            {o.discount ? <> (giá gốc {fmtVnd(o.original_amount)}, mã {o.promo_code} −{fmtVnd(o.discount)})</> : null} · tạo lúc {fmtDateTime(o.created_at)}
          </p>
        </div>
        <span className={`adm-badge ${ORDER_STATUS_CLASS[o.status]}`} style={{ fontSize: 13, padding: "4px 12px" }}>{ORDER_STATUS[o.status]}</span>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      {o.status === "pending" && p.provider === "mcv" ? (
        <section className="adm-card">
          <div className="hd">
            <h2>Quét mã VietQR để thanh toán</h2>
            <span className="muted" style={{ fontSize: 12.5 }}>Đơn giữ tới {fmtDateTime(o.expires_at)}</span>
          </div>
          <div className="bd">
            <McvPayPanel code={o.code} payment={p} onChange={load} onCancel={cancel} />
            <ol className="adm-steps" style={{ fontSize: 13, marginTop: 16 }}>
              <li>Quét QR bằng app ngân hàng (hoặc mở trang thanh toán MCV), giữ nguyên số tiền và nội dung.</li>
              <li>Cổng MCV tự đối soát; trang này cập nhật khi LeadScan nhận được tiền.</li>
              <li>Điểm được cộng ngay vào ví, sau đó bạn có thể yêu cầu xuất hoá đơn.</li>
            </ol>
          </div>
        </section>
      ) : o.status === "pending" ? (
        <section className="adm-card">
          <div className="hd">
            <h2>Quét mã VietQR để thanh toán</h2>
            <span className="muted" style={{ fontSize: 12.5 }}>Hết hạn {fmtDateTime(o.expires_at)}</span>
          </div>
          <div className="bd">
            {!p.configured ? (
              <div className="adm-alert">Tài khoản nhận tiền chưa được cấu hình. Vui lòng liên hệ LeadScan để được hỗ trợ thanh toán.</div>
            ) : (
              <div className="adm-pay">
                <div className="adm-qr">
                  {qr ? <img src={qr} alt={`Mã VietQR chuyển ${fmtVnd(p.amount)} nội dung ${p.transfer_content}`} /> : <Skeleton h={228} w={228} />}
                  <span className="muted" style={{ fontSize: 12 }}>Mở app ngân hàng → Quét QR</span>
                </div>
                <div style={{ display: "grid", gap: 12 }}>
                  <CopyField label="Ngân hàng" value={p.bank_name || "—"} />
                  <CopyField label="Số tài khoản" value={p.account_no} />
                  <CopyField label="Chủ tài khoản" value={p.account_name || "—"} />
                  <CopyField label="Số tiền" value={p.amount.toLocaleString("vi-VN")} />
                  <CopyField label="Nội dung chuyển khoản (bắt buộc đúng)" value={p.transfer_content} />
                  <ol className="adm-steps" style={{ fontSize: 13 }}>
                    <li>Quét QR hoặc chuyển khoản đúng <b>số tiền</b> và <b>nội dung</b> ở trên.</li>
                    <li>Hệ thống InfoCMS tự đối soát; trang này cập nhật khi nhận được tiền.</li>
                    <li>Điểm được cộng ngay vào ví, sau đó bạn có thể yêu cầu xuất hoá đơn.</li>
                  </ol>
                  <div className="adm-actions" style={{ justifyContent: "flex-start" }}>
                    <span className="muted" style={{ fontSize: 12.5, alignSelf: "center" }}>● Đang chờ thanh toán…</span>
                    <button className="adm-btn sm ghost danger" onClick={cancel}>Huỷ đơn</button>
                    {p.provider === "mock" ? (
                      <button className="adm-btn sm" onClick={simulate} disabled={simBusy} title="Chỉ có ở chế độ chạy thử">
                        {simBusy ? "Đang giả lập…" : "Giả lập đã thanh toán (chạy thử)"}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      ) : o.status === "paid" && o.amount <= 0 ? (
        <section className="adm-card">
          <div className="bd" style={{ display: "grid", gap: 12, maxWidth: 560 }}>
            <div className="adm-alert ok">
              <b>Đã kích hoạt — miễn phí!</b> Mã khuyến mãi {o.promo_code} giảm toàn bộ {fmtVnd(o.discount)}, không cần thanh toán.
              {" "}Đã cộng {fmtPts(o.points)} vào ví lúc {fmtDateTime(o.paid_at)}.
            </div>
            <dl className="adm-kv">
              <dt>Số dư hiện tại</dt><dd><b>{fmtPts(d.me.company.points_balance)}</b></dd>
              {o.kind === "membership" ? (<><dt>Thành viên đến</dt><dd>{fmtDateTime(d.me.company.membership_expires_at)}</dd></>) : null}
            </dl>
            <Link className="adm-btn primary" href="/thanh-vien/co-hoi">Vào kho cơ hội</Link>
          </div>
        </section>
      ) : o.status === "paid" ? (
        <div className="adm-grid side">
          <InvoiceForm order={o} me={d.me} onDone={load} />
          <section className="adm-card">
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              <div className="adm-alert ok">
                <b>Thanh toán thành công!</b> Đã cộng {fmtPts(o.points)} vào ví lúc {fmtDateTime(o.paid_at)}.
              </div>
              <dl className="adm-kv">
                <dt>Số tiền nhận</dt><dd>{fmtVnd(o.paid_amount)}</dd>
                <dt>Số dư hiện tại</dt><dd><b>{fmtPts(d.me.company.points_balance)}</b></dd>
              </dl>
              <Link className="adm-btn primary" href="/thanh-vien/co-hoi">Vào kho cơ hội</Link>
            </div>
          </section>
        </div>
      ) : (
        <section className="adm-card adm-empty">
          <p>Đơn này {o.status === "expired" ? "đã hết hạn" : "đã bị huỷ"}. Nếu bạn đã chuyển khoản, đừng lo — hệ thống vẫn ghi nhận theo nội dung chuyển khoản; hoặc liên hệ LeadScan.</p>
          <p style={{ marginTop: 12 }}><Link className="adm-btn primary" href="/thanh-vien/nap-tien">Tạo đơn mới</Link></p>
        </section>
      )}
    </>
  );
}

function InvoiceForm({ order, me, onDone }: { order: Order; me: MemberMe; onDone: () => void }) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const inv = order.invoice;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setErrors({});
    setMsg("");
    try {
      await mapi.post(`/orders/${order.code}/invoice`, f);
      onDone();
    } catch (err) {
      setMsg(errMsg(err));
      setErrors(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  if (inv) {
    return (
      <section className="adm-card" id="hoa-don">
        <div className="hd">
          <h2>Thông tin xuất hoá đơn</h2>
          {inv.status === "issued" ? <span className="adm-badge s-active">Đã xuất</span> : <span className="adm-badge s-contacted">Chờ xuất</span>}
        </div>
        <div className="bd" style={{ display: "grid", gap: 12 }}>
          <dl className="adm-kv">
            <dt>Đơn vị</dt><dd>{inv.company_name}</dd>
            <dt>Mã số thuế</dt><dd className="mono">{inv.tax_code}</dd>
            <dt>Địa chỉ</dt><dd>{inv.address}</dd>
            <dt>Người mua hàng</dt><dd>{inv.buyer_name || "—"}</dd>
            <dt>Email nhận HĐ</dt><dd>{inv.receive_email}</dd>
            {inv.einvoice_serial && inv.invoice_number ? (<><dt>Ký hiệu</dt><dd className="mono">{inv.einvoice_serial}</dd></>) : null}
            {inv.invoice_number ? (<><dt>Số hoá đơn</dt><dd><b>{inv.invoice_number}</b></dd></>) : null}
          </dl>
          <p className="muted" style={{ fontSize: 13 }}>
            {inv.status === "issued"
              ? `Hoá đơn điện tử đã được xuất${inv.issued_at ? ` ngày ${fmtDateTime(inv.issued_at)}` : ""} và gửi tới ${inv.receive_email}.`
              : "Hoá đơn đang được xuất và sẽ gửi về email của bạn."}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="adm-card" id="hoa-don">
      <div className="hd">
        <div>
          <h2>Thông tin xuất hoá đơn</h2>
          <p className="muted" style={{ fontSize: 12.5 }}>Kiểm tra và gửi để kế toán LeadScan xuất hoá đơn cho đơn {order.code}.</p>
        </div>
      </div>
      <form className="bd adm-form" onSubmit={submit} noValidate>
        {msg ? <div className="adm-alert full">{msg}</div> : null}
        <Field label="Tên đơn vị (theo đăng ký kinh doanh)" error={errors.company_name} full htmlFor="i-name">
          <input id="i-name" className="adm-input" name="company_name" defaultValue={me.company.name} maxLength={200} aria-invalid={!!errors.company_name} />
        </Field>
        <Field label="Mã số thuế" error={errors.tax_code} htmlFor="i-tax">
          <input id="i-tax" className="adm-input" name="tax_code" defaultValue={me.company.tax_code} maxLength={14} inputMode="numeric" aria-invalid={!!errors.tax_code} />
        </Field>
        <Field label="Người mua hàng" error={errors.buyer_name} htmlFor="i-buyer">
          <input id="i-buyer" className="adm-input" name="buyer_name" defaultValue={me.full_name} maxLength={100} />
        </Field>
        <Field label="Địa chỉ trên hoá đơn" error={errors.address} full htmlFor="i-addr">
          <input id="i-addr" className="adm-input" name="address" defaultValue={me.company.address} maxLength={300} aria-invalid={!!errors.address} />
        </Field>
        <Field label="Email nhận hoá đơn" error={errors.receive_email} full htmlFor="i-email">
          <input id="i-email" className="adm-input" name="receive_email" type="email" defaultValue={me.email} maxLength={150} aria-invalid={!!errors.receive_email} />
        </Field>
        <Field label="Ghi chú (không bắt buộc)" full htmlFor="i-note">
          <textarea id="i-note" className="adm-input" name="note" maxLength={1000} placeholder="Ví dụ: ghi tên hàng hoá theo yêu cầu, gửi kèm bản giấy…" />
        </Field>
        <div className="adm-actions full">
          <button className="adm-btn primary" disabled={busy}>{busy ? "Đang gửi…" : "Gửi thông tin xuất hoá đơn"}</button>
        </div>
      </form>
    </section>
  );
}
