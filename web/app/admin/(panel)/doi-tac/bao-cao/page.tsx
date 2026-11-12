"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { vnd } from "@/lib/partner/content";

interface KpiItem { key: string; label: string; value: number | null; unit: string; target: number; better: "higher" | "lower"; note: string; met: boolean | null }
interface Kpi { items: KpiItem[]; met: number; total: number; gate_passed: boolean; revenue: number; cost: number; adjust: number; sent: number; ok: number; sold: number }
interface PerfRow { key: string | number; label: string; sent: number; ok: number; open: number; sold: number; revenue: number; cost: number; pass_rate: number | null; cost_ratio: number | null }
interface Perf { group: string; items: PerfRow[]; totals: Omit<PerfRow, "key" | "label"> }
interface LiabRow { partner: { id: number; code: string; full_name: string; tier: string }; pending: number; available: number; withdrawing: number; paid: number; owed: number }
interface Liab { items: LiabRow[]; totals: Omit<LiabRow, "partner"> }

const GROUPS: [string, string][] = [["partner", "Đối tác"], ["industry", "Ngành"], ["province", "Tỉnh/thành"]];
const pct = (v: number | null) => (v === null ? "—" : `${v.toLocaleString("vi-VN")}%`);

/** Ngày theo giờ máy (yyyy-mm-dd) — kỳ báo cáo backend tính theo giờ Việt Nam. */
const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
function preset(key: string): [string, string] {
  const now = new Date();
  if (key === "month") return [ymd(new Date(now.getFullYear(), now.getMonth(), 1)), ymd(now)];
  if (key === "prev") return [ymd(new Date(now.getFullYear(), now.getMonth() - 1, 1)), ymd(new Date(now.getFullYear(), now.getMonth(), 0))];
  const days = Number(key);
  return [ymd(new Date(now.getFullYear(), now.getMonth(), now.getDate() - days + 1)), ymd(now)];
}
const PRESETS: [string, string][] = [["month", "Tháng này"], ["prev", "Tháng trước"], ["30", "30 ngày"], ["90", "90 ngày"]];

/** Ô KPI: giá trị + mục tiêu + trạng thái bằng biểu tượng và chữ (không chỉ dựa vào màu). */
function KpiTile({ k }: { k: KpiItem }) {
  const status = k.met === null ? { icon: "–", text: "Chưa có dữ liệu", color: "var(--muted)" } : k.met ? { icon: "✓", text: "Đạt mục tiêu", color: "var(--ok)" } : { icon: "✗", text: "Chưa đạt", color: "var(--danger)" };
  return (
    <section className="adm-card adm-stat">
      <small>{k.label}</small>
      <b>{k.value === null ? "—" : `${k.value.toLocaleString("vi-VN")}${k.unit}`}</b>
      <span style={{ display: "block" }}>Mục tiêu {k.better === "higher" ? "≥" : "≤"} {k.target.toLocaleString("vi-VN")}{k.unit}</span>
      <span style={{ display: "block", color: status.color, fontWeight: 600, marginTop: 4 }}><span aria-hidden="true">{status.icon}</span> {status.text}</span>
      <span style={{ display: "block", marginTop: 2 }}>{k.note}</span>
    </section>
  );
}

