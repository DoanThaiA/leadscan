"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Dialog, Field, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";
import type { AdminWithdrawal, PayoutBatch } from "@/lib/admin/partners";
import { vnd } from "@/lib/partner/content";

const BADGE = { requested: "contacted", approved: "new", paid: "active", rejected: "rejected", cancelled: "suspended" } as const;
const BATCH_BADGE = { draft: "contacted", exported: "new", paid: "active" } as const;
const TABS: [string, string][] = [["open", "Cần xử lý"], ["paid", "Đã chi"], ["rejected", "Từ chối"], ["all", "Tất cả"]];

interface ListRes { total: number; items: AdminWithdrawal[]; counts: Record<string, number>; next_pay_date: string }
interface BatchRes { items: PayoutBatch[]; approved_unbatched: number; next_pay_date: string }
interface TaxRes { items: { code: string; partner: string; legal_name: string; tax_code: string; amount: number; tax: number; net: number; paid_at: string; tax_cert_no: string }[]; total_amount: number; total_tax: number }

function Flags({ w }: { w: AdminWithdrawal }) {
  const f: string[] = [];
  if (!w.name_match) f.push("Tên chủ TK không khớp hồ sơ");
  if (w.shared_with.length) f.push(`TK trùng đối tác ${w.shared_with.join(", ")}`);
  if (w.profile_changed) f.push("Đối tác đã đổi TK sau khi đặt lệnh");
  if (w.needs_invoice) f.push("Tổ chức: chưa có số hoá đơn");
  if (w.partner.status === "locked") f.push("Tài khoản đối tác đang khoá");
  return f.length ? <div style={{ display: "grid", gap: 2 }}>{f.map((x) => <span key={x} style={{ color: "var(--danger)", fontSize: 12 }}>⚠ {x}</span>)}</div> : null;
}

