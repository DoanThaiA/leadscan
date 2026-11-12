"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { Skeleton, StatusBadge } from "@/components/admin/ui";
import { Balances } from "@/components/partner/Balances";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";
import { errMsg, papi, type PayoutProfile, type WalletSummary, type Withdrawal, type WithdrawRules } from "@/lib/partner/api";
import { vnd } from "@/lib/partner/content";

interface Res {
  summary: WalletSummary;
  rules: WithdrawRules;
  profile: PayoutProfile | null;
  items: Withdrawal[];
}

const BADGE = { requested: "contacted", approved: "new", paid: "active", rejected: "rejected", cancelled: "suspended" } as const;

/** Rút tiền (brief 6.2): từ mức tối thiểu Khả dụng, về tài khoản chính chủ, chi theo lô. */
export default function WithdrawPage() {
  const [d, setD] = useState<Res | null>(null);
  const [amount, setAmount] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => papi.get<Res>("/withdrawals").then(setD, (e) => setMsg({ ok: false, text: errMsg(e) }));
  useEffect(() => {
    document.title = "Rút tiền · Đối tác LeadScan";
    load();
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const w = await papi.post<Withdrawal>("/withdrawals", { amount: Number(amount) });
      setAmount("");
      setMsg({ ok: true, text: `Đã tạo lệnh rút ${w.code}. LeadScan duyệt và chi theo lô gần nhất.` });
      await load();
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  async function cancel(w: Withdrawal) {
    if (!confirm(`Huỷ lệnh rút ${w.code}?`)) return;
    try {
      await papi.post(`/withdrawals/${w.id}/cancel`);
      setMsg({ ok: true, text: `Đã huỷ lệnh ${w.code}, tiền trở lại số dư Khả dụng.` });
      await load();
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
    }
  }

  if (!d) return msg ? <div className="adm-alert">{msg.text}</div> : <div style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>;
  const r = d.rules;
  const n = Number(amount) || 0;
  const tax = r.withholds_tax && n >= r.tax_threshold ? Math.floor((n * r.tax_rate) / 100) : 0;
  const amountErr = n && n < r.min ? `Tối thiểu ${vnd(r.min)}` : n > r.max ? `Vượt số dư Khả dụng (${vnd(r.max)})` : "";

  return (
    <>
      <div className="adm-head">
        <div><h1>Rút tiền</h1><p>Về tài khoản ngân hàng chính chủ · chi theo lô {r.pay_days.map((x) => `ngày ${x}`).join(" và ")} hằng tháng</p></div>
      </div>
      <Balances w={d.summary} />
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ margin: "16px 0 0" }}>{msg.text}</div> : null}

      <div className="adm-grid side" style={{ marginTop: 16 }}>
        <section className="adm-card">
          <div className="hd"><h2>Lịch sử rút tiền</h2></div>
          {!d.items.length ? <div className="adm-empty">Chưa có lệnh rút nào.</div> : (
            <div className="adm-table-wrap">
              <table className="adm-table">
                <thead><tr><th>Lệnh</th><th style={{ textAlign: "right" }}>Số tiền</th><th style={{ textAlign: "right" }}>Thuế TNCN</th><th style={{ textAlign: "right" }}>Thực nhận</th><th>Trạng thái</th><th /></tr></thead>
                <tbody>
                  {d.items.map((w) => (
                    <tr key={w.id}>
                      <td><div className="mono"><b>{w.code}</b></div><div className="sub">{fmtDate(w.created_at)} · {w.bank_name} {w.account_masked}</div></td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>{vnd(w.amount)}</td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>{w.tax_withheld ? vnd(w.tax_withheld) : "—"}{w.tax_cert_no ? <div className="sub">CT {w.tax_cert_no}</div> : null}</td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap", fontWeight: 600 }}>{vnd(w.net_amount)}</td>
                      <td>
                        <StatusBadge status={BADGE[w.status]} label={w.status_label} />
                        {w.status === "paid" ? <div className="sub">{fmtDateTime(w.paid_at)}</div> : null}
                        {w.status === "approved" && w.batch ? <div className="sub">Chi ngày {fmtDate(w.batch.pay_date)}</div> : null}
                        {w.reject_reason ? <div className="sub" style={{ color: "var(--danger)" }}>{w.reject_reason}</div> : null}
                      </td>
                      <td>{w.status === "requested" ? <button className="adm-btn sm ghost" onClick={() => cancel(w)}>Huỷ</button> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Tạo lệnh rút</h2></div>
            <form className="bd" style={{ display: "grid", gap: 12 }} onSubmit={submit}>
              {d.profile ? (
                <p style={{ fontSize: 13.5 }}>Về: <b>{d.profile.bank_name} {d.profile.account_masked}</b> — {d.profile.account_holder} · <Link href="/doi-tac/ho-so-thanh-toan" style={{ color: "var(--brand-600)" }}>đổi</Link></p>
              ) : null}
              {!r.can_request ? (
                <div className="adm-alert warn">
                  {r.reason}{" "}
                  {!d.profile ? <Link href="/doi-tac/ho-so-thanh-toan" style={{ fontWeight: 600, textDecoration: "underline" }}>Tạo hồ sơ thanh toán</Link> : null}
                </div>
              ) : (
                <>
                  <div className="adm-field">
                    <label htmlFor="wd-amount">Số tiền rút (đ)</label>
                    <div style={{ display: "flex", gap: 8 }}>
                      <input id="wd-amount" className="adm-input" type="number" min={r.min} max={r.max} step={1000} value={amount} onChange={(e) => setAmount(e.target.value)} />
                      <button type="button" className="adm-btn" onClick={() => setAmount(String(r.max))}>Rút hết</button>
                    </div>
                    {amountErr ? <span className="adm-err">{amountErr}</span> : <span className="muted" style={{ fontSize: 12.5 }}>Từ {vnd(r.min)} đến {vnd(r.max)}</span>}
                  </div>
                  {n >= r.min && !amountErr ? (
                    <dl className="adm-kv" style={{ fontSize: 13.5 }}>
                      <dt>Trừ khỏi ví</dt><dd>{vnd(n)}</dd>
                      {r.withholds_tax ? <><dt>Thuế TNCN</dt><dd>{tax ? `${vnd(tax)} (${r.tax_rate}%)` : `0đ (dưới ${vnd(r.tax_threshold)}/lần)`}</dd></> : null}
                      <dt>Thực nhận</dt><dd><b>{vnd(n - tax)}</b></dd>
                      <dt>Dự kiến chi</dt><dd>{fmtDate(r.next_pay_date)}</dd>
                    </dl>
                  ) : null}
                  <button className="adm-btn primary" disabled={busy || !n || !!amountErr}>{busy ? "Đang tạo…" : "Tạo lệnh rút"}</button>
                </>
              )}
            </form>
          </section>
          <section className="adm-card">
            <div className="hd"><h2>Quy định</h2></div>
            <div className="bd" style={{ display: "grid", gap: 6, fontSize: 13, color: "var(--ink-2)" }}>
              <p>Rút từ {vnd(r.min)} Khả dụng; mỗi lúc 1 lệnh, tối đa {r.month_max} lệnh/tháng (tháng này: {r.month_count}).</p>
              <p>LeadScan duyệt và chi theo lô {r.pay_days.map((x) => `ngày ${x}`).join(" và ")}, tiền về trong 3 ngày làm việc.</p>
              {r.withholds_tax ? <p>Cá nhân: lệnh từ {vnd(r.tax_threshold)} trở lên khấu trừ {r.tax_rate}% thuế TNCN, LeadScan cấp chứng từ khấu trừ.</p> : null}
              {r.needs_invoice ? <p>Tổ chức: gửi hoá đơn cho khoản hoa hồng — LeadScan chi sau khi nhận hoá đơn.</p> : null}
              <p>Lệnh đang chờ duyệt có thể huỷ; tiền trở lại số dư Khả dụng.</p>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
