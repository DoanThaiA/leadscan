"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fromNow } from "@/lib/admin/format";
import { criteriaTags, SEARCH_STATUS, SEARCH_STATUS_CLASS, type SearchReq } from "@/lib/commerce";

type Row = SearchReq & {
  email_sent_at: string | null;
  company: { id: number; code: string; name: string };
  member: { full_name: string; email: string } | null;
};

const CRITERIA_LABELS: [keyof SearchReq["criteria"], string][] = [
  ["industries", "Ngành hàng"],
  ["regions", "Khu vực"],
  ["sizes", "Quy mô khách hàng"],
  ["sources", "Loại cơ hội"],
];

export default function AdminSearchRequestsPage() {
  const [status, setStatus] = useState("open");
  const [items, setItems] = useState<Row[] | null>(null);
  const [error, setError] = useState("");
  const [replies, setReplies] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(() => {
    api.get<{ items: Row[] }>("/search-requests" + qs({ status })).then((r) => setItems(r.items), (e) => setError(errMsg(e)));
  }, [status]);
  useEffect(() => {
    document.title = "Yêu cầu tìm cơ hội · Quản trị LeadScan";
    setItems(null);
    load();
  }, [load]);

  async function resolve(r: Row, st: "done" | "rejected" | "open") {
    setBusy(r.id);
    try {
      await api.patch(`/search-requests/${r.id}`, { status: st, reply: replies[r.id] ?? r.reply ?? "" });
      load();
    } catch (e) {
      alert(errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  async function resend(r: Row) {
    setBusy(r.id);
    try {
      await api.post(`/search-requests/${r.id}/resend-email`);
      setTimeout(load, 1500);
    } catch (e) {
      alert(errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Yêu cầu tìm cơ hội</h1>
          <p>Thành viên bấm “Enrich tìm kiếm cơ hội” trong cổng thành viên. Tìm và thêm cơ hội vào mục Cơ hội & phiếu, rồi trả lời và đánh dấu xong — khách thấy phản hồi trong cổng.</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs">
          {Object.entries(SEARCH_STATUS).map(([k, v]) => <button key={k} className={status === k ? "on" : undefined} onClick={() => setStatus(k)}>{v}</button>)}
          <button className={!status ? "on" : undefined} onClick={() => setStatus("")}>Tất cả</button>
        </div>
        {!items ? (
          <div className="bd"><Skeleton h={80} /></div>
        ) : !items.length ? (
          <div className="adm-empty">Không có yêu cầu nào.</div>
        ) : (
          <div className="bd" style={{ display: "grid", gap: 14 }}>
            {items.map((r) => (
              <article key={r.id} className="adm-card" style={{ padding: 14, display: "grid", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                  <div>
                    <b style={{ color: "var(--ink)" }}>#{r.id} · <Link href={`/admin/khach-hang/${r.company.id}`} style={{ color: "var(--brand-600)" }}>{r.company.name}</Link></b>
                    <div className="muted" style={{ fontSize: 12.5 }}>
                      {r.member ? <>{r.member.full_name} · <a href={`mailto:${r.member.email}`}>{r.member.email}</a> · </> : null}
                      <span title={fmtDateTime(r.created_at)}>{fromNow(r.created_at)}</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    {r.email_sent_at ? (
                      <span className="muted" style={{ fontSize: 12 }} title={fmtDateTime(r.email_sent_at)}><Icon name="mail" size={13} /> Đã gửi email</span>
                    ) : (
                      <button className="adm-btn sm" onClick={() => resend(r)} disabled={busy === r.id} title="Email báo admin chưa gửi được">
                        <Icon name="mail" size={13} /> Chưa gửi được email · Gửi lại
                      </button>
                    )}
                    <span className="muted" style={{ fontSize: 12 }}>{r.match_count ?? 0} cơ hội phù hợp</span>
                    <span className={`adm-badge ${SEARCH_STATUS_CLASS[r.status]}`}>{SEARCH_STATUS[r.status]}</span>
                  </div>
                </div>

                <dl className="adm-dl">
                  {CRITERIA_LABELS.map(([k, label]) => (
                    <div key={k}><dt>{label}</dt><dd>{(r.criteria[k] as string[] | undefined)?.join(", ") || "—"}</dd></div>
                  ))}
                  <div><dt>Điểm tối thiểu</dt><dd>{r.criteria.min_score ? `≥ ${r.criteria.min_score}` : "Mọi mức"}</dd></div>
                </dl>
                {criteriaTags(r.criteria).length === 0 ? <p className="muted" style={{ fontSize: 12.5 }}>Khách không chọn tiêu chí nào.</p> : null}

                <div>
                  <div className="muted" style={{ fontSize: 12.5, marginBottom: 4 }}>Mô tả yêu cầu</div>
                  <p style={{ whiteSpace: "pre-wrap", color: "var(--ink)" }}>{r.note}</p>
                </div>

                {r.status === "open" ? (
                  <>
                    <textarea className="adm-input" style={{ minHeight: 80, height: "auto", padding: "8px 10px" }} placeholder="Trả lời khách (hiện trong cổng thành viên), ví dụ: Đã thêm 3 cơ hội phù hợp vào mục Tất cả cơ hội." value={replies[r.id] ?? ""} onChange={(e) => setReplies((m) => ({ ...m, [r.id]: e.target.value }))} aria-label="Trả lời khách" />
                    <div className="adm-actions">
                      <button className="adm-btn sm ghost danger" onClick={() => resolve(r, "rejected")} disabled={busy === r.id}>Từ chối</button>
                      <button className="adm-btn sm primary" onClick={() => resolve(r, "done")} disabled={busy === r.id}>Đã có kết quả</button>
                    </div>
                  </>
                ) : (
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    <p className="muted">{r.reply ? <>Đã trả lời: {r.reply}</> : "Không có phản hồi."}</p>
                    <button className="adm-btn sm ghost" onClick={() => resolve(r, "open")} disabled={busy === r.id}>Mở lại</button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
