"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { fmtVnd, type Invoice, ORDER_KIND } from "@/lib/commerce";

type AdminInvoice = Invoice & {
  order: { id: number; code: string; kind: "membership" | "topup"; amount: number; paid_at: string | null };
  company: { id: number; code: string; name: string };
};

type Meta = {
  invoice_email: string;
  einvoice: { enabled: boolean; provider: string; serial: string; sign: boolean; on_payment: boolean; portal: string };
};

export default function AdminInvoicesPage() {
  const [status, setStatus] = useState("pending");
  const [d, setD] = useState<{ total: number; items: AdminInvoice[] } | null>(null);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    api.get<{ total: number; items: AdminInvoice[] }>("/invoices" + qs({ status, page_size: 100 })).then(setD, (e) => setError(errMsg(e)));
  }, [status]);
  useEffect(() => {
    document.title = "Hoá đơn · Quản trị LeadScan";
    setD(null);
    load();
  }, [load]);
  useEffect(() => {
    api.get<Meta>("/commerce-meta").then(setMeta, () => {});
  }, []);

  async function issue(i: AdminInvoice) {
    const num = prompt(`Số hoá đơn đã xuất cho ${i.company_name}:`, i.invoice_number);
    if (num === null) return;
    try {
      await api.patch(`/invoices/${i.id}`, { status: "issued", invoice_number: num.trim() });
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  async function einvoice(i: AdminInvoice) {
    setBusyId(i.id);
    try {
      const r = await api.post<AdminInvoice>(`/invoices/${i.id}/einvoice`);
      alert(r.status === "issued" ? `Đã phát hành hoá đơn số ${r.invoice_number} (${r.einvoice_serial}).` : "Đã tạo hoá đơn nháp trên IAM — vào IAM để ký phát hành.");
    } catch (e) {
      alert(errMsg(e));
    } finally {
      setBusyId(null);
      load();
    }
  }

  async function resend(i: AdminInvoice) {
    try {
      await api.post(`/invoices/${i.id}/resend`);
      alert(`Đã gửi lại email tới ${meta?.invoice_email ?? "kế toán"}.`);
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Yêu cầu xuất hoá đơn</h1>
          {meta?.einvoice.enabled ? (
            <p>
              Tự xuất hoá đơn điện tử qua <b>{meta.einvoice.provider}</b> (ký hiệu <span className="mono">{meta.einvoice.serial || "chưa cấu hình"}</span>
              {meta.einvoice.sign ? ", ký số ngay" : ", tạo nháp chờ ký trên IAM"})
              {meta.einvoice.on_payment ? " ngay khi khách thanh toán, theo thông tin doanh nghiệp đã đăng ký (thiếu địa chỉ thì chờ khách điền form)" : " khi khách gửi thông tin xuất hoá đơn"}.
              {" "}Lỗi thì email <b>{meta.invoice_email}</b> để xuất thủ công.
            </p>
          ) : (
            <p>Khách nhập sau khi thanh toán; hệ thống gửi email tới <b>{meta?.invoice_email ?? "…"}</b> để xuất thủ công. Xuất xong, nhập số hoá đơn tại đây.</p>
          )}
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs">
          {[["pending", "Chờ xuất"], ["issued", "Đã xuất"], ["", "Tất cả"]].map(([k, v]) => (
            <button key={k} className={status === k ? "on" : undefined} onClick={() => setStatus(k)}>{v}</button>
          ))}
        </div>
        {!d ? (
          <div className="bd"><Skeleton h={80} /></div>
        ) : !d.items.length ? (
          <div className="adm-empty">Không có yêu cầu nào.</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Thông tin xuất HĐ</th><th>Đơn</th><th>Email nhận</th><th>Email kế toán</th><th>Trạng thái</th><th></th></tr></thead>
              <tbody>
                {d.items.map((i) => (
                  <tr key={i.id}>
                    <td>
                      <div className="name">{i.company_name}</div>
                      <div className="sub">MST <span className="mono">{i.tax_code}</span> · {i.address}</div>
                      {i.buyer_name ? <div className="sub">Người mua: {i.buyer_name}</div> : null}
                      {i.note ? <div className="sub">Ghi chú: {i.note}</div> : null}
                      {i.source === "auto" ? <div className="sub">Tự lấy từ hồ sơ doanh nghiệp khi thanh toán</div> : null}
                      <div className="sub">KH: <Link href={`/admin/khach-hang/${i.company.id}`} style={{ color: "var(--brand-600)" }}>{i.company.name}</Link></div>
                    </td>
                    <td><b className="mono">{i.order.code}</b><div className="sub">{ORDER_KIND[i.order.kind]} · {fmtVnd(i.order.amount)}</div><div className="sub">TT {fmtDateTime(i.order.paid_at)}</div></td>
                    <td>{i.receive_email}</td>
                    <td>{i.email_sent_at ? <span className="sub">Đã gửi {fmtDateTime(i.email_sent_at)}</span> : <span className="sub" style={{ color: "var(--danger)" }}>Chưa gửi được</span>}</td>
                    <td>
                      {i.status === "issued" ? (
                        <>
                          <span className="adm-badge s-active">Đã xuất</span>
                          <div className="sub">{i.einvoice_serial ? <span className="mono">{i.einvoice_serial} · </span> : null}Số {i.invoice_number} · {fmtDateTime(i.issued_at)}</div>
                          {i.einvoice_serial ? <div className="sub">HĐĐT IAM</div> : null}
                        </>
                      ) : i.einvoice_error ? (
                        <><span className="adm-badge s-rejected">Lỗi HĐĐT</span><div className="sub" style={{ color: "var(--danger)", maxWidth: 260 }}>{i.einvoice_error}</div></>
                      ) : i.einvoice_status === "InvNotIssued" ? (
                        <><span className="adm-badge s-contacted">Nháp trên IAM</span><div className="sub">Chờ ký phát hành</div></>
                      ) : <span className="adm-badge s-contacted">Chờ xuất</span>}
                    </td>
                    <td>
                      <div className="adm-actions">
                        {meta?.einvoice.enabled && i.status !== "issued" ? (
                          <button className="adm-btn sm" disabled={busyId === i.id} onClick={() => einvoice(i)}>
                            {busyId === i.id ? "Đang gọi IAM…" : i.einvoice_status === "InvNotIssued" ? "Kiểm tra / ký HĐĐT" : "Phát hành HĐĐT"}
                          </button>
                        ) : null}
                        <button className="adm-btn sm" onClick={() => resend(i)}>Gửi lại email</button>
                        {i.status !== "issued" ? <button className="adm-btn sm primary" onClick={() => issue(i)}>Đã xuất hoá đơn</button> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
