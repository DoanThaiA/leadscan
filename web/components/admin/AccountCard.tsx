"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api, errMsg } from "@/lib/admin/api";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";
import { fmtPts, fmtVnd, ORDER_KIND, ORDER_STATUS, ORDER_STATUS_CLASS, type Order, TX_KIND, type Tx } from "@/lib/commerce";

import { useAdmin } from "./AdminContext";
import { Dialog, Field, Icon, Skeleton } from "./ui";

interface Member { id: number; email: string; full_name: string; is_active: boolean; created_at: string; last_login_at: string | null }
interface Account {
  points_balance: number;
  membership_expires_at: string | null;
  membership_active: boolean;
  members: Member[];
  transactions: Tx[];
  orders: Order[];
  purchases: { id: number; price: number; created_at: string; opportunity: { id: number; code: string; title: string } }[];
}

/** Ví điểm, thành viên, tài khoản đăng nhập, đơn & phiếu đã mua của 1 khách hàng */
export function AccountCard({ companyId, onChanged }: { companyId: number; onChanged: () => void }) {
  const { user } = useAdmin();
  const [a, setA] = useState<Account | null>(null);
  const [tab, setTab] = useState<"tx" | "orders" | "buys">("tx");
  const [adjusting, setAdjusting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => api.get<Account>(`/companies/${companyId}/account`).then(setA, (e) => setError(errMsg(e))), [companyId]);
  useEffect(() => {
    load();
  }, [load]);

  async function toggleMember(m: Member) {
    try {
      await api.patch(`/members/${m.id}`, { is_active: !m.is_active });
      load();
      onChanged();
    } catch (e) {
      alert(errMsg(e));
    }
  }
  async function resetMember(m: Member) {
    const pw = prompt(`Mật khẩu mới cho ${m.email} (≥ 8 ký tự):`);
    if (!pw) return;
    try {
      await api.patch(`/members/${m.id}`, { password: pw });
      alert("Đã đặt mật khẩu mới và đăng xuất mọi thiết bị của tài khoản này.");
      onChanged();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  if (error) return <section className="adm-card"><div className="bd adm-alert">{error}</div></section>;
  if (!a) return <section className="adm-card"><div className="bd"><Skeleton h={120} /></div></section>;

  return (
    <section className="adm-card">
      <div className="hd">
        <h2>Ví điểm & thành viên</h2>
        {user.role === "admin" ? <button className="adm-btn sm" onClick={() => setAdjusting(true)}>Điều chỉnh điểm</button> : null}
      </div>
      <div className="bd" style={{ display: "grid", gap: 16 }}>
        <div className="adm-grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))" }}>
          <div><small className="muted">Số dư</small><div className="adm-price" style={{ fontSize: 22 }}>{fmtPts(a.points_balance)}</div></div>
          <div>
            <small className="muted">Thành viên</small>
            <div style={{ fontWeight: 600, color: a.membership_active ? "var(--ok)" : "var(--danger)" }}>{a.membership_active ? "Đang hiệu lực" : "Chưa kích hoạt / hết hạn"}</div>
            <div className="muted" style={{ fontSize: 12.5 }}>{a.membership_expires_at ? `Đến ${fmtDate(a.membership_expires_at)}` : "—"}</div>
          </div>
        </div>

        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <h3>Tài khoản đăng nhập cổng thành viên</h3>
            <button className="adm-btn sm ghost" onClick={() => setCreating(true)}><Icon name="plus" size={14} /> Thêm</button>
          </div>
          {a.members.length ? a.members.map((m) => (
            <div className="adm-contact" key={m.id}>
              <div className="lines">
                <b>{m.full_name} {m.is_active ? null : <span className="adm-badge s-suspended" style={{ marginLeft: 6 }}>Đã khoá</span>}</b>
                <span>{m.email}</span>
                <span className="muted">Đăng nhập gần nhất: {m.last_login_at ? fmtDateTime(m.last_login_at) : "chưa"}</span>
              </div>
              <div style={{ display: "flex", gap: 4, alignItems: "flex-start" }}>
                <button className="adm-btn sm ghost" onClick={() => resetMember(m)}>Đặt lại MK</button>
                <button className={m.is_active ? "adm-btn sm ghost danger" : "adm-btn sm ghost"} onClick={() => toggleMember(m)}>{m.is_active ? "Khoá" : "Mở"}</button>
              </div>
            </div>
          )) : <p className="muted">Chưa có tài khoản đăng nhập.</p>}
        </div>

        <div>
          <div className="adm-tabs" style={{ padding: 0 }}>
            <button className={tab === "tx" ? "on" : undefined} onClick={() => setTab("tx")}>Lịch sử điểm<span>{a.transactions.length}</span></button>
            <button className={tab === "orders" ? "on" : undefined} onClick={() => setTab("orders")}>Đơn thanh toán<span>{a.orders.length}</span></button>
            <button className={tab === "buys" ? "on" : undefined} onClick={() => setTab("buys")}>Phiếu đã mua<span>{a.purchases.length}</span></button>
          </div>
          <div className="adm-table-wrap">
            <table className="adm-table">
              <tbody>
                {tab === "tx" && a.transactions.map((t) => (
                  <tr key={t.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(t.created_at)}</td>
                    <td>{TX_KIND[t.kind] ?? t.kind}<div className="sub">{t.note}{t.actor ? ` · bởi ${t.actor.full_name}` : ""}</div></td>
                    <td className={t.amount > 0 ? "adm-pos" : "adm-neg"} style={{ textAlign: "right" }}>{t.amount > 0 ? "+" : "−"}{Math.abs(t.amount).toLocaleString("vi-VN")}</td>
                  </tr>
                ))}
                {tab === "orders" && a.orders.map((o) => (
                  <tr key={o.id}>
                    <td className="mono"><b>{o.code}</b><div className="sub">{fmtDateTime(o.created_at)}</div></td>
                    <td>{ORDER_KIND[o.kind]} · {fmtVnd(o.amount)}</td>
                    <td><span className={`adm-badge ${ORDER_STATUS_CLASS[o.status]}`}>{ORDER_STATUS[o.status]}</span>{o.invoice ? <div className="sub">HĐ: {o.invoice.status === "issued" ? `đã xuất #${o.invoice.invoice_number}` : "chờ xuất"}</div> : null}</td>
                  </tr>
                ))}
                {tab === "buys" && a.purchases.map((p) => (
                  <tr key={p.id}>
                    <td><Link className="name" href={`/admin/co-hoi/${p.opportunity.id}`}>{p.opportunity.title}</Link><div className="sub mono">{p.opportunity.code}</div></td>
                    <td className="adm-neg">{fmtPts(p.price)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(tab === "tx" ? a.transactions : tab === "orders" ? a.orders : a.purchases).length === 0 ? <div className="adm-empty">Chưa có dữ liệu.</div> : null}
          </div>
        </div>
      </div>

      <AdjustDialog open={adjusting} companyId={companyId} onClose={() => setAdjusting(false)} onDone={() => { setAdjusting(false); load(); onChanged(); }} />
      <CreateMemberDialog open={creating} companyId={companyId} onClose={() => setCreating(false)} onDone={() => { setCreating(false); load(); onChanged(); }} />
    </section>
  );
}

function AdjustDialog({ open, companyId, onClose, onDone }: { open: boolean; companyId: number; onClose: () => void; onDone: () => void }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    const n = Number(f.amount.replace(/[^\d]/g, "")) * (f.sign === "-" ? -1 : 1);
    setBusy(true);
    setMsg("");
    try {
      await api.post(`/companies/${companyId}/wallet/adjust`, { amount: n, note: f.note });
      onDone();
    } catch (err) {
      setMsg(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} title="Điều chỉnh điểm" onClose={onClose}>
      {open ? (
        <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
          {msg ? <div className="adm-alert">{msg}</div> : null}
          <div className="adm-form">
            <Field label="Loại" htmlFor="a-sign"><select id="a-sign" className="adm-input" name="sign"><option value="+">Cộng điểm</option><option value="-">Trừ điểm</option></select></Field>
            <Field label="Số điểm" htmlFor="a-amt"><input id="a-amt" className="adm-input" name="amount" inputMode="numeric" required /></Field>
            <Field label="Lý do (bắt buộc, khách hàng sẽ thấy)" full htmlFor="a-note"><input id="a-note" className="adm-input" name="note" required minLength={3} maxLength={300} placeholder="Ví dụ: Hoàn điểm phiếu CH-000012 do đầu mối sai" /></Field>
          </div>
          <div className="adm-actions">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Ghi nhận"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}

function CreateMemberDialog({ open, companyId, onClose, onDone }: { open: boolean; companyId: number; onClose: () => void; onDone: () => void }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setMsg("");
    try {
      await api.post(`/companies/${companyId}/members`, f);
      onDone();
    } catch (err) {
      setMsg(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} title="Thêm tài khoản đăng nhập" onClose={onClose}>
      {open ? (
        <form onSubmit={submit} style={{ display: "grid", gap: 14 }} noValidate>
          {msg ? <div className="adm-alert">{msg}</div> : null}
          <Field label="Họ và tên" htmlFor="mb-name"><input id="mb-name" className="adm-input" name="full_name" maxLength={100} autoFocus /></Field>
          <Field label="Email đăng nhập" htmlFor="mb-email"><input id="mb-email" className="adm-input" name="email" type="email" maxLength={150} autoComplete="off" /></Field>
          <Field label="Mật khẩu ban đầu (≥ 8 ký tự)" htmlFor="mb-pw"><input id="mb-pw" className="adm-input" name="password" type="password" autoComplete="new-password" /></Field>
          <div className="adm-actions">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button className="adm-btn primary" disabled={busy}>{busy ? "Đang tạo…" : "Tạo tài khoản"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}
