"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { OppList } from "@/components/member/OppList";
import type { Criteria, MatchList } from "@/lib/commerce";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface MatchResp {
  criteria: Criteria;
  configured: boolean;
  options: { industries: string[]; regions: string[]; sizes: string[]; sources: string[]; min_scores: number[] };
}

const PAGE_SIZE = 10;
const SORTS: [string, string][] = [["score", "Điểm cao"], ["new", "Mới nhất"], ["price_asc", "Giá thấp"]];

/** Nhóm chip chọn nhiều; quá `limit` thì thu gọn (chip đang chọn luôn hiện) */
function ChipGroup({
  icon, label, options, value, onChange, limit = 10, hint,
}: {
  icon: string; label: string; options: string[]; value: string[]; onChange: (v: string[]) => void; limit?: number; hint?: string;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? options : options.filter((o, i) => i < limit || value.includes(o));
  const toggle = (o: string) => onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o]);
  return (
    <div className="mt-group" role="group" aria-label={label}>
      <div className="mt-label"><Icon name={icon} />{label}{value.length ? <small>{value.length} đã chọn</small> : hint ? <small>{hint}</small> : null}</div>
      <div className="mt-chips">
        {shown.map((o) => (
          <button key={o} type="button" className="mt-chip" aria-pressed={value.includes(o)} onClick={() => toggle(o)}>{o}</button>
        ))}
        {options.length > shown.length || all ? (
          <button type="button" className="mt-more" onClick={() => setAll(!all)}>{all ? "Thu gọn" : `+${options.length - shown.length} khác`}</button>
        ) : null}
      </div>
    </div>
  );
}

function MatchFilter({ data, onSaved }: { data: MatchResp; onSaved: (c: Criteria) => void }) {
  const [c, setC] = useState<Criteria>(data.criteria);
  const [extra, setExtra] = useState<string[]>([]); // ngành tự thêm
  const [other, setOther] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const dirty = JSON.stringify(c) !== JSON.stringify(data.criteria);
  const set = (patch: Partial<Criteria>) => { setC({ ...c, ...patch }); setMsg(null); };

  function addIndustry(e: FormEvent) {
    e.preventDefault();
    const v = other.trim();
    if (!v) return;
    if (!data.options.industries.includes(v) && !extra.includes(v)) setExtra([...extra, v]);
    if (!c.industries.includes(v)) set({ industries: [...c.industries, v] });
    setOther("");
  }

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await mapi.put<{ criteria: Criteria }>("/match", c);
      setC(r.criteria);
      onSaved(r.criteria);
      setMsg({ ok: true, text: "Đã lưu tiêu chí." });
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="mt-filter">
      <h2>Tìm cơ hội phù hợp</h2>
      <p className="hint">Chọn tiêu chí — AI lọc và chấm điểm cơ hội cho bạn</p>
      <ChipGroup icon="factory" label="Ngành hàng" options={[...data.options.industries, ...extra]} value={c.industries} onChange={(v) => set({ industries: v })} />
      <form className="mt-add" onSubmit={addIndustry} style={{ marginTop: -4, marginBottom: 12 }}>
        <input className="adm-input" value={other} onChange={(e) => setOther(e.target.value)} placeholder="Thêm ngành khác…" maxLength={60} aria-label="Thêm ngành hàng khác" />
        <button className="adm-btn sm" type="submit" disabled={!other.trim()}><Icon name="plus" size={14} /></button>
      </form>
      <ChipGroup icon="map" label="Khu vực" options={data.options.regions} value={c.regions} onChange={(v) => set({ regions: v })} limit={8} />
      <ChipGroup icon="users" label="Quy mô khách hàng" options={data.options.sizes} value={c.sizes} onChange={(v) => set({ sizes: v })} hint="AI dùng để chấm điểm" />
      <ChipGroup icon="layers" label="Loại cơ hội" options={data.options.sources} value={c.sources} onChange={(v) => set({ sources: v })} />
      <div className="mt-group" role="group" aria-label="Điểm chất lượng">
        <div className="mt-label"><Icon name="gauge" />Điểm chất lượng</div>
        <div className="mt-chips">
          {data.options.min_scores.map((s) => (
            <button key={s} type="button" className="mt-chip" aria-pressed={c.min_score === s} onClick={() => set({ min_score: s })}>{s ? `≥ ${s} điểm` : "Mọi mức"}</button>
          ))}
        </div>
      </div>
      <div className="mt-save">
        {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
        <button className="adm-btn primary" onClick={save} disabled={busy || (!dirty && data.configured)}>
          <Icon name="scan" size={16} /> {busy ? "Đang tìm…" : "Lưu & tìm cơ hội"}
        </button>
        <small>Bỏ trống nhóm nào thì không lọc theo nhóm đó.</small>
      </div>
    </aside>
  );
}

