import type { Metadata } from "next";

import ArticleCardItem from "@/components/cam-nang/ArticleCardItem";
import { fetchArticles, fetchSections, sectionHref } from "@/lib/blog";
import { breadcrumbLd, ldJson } from "@/lib/seo";

export const dynamic = "force-dynamic";

const TITLE = "Bài viết – LeadScan";
const DESC = "Cẩm nang tìm khách hàng B2B, tin tức và câu chuyện tuyển dụng từ LeadScan.";

export async function generateMetadata(): Promise<Metadata> {
  const data = await fetchArticles({ page_size: "1" });
  return {
    title: TITLE,
    description: DESC,
    alternates: { canonical: "/bai-viet" },
    robots: data && data.total === 0 ? { index: false, follow: true } : undefined,
  };
}

/** Trang gộp: các danh mục đang có bài + bài mới nhất của mọi danh mục */
export default async function PostsIndexPage() {
  const [sections, latest] = await Promise.all([fetchSections(), fetchArticles({ page_size: "9" })]);
  const withPosts = (sections ?? []).filter((s) => s.count > 0);
  const ld = ldJson([breadcrumbLd([["Trang chủ", "/"], ["Bài viết", "/bai-viet"]])]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <section className="blog-hero">
        <div className="container">
          <span className="pill-tag">Bài viết LeadScan</span>
          <h1 className="h-display">Bài viết từ <b>LeadScan</b></h1>
          <p>{DESC}</p>
          {withPosts.length ? (
            <nav className="blog-cats" aria-label="Danh mục">
              {withPosts.map((s) => <a key={s.slug} href={sectionHref(s.slug)}>{s.name}<span>{s.count}</span></a>)}
            </nav>
          ) : null}
        </div>
      </section>

      <section className="blog-list">
        <div className="container">
          {!latest ? (
            <p className="blog-empty">Không tải được bài viết. Vui lòng thử lại sau ít phút.</p>
          ) : !latest.items.length ? (
            <p className="blog-empty">Bài viết đang được biên soạn — quay lại sau nhé.</p>
          ) : (
            <div className="blog-grid">
              {latest.items.map((a, i) => <ArticleCardItem key={a.slug} a={a} lead={i === 0} />)}
            </div>
          )}
        </div>
      </section>
    </>
  );
}
