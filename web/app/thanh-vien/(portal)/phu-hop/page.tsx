"use client";

import { type FormEvent, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { MultiSelect } from "@/components/member/MultiSelect";
import { SearchReqList } from "@/components/member/SearchReqList";
import { type Criteria, criteriaTags, type SearchReq } from "@/lib/commerce";
import { errMsg, mapi } from "@/lib/member/api";

interface MatchResp {
  criteria: Criteria;
  options: { industries: string[]; regions: string[]; sizes: string[]; sources: string[]; min_scores: number[] };
}

const NOTE_MIN = 10;

export default function MatchPage() {
  const [m, setM] = useState<MatchResp | null>(null);
  const [c, setC] = useState<Criteria | null>(null);
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
      const n = r.match_count ?? 0;
      setMsg({
        ok: true,
        text: n
          ? `Đã gửi yêu cầu #${r.id}. Tìm thấy ${n} cơ hội phù hợp — đã chấm điểm riêng cho bạn, thêm vào Tất cả cơ hội và Kho của tôi. Bấm vào phiếu bên dưới để xem.`
          : `Đã gửi yêu cầu #${r.id}. Hiện chưa có cơ hội nào đạt mức phù hợp; cơ hội mới mở bán sẽ tự được so khớp và thêm vào kho của bạn.`,
      });
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
          <p>Cho LeadScan biết bạn cần cơ hội thế nào. Hệ thống so khớp tiêu chí và ngữ nghĩa mô tả của bạn với từng phiếu cơ hội, chấm điểm riêng cho bạn rồi thêm vào Tất cả cơ hội và Kho của tôi (đã loại trùng).</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card mt-board">
        {m && c ? (
          <aside className="mt-filter">
            <h2>Tiêu chí tìm kiếm</h2>
            <p className="hint">Chọn những gì bạn cần — bỏ trống nhóm nào thì không giới hạn nhóm đó</p>
            <MultiSelect icon="factory" label="Ngành hàng" options={m.options.industries} value={c.industries} onChange={(v) => set({ industries: v })} placeholder="Gõ ngành hàng, vd: bao bì, nhựa…" allowCustom />
            <MultiSelect icon="map" label="Khu vực" options={m.options.regions} value={c.regions} onChange={(v) => set({ regions: v })} placeholder="Gõ tỉnh/thành, miền, quốc tế…" allowCustom maxLength={80} />
            <MultiSelect icon="users" label="Quy mô khách hàng" options={m.options.sizes} value={c.sizes} onChange={(v) => set({ sizes: v })} placeholder="Chọn quy mô…" />
            <MultiSelect icon="layers" label="Loại cơ hội" options={m.options.sources} value={c.sources} onChange={(v) => set({ sources: v })} placeholder="Gõ loại cơ hội, vd: gói thầu…" />
            <div className="mt-group">
              <label className="mt-label" htmlFor="sr-score"><Icon name="gauge" />Điểm phù hợp tối thiểu</label>
              <select id="sr-score" className="adm-input" value={c.min_score} onChange={(e) => set({ min_score: Number(e.target.value) })}>
                {m.options.min_scores.map((s) => <option key={s} value={s}>{s ? `Từ ${s} điểm trở lên` : "Mọi mức điểm"}</option>)}
              </select>
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
