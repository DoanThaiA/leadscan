import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { cache } from "react";

import ArticleCardItem from "@/components/cam-nang/ArticleCardItem";
import { articleHref, DEFAULT_SECTION, fetchArticles, fetchSections, slugify } from "@/lib/blog";
import { breadcrumbLd, ldJson, orgRef, SITE_URL } from "@/lib/seo";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 12;

type Props = { params: Promise<{ section: string }>; searchParams: Promise<Record<string, string | undefined>> };

const getSection = cache(async (slug: string) => (await fetchSections())?.find((s) => s.slug === slug) ?? null);

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const [{ section }, sp] = await Promise.all([params, searchParams]);
  const s = await getSection(section);
  if (!s) return { title: "Không tìm thấy danh mục – LeadScan" };
  const title = `${s.name} – LeadScan`;
  const description = s.description || `Bài viết ${s.name.toLowerCase()} từ LeadScan.`;
  const filtered = Boolean(sp.chu_de || (Number(sp.trang) || 1) > 1);
  return {
    title, description,
    alternates: { canonical: `/bai-viet/${s.slug}` },
    robots: filtered || s.count === 0 ? { index: false, follow: true } : undefined,
    openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: `/bai-viet/${s.slug}`, title, description,
      images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }] },
  };
}

export default async function SectionPage({ params, searchParams }: Props) {
  const [{ section }, sp] = await Promise.all([params, searchParams]);
  if (section === DEFAULT_SECTION) permanentRedirect("/cam-nang");
  const s = await getSection(section);
  if (!s) notFound();

  const page = Math.max(1, Number(sp.trang) || 1);
  const all = await fetchArticles({ section: s.slug, page_size: "1" });
  const cats = (all?.categories ?? []).filter(([, n]) => n > 0);
  const cat = cats.find(([c]) => slugify(c) === sp.chu_de)?.[0] ?? "";
  const data = await fetchArticles({ section: s.slug, category: cat, page: String(page), page_size: String(PAGE_SIZE) });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const base = `/bai-viet/${s.slug}`;
  const href = (o: { chu_de?: string; trang?: number }) => {
    const q = new URLSearchParams();
    const c = o.chu_de ?? (cat ? slugify(cat) : "");
    if (c) q.set("chu_de", c);
    if (o.trang && o.trang > 1) q.set("trang", String(o.trang));
    const qs = q.toString();
    return `${base}${qs ? `?${qs}` : ""}`;
  };

  const ld = ldJson([
    { "@type": "CollectionPage", name: s.name, description: s.description, url: `${SITE_URL}${base}`, inLanguage: "vi-VN", publisher: orgRef,
      ...(data?.items.length ? { mainEntity: { "@type": "ItemList", itemListElement: data.items.map((a, i) => ({ "@type": "ListItem", position: (page - 1) * PAGE_SIZE + i + 1, url: `${SITE_URL}${articleHref(a)}`, name: a.title })) } } : {}) },
    breadcrumbLd([["Trang chủ", "/"], ["Bài viết", "/bai-viet"], [s.name, base]]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <section className="blog-hero">
        <div className="container">
          <nav className="art-crumb" aria-label="Đường dẫn"><a href="/bai-viet">Bài viết</a><span>/</span><b>{s.name}</b></nav>
          <h1 className="h-display">{s.name}</h1>
          {s.description ? <p>{s.description}</p> : null}
          {cats.length > 1 ? (
            <nav className="blog-cats" aria-label="Chủ đề">
              <a className={!cat ? "on" : undefined} href={base}>Tất cả<span>{all?.total ?? 0}</span></a>
              {cats.map(([c, n]) => <a key={c} className={c === cat ? "on" : undefined} href={href({ chu_de: slugify(c), trang: 1 })}>{c}<span>{n}</span></a>)}
            </nav>
          ) : null}
        </div>
      </section>

      <section className="blog-list">
        <div className="container">
          {!data ? (
            <p className="blog-empty">Không tải được bài viết. Vui lòng thử lại sau ít phút.</p>
          ) : !data.items.length ? (
            <p className="blog-empty">Bài viết đang được biên soạn — quay lại sau nhé.</p>
          ) : (
            <>
              <div className="blog-grid">
                {data.items.map((a, i) => <ArticleCardItem key={a.slug} a={a} lead={i === 0 && page === 1 && !cat} />)}
              </div>
              {pages > 1 ? (
                <nav className="blog-pager" aria-label="Phân trang">
                  {page > 1 ? <a className="btn btn-outline btn-sm" href={href({ trang: page - 1 })}>← Bài mới hơn</a> : <span />}
                  <span>Trang {page}/{pages}</span>
                  {page < pages ? <a className="btn btn-outline btn-sm" href={href({ trang: page + 1 })}>Bài cũ hơn →</a> : <span />}
                </nav>
              ) : null}
            </>
          )}
        </div>
      </section>
    </>
  );
}
