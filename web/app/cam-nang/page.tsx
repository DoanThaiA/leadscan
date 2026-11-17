import type { Metadata } from "next";

import ArticleCardItem from "@/components/cam-nang/ArticleCardItem";
import { AREA_PAGES, articleAreasFor } from "@/lib/areas";
import { fetchArticles, slugify } from "@/lib/blog";
import { breadcrumbLd, ldJson, orgRef, SITE_URL } from "@/lib/seo";

export const dynamic = "force-dynamic";

const TITLE = "Cẩm nang tìm khách hàng B2B & cơ hội kinh doanh – LeadScan";
const DESC = "Hướng dẫn tìm khách hàng doanh nghiệp, đọc nhu cầu mua hàng B2B, kiếm thêm thu nhập khi giới thiệu cơ hội và dùng LeadScan hiệu quả.";
const PAGE_SIZE = 12;

type Props = { searchParams: Promise<Record<string, string | undefined>> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const sp = await searchParams;
  const data = await fetchArticles({ page_size: "1" });
  const filtered = Boolean(sp.chu_de || (Number(sp.trang) || 1) > 1);
  return {
    title: TITLE,
    description: DESC,
    alternates: { canonical: "/cam-nang" },
    // Trang lọc chủ đề / trang 2+ vẫn cho Google đi theo link bài nhưng không lập chỉ mục riêng; chưa có bài thì ẩn
    robots: filtered || (data && data.total === 0) ? { index: false, follow: true } : undefined,
    openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: "/cam-nang", title: TITLE, description: DESC,
      images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }] },
  };
}

export default async function BlogPage({ searchParams }: Props) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.trang) || 1);
  const all = await fetchArticles({ page_size: "1" }); // lấy danh sách chủ đề + số bài
  const cats = (all?.categories ?? []).filter(([, n]) => n > 0);
  const cat = cats.find(([c]) => slugify(c) === sp.chu_de)?.[0] ?? "";
  const data = await fetchArticles({ category: cat, page: String(page), page_size: String(PAGE_SIZE) });
  const areaCounts = all?.area_counts ?? {};
  const areasWithPosts = AREA_PAGES.filter((x) => articleAreasFor(x.slug).some((s) => (areaCounts[s] ?? 0) > 0));
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const href = (o: { chu_de?: string; trang?: number }) => {
    const q = new URLSearchParams();
    const c = o.chu_de ?? (cat ? slugify(cat) : "");
    if (c) q.set("chu_de", c);
    if (o.trang && o.trang > 1) q.set("trang", String(o.trang));
    const s = q.toString();
    return `/cam-nang${s ? `?${s}` : ""}`;
  };

  const ld = ldJson([
    { "@type": "Blog", name: "Cẩm nang LeadScan", description: DESC, url: `${SITE_URL}/cam-nang`, inLanguage: "vi-VN", publisher: orgRef,
      ...(data?.items.length ? { blogPost: data.items.map((a) => ({ "@type": "BlogPosting", headline: a.title, url: `${SITE_URL}/cam-nang/${a.slug}`, datePublished: a.published_at })) } : {}) },
    breadcrumbLd([["Trang chủ", "/"], ["Cẩm nang", "/cam-nang"]]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <section className="blog-hero">
        <div className="container">
          <span className="pill-tag">Cẩm nang LeadScan</span>
          <h1 className="h-display">Cẩm nang <b>tìm khách hàng B2B</b> và cơ hội kinh doanh</h1>
          <p>Kinh nghiệm thực tế để tìm đúng doanh nghiệp đang cần mua, tiếp cận trước đối thủ, và kiếm thêm thu nhập khi bạn biết cơ hội.</p>
          {cats.length > 1 ? (
            <nav className="blog-cats" aria-label="Chủ đề">
              <a className={!cat ? "on" : undefined} href="/cam-nang">Tất cả<span>{all?.total ?? 0}</span></a>
              {cats.map(([c, n]) => <a key={c} className={c === cat ? "on" : undefined} href={href({ chu_de: slugify(c), trang: 1 })}>{c}<span>{n}</span></a>)}
            </nav>
          ) : null}
          {areasWithPosts.length ? (
            <nav className="blog-cats" aria-label="Theo khu vực">
              <strong style={{ alignSelf: "center", fontSize: 14, color: "var(--muted)" }}>Theo khu vực:</strong>
              {areasWithPosts.map((x) => <a key={x.slug} href={`/cam-nang/khu-vuc/${x.slug}`}>{x.name}</a>)}
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
