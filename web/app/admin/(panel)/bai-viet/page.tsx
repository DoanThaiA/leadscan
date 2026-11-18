"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { liveBadge, useArticleMeta } from "@/components/admin/ArticleForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";
import { ARTICLE_STATUS, type ArticleAdmin, articleHref, sectionHref } from "@/lib/blog";

interface Resp {
  items: Omit<ArticleAdmin, "body">[];
  counts: Record<string, number>;
}

function ArticlesAdmin() {
  const router = useRouter();
  const params = useSearchParams();
  const sectionId = params.get("danh_muc") ?? ""; // giữ bộ lọc trên URL: quay lại từ trang sửa bài vẫn đúng danh mục
  const { sections } = useArticleMeta();
  const section = sections.find((x) => String(x.id) === sectionId);
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
    document.title = `${section?.name ?? "Bài viết"} · Quản trị LeadScan`;
  }, [section]);

  useEffect(() => {
    setD(null);
    api.get<Resp>("/articles" + qs({ status, q, section_id: sectionId })).then(setD, (e) => setError(errMsg(e)));
  }, [status, q, sectionId]);

  const pickSection = (id: string) => router.replace(id ? `/admin/bai-viet?danh_muc=${id}` : "/admin/bai-viet");
  const all = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;
  const newHref = `/admin/bai-viet/moi${sectionId ? `?danh_muc=${sectionId}` : ""}`;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>{section ? section.name : "Bài viết"}</h1>
          <p>
            {section ? (
              <>Bài trong danh mục, hiện trên <a href={sectionHref(section.slug)} target="_blank" rel="noopener" style={{ color: "var(--brand-600)" }}>{sectionHref(section.slug)}</a>{section.is_active ? "" : " (danh mục đang ẩn)"}.</>
            ) : (
              <>Mọi bài viết của các danh mục. Quản lý danh mục ở <Link href="/admin/bai-viet/danh-muc" style={{ color: "var(--brand-600)" }}>Danh mục bài viết</Link>.</>
            )}
          </p>
        </div>
        <div className="adm-actions">
          <Link className="adm-btn primary" href={newHref}><Icon name="plus" size={16} /> Viết bài mới</Link>
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
          <select className="adm-input" style={{ width: "auto" }} value={sectionId} onChange={(e) => pickSection(e.target.value)} aria-label="Lọc theo danh mục">
            <option value="">Mọi danh mục</option>
            {sections.map((x) => <option key={x.id} value={x.id}>{x.name}{x.is_active ? "" : " (đang ẩn)"}</option>)}
          </select>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">
            {q || status ? "Không có bài nào khớp bộ lọc." : <>Chưa có bài viết{section ? ` trong “${section.name}”` : ""}. <Link href={newHref} style={{ color: "var(--brand-600)" }}>Viết bài đầu tiên →</Link></>}
          </div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Bài viết</th>{section ? null : <th>Danh mục</th>}<th>Trạng thái</th><th>Ngày đăng</th><th>Cập nhật</th></tr></thead>
              <tbody>
                {d.items.map((a) => (
                  <tr key={a.id} className="link" onClick={() => router.push(`/admin/bai-viet/${a.id}`)}>
                    <td>
                      <Link className="name" href={`/admin/bai-viet/${a.id}`} onClick={(e) => e.stopPropagation()}>{a.title}</Link>
                      <div className="sub">{[a.category, articleHref(a)].filter(Boolean).join(" · ")}</div>
                    </td>
                    {section ? null : <td style={{ whiteSpace: "nowrap" }}>{a.section_name}</td>}
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

export default function ArticlesAdminPage() {
  return (
    <Suspense fallback={<Skeleton h={400} />}>
      <ArticlesAdmin />
    </Suspense>
  );
}
