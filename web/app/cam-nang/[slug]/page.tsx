import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import ArticleBody from "@/components/cam-nang/ArticleBody";
import ArticleCardItem from "@/components/cam-nang/ArticleCardItem";
import { areaBySlug } from "@/lib/areas";
import { articleToc, fetchArticle, fmtDate, slugify } from "@/lib/blog";
import { breadcrumbLd, ldJson, orgRef, SITE_URL } from "@/lib/seo";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

const getArticle = cache(fetchArticle); // generateMetadata và trang dùng chung 1 lần gọi API
const OG = "/brand/leadscan-og.jpg";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const a = await getArticle((await params).slug);
  if (!a) return { title: "Không tìm thấy bài viết – LeadScan" };
  const title = `${a.seo_title || a.title} | Cẩm nang LeadScan`;
  const description = a.excerpt.slice(0, 300);
  const image = a.cover_image || OG;
  return {
    title, description,
    alternates: { canonical: `/cam-nang/${a.slug}` },
    authors: [{ name: a.author_name }],
    openGraph: {
      type: "article", locale: "vi_VN", siteName: "LeadScan B2B", url: `/cam-nang/${a.slug}`, title, description,
      publishedTime: a.published_at ?? undefined, modifiedTime: a.updated_at ?? undefined, section: a.category || undefined,
      images: [{ url: image, alt: a.title }],
    },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

export default async function ArticlePage({ params }: Props) {
  const a = await getArticle((await params).slug);
  if (!a) notFound();
  const toc = articleToc(a.body);
  const url = `${SITE_URL}/cam-nang/${a.slug}`;
  const abs = (u: string) => (u.startsWith("/") ? `${SITE_URL}${u}` : u);
  const area = areaBySlug(a.area);
  const catHref = a.category ? `/cam-nang?chu_de=${slugify(a.category)}` : "/cam-nang";

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
      ...(a.category ? { articleSection: a.category } : {}),
    },
    breadcrumbLd([["Trang chủ", "/"], ["Cẩm nang", "/cam-nang"], ...(area ? [[area.name, `/cam-nang/khu-vuc/${area.slug}`] as [string, string]] : a.category ? [[a.category, catHref] as [string, string]] : []), [a.title, `/cam-nang/${a.slug}`]]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <article className="art">
        <div className="container art-wrap">
          <div style={{ minWidth: 0 }}>
            <nav className="art-crumb" aria-label="Đường dẫn">
              <a href="/cam-nang">Cẩm nang</a>
              {a.category ? <><span>/</span><a href={catHref}>{a.category}</a></> : null}
              {area ? <><span>/</span><a href={`/cam-nang/khu-vuc/${area.slug}`}>{area.name}</a></> : null}
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
                <b>Tìm khách hàng đang cần mua?</b>
                <p>Xem trước cơ hội B2B đã được xác minh, miễn phí. Mua phiếu để mở khoá đầu mối liên hệ.</p>
              </div>
              <div className="acts">
                <a className="btn btn-primary" href={area ? `/co-hoi/khu-vuc/${area.slug}` : "/co-hoi"}>{area ? `Cơ hội đang mở tại ${area.name}` : "Xem cơ hội đang mở"}</a>
                <a className="btn btn-outline" href="/#dang-ky">Đăng ký thành viên</a>
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
            <div className="art-cta">
              <b>Biết doanh nghiệp đang cần mua?</b>
              <p>Đăng lên sàn LeadScan, nhận ít nhất 1 ly cafe cho mỗi cơ hội đạt xác minh.</p>
              <a className="btn btn-primary" href="/doi-tac">Tìm hiểu chương trình đối tác</a>
            </div>
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