/** Báo cáo Đối tác (brief mục 2 & 9): KPI thí điểm, hiệu quả theo đối tác/ngành/tỉnh, công nợ. Thuế TNCN ở trang Rút tiền đối tác. */
export default function PartnerReportsPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [group, setGroup] = useState("partner");
  const [tab, setTab] = useState<"perf" | "liab">("perf");
  const [kpi, setKpi] = useState<Kpi | null>(null);
  const [perf, setPerf] = useState<Perf | null>(null);
  const [liab, setLiab] = useState<Liab | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Báo cáo đối tác · Quản trị LeadScan";
  }, []);
  useEffect(() => {
    setKpi(null);
    setError("");
    api.get<Kpi>("/partner-reports/kpi" + qs({ from, to })).then(setKpi, (e) => setError(errMsg(e)));
  }, [from, to]);
  useEffect(() => {
    setPerf(null);
    api.get<Perf>("/partner-reports/performance" + qs({ group, from, to })).then(setPerf, (e) => setError(errMsg(e)));
  }, [group, from, to]);
  useEffect(() => {
    if (tab === "liab" && !liab) api.get<Liab>("/partner-reports/liabilities").then(setLiab, (e) => setError(errMsg(e)));
  }, [tab, liab]);

  const badRange = !!(from && to && from > to);
  const active = PRESETS.find(([k]) => { const [f, t] = preset(k); return f === from && t === to; })?.[0];

  return (
    <>
      <div className="adm-head">
        <div>
          <Link href="/admin/doi-tac" className="muted" style={{ fontSize: 13 }}>← Đối tác</Link>
          <h1 style={{ marginTop: 4 }}>Báo cáo đối tác</h1>
          <p>KPI thí điểm 90 ngày, hiệu quả và chi phí theo đối tác / ngành / tỉnh, công nợ phải trả</p>
        </div>
        <div className="adm-actions" style={{ alignItems: "flex-end" }}>
          <label className="adm-field" style={{ gap: 2 }}><span className="muted" style={{ fontSize: 12 }}>Từ ngày</span><input className="adm-input" type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} /></label>
          <label className="adm-field" style={{ gap: 2 }}><span className="muted" style={{ fontSize: 12 }}>Đến ngày</span><input className="adm-input" type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} /></label>
        </div>
      </div>
      <div role="group" aria-label="Chọn nhanh kỳ báo cáo" style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
        <button className={!from && !to ? "adm-btn primary sm" : "adm-btn sm"} aria-pressed={!from && !to} onClick={() => { setFrom(""); setTo(""); }}>Toàn thời gian</button>
        {PRESETS.map(([k, label]) => (
          <button key={k} className={active === k ? "adm-btn primary sm" : "adm-btn sm"} aria-pressed={active === k} onClick={() => { const [f, t] = preset(k); setFrom(f); setTo(t); }}>{label}</button>
        ))}
      </div>
      {badRange ? <div className="adm-alert warn" style={{ marginBottom: 16 }}>“Từ ngày” đang sau “Đến ngày” — kỳ báo cáo rỗng.</div> : null}
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      {!kpi ? <Skeleton h={120} /> : (
        <>
          <div className={kpi.gate_passed ? "adm-alert ok" : "adm-alert warn"} style={{ marginBottom: 16 }}>
            <b>{kpi.gate_passed ? "✓ Đạt cổng chuyển giai đoạn" : "Chưa đạt cổng chuyển giai đoạn"}</b> — {kpi.met}/{kpi.total} KPI đạt mục tiêu
            (cần ≥ 3/5, bắt buộc chi phí đối tác / doanh thu ≤ 35%). Doanh thu phiếu từ cơ hội đối tác {vnd(kpi.revenue)} (chưa gồm GTGT) · chi phí đối tác {vnd(kpi.cost)}
            {kpi.adjust ? ` · điều chỉnh tay ${vnd(kpi.adjust)} (không tính vào tỷ lệ)` : ""}.
          </div>
          <div className="adm-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", marginBottom: 16 }}>
            {kpi.items.map((k) => <KpiTile key={k.key} k={k} />)}
          </div>
        </>
      )}

      <section className="adm-card">
        <div className="adm-tabs" role="tablist">
          <button role="tab" aria-selected={tab === "perf"} className={tab === "perf" ? "on" : undefined} onClick={() => setTab("perf")}>Hiệu quả & chi phí</button>
          <button role="tab" aria-selected={tab === "liab"} className={tab === "liab" ? "on" : undefined} onClick={() => setTab("liab")}>Công nợ đối tác</button>
        </div>

        {tab === "perf" ? (
          <>
            <div className="adm-toolbar">
              <div role="group" aria-label="Nhóm theo" style={{ display: "flex", gap: 6 }}>
                {GROUPS.map(([k, label]) => <button key={k} className={group === k ? "adm-btn primary sm" : "adm-btn sm"} aria-pressed={group === k} onClick={() => setGroup(k)}>Theo {label.toLowerCase()}</button>)}
              </div>
              <a className="adm-btn sm" style={{ marginLeft: "auto" }} href={`/api/admin/partner-reports/performance${qs({ group, from, to, format: "csv" })}`}>Tải CSV</a>
            </div>
            {!perf ? <div className="bd"><Skeleton h={22} /></div> : !perf.items.length ? <div className="adm-empty">Chưa có cơ hội đối tác trong kỳ.</div> : (
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead>
                    <tr>
                      <th>{GROUPS.find(([k]) => k === group)?.[1]}</th>
                      <th style={{ textAlign: "right" }}>Đã gửi</th><th style={{ textAlign: "right" }}>Đạt</th><th style={{ textAlign: "right" }}>Tỷ lệ đạt</th>
                      <th style={{ textAlign: "right" }}>Bán được</th><th style={{ textAlign: "right" }}>Doanh thu thuần</th><th style={{ textAlign: "right" }}>Chi phí đối tác</th><th style={{ textAlign: "right" }}>Chi phí / DT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {perf.items.map((r) => (
                      <tr key={String(r.key)}>
                        <td>{group === "partner" ? <Link href={`/admin/doi-tac/${r.key}`} style={{ color: "var(--brand-600)" }}>{r.label}</Link> : r.label}{r.open ? <div className="sub">{r.open} đang xác minh</div> : null}</td>
                        <td style={{ textAlign: "right" }}>{r.sent}</td><td style={{ textAlign: "right" }}>{r.ok}</td><td style={{ textAlign: "right" }}>{pct(r.pass_rate)}</td>
                        <td style={{ textAlign: "right" }}>{r.sold}</td><td style={{ textAlign: "right", whiteSpace: "nowrap" }}>{vnd(r.revenue)}</td>
                        <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>{vnd(r.cost)}</td>
                        <td style={{ textAlign: "right", whiteSpace: "nowrap", fontWeight: r.cost_ratio !== null && r.cost_ratio > 35 ? 700 : undefined }}>
                          {pct(r.cost_ratio)}{r.cost_ratio !== null && r.cost_ratio > 35 ? <span title="Vượt 35%"> ⚠</span> : null}
                        </td>
                      </tr>
                    ))}
                    <tr style={{ fontWeight: 700 }}>
                      <td>Tổng</td><td style={{ textAlign: "right" }}>{perf.totals.sent}</td><td style={{ textAlign: "right" }}>{perf.totals.ok}</td><td style={{ textAlign: "right" }}>{pct(perf.totals.pass_rate)}</td>
                      <td style={{ textAlign: "right" }}>{perf.totals.sold}</td><td style={{ textAlign: "right" }}>{vnd(perf.totals.revenue)}</td><td style={{ textAlign: "right" }}>{vnd(perf.totals.cost)}</td><td style={{ textAlign: "right" }}>{pct(perf.totals.cost_ratio)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
            <p className="muted" style={{ fontSize: 12.5, padding: "10px 14px" }}>Nhóm theo cơ hội gửi trong kỳ; doanh thu và chi phí tính trên toàn bộ vòng đời của các cơ hội đó. Doanh thu chưa gồm GTGT, đã trừ phần hoàn phiếu.</p>
          </>
        ) : (
          <>
            <div className="adm-toolbar">
              <span className="muted" style={{ fontSize: 13 }}>Số LeadScan đang nợ = Chờ duyệt + Khả dụng chưa rút + Đang rút. Không lọc theo kỳ (số dư tại thời điểm xem).</span>
              <a className="adm-btn sm" style={{ marginLeft: "auto" }} href="/api/admin/partner-reports/liabilities?format=csv">Tải CSV</a>
            </div>
            {!liab ? <div className="bd"><Skeleton h={22} /></div> : !liab.items.length ? <div className="adm-empty">Chưa có công nợ.</div> : (
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead><tr><th>Đối tác</th><th style={{ textAlign: "right" }}>Chờ duyệt</th><th style={{ textAlign: "right" }}>Khả dụng</th><th style={{ textAlign: "right" }}>Đang rút</th><th style={{ textAlign: "right" }}>Đang nợ</th><th style={{ textAlign: "right" }}>Đã chi</th></tr></thead>
                  <tbody>
                    {liab.items.map((r) => (
                      <tr key={r.partner.id}>
                        <td><Link href={`/admin/doi-tac/${r.partner.id}`} style={{ color: "var(--brand-600)" }}>{r.partner.code}</Link> · {r.partner.full_name}<div className="sub">Hạng {r.partner.tier}</div></td>
                        <td style={{ textAlign: "right" }}>{vnd(r.pending)}</td><td style={{ textAlign: "right" }}>{vnd(r.available)}</td><td style={{ textAlign: "right" }}>{vnd(r.withdrawing)}</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>{vnd(r.owed)}</td><td style={{ textAlign: "right" }}>{vnd(r.paid)}</td>
                      </tr>
                    ))}
                    <tr style={{ fontWeight: 700 }}>
                      <td>Tổng</td><td style={{ textAlign: "right" }}>{vnd(liab.totals.pending)}</td><td style={{ textAlign: "right" }}>{vnd(liab.totals.available)}</td><td style={{ textAlign: "right" }}>{vnd(liab.totals.withdrawing)}</td>
                      <td style={{ textAlign: "right" }}>{vnd(liab.totals.owed)}</td><td style={{ textAlign: "right" }}>{vnd(liab.totals.paid)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>
    </>
  );
}
