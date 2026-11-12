"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Field, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";

interface PField { key: string; label: string; type: "int" | "float"; min: number; max: number; default: number }
interface PView {
  values: Record<string, number>;
  fields: PField[];
  logs: { key: string; old: string; new: string; reason: string; actor: string | null; created_at: string }[];
}
interface Breakdown { base: number; score: number; urgency: number; info: number; value: number; price: number }
interface Scenario { score: number; base?: number; days_left?: number | null; info_pct?: number; value_vnd?: number; opp_code?: string }
interface PreviewItem {
  opportunity: { code: string; title: string; base: number; deadline: string | null; info_pct: number; value_vnd: number; estimated_value: string } | null;
  current: Breakdown;
  draft: Breakdown;
}

const GROUPS: { title: string; note: string; keys: string[] }[] = [
  { title: "Giá cơ bản & làm tròn", note: "Giá cơ bản đặt riêng cho từng phiếu; thấp hơn mức tối thiểu thì tính theo mức tối thiểu. Phiếu giá cơ bản 0 = miễn phí.", keys: ["min_price", "round_to"] },
  { title: "Hệ số điểm phù hợp", note: "Điểm so khớp giữa phiếu và phiếu tìm cơ hội của từng doanh nghiệp — điểm càng cao giá càng cao.", keys: ["score_from", "score_max_mult", "score_curve"] },
  { title: "Hệ số gấp (hạn chót)", note: "Không có hạn chót, còn trên 30 ngày hoặc đã quá hạn: ×1.", keys: ["urg_30", "urg_14", "urg_7", "urg_3"] },
  { title: "Hệ số đủ thông tin", note: "10 mục: bên mua, tên / chức vụ / SĐT / email đầu mối, quy mô, giá trị, hạn chót, link nguồn, mô tả ≥ 100 ký tự. Hệ số tăng đều theo tỷ lệ mục có đủ.", keys: ["info_full_mult"] },
];
const VALUE_ROWS: [string | null, string][] = [[null, "value_m0"], ["value_t1", "value_m1"], ["value_t2", "value_m2"], ["value_t3", "value_m3"], ["value_t4", "value_m4"]];
const SCORES = [50, 60, 70, 80, 86, 90, 100];
const EXAMPLES: { label: string; sc: Scenario }[] = [
  { label: "Điểm 70, không hạn chót, ít thông tin", sc: { score: 70 } },
  { label: "Điểm 86, còn 7 ngày, đủ 80%, đơn ~3 tỷ", sc: { score: 86, days_left: 7, info_pct: 80, value_vnd: 3_000_000_000 } },
  { label: "Điểm 100, còn 3 ngày, đủ 100%, đơn > 20 tỷ", sc: { score: 100, days_left: 3, info_pct: 100, value_vnd: 25_000_000_000 } },
];

const vnd = (n: number) => `${fmtNum(n)}đ`;
const x = (n: number) => `×${n.toLocaleString("vi-VN", { maximumFractionDigits: 3 })}`;
function money(n: number) {
  if (n >= 1e9) return `${(n / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tỷ`;
  if (n >= 1e6) return `${(n / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} triệu`;
  return vnd(n);
}

/** Giá + mũi tên so sánh: giá đang áp dụng → giá theo bản đang sửa. */
function PriceCell({ cur, draft }: { cur: number; draft: number }) {
  if (cur === draft) return <b>{vnd(cur)}</b>;
  return <span style={{ whiteSpace: "nowrap" }}><span className="muted" style={{ textDecoration: "line-through" }}>{vnd(cur)}</span> → <b style={{ color: draft > cur ? "var(--danger)" : "var(--ok)" }}>{vnd(draft)}</b></span>;
}

