"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { liveBadge } from "@/components/admin/ArticleForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";
import { ARTICLE_STATUS, type ArticleAdmin } from "@/lib/blog";

interface Resp {
  items: Omit<ArticleAdmin, "body">[];
  counts: Record<string, number>;
}

export default function ArticlesAdminPage() {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [d, setD] = useState<Resp | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    document.title = "Cẩm nang · Quản trị LeadScan";
    setD(null);
    api.get<Resp>("/articles" + qs({ status, q })).then(setD, (e) => setError(errMsg(e)));
  }, [status, q]);

  const all = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Cẩm nang</h1>
          <p>Bài viết SEO trên <a href="/cam-nang" target="_blank" rel="noopener" style={{ color: "var(--brand-600)" }}>/cam-nang</a>. Đều đặn 1 bài/tuần giúp LeadScan lên Google với nhiều từ khoá hơn.</p>
        </div>
        <div className="adm-actions">
          <Link className="adm-btn primary" href="/admin/cam-nang/moi"><Icon name="plus" size={16} /> Viết bài mới</Link>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!status ? "on" : undefined} onClick={() => setStatus("")}>Tất cả{all !== null ? <span>{fmtNum(all)}</span> : null}</button>
          {Object.entries(ARTICLE_STATUS).map(([k, v]) => (
            <button key={k} className={status === k ? "on" : undefined} onClick={() => setStatus(k)}>{v}{d ? <span>{fmtNum(d.counts[k] ?? 0)}</span> : null}</button>
          ))}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tiêu đề…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm bài viết" />
          </div>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">
            {q || status ? "Không có bài nào khớp bộ lọc." : <>Chưa có bài viết. <Link href="/admin/cam-nang/moi" style={{ color: "var(--brand-600)" }}>Viết bài đầu tiên →</Link></>}
          </div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Bài viết</th><th>Trạng thái</th><th>Ngày đăng</th><th>Cập nhật</th></tr></thead>
              <tbody>
                {d.items.map((a) => (
                  <tr key={a.id} className="link" onClick={() => router.push(`/admin/cam-nang/${a.id}`)}>
                    <td>
                      <Link className="name" href={`/admin/cam-nang/${a.id}`} onClick={(e) => e.stopPropagation()}>{a.title}</Link>
                      <div className="sub">{[a.category, `/cam-nang/${a.slug}`].filter(Boolean).join(" · ")}</div>
                    </td>
                    <td>{liveBadge(a)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{a.published_at ? fmtDateTime(a.published_at) : <span className="muted">—</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(a.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
