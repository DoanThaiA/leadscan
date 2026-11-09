"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { MultiSelect } from "@/components/member/MultiSelect";
import { useNotices } from "@/components/member/Notifications";
import { SearchReqDetail } from "@/components/member/SearchReqDetail";
import { SearchReqSummary } from "@/components/member/SearchReqList";
import { type Criteria, criteriaTags, isMatching, type SearchReq } from "@/lib/commerce";
import { errMsg, mapi } from "@/lib/member/api";

interface MatchResp {
  criteria: Criteria;
  options: { industries: string[]; regions: string[]; sizes: string[]; sources: string[]; min_scores: number[] };
}

const NOTE_MIN = 10;
const POLL_MS = 2500;
const POLL_MAX = 120; // ~5 phút

export default function MatchPage() {
  return (
    <Suspense fallback={<Skeleton h={420} />}>
      <MatchPageInner />
    </Suspense>
  );
}

function MatchPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { unread, reload: reloadNotices } = useNotices();

  const [m, setM] = useState<MatchResp | null>(null);
  const [c, setC] = useState<Criteria | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [reqs, setReqs] = useState<SearchReq[] | null>(null);
  const [error, setError] = useState("");
  const polls = useRef(0);
  const boardRef = useRef<HTMLDivElement>(null);

  const loadReqs = useCallback(() => {
    mapi.get<{ items: SearchReq[] }>("/search-requests").then((r) => setReqs(r.items), (e) => setError(errMsg(e)));
  }, []);

  useEffect(() => {
    document.title = "Tìm cơ hội phù hợp · LeadScan B2B";
    mapi.get<MatchResp>("/match").then((r) => { setM(r); setC(r.criteria); }, (e) => setError(errMsg(e)));
    loadReqs();
  }, [loadReqs]);

  // Có thông báo cơ hội mới → tải lại danh sách phiếu để cập nhật số cơ hội / số "mới"
  const lastUnread = useRef(unread);
  useEffect(() => {
    if (unread > lastUnread.current) loadReqs();
    lastUnread.current = unread;
  }, [unread, loadReqs]);

  // Phiếu vừa gửi còn đang so khớp (hiếm: lỗi tạm phải chạy nền) → hỏi lại định kỳ
  const pending = !!reqs?.some(isMatching);
  useEffect(() => {
    if (!pending || polls.current >= POLL_MAX) return;
    const t = setTimeout(() => { polls.current += 1; loadReqs(); }, POLL_MS);
    return () => clearTimeout(t);
  }, [pending, reqs, loadReqs]);

  const wanted = Number(params.get("yeu-cau")) || null;
  const selected = reqs?.find((r) => r.id === wanted) ?? reqs?.[0] ?? null;

  const select = useCallback((id: number) => {
    router.replace(`${pathname}?yeu-cau=${id}`, { scroll: false });
  }, [router, pathname]);

  // Mở từ chuông / email (?yeu-cau=) → cuộn tới kết quả
  useEffect(() => {
    if (wanted && reqs?.some((r) => r.id === wanted)) boardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [wanted, reqs]);

  const onSeen = useCallback(() => {
    loadReqs();
    reloadNotices();
  }, [loadReqs, reloadNotices]);

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
      setReqs((prev) => [r, ...(prev ?? []).filter((x) => x.id !== r.id)]);
      setNote("");
      polls.current = 0;
      const n = r.match_count ?? 0;
      setMsg({
        ok: true,
        text: isMatching(r)
          ? `Đã tạo yêu cầu #${r.id}. Hệ thống đang chấm điểm cơ hội — kết quả hiện bên dưới sau ít giây.`
          : n
            ? `Đã tạo yêu cầu #${r.id}: tìm thấy ${n} cơ hội phù hợp, đã thêm vào Tất cả cơ hội và Kho của tôi.`
            : `Đã tạo yêu cầu #${r.id}. Hiện chưa có cơ hội đạt mức phù hợp — LeadScan sẽ tìm kiếm liên tục và báo bạn khi có.`,
      });
      router.replace(`${pathname}?yeu-cau=${r.id}`, { scroll: false });
      setTimeout(() => boardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  const tags = c ? criteriaTags(c) : [];
  const live = reqs?.filter((r) => r.status === "open").length ?? 0;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Tìm cơ hội phù hợp</h1>
          <p>Mô tả nhu cầu một lần — LeadScan tìm ngay và tiếp tục tìm kiếm liên tục, báo bạn mỗi khi có cơ hội mới phù hợp.</p>
        </div>
        {reqs?.length ? (
          <div className="sr-stats" aria-label="Tóm tắt">
            <div><b>{live}</b><span>yêu cầu đang tìm</span></div>
            <div className={unread ? "hot" : undefined}><b>{unread}</b><span>cơ hội mới chưa xem</span></div>
          </div>
        ) : null}
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <form className="adm-card sf-card" onSubmit={submit}>
        <div className="sf-head">
          <h2><Icon name="spark" size={17} /> Tạo yêu cầu tìm kiếm</h2>
          <span className="muted">Bỏ trống tiêu chí nào thì không giới hạn tiêu chí đó</span>
        </div>

        <div className="sf-grid">
          <div className="sf-note">
            <label htmlFor="sr-note" className="mt-label"><Icon name="note" />Mô tả nhu cầu</label>
            <textarea
              id="sr-note"
              className="adm-input"
              maxLength={3000}
              value={note}
              onChange={(e) => { setNote(e.target.value); setMsg(null); }}
              placeholder="Sản phẩm/dịch vụ bạn cung cấp, loại khách hàng cần tìm, số lượng, thị trường, thời gian… Ví dụ: Chúng tôi sản xuất bao PP dệt 25–50 kg, công suất 2 triệu bao/tháng. Cần tìm nhà nhập khẩu hoặc nhà máy phân bón, gạo, thức ăn chăn nuôi ở Châu Phi và Đông Nam Á, đơn hàng từ 1 container/tháng."
            />
            <div className="sr-count muted">{note.trim().length}/3000</div>
          </div>

          {m && c ? (
            <div className="sf-crit">
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
            </div>
          ) : (
            <div className="sf-crit"><Skeleton h={330} /></div>
          )}
        </div>

        {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status" style={{ marginTop: 14 }}>{msg.text}</div> : null}

        <div className="sf-foot">
          <div className="sr-tags">
            {tags.length ? tags.map((t) => <span className="adm-tag" key={t}>{t}</span>) : <span className="muted" style={{ fontSize: 12.5 }}>Chưa chọn tiêu chí — tìm theo mô tả trên mọi ngành, khu vực</span>}
          </div>
          <button className="adm-btn primary sr-submit" disabled={busy || !c}>
            <Icon name="spark" size={16} /> {busy ? "Đang tìm cơ hội phù hợp…" : "Enrich tìm kiếm cơ hội"}
          </button>
        </div>
      </form>

      <div className="sr-board" ref={boardRef}>
        {!reqs ? (
          <>
            <div className="adm-card sr-side"><Skeleton h={240} /></div>
            <div className="adm-card sr-detail"><Skeleton h={320} /></div>
          </>
        ) : reqs.length && selected ? (
          <>
            <aside className="adm-card sr-side" aria-label="Yêu cầu của bạn">
              <div className="sr-side-head">
                <h2>Yêu cầu của bạn <span>({reqs.length})</span></h2>
              </div>
              <div className="sr-side-list">
                {reqs.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className={r.id === selected.id ? "sr-card on" : "sr-card"}
                    aria-current={r.id === selected.id ? "true" : undefined}
                    onClick={() => select(r.id)}
                  >
                    <SearchReqSummary r={r} />
                  </button>
                ))}
              </div>
            </aside>
            <SearchReqDetail r={selected} onSeen={onSeen} />
          </>
        ) : (
          <div className="adm-card sr-intro">
            <h2>Cách LeadScan tìm cơ hội cho bạn</h2>
            <ol>
              <li><b>Mô tả nhu cầu</b><span>Viết rõ sản phẩm bạn cung cấp và khách hàng bạn muốn tìm, chọn thêm tiêu chí nếu cần.</span></li>
              <li><b>Có kết quả ngay</b><span>Hệ thống so khớp với mọi cơ hội đang mở bán và chấm điểm riêng cho bạn.</span></li>
              <li><b>Tìm kiếm liên tục</b><span>Cơ hội mới phù hợp được tự thêm vào và báo cho bạn qua chuông thông báo và email.</span></li>
            </ol>
          </div>
        )}
      </div>
    </>
  );
}