/** Công thức giá phiếu cơ hội — chỉnh tham số, xem thử giá trước khi lưu. Chỉ quản trị viên được lưu. */
export default function PricingFormulaPage() {
  const { user } = useAdmin();
  const isAdmin = user.role === "admin";
  const [data, setData] = useState<PView | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [calc, setCalc] = useState({ opp_code: "", base: "29000", score: "80", days_left: "", info_pct: "60", value: "" });
  const [preview, setPreview] = useState<{ calc: PreviewItem | null; scores: PreviewItem[]; examples: PreviewItem[] } | null>(null);
  const [previewErr, setPreviewErr] = useState("");

  function load(d: PView) {
    setData(d);
    setVals(Object.fromEntries(Object.entries(d.values).map(([k, v]) => [k, String(v)])));
  }

  useEffect(() => {
    document.title = "Công thức giá phiếu · Quản trị LeadScan";
    api.get<PView>("/pricing").then(load, (e) => setMsg({ ok: false, text: errMsg(e) }));
  }, []);

  const changed = useMemo(() => {
    if (!data) return {};
    return Object.fromEntries(Object.entries(vals).filter(([k, v]) => v.trim() !== "" && Number(v) !== data.values[k]).map(([k, v]) => [k, Number(v)]));
  }, [vals, data]);
  const nChanged = Object.keys(changed).length;
  const hasBlank = Object.values(vals).some((v) => v.trim() === "" || Number.isNaN(Number(v)));

  // Xem thử: gọi lại sau 300ms mỗi khi sửa tham số hoặc ô máy tính
  useEffect(() => {
    if (!data || hasBlank) return;
    const calcSc: Scenario = calc.opp_code.trim()
      ? { score: Number(calc.score) || 0, opp_code: calc.opp_code.trim() }
      : { score: Number(calc.score) || 0, base: Number(calc.base) || 0, days_left: calc.days_left.trim() === "" ? null : Number(calc.days_left),
          info_pct: Number(calc.info_pct) || 0, value_vnd: Math.round((Number(calc.value) || 0) * 1e9) };
    const scenarios = [calcSc, ...SCORES.map((s) => ({ score: s })), ...EXAMPLES.map((e) => e.sc)];
    const t = setTimeout(() => {
      api.post<{ items: PreviewItem[] }>("/pricing/preview", { values: changed, scenarios }).then(
        (r) => { setPreview({ calc: r.items[0], scores: r.items.slice(1, 1 + SCORES.length), examples: r.items.slice(1 + SCORES.length) }); setPreviewErr(""); },
        (e) => setPreviewErr(errMsg(e)),
      );
    }, 300);
    return () => clearTimeout(t);
  }, [data, changed, calc, hasBlank]);

  if (!data) return msg ? <div className="adm-alert">{msg.text}</div> : <div style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>;

  const byKey = Object.fromEntries(data.fields.map((f) => [f.key, f]));

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      load(await api.put<PView>("/pricing", { values: changed, reason }));
      setReason("");
      setMsg({ ok: true, text: "Đã lưu công thức giá. Áp dụng cho giá hiển thị và lượt mua từ bây giờ (tối đa 30 giây để mọi máy chủ cập nhật); phiếu đã bán giữ nguyên giá đã trả." });
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  function input(k: string, opts?: { compact?: boolean }) {
    const f = byKey[k];
    if (!f) return null;
    const dirty = vals[k]?.trim() !== "" && Number(vals[k]) !== data!.values[k];
    const el = (
      <input id={`pr-${k}`} className="adm-input" type="number" inputMode="decimal" min={f.min} max={f.max} step={f.type === "float" ? 0.01 : k.startsWith("value_t") ? 1_000_000 : 1}
        value={vals[k] ?? ""} disabled={!isAdmin} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}
        style={dirty ? { borderColor: "var(--brand)", boxShadow: "0 0 0 2px var(--brand-50)" } : undefined} aria-label={f.label} />
    );
    if (opts?.compact) return el;
    const def = f.type === "int" && f.default >= 1e6 ? money(f.default) : f.type === "float" && k !== "score_curve" ? x(f.default) : fmtNum(f.default);
    return (
      <Field key={k} label={`${f.label}${dirty ? " •" : ""}`} htmlFor={`pr-${k}`}>
        {el}
        <span className="muted" style={{ fontSize: 12 }}>Mặc định: {def}</span>
      </Field>
    );
  }

  const c = preview?.calc;
  return (
    <>
      <div className="adm-head">
        <div>
          <Link href="/admin/co-hoi" className="muted" style={{ fontSize: 13 }}>← Cơ hội & phiếu</Link>
          <h1 style={{ marginTop: 4 }}>Công thức giá phiếu</h1>
          <p>Giá mỗi doanh nghiệp phải trả = giá cơ bản × hệ số điểm phù hợp × hệ số gấp × hệ số đủ thông tin × hệ số giá trị đơn hàng</p>
        </div>
      </div>
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ marginBottom: 16 }} role="status">{msg.text}</div> : null}
      {!isAdmin ? <div className="adm-alert warn" style={{ marginBottom: 16 }}>Chỉ quản trị viên được sửa công thức giá. Bạn vẫn xem thử được.</div> : null}

      <div className="adm-grid side">
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {GROUPS.map((g) => (
            <section key={g.title} className="adm-card">
              <div className="hd"><h2>{g.title}</h2></div>
              <div className="bd" style={{ display: "grid", gap: 12 }}>
                <p className="muted" style={{ fontSize: 13 }}>{g.note}</p>
                <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>{g.keys.map((k) => input(k))}</div>
                {g.keys.includes("score_from") && preview ? (
                  <div className="adm-table-wrap">
                    <table className="adm-table">
                      <thead><tr><th>Điểm</th>{SCORES.map((s) => <th key={s} style={{ textAlign: "right" }}>{s}</th>)}</tr></thead>
                      <tbody>
                        <tr><td>Hệ số</td>{preview.scores.map((it, i) => <td key={i} style={{ textAlign: "right", whiteSpace: "nowrap" }}>{x(it.draft.score)}</td>)}</tr>
                        <tr><td>Giá (cơ bản {vnd(preview.scores[0]?.draft.base ?? 0)})</td>{preview.scores.map((it, i) => <td key={i} style={{ textAlign: "right" }}><PriceCell cur={it.current.price} draft={it.draft.price} /></td>)}</tr>
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            </section>
          ))}

          <section className="adm-card">
            <div className="hd"><h2>Hệ số giá trị đơn hàng</h2></div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              <p className="muted" style={{ fontSize: 13 }}>Theo ô “Giá trị ước tính” của phiếu (máy đọc dạng “2–3 tỷ”, “500 triệu”, “120.000 USD”; khoảng thì lấy số lớn nhất). Ngưỡng phải tăng dần.</p>
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead><tr><th>Giá trị đơn hàng</th><th>Ngưỡng (đ)</th><th>Hệ số</th></tr></thead>
                  <tbody>
                    {VALUE_ROWS.map(([t, m]) => (
                      <tr key={m}>
                        <td>{t ? <>Từ {money(Number(vals[t]) || 0)}</> : <>Dưới {money(Number(vals.value_t1) || 0)} / không rõ</>}</td>
                        <td>{t ? input(t, { compact: true }) : <span className="muted">—</span>}</td>
                        <td style={{ width: 140 }}>{input(m, { compact: true })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>

        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Xem thử giá</h2></div>
            <div className="bd" style={{ display: "grid", gap: 10 }}>
              {previewErr ? <div className="adm-alert" role="status">{previewErr}</div> : null}
              {hasBlank ? <div className="adm-alert warn">Còn ô tham số để trống hoặc không phải số.</div> : null}
              <Field label="Mã phiếu thật (tuỳ chọn)" htmlFor="c-opp">
                <input id="c-opp" className="adm-input mono" value={calc.opp_code} placeholder="vd. CH-000123 — bỏ trống để tự nhập" onChange={(e) => setCalc({ ...calc, opp_code: e.target.value })} />
              </Field>
              <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr" }}>
                <Field label="Điểm phù hợp (0–100)" htmlFor="c-score"><input id="c-score" className="adm-input" type="number" min={0} max={100} value={calc.score} onChange={(e) => setCalc({ ...calc, score: e.target.value })} /></Field>
                {!calc.opp_code.trim() ? (
                  <>
                    <Field label="Giá cơ bản (đ)" htmlFor="c-base"><input id="c-base" className="adm-input" type="number" min={0} step={1000} value={calc.base} onChange={(e) => setCalc({ ...calc, base: e.target.value })} /></Field>
                    <Field label="Còn bao nhiêu ngày tới hạn" htmlFor="c-days"><input id="c-days" className="adm-input" type="number" value={calc.days_left} placeholder="trống = không có hạn" onChange={(e) => setCalc({ ...calc, days_left: e.target.value })} /></Field>
                    <Field label="Đủ thông tin (%)" htmlFor="c-info"><input id="c-info" className="adm-input" type="number" min={0} max={100} step={10} value={calc.info_pct} onChange={(e) => setCalc({ ...calc, info_pct: e.target.value })} /></Field>
                    <Field label="Giá trị đơn hàng (tỷ đồng)" htmlFor="c-value"><input id="c-value" className="adm-input" type="number" min={0} step={0.1} value={calc.value} placeholder="trống = không rõ" onChange={(e) => setCalc({ ...calc, value: e.target.value })} /></Field>
                  </>
                ) : null}
              </div>
              {c ? (
                <div style={{ display: "grid", gap: 6, fontSize: 13.5 }}>
                  {c.opportunity ? (
                    <p className="muted" style={{ fontSize: 12.5 }}>
                      <b>{c.opportunity.code}</b> · {c.opportunity.title} — giá cơ bản {vnd(c.opportunity.base)}, hạn chót {c.opportunity.deadline ?? "không có"}, đủ {c.opportunity.info_pct}% thông tin, giá trị “{c.opportunity.estimated_value || "—"}” ({c.opportunity.value_vnd ? money(c.opportunity.value_vnd) : "không đọc được"})
                    </p>
                  ) : null}
                  <dl className="adm-kv">
                    <dt>Giá cơ bản áp dụng</dt><dd>{vnd(c.draft.base)}</dd>
                    <dt>Hệ số điểm</dt><dd>{x(c.draft.score)}</dd>
                    <dt>Hệ số gấp</dt><dd>{x(c.draft.urgency)}</dd>
                    <dt>Hệ số đủ thông tin</dt><dd>{x(c.draft.info)}</dd>
                    <dt>Hệ số giá trị đơn</dt><dd>{x(c.draft.value)}</dd>
                    <dt>Giá phải trả</dt><dd style={{ fontSize: 16 }}><PriceCell cur={c.current.price} draft={c.draft.price} /></dd>
                  </dl>
                </div>
              ) : <Skeleton h={120} />}
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Ví dụ (giá cơ bản 29.000đ)</h2></div>
            <div className="bd" style={{ display: "grid", gap: 8 }}>
              {preview ? EXAMPLES.map((e, i) => (
                <div key={e.label} style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 13.5 }}>
                  <span>{e.label}</span><PriceCell cur={preview.examples[i].current.price} draft={preview.examples[i].draft.price} />
                </div>
              )) : <Skeleton h={60} />}
              {nChanged ? <p className="muted" style={{ fontSize: 12 }}>Giá gạch ngang = đang áp dụng; giá đậm = theo bản đang sửa (chưa lưu).</p> : null}
            </div>
          </section>

          {isAdmin ? (
            <section className="adm-card">
              <div className="hd"><h2>Lưu thay đổi</h2></div>
              <div className="bd" style={{ display: "grid", gap: 12 }}>
                <p className="muted" style={{ fontSize: 13 }}>
                  {nChanged ? `${nChanged} tham số thay đổi.` : "Chưa thay đổi gì."} Giá mới áp dụng ngay cho mọi phiếu đang bán; phiếu đã bán giữ giá đã trả. Mỗi lần lưu được ghi lịch sử.
                </p>
                <Field label="Lý do (bắt buộc)" htmlFor="pr-reason"><input id="pr-reason" className="adm-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="vd. Tăng giá phiếu điểm cao từ tháng 12" /></Field>
                <div className="adm-actions">
                  <button className="adm-btn" disabled={busy || !nChanged} onClick={() => load(data)}>Huỷ thay đổi</button>
                  <button className="adm-btn primary" disabled={busy || !nChanged || hasBlank || !!previewErr || reason.trim().length < 3} onClick={save}>{busy ? "Đang lưu…" : "Lưu công thức"}</button>
                </div>
                <button className="adm-btn sm ghost" style={{ justifySelf: "start" }} disabled={busy}
                  onClick={() => setVals(Object.fromEntries(data.fields.map((f) => [f.key, String(f.default)])))}>Điền lại toàn bộ mức mặc định</button>
              </div>
            </section>
          ) : null}

          <section className="adm-card">
            <div className="hd"><h2>Lịch sử thay đổi</h2></div>
            <div className="bd">
              {!data.logs.length ? <p className="muted">Chưa thay đổi lần nào — đang dùng mức mặc định.</p> : (
                <ul className="adm-timeline">
                  {data.logs.map((l, i) => (
                    <li key={i} className="k-status">
                      <span className="dot">•</span>
                      <div>
                        <div className="txt">{byKey[l.key]?.label ?? l.key}: {l.old} → <b>{l.new}</b></div>
                        <div className="meta">{l.reason} · {l.actor ?? "—"} · {fmtDateTime(l.created_at)}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
