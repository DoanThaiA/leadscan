"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Icon, ScoreChip, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { fmtPts, type Opp, OPP_STATUS } from "@/lib/commerce";

const ST_CLASS: Record<string, string> = { draft: "s-suspended", published: "s-active", closed: "s-rejected" };

export default function AdminOppsPage() {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [d, setD] = useState<{ total: number; items: Opp[]; counts: Record<string, number> } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    document.title = "Cơ hội · Quản trị LeadScan";
    setD(null);
    api.get<{ total: number; items: Opp[]; counts: Record<string, number> }>("/opportunities" + qs({ status, q, page })).then(setD, (e) => setError(errMsg(e)));
  }, [status, q, page]);

  const total = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;
  const pages = d ? Math.max(1, Math.ceil(d.total / 20)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Cơ hội & phiếu</h1>
          <p>Nhập cơ hội thủ công (giai đoạn sau: crawl + AI tự tạo), định giá và mở bán phiếu.</p>
        </div>
        <Link className="adm-btn primary" href="/admin/co-hoi/moi"><Icon name="plus" size={16} /> Thêm cơ hội</Link>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!status ? "on" : undefined} onClick={() => { setStatus(""); setPage(1); }}>Tất cả{total !== null ? <span>{total}</span> : null}</button>
          {Object.entries(OPP_STATUS).map(([k, v]) => (
            <button key={k} className={status === k ? "on" : undefined} onClick={() => { setStatus(k); setPage(1); }}>{v}{d ? <span>{d.counts[k] ?? 0}</span> : null}</button>
          ))}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search"><Icon name="search" /><input className="adm-input" type="search" placeholder="Tìm theo tiêu đề, mã, bên có nhu cầu…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm cơ hội" /></div>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">Chưa có cơ hội nào. <Link href="/admin/co-hoi/moi" style={{ color: "var(--brand-600)" }}>Thêm cơ hội đầu tiên →</Link></div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Cơ hội</th><th>Điểm</th><th>Giá</th><th>Đã bán</th><th>Đầu mối</th><th>Trạng thái</th><th>Cập nhật</th></tr></thead>
              <tbody>
                {d.items.map((o) => (
                  <tr key={o.id} className="link" onClick={() => router.push(`/admin/co-hoi/${o.id}`)}>
                    <td>
                      <Link className="name" href={`/admin/co-hoi/${o.id}`} onClick={(e) => e.stopPropagation()}>{o.title}</Link>
                      <div className="sub mono">{o.code} · {o.industry || "—"} · {o.province || o.region || "—"}</div>
                    </td>
                    <td><ScoreChip score={o.score} /></td>
                    <td className="adm-neg">{fmtPts(o.price)}</td>
                    <td style={{ fontVariantNumeric: "tabular-nums" }}>{o.sold_count}/{o.max_buyers}</td>
                    <td>{o.contact_count}</td>
                    <td><span className={`adm-badge ${ST_CLASS[o.status ?? "draft"]}`}>{OPP_STATUS[o.status ?? "draft"]}</span></td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(o.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d && pages > 1 ? (
          <div className="adm-pager"><span>{d.total} cơ hội</span><div>
            <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
            <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
          </div></div>
        ) : null}
      </section>
    </>
  );
}