/** Rút tiền đối tác: duyệt lệnh → lập lô theo ngày chi → xuất file chi → chuyển khoản → đánh dấu đã chi (brief mục 9). */
export default function PartnerPayoutsPage() {
  const { user } = useAdmin();
  const isAdmin = user.role === "admin";
  const [tab, setTab] = useState("open");
  const [list, setList] = useState<ListRes | null>(null);
  const [batches, setBatches] = useState<BatchRes | null>(null);
  const [batch, setBatch] = useState<PayoutBatch | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState<AdminWithdrawal | null>(null);
  const [reason, setReason] = useState("");
  const [payDate, setPayDate] = useState("");
  const [paying, setPaying] = useState<PayoutBatch | null>(null);
  const [bankRef, setBankRef] = useState("");
  const [taxPeriod, setTaxPeriod] = useState(() => new Date().toISOString().slice(0, 7));
  const [taxRep, setTaxRep] = useState<TaxRes | null>(null);

  const load = useCallback(() => {
    api.get<ListRes>("/partner-withdrawals" + qs({ status: tab })).then(setList, (e) => setMsg({ ok: false, text: errMsg(e) }));
    api.get<BatchRes>("/partner-payout-batches").then((b) => { setBatches(b); setPayDate((d) => d || b.next_pay_date); }, () => {});
  }, [tab]);

  useEffect(() => {
    document.title = "Rút tiền đối tác · Quản trị LeadScan";
    load();
  }, [load]);

  useEffect(() => {
    const [y, m] = taxPeriod.split("-").map(Number);
    if (y) api.get<TaxRes>("/partner-withdrawals/tax-report" + qs({ year: y, month: m })).then(setTaxRep, () => setTaxRep(null));
  }, [taxPeriod]);

  async function act(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      load();
      if (batch) setBatch(await api.get<PayoutBatch>(`/partner-payout-batches/${batch.id}`));
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  const openBatch = async (b: PayoutBatch) => setBatch(await api.get<PayoutBatch>(`/partner-payout-batches/${b.id}`));

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Rút tiền đối tác</h1>
          <p>Duyệt lệnh rút, lập lô chi theo ngày chi, xuất file chi cho ngân hàng, đánh dấu đã chi</p>
        </div>
        <Link className="adm-btn" href="/admin/doi-tac/cau-hinh">Ngưỡng rút, thuế, ngày chi</Link>
      </div>
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ marginBottom: 16 }}>{msg.text}</div> : null}
      {!isAdmin ? <div className="adm-alert warn" style={{ marginBottom: 16 }}>Chỉ quản trị viên duyệt lệnh, lập lô và xuất file chi.</div> : null}

      <div className="adm-grid side">
        <section className="adm-card">
          <div className="adm-tabs" role="tablist">
            {TABS.map(([k, label]) => {
              const n = list ? (k === "open" ? (list.counts.requested ?? 0) + (list.counts.approved ?? 0) : k === "all" ? Object.values(list.counts).reduce((a, b) => a + b, 0) : list.counts[k] ?? 0) : null;
              return <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : undefined} onClick={() => setTab(k)}>{label}{n !== null ? <span>{n}</span> : null}</button>;
            })}
          </div>
          {!list ? <div className="bd"><Skeleton h={22} /></div> : !list.items.length ? <div className="adm-empty">Không có lệnh rút.</div> : (
            <div className="adm-table-wrap">
              <table className="adm-table">
                <thead><tr><th>Lệnh</th><th>Người nhận</th><th style={{ textAlign: "right" }}>Số tiền</th><th>Trạng thái</th><th /></tr></thead>
                <tbody>
                  {list.items.map((w) => (
                    <tr key={w.id}>
                      <td>
                        <div className="mono"><b>{w.code}</b></div>
                        <div className="sub"><Link href={`/admin/doi-tac/${w.partner.id}`} style={{ color: "var(--brand-600)" }}>{w.partner.code}</Link> · {w.partner.full_name}</div>
                        <div className="sub">{fmtDateTime(w.created_at)}</div>
                      </td>
                      <td>
                        <div>{w.holder}</div>
                        <div className="sub">{w.bank_name} {w.account_masked}{w.tax_code ? ` · MST ${w.tax_code}` : ""}</div>
                        <Flags w={w} />
                      </td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <b>{vnd(w.net_amount)}</b>
                        <div className="sub">{vnd(w.amount)}{w.tax_withheld ? ` − thuế ${vnd(w.tax_withheld)}` : ""}</div>
                      </td>
                      <td>
                        <StatusBadge status={BADGE[w.status]} label={w.status_label} />
                        {w.batch ? <div className="sub">Lô {w.batch.code}</div> : null}
                        {w.reject_reason ? <div className="sub">{w.reject_reason}</div> : null}
                        {w.partner.kind === "org" && w.status !== "rejected" && w.status !== "cancelled" ? (
                          <input className="adm-input" style={{ height: 28, marginTop: 4, width: 130 }} placeholder="Số hoá đơn" defaultValue={w.invoice_no}
                            onBlur={(e) => e.target.value.trim() !== w.invoice_no && act(() => api.patch(`/partner-withdrawals/${w.id}`, { invoice_no: e.target.value }), `Đã lưu số hoá đơn cho ${w.code}.`)} />
                        ) : null}
                        {w.status === "paid" && w.tax_withheld ? (
                          <input className="adm-input" style={{ height: 28, marginTop: 4, width: 130 }} placeholder="Số chứng từ thuế" defaultValue={w.tax_cert_no}
                            onBlur={(e) => e.target.value.trim() !== w.tax_cert_no && act(() => api.patch(`/partner-withdrawals/${w.id}`, { tax_cert_no: e.target.value }), `Đã lưu số chứng từ khấu trừ cho ${w.code}.`)} />
                        ) : null}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {isAdmin && w.status === "requested" ? <button className="adm-btn primary sm" disabled={busy} onClick={() => act(() => api.post(`/partner-withdrawals/${w.id}/approve`), `Đã duyệt ${w.code}.`)}>Duyệt</button> : null}{" "}
                        {isAdmin && (w.status === "requested" || w.status === "approved") ? <button className="adm-btn sm danger" disabled={busy} onClick={() => { setReason(""); setRejecting(w); }}>Từ chối</button> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Lô chi</h2></div>
            <div className="bd" style={{ display: "grid", gap: 10 }}>
              <p className="muted" style={{ fontSize: 13 }}>{batches?.approved_unbatched ?? 0} lệnh đã duyệt chưa vào lô. Lệnh của tổ chức cần số hoá đơn mới vào lô.</p>
              {isAdmin ? (
                <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                  <Field label="Ngày chi" htmlFor="b-date"><input id="b-date" className="adm-input" type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} /></Field>
                  <button className="adm-btn primary" disabled={busy || !batches?.approved_unbatched}
                    onClick={() => act(async () => setBatch(await api.post<PayoutBatch>("/partner-payout-batches", { pay_date: payDate || null })), "Đã lập lô chi.")}>Lập lô</button>
                </div>
              ) : null}
            </div>
            {batches?.items.length ? (
              <div>
                {batches.items.map((b) => (
                  <button key={b.id} className="ptn-list-row" style={{ width: "100%", background: "none", border: 0, borderTop: "1px solid var(--line-2)", textAlign: "left", cursor: "pointer", font: "inherit" }} onClick={() => openBatch(b)}>
                    <div><b className="mono">{b.code}</b><div className="sub">{b.count} lệnh · chi {vnd(b.net)} · ngày {fmtDate(b.pay_date)}</div></div>
                    <StatusBadge status={BATCH_BADGE[b.status]} label={b.status_label} />
                  </button>
                ))}
              </div>
            ) : null}
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Thuế TNCN đã khấu trừ</h2><input className="adm-input" type="month" style={{ width: 150, height: 30 }} value={taxPeriod} onChange={(e) => setTaxPeriod(e.target.value)} /></div>
            <div className="bd" style={{ fontSize: 13.5 }}>
              {taxRep ? (
                <>
                  <p>{taxRep.items.length} lần chi · tổng chi trả {vnd(taxRep.total_amount)} · <b>thuế khấu trừ {vnd(taxRep.total_tax)}</b></p>
                  {taxRep.items.filter((x) => x.tax).map((x) => (
                    <div key={x.code} className="sub" style={{ marginTop: 4 }}>{x.code} · {x.legal_name} · MST {x.tax_code || "(số định danh)"} · thuế {vnd(x.tax)}{x.tax_cert_no ? ` · CT ${x.tax_cert_no}` : " · chưa có chứng từ"}</div>
                  ))}
                  <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>Theo ngày chi. Kế toán cần xác nhận cách xác định “lần chi trả” với ngưỡng mới.</p>
                </>
              ) : <Skeleton h={18} />}
            </div>
          </section>
        </div>
      </div>

      <Dialog open={!!batch} title={batch ? `Lô ${batch.code} — chi ngày ${fmtDate(batch.pay_date)}` : ""} onClose={() => setBatch(null)}
        footer={batch ? <>
          <button className="adm-btn" onClick={() => setBatch(null)}>Đóng</button>
          {isAdmin && batch.status !== "paid" ? <a className="adm-btn" href={`/api/admin/partner-payout-batches/${batch.id}/export`} onClick={() => setTimeout(() => openBatch(batch), 1500)}>Tải file chi (CSV)</a> : null}
          {isAdmin && batch.status === "exported" ? <button className="adm-btn primary" onClick={() => { setBankRef(""); setPaying(batch); }}>Đánh dấu đã chi</button> : null}
        </> : null}>
        {batch ? (
          <div style={{ display: "grid", gap: 10, minWidth: "min(640px, 80vw)" }}>
            <p><StatusBadge status={BATCH_BADGE[batch.status]} label={batch.status_label} /> {batch.count} lệnh · tổng {vnd(batch.gross)} · thuế {vnd(batch.tax)} · <b>chuyển khoản {vnd(batch.net)}</b></p>
            {batch.status === "draft" ? <p className="muted" style={{ fontSize: 13 }}>File chi có số tài khoản đầy đủ — chỉ tải khi chuẩn bị chuyển khoản (có ghi nhật ký). Cột theo mẫu chung; dán sang mẫu chi hộ của ngân hàng nếu cần.</p> : null}
            <table className="adm-table">
              <thead><tr><th>Lệnh</th><th>Người nhận</th><th style={{ textAlign: "right" }}>Chuyển</th></tr></thead>
              <tbody>
                {batch.items?.map((w) => (
                  <tr key={w.id}><td className="mono">{w.code}<div className="sub">{w.partner.code}</div></td><td>{w.holder}<div className="sub">{w.bank_name} {w.account_masked}</div><Flags w={w} /></td><td style={{ textAlign: "right" }}>{vnd(w.net_amount)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Dialog>

      <Dialog open={!!paying} title="Xác nhận đã chuyển khoản" onClose={() => setPaying(null)}
        footer={<><button className="adm-btn" onClick={() => setPaying(null)}>Huỷ</button>
          <button className="adm-btn primary" disabled={busy} onClick={() => paying && act(async () => { setBatch(await api.post<PayoutBatch>(`/partner-payout-batches/${paying.id}/paid`, { bank_ref: bankRef })); setPaying(null); }, "Đã đánh dấu đã chi — đối tác nhận email.")}>Đã chi</button></>}>
        <div style={{ display: "grid", gap: 12 }}>
          <p>Chỉ xác nhận khi ngân hàng đã chuyển xong toàn bộ {paying?.count} lệnh ({vnd(paying?.net ?? 0)}).</p>
          <Field label="Mã giao dịch / số lô ngân hàng (không bắt buộc)" htmlFor="p-ref"><input id="p-ref" className="adm-input" value={bankRef} onChange={(e) => setBankRef(e.target.value)} maxLength={100} /></Field>
        </div>
      </Dialog>

      <Dialog open={!!rejecting} title={`Từ chối lệnh rút ${rejecting?.code ?? ""}`} onClose={() => setRejecting(null)}
        footer={<><button className="adm-btn" onClick={() => setRejecting(null)}>Huỷ</button>
          <button className="adm-btn danger" disabled={busy || reason.trim().length < 3} onClick={() => rejecting && act(async () => { await api.post(`/partner-withdrawals/${rejecting.id}/reject`, { reason }); setRejecting(null); }, `Đã từ chối ${rejecting?.code}, tiền trở lại số dư Khả dụng của đối tác.`)}>Từ chối</button></>}>
        <Field label="Lý do (đối tác thấy, kèm email)" htmlFor="r-reason"><input id="r-reason" className="adm-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></Field>
      </Dialog>
    </>
  );
}
