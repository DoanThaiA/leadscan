"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import {
  type Batch,
  CMP_LABEL,
  type CompanyListItem,
  type Condition,
  type EnrichMeta,
  type EnrichStats,
  type FilterDef,
  NO_VALUE,
  pct,
  postDownload,
  type SavedFilterRow,
  type SearchMeta,
  useEnrichMeta,
  type WatchlistRow,
} from "@/lib/admin/enrich";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";

interface Resp {
  total: number;
  items: (CompanyListItem & { ma_ck?: string | null })[];
}

const PAGE_SIZE = 20;

function Target({ value, total, goal }: { value: number; total: number; goal: number }) {
  const p = total ? (value / total) * 100 : 0;
  return (
    <span className="er-target" aria-hidden>
      <i style={{ width: `${Math.min(100, p)}%` }} />
      <u style={{ left: `${goal}%` }} />
    </span>
  );
}

function ConditionRow({ c, sm, onChange, onRemove, batches, meta }: { c: Condition; sm: SearchMeta; onChange: (c: Condition) => void; onRemove: () => void; batches: Batch[]; meta: EnrichMeta }) {
  const f = sm.fields[c.field];
  const cmps = f?.cmps ?? [];
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
      <select className="adm-input" style={{ width: 200 }} value={c.field} onChange={(e) => onChange({ field: e.target.value, cmp: sm.fields[e.target.value].cmps[0], value: "" })} aria-label="Trường">
        {Object.entries(sm.fields).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
      </select>
      <select className="adm-input" style={{ width: 190 }} value={c.cmp} onChange={(e) => onChange({ ...c, cmp: e.target.value })} aria-label="Phép so sánh">
        {cmps.map((k) => <option key={k} value={k}>{CMP_LABEL[k] ?? k}</option>)}
      </select>
      {NO_VALUE.has(c.cmp) ? null : f?.type === "batch" ? (
        <select className="adm-input" style={{ width: 220 }} value={String(c.value ?? "")} onChange={(e) => onChange({ ...c, value: e.target.value })} aria-label="Lô">
          <option value="">— chọn lô —</option>
          {batches.map((b) => <option key={b.id} value={b.id}>#{b.id} · {b.name}</option>)}
        </select>
      ) : f?.type === "purpose" ? (
        <select className="adm-input" style={{ width: 240 }} value={String(c.value ?? "")} onChange={(e) => onChange({ ...c, value: e.target.value })} aria-label="Mục đích">
          <option value="">— chọn mục đích —</option>
          {Object.entries(meta.purposes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      ) : f?.type === "signal" ? (
        <>
          <select className="adm-input" style={{ width: 160 }} value={String((c.value as { kind?: string })?.kind ?? "")} onChange={(e) => onChange({ ...c, value: { ...(c.value as object), kind: e.target.value } })} aria-label="Loại tín hiệu">
            <option value="">Mọi tín hiệu</option>
            {Object.entries(meta.signal_kinds).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input className="adm-input" style={{ width: 110 }} type="number" min={1} placeholder="trong N ngày" value={String((c.value as { days?: number })?.days ?? "")} onChange={(e) => onChange({ ...c, value: { ...(c.value as object), days: Number(e.target.value) || undefined } })} aria-label="Số ngày" />
        </>
      ) : (
        <input className="adm-input" style={{ width: 240 }} type={f?.type === "date" ? "date" : f?.type === "number" ? "number" : "text"} value={String(c.value ?? "")} onChange={(e) => onChange({ ...c, value: e.target.value })} aria-label="Giá trị" placeholder={c.cmp === "regex" ? "vd: ^CÔNG TY (CP|TNHH)" : ""} />
      )}
      <button className="adm-btn sm ghost" onClick={onRemove} aria-label="Bỏ điều kiện"><Icon name="trash" size={14} /></button>
    </div>
  );
}

function EnrichListInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { meta, error: metaError } = useEnrichMeta();
  const [sm, setSm] = useState<SearchMeta | null>(null);
  const [stats, setStats] = useState<EnrichStats | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [saved, setSaved] = useState<SavedFilterRow[]>([]);
  const [batchId, setBatchId] = useState(params.get("lo") ?? "");
  const [missing, setMissing] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [advOpen, setAdvOpen] = useState(false);
  const [op, setOp] = useState<"and" | "or">("and");
  const [conds, setConds] = useState<Condition[]>([]);
  const [applied, setApplied] = useState<{ op: "and" | "or"; conds: Condition[] }>({ op: "and", conds: [] });
  const [page, setPage] = useState(1);
  const [d, setD] = useState<Resp | null>(null);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"" | "export" | "save" | "watch">("");
  const [flash, setFlash] = useState("");

  const definition: FilterDef = useMemo(() => {
    const base: Condition[] = [];
    if (batchId) base.push({ field: "lo", cmp: "eq", value: batchId });
    if (missing) base.push({ field: missing, cmp: "empty" });
    const adv = applied.conds.length ? [{ op: applied.op, conditions: applied.conds }] : [];
    return { op: "and", q, conditions: [...base, ...adv] };
  }, [batchId, missing, q, applied]);

  const loadSaved = useCallback(() => { api.get<SavedFilterRow[]>("/enrich/filters").then(setSaved, () => {}); }, []);

  useEffect(() => {
    document.title = "Làm giàu theo MST · Quản trị LeadScan";
    api.get<EnrichStats>("/enrich/stats").then(setStats, (e) => setError(errMsg(e)));
    api.get<Batch[]>("/enrich/batches").then(setBatches, () => {});
    api.get<SearchMeta>("/enrich/search/meta").then(setSm, () => {});
    loadSaved();
  }, [loadSaved]);

  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    setD(null);
    setError("");
    api.post<Resp>("/enrich/companies/search", { definition, page, page_size: PAGE_SIZE }).then(setD, (e) => { setError(errMsg(e)); setD({ total: 0, items: [] }); });
  }, [definition, page]);

  function loadSavedFilter(id: string) {
    const f = saved.find((x) => String(x.id) === id);
    if (!f) return;
    const def = f.definition;
    setSearch(def.q ?? "");
    setBatchId(""); setMissing("");
    const flat = (def.conditions ?? []).flatMap((c) => ("conditions" in c ? (c.conditions as Condition[]) : [c as Condition]));
    const nestedOp = (def.conditions ?? []).find((c) => "conditions" in c) as FilterDef | undefined;
    setOp(nestedOp?.op ?? def.op ?? "and");
    setConds(flat);
    setApplied({ op: nestedOp?.op ?? def.op ?? "and", conds: flat });
    setAdvOpen(true);
    setPage(1);
  }

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;

  const canImport = meta?.caps.includes("batch.import");
  const canExport = meta?.caps.includes("a.export");
  const pages = d ? Math.max(1, Math.ceil(d.total / PAGE_SIZE)) : 1;
  const total = stats?.total ?? 0;
  const fields = meta?.fields ?? {};
  const hasFilter = !!(q || batchId || missing || applied.conds.length);

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Làm giàu dữ liệu theo MST</h1>
          <p>Hồ sơ doanh nghiệp theo mã số thuế. Mỗi trường hiển thị đều kèm nguồn, đường dẫn và thời điểm thu thập.</p>
        </div>
        <div className="adm-actions">
          <Link className={canImport ? "adm-btn primary" : "adm-btn"} href="/admin/lam-giau/nhap-lo">
            <Icon name={canImport ? "plus" : "layers"} size={16} /> {canImport ? "Nhập lô MST" : "Các lô MST"}
          </Link>
        </div>
      </div>
      {meta ? <EnrichNav caps={meta.caps} /> : null}
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {flash ? <div className="adm-alert ok" role="status" style={{ marginBottom: 16 }}>{flash}</div> : null}

      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        {stats ? (
          <>
            <div className="adm-card adm-stat"><small>Mã số thuế trong hệ thống</small><b>{fmtNum(stats.total)}</b><span>{fmtNum(stats.batches)} lô đã nhập</span></div>
            <div className="adm-card adm-stat"><small>Có tên doanh nghiệp</small><b>{pct(stats.by_field.ten ?? 0, total)}</b><span>{fmtNum(stats.by_field.ten ?? 0)} / {fmtNum(total)} MST</span></div>
            <div className="adm-card adm-stat" title="Đủ tên, địa chỉ, tình trạng hoạt động, ngành nghề chính">
              <small>Hồ sơ đủ trường bắt buộc</small><b>{pct(stats.full_profile, total)}</b><span>Mục tiêu ≥ 95% · {fmtNum(stats.full_profile)} MST</span>
              <Target value={stats.full_profile} total={total} goal={95} />
            </div>
            <div className="adm-card adm-stat">
              <small>Có người ra quyết định</small><b>{pct(stats.with_decision_maker, total)}</b><span>Mục tiêu ≥ 70% · {fmtNum(stats.with_decision_maker)} DN</span>
              <Target value={stats.with_decision_maker} total={total} goal={70} />
            </div>
          </>
        ) : Array.from({ length: 4 }, (_, i) => <div className="adm-card adm-stat" key={i}><Skeleton h={14} w="50%" /><div style={{ height: 10 }} /><Skeleton h={28} w="40%" /></div>)}
      </div>

      <section className="adm-card">
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tên (không dấu), MST hoặc mã CK…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm doanh nghiệp" />
          </div>
          <select className="adm-input" style={{ width: "auto", maxWidth: 220 }} value={batchId} onChange={(e) => { setBatchId(e.target.value); setPage(1); }} aria-label="Lọc theo lô">
            <option value="">Mọi lô</option>
            {batches.map((b) => <option key={b.id} value={b.id}>#{b.id} · {b.name}</option>)}
          </select>
          <select className="adm-input" style={{ width: "auto" }} value={missing} onChange={(e) => { setMissing(e.target.value); setPage(1); }} aria-label="Lọc hồ sơ thiếu trường">
            <option value="">Mọi hồ sơ</option>
            {(meta?.required_fields ?? []).map((f) => <option key={f} value={f}>Thiếu {fields[f]?.toLowerCase()}</option>)}
          </select>
          <button className={advOpen || applied.conds.length ? "adm-btn sm primary" : "adm-btn sm"} onClick={() => setAdvOpen((v) => !v)}>
            <Icon name="target" size={14} /> Bộ lọc nâng cao{applied.conds.length ? ` (${applied.conds.length})` : ""}
          </button>
          {saved.length ? (
            <select className="adm-input" style={{ width: "auto", maxWidth: 200 }} value="" onChange={(e) => loadSavedFilter(e.target.value)} aria-label="Bộ lọc đã lưu">
              <option value="">Bộ lọc đã lưu…</option>
              {saved.map((f) => <option key={f.id} value={f.id}>{f.name}{f.shared ? " (nhóm)" : ""}{!f.mine && f.owner ? ` — ${f.owner}` : ""}</option>)}
            </select>
          ) : null}
        </div>

        {advOpen && sm && meta ? (
          <div className="bd" style={{ borderBottom: "1px solid var(--line)", display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
              Khớp
              <select className="adm-input" style={{ width: "auto", height: 30 }} value={op} onChange={(e) => setOp(e.target.value as "and" | "or")} aria-label="Cách kết hợp">
                <option value="and">TẤT CẢ điều kiện (AND)</option>
                <option value="or">MỘT TRONG các điều kiện (OR)</option>
              </select>
            </div>
            {conds.map((c, i) => (
              <ConditionRow key={i} c={c} sm={sm} batches={batches} meta={meta} onChange={(n) => setConds((cs) => cs.map((x, j) => (j === i ? n : x)))} onRemove={() => setConds((cs) => cs.filter((_, j) => j !== i))} />
            ))}
            <div className="adm-actions" style={{ justifyContent: "space-between" }}>
              <button className="adm-btn sm" onClick={() => setConds((cs) => [...cs, { field: "tinh", cmp: "eq", value: "" }])}><Icon name="plus" size={14} /> Thêm điều kiện</button>
              <div className="adm-actions">
                <button className="adm-btn sm ghost" onClick={() => { setConds([]); setApplied({ op: "and", conds: [] }); setPage(1); }}>Xoá điều kiện</button>
                <button className="adm-btn sm primary" onClick={() => { setApplied({ op, conds }); setPage(1); }}>Áp dụng</button>
              </div>
            </div>
          </div>
        ) : null}

        <div className="bd adm-actions" style={{ justifyContent: "space-between", paddingTop: 10, paddingBottom: 10 }}>
          <span className="muted" style={{ fontSize: 13 }}>{d ? `${fmtNum(d.total)} doanh nghiệp khớp` : "Đang lọc…"}</span>
          <div className="adm-actions">
            {hasFilter ? <button className="adm-btn sm" onClick={() => setDialog("save")}><Icon name="bookmark" size={14} /> Lưu bộ lọc</button> : null}
            <button className="adm-btn sm" onClick={() => setDialog("watch")} disabled={!d?.total}><Icon name="bell" size={14} /> Theo dõi kết quả</button>
            {canExport ? <button className="adm-btn sm" onClick={() => setDialog("export")} disabled={!d?.total}><Icon name="download" size={14} /> Xuất CSV</button> : null}
          </div>
        </div>

        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3, 4].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">
            {hasFilter ? "Không có doanh nghiệp nào khớp bộ lọc." : canImport ? <>Chưa có mã số thuế nào. <Link href="/admin/lam-giau/nhap-lo" style={{ color: "var(--brand-600)" }}>Nhập lô MST đầu tiên →</Link></> : "Chưa có mã số thuế nào."}
          </div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Doanh nghiệp</th><th>Tỉnh/thành</th><th>Tình trạng</th><th>Còn thiếu</th><th>Cập nhật</th></tr></thead>
              <tbody>
                {d.items.map((c) => (
                  <tr key={c.mst} className="link" onClick={() => router.push(`/admin/lam-giau/${c.mst}`)}>
                    <td>
                      <Link className="name" href={`/admin/lam-giau/${c.mst}`} onClick={(e) => e.stopPropagation()}>{c.ten || <span className="muted" style={{ fontWeight: 400 }}>Chưa có tên</span>}</Link>
                      <div className="sub mono">{c.mst}{c.ma_ck ? ` · ${c.ma_ck}` : ""}</div>
                    </td>
                    <td>{c.tinh || "—"}</td>
                    <td>{c.trang_thai || "—"}</td>
                    <td>{c.missing.length ? <div className="er-tags">{c.missing.map((f) => <span key={f} className="adm-tag">{fields[f] ?? f}</span>)}</div> : <span className="adm-badge s-active">Đủ</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d && d.total > 0 && pages > 1 ? (
          <div className="adm-pager">
            <span>trang {page}/{pages}</span>
            <div>
              <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
              <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
            </div>
          </div>
        ) : null}
      </section>

      {meta && sm ? (
        <>
          <ExportDialog open={dialog === "export"} onClose={() => setDialog("")} definition={definition} total={d?.total ?? 0} meta={meta} sm={sm} onDone={(m) => { setDialog(""); setFlash(m); }} />
          <SaveDialog open={dialog === "save"} onClose={() => setDialog("")} definition={definition} onDone={() => { setDialog(""); setFlash("Đã lưu bộ lọc."); loadSaved(); }} />
          <WatchDialog open={dialog === "watch"} onClose={() => setDialog("")} definition={definition} total={d?.total ?? 0} onDone={(m) => { setDialog(""); setFlash(m); }} />
        </>
      ) : null}
    </>
  );
}

function ExportDialog({ open, onClose, definition, total, meta, sm, onDone }: { open: boolean; onClose: () => void; definition: FilterDef; total: number; meta: EnrichMeta; sm: SearchMeta; onDone: (m: string) => void }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setMsg(""); }, [open]);
  const kb = new Set(["nguoi_quyet_dinh", "email_nguoi"]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const purpose = String(f.get("purpose") ?? "");
    if (!purpose) return setMsg("Chọn mục đích sử dụng của bản xuất.");
    setBusy(true); setMsg("");
    try {
      const r = await postDownload("/enrich/exports", { definition, columns: f.getAll("columns").map(String), purpose, include_inferred: f.get("inferred") === "on" });
      onDone(`Đã xuất ${fmtNum(r.rows)} doanh nghiệp${r.blocked ? ` — ${fmtNum(r.blocked)} doanh nghiệp bị loại vì lô của chúng không cho phép mục đích này` : ""}. Lần xuất đã ghi nhật ký.`);
    } catch (err) { setMsg(err instanceof Error ? err.message : "Không xuất được."); } finally { setBusy(false); }
  }

  return (
    <Dialog open={open} title={`Xuất ${fmtNum(total)} doanh nghiệp đang lọc`} onClose={onClose} wide>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Mục đích sử dụng (bắt buộc)" full htmlFor="x-purpose">
            <select id="x-purpose" className="adm-input" name="purpose" defaultValue="">
              <option value="">— chọn —</option>
              {Object.entries(meta.purposes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <div className="adm-field full" role="group" aria-labelledby="x-cols">
            <label id="x-cols">Cột</label>
            <div className="adm-checks">
              {Object.entries(sm.export_columns).map(([k, v]) => (
                <label key={k}><input type="checkbox" name="columns" value={k} defaultChecked={["mst", "ten", "dia_chi", "tinh", "trang_thai"].includes(k)} /> {v}{kb.has(k) ? " (dữ liệu cá nhân)" : ""}</label>
              ))}
            </div>
          </div>
          {Object.keys(sm.export_columns).some((k) => kb.has(k)) ? (
            <label className="full" style={{ display: "flex", gap: 8, fontSize: 13 }}><input type="checkbox" name="inferred" /> Kèm email suy luận (ghi rõ “suy luận” trong file)</label>
          ) : null}
          <p className="muted full" style={{ fontSize: 12.5 }}>Doanh nghiệp mà lô của nó không cho phép mục đích đã chọn sẽ bị loại. Người / email / điện thoại trong danh sách từ chối bị loại. File có dòng đầu ghi mục đích và hạn sử dụng; mọi lần xuất đều ghi nhật ký. MST cá nhân không bao giờ có trong file.</p>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang xuất…" : "Xuất CSV"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}

function SaveDialog({ open, onClose, definition, onDone }: { open: boolean; onClose: () => void; definition: FilterDef; onDone: () => void }) {
  const [msg, setMsg] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api.post("/enrich/filters", { name: f.get("name"), shared: f.get("shared") === "on", definition });
      onDone();
    } catch (err) { setMsg(errMsg(err)); }
  }
  return (
    <Dialog open={open} title="Lưu bộ lọc" onClose={onClose}>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Tên bộ lọc" full htmlFor="sf-name"><input id="sf-name" className="adm-input" name="name" maxLength={200} autoFocus /></Field>
          <label className="full" style={{ display: "flex", gap: 8, fontSize: 13 }}><input type="checkbox" name="shared" /> Chia sẻ cho cả nhóm</label>
          <div className="adm-actions full"><button type="button" className="adm-btn" onClick={onClose}>Huỷ</button><button type="submit" className="adm-btn primary">Lưu</button></div>
        </form>
      ) : null}
    </Dialog>
  );
}

function WatchDialog({ open, onClose, definition, total, onDone }: { open: boolean; onClose: () => void; definition: FilterDef; total: number; onDone: (m: string) => void }) {
  const [lists, setLists] = useState<WatchlistRow[]>([]);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    if (!open) return;
    setMsg("");
    api.get<WatchlistRow[]>("/enrich/watchlists").then((l) => setLists(l.filter((x) => x.mine)), () => {});
  }, [open]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      let id = String(f.get("wl") ?? "");
      if (!id) {
        const name = String(f.get("name") ?? "").trim();
        if (!name) return setMsg("Chọn danh sách hoặc đặt tên danh sách mới.");
        id = String((await api.post<WatchlistRow>("/enrich/watchlists", { name })).id);
      }
      const r = await api.post<{ added: number; already: number }>(`/enrich/watchlists/${id}/items`, { definition });
      onDone(`Đã thêm ${fmtNum(r.added)} doanh nghiệp vào danh sách theo dõi${r.already ? ` (${fmtNum(r.already)} đã có sẵn)` : ""}.`);
    } catch (err) { setMsg(errMsg(err)); }
  }
  return (
    <Dialog open={open} title={`Theo dõi ${fmtNum(total)} doanh nghiệp đang lọc`} onClose={onClose}>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          {lists.length ? (
            <Field label="Thêm vào danh sách" full htmlFor="w-list">
              <select id="w-list" className="adm-input" name="wl" defaultValue=""><option value="">— tạo danh sách mới —</option>{lists.map((l) => <option key={l.id} value={l.id}>{l.name} ({fmtNum(l.count)})</option>)}</select>
            </Field>
          ) : null}
          <Field label="Tên danh sách mới" full htmlFor="w-name"><input id="w-name" className="adm-input" name="name" maxLength={200} placeholder="VD: Khách hàng chiến lược" /></Field>
          <p className="muted full" style={{ fontSize: 12.5 }}>Bạn nhận cảnh báo khi doanh nghiệp đổi người đại diện, địa chỉ, tình trạng MST, có nợ thuế, trúng thầu, bổ nhiệm — từ thời điểm thêm vào danh sách.</p>
          <div className="adm-actions full"><button type="button" className="adm-btn" onClick={onClose}>Huỷ</button><button type="submit" className="adm-btn primary">Thêm</button></div>
        </form>
      ) : null}
    </Dialog>
  );
}

export default function EnrichListPage() {
  return (
    <Suspense fallback={<Skeleton h={400} />}>
      <EnrichListInner />
    </Suspense>
  );
}
