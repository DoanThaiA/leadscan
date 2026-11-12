"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Dialog, Field, StatusBadge } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";
import type { AdminPartnerDetail } from "@/lib/admin/partners";
import type { Credit, WalletSummary } from "@/lib/partner/api";
import { vnd } from "@/lib/partner/content";

const STATE_BADGE = { pending: "contacted", available: "active", void: "suspended" } as const;

/** Bảng khoản ghi ví (dùng ở chi tiết đối tác và chi tiết cơ hội đối tác) — kèm căn cứ tính để đối soát. */
export function CreditTable({ items, showSub = true }: { items: Credit[]; showSub?: boolean }) {
  if (!items.length) return <div className="adm-empty">Chưa có khoản ghi ví.</div>;
  return (
    <div className="adm-table-wrap">
      <table className="adm-table">
        <thead><tr><th>Ngày</th><th>Khoản</th>{showSub ? <th>Cơ hội</th> : null}<th style={{ textAlign: "right" }}>Số tiền</th><th>Trạng thái</th></tr></thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id}>
              <td style={{ whiteSpace: "nowrap" }} title={fmtDateTime(c.created_at)}>{fmtDate(c.created_at)}</td>
              <td>
                <div>{c.kind_label}{c.purchase_id ? <span className="muted"> · lượt mua #{c.purchase_id}</span> : null}</div>
                <div className="sub">{c.note}{c.actor ? ` — ${c.actor}` : ""}</div>
                {c.calc ? <div className="sub mono" title="Căn cứ tính">{Object.entries(c.calc).map(([k, v]) => `${k}=${typeof v === "number" ? v.toLocaleString("vi-VN") : v}`).join(" · ")}</div> : null}
              </td>
              {showSub ? <td>{c.submission ? <Link href={`/admin/xac-minh-doi-tac/${c.submission.id}`} className="mono" style={{ color: "var(--brand-600)" }}>{c.submission.code}</Link> : "—"}</td> : null}
              <td style={{ textAlign: "right", whiteSpace: "nowrap", fontWeight: 600, color: c.amount < 0 ? "var(--danger)" : undefined, textDecoration: c.state === "void" ? "line-through" : undefined }}>
                {c.amount > 0 ? "+" : ""}{vnd(c.amount)}
              </td>
              <td>
                <StatusBadge status={STATE_BADGE[c.state]} label={c.state_label} />
                {c.state === "pending" ? <div className="sub">{c.available_at ? `Khả dụng ${fmtDate(c.available_at)}` : "Khi phiếu xuất bản"}</div> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Ví hoa hồng của 1 đối tác: số dư, hạn mức, thoả thuận riêng, điều chỉnh tay (quản trị viên), lịch sử khoản ghi. */
export function PartnerWalletCard({ p, isAdmin, onChanged }: { p: AdminPartnerDetail; isAdmin: boolean; onChanged: (d: AdminPartnerDetail, msg: string) => void }) {
  const [items, setItems] = useState<Credit[] | null>(null);
  const [dlg, setDlg] = useState<null | "adjust" | "terms">(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [rate, setRate] = useState("");
  const [quota, setQuota] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const w: WalletSummary = p.wallet;

  useEffect(() => {
    api.get<{ items: Credit[] }>(`/partners/${p.id}/wallet?page_size=100`).then((r) => setItems(r.items), () => setItems([]));
  }, [p.id, w.total, w.available]);

  async function submit(fn: () => Promise<AdminPartnerDetail>, ok: string) {
    setBusy(true);
    setErr("");
    try {
      onChanged(await fn(), ok);
      setDlg(null);
      setAmount("");
      setReason("");
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  const openTerms = () => {
    setRate(p.custom_rate === null ? "" : String(p.custom_rate));
    setQuota(p.custom_cafe_quota === null ? "" : String(p.custom_cafe_quota));
    setErr("");
    setDlg("terms");
  };

  return (
    <section className="adm-card">
      <div className="hd">
        <h2>Ví hoa hồng</h2>
        {isAdmin ? (
          <div className="adm-actions">
            <button className="adm-btn sm" onClick={openTerms}>Thoả thuận riêng</button>
            <button className="adm-btn sm" onClick={() => { setErr(""); setDlg("adjust"); }}>Điều chỉnh</button>
          </div>
        ) : null}
      </div>
      <div className="bd" style={{ display: "grid", gap: 12 }}>
        <dl className="adm-kv">
          <dt>Chờ duyệt</dt><dd><b>{vnd(w.pending)}</b></dd>
          <dt>Khả dụng</dt><dd><b style={{ color: w.available < 0 ? "var(--danger)" : undefined }}>{vnd(w.available)}</b></dd>
          <dt>Đang rút · Đã rút</dt><dd>{vnd(w.withdrawing)} · {vnd(w.paid)} <Link href="/admin/rut-tien-doi-tac" style={{ color: "var(--brand-600)" }}>lệnh rút</Link></dd>
          <dt>Tháng này</dt><dd>{vnd(w.month)}</dd>
          <dt>Hoa hồng</dt><dd>{w.rate}%{p.custom_rate !== null ? " (thoả thuận riêng)" : ` (hạng ${p.tier_label})`}</dd>
          <dt>Ly cafe tháng này</dt><dd>{w.cafe_used}/{w.cafe_quota}{p.custom_cafe_quota !== null ? " (thoả thuận riêng)" : ""}</dd>
          <dt>Hồ sơ thanh toán</dt>
          <dd>
            {p.payout_profile ? (
              <>
                {p.payout_profile.legal_name} · {p.payout_profile.bank_name} {p.payout_profile.account_masked}
                {p.payout_profile.shared_with?.length ? <div style={{ color: "var(--danger)", fontSize: 12.5 }}>⚠ Tài khoản ngân hàng trùng đối tác {p.payout_profile.shared_with.join(", ")}</div> : null}
              </>
            ) : <span className="muted">Chưa có (chỉ cần khi rút tiền)</span>}
          </dd>
        </dl>
      </div>
      {items === null ? <div className="adm-empty">Đang tải…</div> : <CreditTable items={items} />}

      <Dialog open={dlg === "adjust"} title="Điều chỉnh ví đối tác" onClose={() => setDlg(null)}
        footer={<><button className="adm-btn" onClick={() => setDlg(null)}>Huỷ</button>
          <button className="adm-btn primary" disabled={busy || !Number(amount) || reason.trim().length < 3}
            onClick={() => submit(() => api.post(`/partners/${p.id}/adjust`, { amount: Number(amount), reason }), "Đã điều chỉnh ví.")}>Ghi điều chỉnh</button></>}>
        <div style={{ display: "grid", gap: 12 }}>
          {err ? <div className="adm-alert">{err}</div> : null}
          <p className="muted" style={{ fontSize: 13 }}>Ghi 1 khoản vào Khả dụng ngay (số âm để trừ). Dùng khi bù lỗi tính, thưởng riêng theo hợp đồng… Không sửa/xoá khoản đã ghi.</p>
          <Field label="Số tiền (đ)" htmlFor="aj-amount"><input id="aj-amount" className="adm-input" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="vd 50000 hoặc -30000" /></Field>
          <Field label="Lý do (bắt buộc, đối tác thấy)" htmlFor="aj-reason"><input id="aj-reason" className="adm-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></Field>
        </div>
      </Dialog>

      <Dialog open={dlg === "terms"} title="Thoả thuận riêng" onClose={() => setDlg(null)}
        footer={<><button className="adm-btn" onClick={() => setDlg(null)}>Huỷ</button>
          <button className="adm-btn primary" disabled={busy}
            onClick={() => submit(() => api.patch(`/partners/${p.id}`, { custom_rate: rate === "" ? null : Number(rate), custom_cafe_quota: quota === "" ? null : Number(quota), reason }), "Đã lưu thoả thuận riêng.")}>Lưu</button></>}>
        <div style={{ display: "grid", gap: 12 }}>
          {err ? <div className="adm-alert">{err}</div> : null}
          <p className="muted" style={{ fontSize: 13 }}>Thường dùng cho hạng Chiến lược (hiệp hội, hội chợ, KCN). Để trống = theo cấu hình chung của hạng. Áp dụng cho khoản ghi từ nay.</p>
          <Field label="Hoa hồng phiếu thường (%)" htmlFor="tm-rate"><input id="tm-rate" className="adm-input" type="number" min={0} max={50} value={rate} onChange={(e) => setRate(e.target.value)} placeholder="theo hạng" /></Field>
          <Field label="Hạn mức ly cafe / tháng" htmlFor="tm-quota"><input id="tm-quota" className="adm-input" type="number" min={0} value={quota} onChange={(e) => setQuota(e.target.value)} placeholder="theo hạng" /></Field>
          <Field label="Lý do / số hợp đồng" htmlFor="tm-reason"><input id="tm-reason" className="adm-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></Field>
        </div>
      </Dialog>
    </section>
  );
}
