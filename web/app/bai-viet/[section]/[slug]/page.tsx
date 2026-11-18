import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { cache } from "react";

import ArticleBody from "@/components/cam-nang/ArticleBody";
import ArticleCardItem from "@/components/cam-nang/ArticleCardItem";
import { articleHref, articleToc, fetchArticle, fmtDate, sectionHref, slugify } from "@/lib/blog";
import { breadcrumbLd, ldJson, orgRef, SITE_URL } from "@/lib/seo";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ section: string; slug: string }> };

const getArticle = cache(fetchArticle);
const OG = "/brand/leadscan-og.jpg";

/** Lời mời cuối bài theo danh mục (danh mục mới tạo dùng lời mời chung) */
const CTA: Record<string, { title: string; text: string; href: string; label: string }> = {
  "tuyen-dung": { title: "Muốn làm việc cùng LeadScan?", text: "Xem các vị trí đang tuyển và ứng tuyển trực tuyến trong 2 phút.", href: "/tuyen-dung", label: "Xem vị trí đang tuyển" },
};
const CTA_DEFAULT = { title: "Tìm khách hàng đang cần mua?", text: "Xem trước cơ hội B2B đã được xác minh, miễn phí. Mua phiếu để mở khoá đầu mối liên hệ.", href: "/co-hoi", label: "Xem cơ hội đang mở" };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const a = await getArticle((await params).slug);
  if (!a) return { title: "Không tìm thấy bài viết – LeadScan" };
  const title = `${a.seo_title || a.title} | ${a.section_name} LeadScan`;
  const description = a.excerpt.slice(0, 300);
  const image = a.cover_image || OG;
  const url = articleHref(a);
  return {
    title, description,
    alternates: { canonical: url },
    authors: [{ name: a.author_name }],
    openGraph: {
      type: "article", locale: "vi_VN", siteName: "LeadScan B2B", url, title, description,
      publishedTime: a.published_at ?? undefined, modifiedTime: a.updated_at ?? undefined, section: a.section_name,
      images: [{ url: image, alt: a.title }],
    },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

export default async function PostPage({ params }: Props) {
  const { section, slug } = await params;
  const a = await getArticle(slug);
  if (!a) notFound();
  if (a.section !== section) permanentRedirect(articleHref(a)); // sai danh mục / bài Cẩm nang → link đúng
  const toc = articleToc(a.body);
  const path = articleHref(a);
  const url = `${SITE_URL}${path}`;
  const secHref = sectionHref(a.section);
  const abs = (u: string) => (u.startsWith("/") ? `${SITE_URL}${u}` : u);
  const catHref = a.category ? `${secHref}?chu_de=${slugify(a.category)}` : secHref;
  const cta = CTA[a.section] ?? CTA_DEFAULT;

  const ld = ldJson([
    {
      "@type": "BlogPosting",
      headline: a.title,
      description: a.excerpt,
      image: [abs(a.cover_image || OG)],
      datePublished: a.published_at,
      dateModified: a.updated_at || a.published_at,
      author: a.author_name === "LeadScan" ? orgRef : { "@type": "Person", name: a.author_name },
      publisher: orgRef,
      mainEntityOfPage: { "@type": "WebPage", "@id": url },
      url,
      inLanguage: "vi-VN",
      articleSection: a.category || a.section_name,
    },
    breadcrumbLd([["Trang chủ", "/"], ["Bài viết", "/bai-viet"], [a.section_name, secHref], ...(a.category ? [[a.category, catHref] as [string, string]] : []), [a.title, path]]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <article className="art">
        <div className="container art-wrap">
          <div style={{ minWidth: 0 }}>
            <nav className="art-crumb" aria-label="Đường dẫn">
              <a href={secHref}>{a.section_name}</a>
              {a.category ? <><span>/</span><a href={catHref}>{a.category}</a></> : null}
            </nav>
            <h1 className="h-display">{a.title}</h1>
            <div className="art-meta">
              {a.category ? <b>{a.category}</b> : null}
              <time dateTime={a.published_at ?? undefined}>{fmtDate(a.published_at)}</time>
              <span>{a.reading_minutes} phút đọc</span>
              <span>Tác giả: {a.author_name}</span>
            </div>
            {a.excerpt ? <p className="art-lead">{a.excerpt}</p> : null}
            {a.cover_image ? (
              <div className="art-cover">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={a.cover_image} alt={a.title} fetchPriority="high" />
              </div>
            ) : null}
            <ArticleBody text={a.body} />

            <div className="art-end">
              <div>
                <b>{cta.title}</b>
                <p>{cta.text}</p>
              </div>
              <div className="acts">
                <a className="btn btn-primary" href={cta.href}>{cta.label}</a>
                <a className="btn btn-outline" href={secHref}>Bài khác trong {a.section_name}</a>
              </div>
            </div>
          </div>

          <aside className="art-side">
            {toc.length > 1 ? (
              <nav className="art-toc" aria-label="Mục lục">
                <h2>Mục lục</h2>
                <ol>{toc.map((t) => <li key={t.id}><a href={`#${t.id}`}>{t.text}</a></li>)}</ol>
              </nav>
            ) : null}
          </aside>
        </div>

        {a.related.length ? (
          <div className="container art-related">
            <h2>Bài viết liên quan</h2>
            <div className="blog-grid">{a.related.map((r) => <ArticleCardItem key={r.slug} a={r} headingLevel={3} />)}</div>
          </div>
        ) : null}
      </article>
    </>
  );
}
