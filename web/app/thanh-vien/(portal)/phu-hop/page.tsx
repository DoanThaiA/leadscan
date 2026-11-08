"use client";

import { type FormEvent, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { SearchReqList } from "@/components/member/SearchReqList";
import { type Criteria, criteriaTags, type SearchReq } from "@/lib/commerce";
import { errMsg, mapi } from "@/lib/member/api";

interface MatchResp {
  criteria: Criteria;
  options: { industries: string[]; regions: string[]; sizes: string[]; sources: string[]; min_scores: number[] };
}

const NOTE_MIN = 10;

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

export default function MatchPage() {
  const [m, setM] = useState<MatchResp | null>(null);
  const [c, setC] = useState<Criteria | null>(null);
  const [extra, setExtra] = useState<string[]>([]); // ngành tự thêm
  const [other, setOther] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [reqs, setReqs] = useState<SearchReq[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Cơ hội phù hợp · LeadScan B2B";
    mapi.get<MatchResp>("/match").then((r) => { setM(r); setC(r.criteria); }, (e) => setError(errMsg(e)));
    mapi.get<{ items: SearchReq[] }>("/search-requests").then((r) => setReqs(r.items), (e) => setError(errMsg(e)));
  }, []);

  const set = (patch: Partial<Criteria>) => { setC((prev) => (prev ? { ...prev, ...patch } : prev)); setMsg(null); };

  function addIndustry(e: FormEvent) {
    e.preventDefault();
    const v = other.trim();
    if (!v || !c || !m) return;
    if (!m.options.industries.includes(v) && !extra.includes(v)) setExtra([...extra, v]);
    if (!c.industries.includes(v)) set({ industries: [...c.industries, v] });
    setOther("");
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!c) return;
    if (note.trim().length < NOTE_MIN) {
      setMsg({ ok: false, text: `Vui lòng mô tả rõ yêu cầu (ít nhất ${NOTE_MIN} ký tự).` });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const r = await mapi.post<SearchReq>("/search-requests", { ...c, note });
      setReqs((prev) => [r, ...(prev ?? [])]);
      setNote("");
      setMsg({ ok: true, text: `Đã gửi yêu cầu #${r.id}. LeadScan đã nhận và sẽ tìm, enrich cơ hội theo yêu cầu của bạn.` });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  const tags = c ? criteriaTags(c) : [];

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Tìm cơ hội phù hợp</h1>
          <p>Cho LeadScan biết bạn cần cơ hội thế nào. Đội ngũ và AI của LeadScan sẽ tìm, enrich và đưa cơ hội phù hợp vào kho cho bạn.</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card mt-board">
        {m && c ? (
          <aside className="mt-filter">
            <h2>Tiêu chí tìm kiếm</h2>
            <p className="hint">Chọn những gì bạn cần — bỏ trống nhóm nào thì không giới hạn nhóm đó</p>
            <ChipGroup icon="factory" label="Ngành hàng" options={[...m.options.industries, ...extra]} value={c.industries} onChange={(v) => set({ industries: v })} />
            <form className="mt-add" onSubmit={addIndustry} style={{ marginTop: -4, marginBottom: 12 }}>
              <input className="adm-input" value={other} onChange={(e) => setOther(e.target.value)} placeholder="Thêm ngành khác…" maxLength={60} aria-label="Thêm ngành hàng khác" />
              <button className="adm-btn sm" type="submit" disabled={!other.trim()} aria-label="Thêm ngành"><Icon name="plus" size={14} /></button>
            </form>
            <ChipGroup icon="map" label="Khu vực" options={m.options.regions} value={c.regions} onChange={(v) => set({ regions: v })} limit={9} />
            <ChipGroup icon="users" label="Quy mô khách hàng" options={m.options.sizes} value={c.sizes} onChange={(v) => set({ sizes: v })} />
            <ChipGroup icon="layers" label="Loại cơ hội" options={m.options.sources} value={c.sources} onChange={(v) => set({ sources: v })} />
            <div className="mt-group" role="group" aria-label="Điểm chất lượng tối thiểu">
              <div className="mt-label"><Icon name="gauge" />Điểm chất lượng tối thiểu</div>
              <div className="mt-chips">
                {m.options.min_scores.map((s) => (
                  <button key={s} type="button" className="mt-chip" aria-pressed={c.min_score === s} onClick={() => set({ min_score: s })}>{s ? `≥ ${s} điểm` : "Mọi mức"}</button>
                ))}
              </div>
            </div>
          </aside>
        ) : (
          <aside className="mt-filter"><Skeleton h={420} /></aside>
        )}

        <div className="mt-list">
          <form className="sr-form" onSubmit={submit}>
            <div className="mt-top"><h2>Mô tả yêu cầu</h2></div>
            <label htmlFor="sr-note" className="muted" style={{ fontSize: 13 }}>
              Viết rõ bạn đang tìm khách hàng / cơ hội như thế nào: sản phẩm bạn cung cấp, loại khách hàng, số lượng, thị trường, thời gian…
            </label>
            <textarea
              id="sr-note"
              className="adm-input"
              rows={7}
              maxLength={3000}
              value={note}
              onChange={(e) => { setNote(e.target.value); setMsg(null); }}
              placeholder="Ví dụ: Chúng tôi sản xuất bao PP dệt 25–50 kg, công suất 2 triệu bao/tháng. Cần tìm nhà nhập khẩu hoặc nhà máy phân bón, gạo, thức ăn chăn nuôi ở Châu Phi và Đông Nam Á, đơn hàng từ 1 container/tháng."
            />
            <div className="sr-count muted">{note.trim().length}/3000</div>
            <div>
              <div className="muted" style={{ fontSize: 12.5, marginBottom: 6 }}>Tiêu chí đính kèm:</div>
              <div className="sr-tags">
                {tags.length ? tags.map((t) => <span className="adm-tag" key={t}>{t}</span>) : <span className="muted" style={{ fontSize: 12.5 }}>Chưa chọn tiêu chí nào (không giới hạn)</span>}
              </div>
            </div>
            {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
            <button className="adm-btn primary sr-submit" disabled={busy || !c}>
              <Icon name="spark" size={16} /> {busy ? "Đang gửi…" : "Enrich tìm kiếm cơ hội"}
            </button>
            <small className="muted">Yêu cầu được gửi tới đội ngũ LeadScan. Bạn theo dõi trạng thái và phản hồi ngay bên dưới.</small>
          </form>

          <div className="mt-top" style={{ marginTop: 26 }}><h2>Yêu cầu đã gửi{reqs?.length ? <> <span>({reqs.length})</span></> : null}</h2></div>
          {!reqs ? (
            <Skeleton h={80} />
          ) : reqs.length ? (
            <SearchReqList items={reqs} />
          ) : (
            <div className="mt-empty" style={{ padding: "20px 12px" }}>
              <Icon name="scan" />
              <span>Chưa có yêu cầu nào. Chọn tiêu chí, mô tả nhu cầu rồi bấm “Enrich tìm kiếm cơ hội”.</span>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