export default function MatchPage() {
  const [m, setM] = useState<MatchResp | null>(null);
  const [list, setList] = useState<MatchList | null>(null);
  const [sort, setSort] = useState("score");
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);

  const load = useCallback((s: string) => {
    setList(null);
    mapi.get<MatchList>("/matches" + qs({ sort: s, page_size: PAGE_SIZE })).then(setList, (e) => setError(errMsg(e)));
  }, []);

  useEffect(() => {
    document.title = "Cơ hội phù hợp · LeadScan B2B";
    mapi.get<MatchResp>("/match").then(setM, (e) => setError(errMsg(e)));
  }, []);
  useEffect(() => load(sort), [load, sort]);

  async function loadMore() {
    if (!list) return;
    setMore(true);
    try {
      const r = await mapi.get<MatchList>("/matches" + qs({ sort, page_size: PAGE_SIZE, page: list.page + 1 }));
      setList({ ...r, items: [...list.items, ...r.items.filter((x) => !list.items.some((y) => y.id === x.id))] });
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setMore(false);
    }
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Cơ hội phù hợp</h1>
          <p>Nhập tiêu chí bên trái, LeadScan lọc cơ hội đang mở bán khớp với doanh nghiệp bạn. Mua phiếu ngay hoặc thêm vào kho để xem sau.</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card mt-board">
        {m ? (
          <MatchFilter data={m} onSaved={(c) => { setM({ ...m, criteria: c, configured: !!(c.industries.length || c.regions.length || c.sources.length) }); load(sort); }} />
        ) : (
          <aside className="mt-filter"><Skeleton h={420} /></aside>
        )}

        <div className="mt-list">
          <div className="mt-top">
            <h2>{list?.configured ? <><span>{list.total.toLocaleString("vi-VN")}</span> cơ hội phù hợp</> : "Cơ hội phù hợp"}</h2>
            <select className="adm-input" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sắp xếp">
              {SORTS.map(([k, label]) => <option key={k} value={k}>Sắp xếp: {label}</option>)}
            </select>
          </div>
          {!list ? (
            <div style={{ display: "grid", gap: 10 }}>{[1, 2, 3, 4].map((i) => <Skeleton key={i} h={56} />)}</div>
          ) : !list.configured ? (
            <div className="mt-empty">
              <Icon name="scan" />
              <b style={{ color: "var(--ink)" }}>Chọn tiêu chí để bắt đầu</b>
              <span>Chọn ít nhất một ngành hàng, khu vực hoặc loại cơ hội rồi bấm “Lưu & tìm cơ hội”.</span>
            </div>
          ) : list.items.length ? (
            <>
              <OppList items={list.items} onChange={(o) => setList({ ...list, items: list.items.map((x) => (x.id === o.id ? o : x)) })} />
              <div className="mt-foot">
                <span>Hiển thị {list.items.length} / {list.total.toLocaleString("vi-VN")} cơ hội</span>
                {list.items.length < list.total ? (
                  <button className="adm-btn sm ghost" style={{ color: "var(--brand-600)" }} onClick={loadMore} disabled={more}>{more ? "Đang tải…" : "Xem thêm →"}</button>
                ) : null}
              </div>
            </>
          ) : (
            <div className="mt-empty">
              <Icon name="search" />
              <b style={{ color: "var(--ink)" }}>Chưa có cơ hội khớp tiêu chí</b>
              <span>Thử bỏ bớt khu vực hoặc hạ điểm tối thiểu. Hệ thống cập nhật cơ hội mới liên tục.</span>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
