"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";
import { AI_STATUS, AI_STATUS_CLASS, KNOWLEDGE_SOURCE, type KnowledgeListItem } from "@/lib/knowledge";

interface Resp {
  total: number;
  items: KnowledgeListItem[];
  counts: Record<string, number>;
}

const PAGE_SIZE = 20;

export default function KnowledgeListPage() {
  const router = useRouter();
  const [aiStatus, setAiStatus] = useState("");
  const [source, setSource] = useState("");
  const [sort, setSort] = useState("updated");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [d, setD] = useState<Resp | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    document.title = "Kho doanh nghiệp · Quản trị LeadScan";
    setD(null);
    api.get<Resp>("/knowledge-companies" + qs({ ai_status: aiStatus, source, sort, q, page, page_size: PAGE_SIZE })).then(setD, (e) => setError(errMsg(e)));
  }, [aiStatus, source, sort, q, page]);

  const all = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;
  const pages = d ? Math.max(1, Math.ceil(d.total / PAGE_SIZE)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Kho doanh nghiệp</h1>
          <p>Danh sách doanh nghiệp để AI quét tìm cơ hội. Nhập tay hoặc quét từ bảng xếp hạng PROFIT500.</p>
        </div>
        <Link className="adm-btn primary" href="/admin/kho-doanh-nghiep/moi"><Icon name="plus" size={16} /> Thêm doanh nghiệp</Link>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!aiStatus ? "on" : undefined} onClick={() => { setAiStatus(""); setPage(1); }}>Tất cả{all !== null ? <span>{fmtNum(all)}</span> : null}</button>
          {Object.entries(AI_STATUS).map(([k, v]) => (
            <button key={k} className={aiStatus === k ? "on" : undefined} onClick={() => { setAiStatus(k); setPage(1); }}>
              {v}{d ? <span>{fmtNum(d.counts[k] ?? 0)}</span> : null}
            </button>
          ))}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tên, MST, ngành, tỉnh/thành…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm doanh nghiệp" />
          </div>
          <select className="adm-input" style={{ width: "auto" }} value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }} aria-label="Lọc theo nguồn">
            <option value="">Mọi nguồn</option>
            {Object.entries(KNOWLEDGE_SOURCE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className="adm-input" style={{ width: "auto" }} value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }} aria-label="Sắp xếp">
            <option value="updated">Mới cập nhật</option>
            <option value="rank">Theo hạng</option>
            <option value="name">Theo tên A–Z</option>
          </select>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3, 4].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">
            {q || source || aiStatus ? "Không có doanh nghiệp nào khớp bộ lọc." : <>Kho đang trống. <Link href="/admin/kho-doanh-nghiep/moi" style={{ color: "var(--brand-600)" }}>Thêm doanh nghiệp đầu tiên →</Link><br />hoặc chạy lệnh quét PROFIT500 trên máy chủ.</>}
          </div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Doanh nghiệp</th><th>Tỉnh/thành</th><th>Xếp hạng</th><th>Nguồn</th><th>AI</th><th>Cập nhật</th></tr></thead>
              <tbody>
                {d.items.map((k) => (
                  <tr key={k.id} className="link" onClick={() => router.push(`/admin/kho-doanh-nghiep/${k.id}`)}>
                    <td>
                      <Link className="name" href={`/admin/kho-doanh-nghiep/${k.id}`} onClick={(e) => e.stopPropagation()}>{k.name}</Link>
                      <div className="sub"><span className="mono">{k.tax_code || "—"}</span> · {k.industry || "—"}</div>
                    </td>
                    <td>{k.province || "—"}</td>
                    <td style={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>{k.rank ? `#${k.rank}` : "—"}{k.rank_year ? <span className="muted"> · {k.rank_year}</span> : null}</td>
                    <td><span className="adm-badge plain role">{KNOWLEDGE_SOURCE[k.source] ?? k.source}</span></td>
                    <td><span className={`adm-badge ${AI_STATUS_CLASS[k.ai_status] ?? ""}`}>{AI_STATUS[k.ai_status] ?? k.ai_status}</span></td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(k.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d && d.total > 0 ? (
          <div className="adm-pager">
            <span>{fmtNum(d.total)} doanh nghiệp{pages > 1 ? ` · trang ${page}/${pages}` : ""}</span>
            {pages > 1 ? (
              <div>
                <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
                <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </>
  );
}
