import type { Metadata } from "next";

import PublicOppCard from "@/components/public-opp/OppCard";
import type { PublicOppList } from "@/lib/public-opps";
import { breadcrumbLd, ldJson, orgRef, SITE_URL } from "@/lib/seo";

/**
 * Khung chung cho trang đích SEO "cơ hội theo chủ đề" (ngành /co-hoi/nganh/…, khu vực /co-hoi/khu-vuc/…):
 * nội dung riêng của chủ đề + danh sách cơ hội đang mở + liên kết sang chủ đề khác.
 */

export const TOPIC_PAGE_SIZE = 24;
export const pageOf = (sp: Record<string, string | undefined>) => Math.max(1, Number(sp.trang) || 1);

const OG = { url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" };

export function topicMetadata(o: { base: string; page: number; data: PublicOppList | null; title: string; description: string }): Metadata {
  const path = `${o.base}${o.page > 1 ? `?trang=${o.page}` : ""}`;
  const title = o.page > 1 ? `${o.title} – trang ${o.page}` : o.title;
  return {
    title, description: o.description,
    alternates: { canonical: path },
    // Chủ đề chưa có cơ hội nào: không cho Google lập chỉ mục trang mỏng, nhưng vẫn đi theo link
    robots: o.data && o.data.total === 0 ? { index: false, follow: true } : undefined,
    openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: path, title, description: o.description, images: [OG] },
    twitter: { card: "summary_large_image", title, description: o.description, images: [OG.url] },
  };
}

export interface TopicProps {
  base: string; // /co-hoi/nganh/bao-bi-in-an
  name: string; // Bao bì & in ấn
  crumbLabel: string; // tên hiện ở breadcrumb
  h1: React.ReactNode;
  live: string; // "11 cơ hội … đang mở bán"
  intro: string;
  boxes: { title: string; items?: string[]; text?: string; note?: string }[];
  data: PublicOppList | null;
  page: number;
  emptyTitle: string;
  listTitle: React.ReactNode;
  others: { title: string; links: [string, string][] }[];
  cta: { title: React.ReactNode; text: string };
}

export default function TopicPage(p: TopicProps) {
  const { data, page, base } = p;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const pageHref = (n: number) => (n > 1 ? `${base}?trang=${n}` : base);

  const ld = ldJson([
    {
      "@type": "CollectionPage",
      name: typeof p.h1 === "string" ? p.h1 : `Cơ hội kinh doanh ${p.name}`,
      description: p.intro,
      url: `${SITE_URL}${base}`,
      inLanguage: "vi-VN",
      publisher: orgRef,
      ...(data?.items.length
        ? { mainEntity: { "@type": "ItemList", numberOfItems: data.total, itemListElement: data.items.map((o, i) => ({ "@type": "ListItem", position: (page - 1) * data.page_size + i + 1, url: `${SITE_URL}/co-hoi/${o.code}`, name: o.title })) } }
        : {}),
    },
    breadcrumbLd([["Trang chủ", "/"], ["Cơ hội", "/co-hoi"], [p.crumbLabel, base]]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <section className="pub-hero">
        <div className="container">
          <nav className="pub-crumb" aria-label="Đường dẫn"><a href="/co-hoi">Cơ hội</a><span>/</span><b>{p.crumbLabel}</b></nav>
          <span className="pub-live"><i />{p.live}</span>
          <h1 className="h-display">{p.h1}</h1>
          <p className="pub-hero-sub">{p.intro}</p>
          <div className="ind-meta">
            {p.boxes.map((b) => (
              <div key={b.title}>
                <h2>{b.title}</h2>
                {b.items ? <ul>{b.items.map((x) => <li key={x}><svg className="icon"><use href="#i-check" /></svg>{x}</li>)}</ul> : null}
                {b.text ? <p>{b.text}</p> : null}
                {b.note ? <p className="ind-note">{b.note}</p> : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="pub-list">
        <div className="container">
          {!data ? (
            <p className="pub-empty">Không tải được danh sách cơ hội. Vui lòng thử lại sau ít phút.</p>
          ) : !data.items.length ? (
            <div className="pub-empty">
              <b>{p.emptyTitle}</b>
              <span>Thành viên gửi yêu cầu tìm cơ hội theo ngành, khu vực — LeadScan quét và báo ngay khi có cơ hội khớp.</span>
              <a className="btn btn-primary btn-sm" href="/#dang-ky">Đăng ký nhận cơ hội</a>
            </div>
          ) : (
            <>
              <h2 className="ind-h2">{p.listTitle}</h2>
              <div className="pub-grid">{data.items.map((o) => <PublicOppCard key={o.id} o={o} />)}</div>
              {pages > 1 ? (
                <nav className="pub-pager" aria-label="Phân trang">
                  {page > 1 ? <a className="btn btn-outline btn-sm" href={pageHref(page - 1)}>← Trước</a> : <span />}
                  <span>Trang {page}/{pages}</span>
                  {page < pages ? <a className="btn btn-outline btn-sm" href={pageHref(page + 1)}>Sau →</a> : <span />}
                </nav>
              ) : null}
            </>
          )}

          {p.others.map((g) => (
            <nav key={g.title} className="ind-others" aria-label={g.title}>
              <h2>{g.title}</h2>
              <div className="pub-chips wrap">{g.links.map(([href, label]) => <a key={href} href={href}>{label}</a>)}</div>
            </nav>
          ))}
        </div>
      </section>

      <section className="cta pub-band">
        <div className="cta-dots" />
        <div className="container cta-grid">
          <h2>{p.cta.title}</h2>
          <p>{p.cta.text}</p>
          <div className="cta-actions">
            <a className="btn btn-primary" href="/#dang-ky">Đăng ký thành viên</a>
            <a className="btn btn-ghost" href="/doi-tac#dang-ky">Đăng ký đối tác</a>
          </div>
        </div>
      </section>
    </>
  );
}
