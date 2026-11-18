import "../../../co-hoi/co-hoi.css"; // thẻ cơ hội (PublicOppCard) dùng style của trang /co-hoi

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import ArticleCardItem from "@/components/cam-nang/ArticleCardItem";
import PublicOppCard from "@/components/public-opp/OppCard";
import { AREA_PAGES, areaBySlug, articleAreasFor } from "@/lib/areas";
import { DEFAULT_SECTION, fetchArticles } from "@/lib/blog";
import { fetchPublicOpps } from "@/lib/public-opps";
import { breadcrumbLd, ldJson, orgRef, SITE_URL } from "@/lib/seo";

// Trang cẩm nang theo khu vực: bài viết gắn với tỉnh/miền + cơ hội đang mở tại đó (nối sang /co-hoi/khu-vuc/…).
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | undefined>> };

const PAGE_SIZE = 12;
/** "Miền Nam" → "miền Nam" khi đứng giữa câu; tên tỉnh giữ nguyên */
const inSentence = (a: { kind: string; name: string }) => (a.kind === "region" ? a.name.replace(/^Miền/, "miền") : a.name);
const getList = cache((areas: string, page: number) => fetchArticles({ section: DEFAULT_SECTION, areas, page: String(page), page_size: String(PAGE_SIZE) }));
const pageOf = (sp: Record<string, string | undefined>) => Math.max(1, Number(sp.trang) || 1);

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const a = areaBySlug((await params).slug);
  if (!a) return { title: "Không tìm thấy khu vực – LeadScan" };
  const page = pageOf(await searchParams);
  const data = await getList(articleAreasFor(a.slug).join(","), page);
  const where = inSentence(a);
  const title = `Cẩm nang tìm khách hàng B2B tại ${where}${page > 1 ? ` – trang ${page}` : ""} | LeadScan`;
  const description = `Bài viết hướng dẫn tìm khách hàng doanh nghiệp, nhà máy mới và cơ hội kinh doanh B2B tại ${where}. ${a.sectors}`.slice(0, 300);
  const path = `/cam-nang/khu-vuc/${a.slug}${page > 1 ? `?trang=${page}` : ""}`;
  return {
    title, description,
    alternates: { canonical: path },
    robots: data && data.total === 0 ? { index: false, follow: true } : undefined, // chưa có bài: không cho Google lập chỉ mục trang mỏng
    openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: path, title, description,
      images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }] },
  };
}

export default async function AreaGuidePage({ params, searchParams }: Props) {
  const a = areaBySlug((await params).slug);
  if (!a) notFound();
  const page = pageOf(await searchParams);
  const areas = articleAreasFor(a.slug).join(",");
  const [data, opps, all] = await Promise.all([
    getList(areas, page),
    fetchPublicOpps({ places: a.terms.join("|"), page_size: "3" }),
    fetchArticles({ section: DEFAULT_SECTION, page_size: "1" }),
  ]);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const where = inSentence(a);
  const base = `/cam-nang/khu-vuc/${a.slug}`;
  const pageHref = (n: number) => (n > 1 ? `${base}?trang=${n}` : base);
  const counts = all?.area_counts ?? {};
  const others = AREA_PAGES.filter((x) => x.slug !== a.slug && articleAreasFor(x.slug).some((s) => (counts[s] ?? 0) > 0));

  const ld = ldJson([
    {
      "@type": "CollectionPage", name: `Cẩm nang tìm khách hàng B2B tại ${where}`, description: a.intro, url: `${SITE_URL}${base}`, inLanguage: "vi-VN", publisher: orgRef,
      ...(data?.items.length ? { mainEntity: { "@type": "ItemList", itemListElement: data.items.map((x, i) => ({ "@type": "ListItem", position: (page - 1) * PAGE_SIZE + i + 1, url: `${SITE_URL}/cam-nang/${x.slug}`, name: x.title })) } } : {}),
    },
    breadcrumbLd([["Trang chủ", "/"], ["Cẩm nang", "/cam-nang"], [a.name, base]]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <section className="blog-hero">
        <div className="container">
          <nav className="art-crumb" aria-label="Đường dẫn"><a href="/cam-nang">Cẩm nang</a><span>/</span><b>{a.name}</b></nav>
          <span className="pill-tag">Cẩm nang theo khu vực</span>
          <h1 className="h-display">Cẩm nang tìm khách hàng B2B tại <b>{where}</b></h1>
          <p>{a.intro}</p>
          <div className="blog-cats">
            <a href={`/co-hoi/khu-vuc/${a.slug}`}>Cơ hội đang mở tại {where}{opps ? <span>{opps.total}</span> : null}</a>
          </div>
        </div>
      </section>

      <section className="blog-list">
        <div className="container">
          {!data ? (
            <p className="blog-empty">Không tải được bài viết. Vui lòng thử lại sau ít phút.</p>
          ) : !data.items.length ? (
            <p className="blog-empty">Cẩm nang cho {where} đang được biên soạn. Trong lúc chờ, xem <a href={`/co-hoi/khu-vuc/${a.slug}`} style={{ color: "var(--blue)", textDecoration: "underline" }}>các cơ hội đang mở tại {where}</a> hoặc <a href="/cam-nang" style={{ color: "var(--blue)", textDecoration: "underline" }}>cẩm nang chung</a>.</p>
          ) : (
            <>
              <div className="blog-grid">{data.items.map((x) => <ArticleCardItem key={x.slug} a={x} />)}</div>
              {pages > 1 ? (
                <nav className="blog-pager" aria-label="Phân trang">
                  {page > 1 ? <a className="btn btn-outline btn-sm" href={pageHref(page - 1)}>← Bài mới hơn</a> : <span />}
                  <span>Trang {page}/{pages}</span>
                  {page < pages ? <a className="btn btn-outline btn-sm" href={pageHref(page + 1)}>Bài cũ hơn →</a> : <span />}
                </nav>
              ) : null}
            </>
          )}

          {opps?.items.length ? (
            <div className="art-related">
              <h2>Cơ hội đang mở tại {where}</h2>
              <div className="pub-grid">{opps.items.map((o) => <PublicOppCard key={o.id} o={o} />)}</div>
              <p style={{ marginTop: 18 }}><a className="btn btn-outline btn-sm" href={`/co-hoi/khu-vuc/${a.slug}`}>Xem tất cả {opps.total} cơ hội tại {where} →</a></p>
            </div>
          ) : null}

          {others.length ? (
            <nav className="art-related" aria-label="Cẩm nang theo khu vực khác">
              <h2>Cẩm nang theo khu vực khác</h2>
              <div className="blog-cats">{others.map((x) => <a key={x.slug} href={`/cam-nang/khu-vuc/${x.slug}`}>{x.name}</a>)}</div>
            </nav>
          ) : null}
        </div>
      </section>
    </>
  );
}
