import { type ArticleCard, fmtDate } from "@/lib/blog";

export default function ArticleCardItem({ a, lead = false, headingLevel = 2 }: { a: ArticleCard; lead?: boolean; headingLevel?: 2 | 3 }) {
  const H = headingLevel === 2 ? "h2" : "h3";
  return (
    <a className={lead ? "blog-card lead" : "blog-card"} href={`/cam-nang/${a.slug}`}>
      <div className="cv">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {a.cover_image ? <img src={a.cover_image} alt={a.title} loading={lead ? "eager" : "lazy"} decoding="async" /> : <span className="ph">{a.category || "Cẩm nang LeadScan"}</span>}
      </div>
      <div className="bd">
        {a.category ? <span className="cat">{a.category}</span> : null}
        <H>{a.title}</H>
        {a.excerpt ? <p>{a.excerpt}</p> : null}
        <span className="meta">{fmtDate(a.published_at)} · {a.reading_minutes} phút đọc</span>
      </div>
    </a>
  );
}
