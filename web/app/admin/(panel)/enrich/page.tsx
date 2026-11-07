"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fromNow } from "@/lib/admin/format";
import { ENRICH_STATUS, type EnrichReq } from "@/lib/commerce";

type Row = EnrichReq & { company: { id: number; code: string; name: string }; opportunity: { id: number; code: string; title: string } };

export default function AdminEnrichPage() {
  const [status, setStatus] = useState("open");
  const [items, setItems] = useState<Row[] | null>(null);
  const [error, setError] = useState("");
  const [replies, setReplies] = useState<Record<number, string>>({});

  const load = useCallback(() => {
    api.get<{ items: Row[] }>("/enrich-requests" + qs({ status })).then((r) => setItems(r.items), (e) => setError(errMsg(e)));
  }, [status]);
  useEffect(() => {
    document.title = "Yêu cầu enrich · Quản trị LeadScan";
    setItems(null);
    load();
  }, [load]);

  async function resolve(r: Row, st: "done" | "rejected") {
    try {
      await api.patch(`/enrich-requests/${r.id}`, { status: st, reply: replies[r.id] ?? "" });
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Yêu cầu enrich</h1>
          <p>Khách đã mua phiếu yêu cầu tìm thêm đầu mối. Bổ sung đầu mối trong trang cơ hội, rồi trả lời và đánh dấu xong.</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs">
          {Object.entries(ENRICH_STATUS).map(([k, v]) => <button key={k} className={status === k ? "on" : undefined} onClick={() => setStatus(k)}>{v}</button>)}
          <button className={!status ? "on" : undefined} onClick={() => setStatus("")}>Tất cả</button>
        </div>
        {!items ? (
          <div className="bd"><Skeleton h={80} /></div>
        ) : !items.length ? (
          <div className="adm-empty">Không có yêu cầu nào.</div>
        ) : (
          <div className="bd" style={{ display: "grid", gap: 14 }}>
            {items.map((r) => (
              <div key={r.id} className="adm-card" style={{ padding: 14, display: "grid", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                  <div>
                    <Link className="name" href={`/admin/co-hoi/${r.opportunity.id}`} style={{ fontWeight: 600, color: "var(--ink)" }}>{r.opportunity.code} · {r.opportunity.title}</Link>
                    <div className="muted" style={{ fontSize: 12.5 }}>
                      <Link href={`/admin/khach-hang/${r.company.id}`} style={{ color: "var(--brand-600)" }}>{r.company.name}</Link> · {fromNow(r.created_at)}
                    </div>
                  </div>
                  <span className={`adm-badge ${r.status === "open" ? "s-contacted" : r.status === "done" ? "s-active" : "s-suspended"}`}>{ENRICH_STATUS[r.status]}</span>
                </div>
                <p style={{ whiteSpace: "pre-wrap", color: "var(--ink)" }}>{r.note}</p>
                {r.status === "open" ? (
                  <>
                    <textarea className="adm-input" placeholder="Trả lời khách (hiện trong trang phiếu của họ)" value={replies[r.id] ?? ""} onChange={(e) => setReplies((m) => ({ ...m, [r.id]: e.target.value }))} aria-label="Trả lời" />
                    <div className="adm-actions">
                      <button className="adm-btn sm ghost danger" onClick={() => resolve(r, "rejected")}>Từ chối</button>
                      <button className="adm-btn sm primary" onClick={() => resolve(r, "done")}>Đã bổ sung xong</button>
                    </div>
                  </>
                ) : r.reply ? <p className="muted">Đã trả lời: {r.reply}</p> : null}
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
