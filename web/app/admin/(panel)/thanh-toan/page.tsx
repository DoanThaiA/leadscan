"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { fmtPts, fmtVnd, ORDER_KIND, ORDER_STATUS, ORDER_STATUS_CLASS, type Order } from "@/lib/commerce";

type AdminOrder = Order & { company: { id: number; code: string; name: string }; confirmed_by: string | null; provider_txn_id: string | null };

export default function AdminOrdersPage() {
  const { user } = useAdmin();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [d, setD] = useState<{ total: number; items: AdminOrder[] } | null>(null);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState<AdminOrder | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(() => {
    api.get<{ total: number; items: AdminOrder[] }>("/orders" + qs({ status, q, page })).then(setD, (e) => setError(errMsg(e)));
  }, [status, q, page]);
  useEffect(() => {
    document.title = "Thanh toán · Quản trị LeadScan";
    setD(null);
    load();
  }, [load]);

  async function cancel(o: AdminOrder) {
    if (!confirm(`Huỷ đơn ${o.code}?`)) return;
    try {
      await api.post(`/orders/${o.id}/cancel`);
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  const pages = d ? Math.max(1, Math.ceil(d.total / 20)) : 1;
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Đơn thanh toán</h1>
          <p>Thanh toán qua InfoCMS được ghi nhận tự động qua webhook. Xác nhận tay chỉ dùng khi đã đối soát sao kê.</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!status ? "on" : undefined} onClick={() => { setStatus(""); setPage(1); }}>Tất cả</button>
          {Object.entries(ORDER_STATUS).map(([k, v]) => <button key={k} className={status === k ? "on" : undefined} onClick={() => { setStatus(k); setPage(1); }}>{v}</button>)}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search"><Icon name="search" /><input className="adm-input" type="search" placeholder="Tìm theo mã đơn, tên / mã khách hàng…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm đơn" /></div>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={34} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">Chưa có đơn nào.</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Mã đơn</th><th>Khách hàng</th><th>Loại</th><th>Số tiền</th><th>Trạng thái</th><th>Ghi nhận</th><th>Tạo lúc</th><th></th></tr></thead>
              <tbody>
                {d.items.map((o) => (
                  <tr key={o.id}>
                    <td className="mono"><b>{o.code}</b></td>
                    <td><Link className="name" href={`/admin/khach-hang/${o.company.id}`}>{o.company.name}</Link><div className="sub mono">{o.company.code}</div></td>
                    <td>{ORDER_KIND[o.kind]}<div className="sub">+{fmtPts(o.points)}</div></td>
                    <td className="adm-neg">{fmtVnd(o.amount)}</td>
                    <td>
                      <span className={`adm-badge ${ORDER_STATUS_CLASS[o.status]}`}>{ORDER_STATUS[o.status]}</span>
                      {o.note && o.status !== "paid" ? <div className="sub" style={{ color: "var(--danger)" }}>{o.note}</div> : null}
                    </td>
                    <td>
                      {o.status === "paid" ? (
                        <>
                          <div>{fmtDateTime(o.paid_at)}</div>
                          <div className="sub">{o.confirmed_by ? `Xác nhận tay: ${o.confirmed_by}` : o.provider_txn_id ? `InfoCMS · ${o.provider_txn_id}` : ""}</div>
                        </>
                      ) : "—"}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(o.created_at)}</td>
                    <td>
                      {o.status !== "paid" ? (
                        <div className="adm-actions">
                          {user.role === "admin" ? <button className="adm-btn sm" onClick={() => setConfirming(o)}>Xác nhận đã nhận tiền</button> : null}
                          {o.status === "pending" ? <button className="adm-btn sm ghost danger" onClick={() => cancel(o)}>Huỷ</button> : null}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d && pages > 1 ? (
          <div className="adm-pager"><span>{d.total} đơn</span><div>
            <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
            <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
          </div></div>
        ) : null}
      </section>
      <ConfirmDialog order={confirming} onClose={() => setConfirming(null)} onDone={() => { setConfirming(null); load(); }} />
    </>
  );
}

function ConfirmDialog({ order, onClose, onDone }: { order: AdminOrder | null; onClose: () => void; onDone: () => void }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setMsg(""), [order]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!order) return;
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    setBusy(true);
    try {
      await api.post(`/orders/${order.id}/confirm`, { note: f.note, paid_amount: Number(f.paid_amount.replace(/\D/g, "")) || null });
      onDone();
    } catch (err) {
      setMsg(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={order !== null} title={`Xác nhận thanh toán ${order?.code ?? ""}`} onClose={onClose}>
      {order ? (
        <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
          <div className="adm-alert">Chỉ xác nhận khi đã thấy tiền về tài khoản (sao kê / InfoCMS). Điểm sẽ được cộng ngay cho <b>{order.company.name}</b>.</div>
          {msg ? <div className="adm-alert">{msg}</div> : null}
          <Field label="Số tiền thực nhận (đ)" htmlFor="cf-amt"><input id="cf-amt" className="adm-input" name="paid_amount" inputMode="numeric" defaultValue={order.amount.toLocaleString("vi-VN")} /></Field>
          <Field label="Ghi chú đối soát (bắt buộc)" htmlFor="cf-note"><input id="cf-note" className="adm-input" name="note" required minLength={3} placeholder="Ví dụ: Sao kê VCB 07/11, FT26311xxxx" /></Field>
          <div className="adm-actions">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button className="adm-btn primary" disabled={busy}>{busy ? "Đang ghi nhận…" : `Xác nhận & cộng ${fmtPts(order.points)}`}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}
