import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import PublicOppCard from "@/components/public-opp/OppCard";
import { INDUSTRY_PAGES, industryBySlug } from "@/lib/industries";
import { fetchPublicOpps } from "@/lib/public-opps";
import { breadcrumbLd, ldJson, orgRef, SITE_URL } from "@/lib/seo";

// Trang đích SEO cho từng ngành: nội dung riêng + danh sách cơ hội đang mở của ngành đó.
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | undefined>> };

const PAGE_SIZE = 24;
const getList = cache((name: string, page: number) => fetchPublicOpps({ industry: name, page: String(page), page_size: String(PAGE_SIZE) }));
const pageOf = (sp: Record<string, string | undefined>) => Math.max(1, Number(sp.trang) || 1);

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const ind = industryBySlug((await params).slug);
  if (!ind) return { title: "Không tìm thấy ngành – LeadScan B2B" };
  const page = pageOf(await searchParams);
  const data = await getList(ind.name, page);
  const path = `/co-hoi/nganh/${ind.slug}${page > 1 ? `?trang=${page}` : ""}`;
  const n = data?.total ?? 0;
  const title = `${ind.name}: ${n ? `${n} cơ hội` : "cơ hội"} kinh doanh B2B đang mở${page > 1 ? ` – trang ${page}` : ""} | LeadScan`;
  const description = `Cập nhật ${ind.keyword} đã được LeadScan xác minh và chấm điểm. ${ind.needs.slice(0, 2).join("; ")}… Xem tóm tắt miễn phí.`.slice(0, 300);
  return {
    title, description,
    alternates: { canonical: path },
    // Ngành chưa có cơ hội nào: không cho Google lập chỉ mục trang mỏng, nhưng vẫn đi theo link
    robots: data && n === 0 ? { index: false, follow: true } : undefined,
    openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: path, title, description,
      images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }] },
    twitter: { card: "summary_large_image", title, description, images: ["/brand/leadscan-og.jpg"] },
  };
}

export default async function IndustryPage({ params, searchParams }: Props) {
  const ind = industryBySlug((await params).slug);
  if (!ind) notFound();
  const page = pageOf(await searchParams);
  const data = await getList(ind.name, page);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const base = `/co-hoi/nganh/${ind.slug}`;
  const pageHref = (p: number) => (p > 1 ? `${base}?trang=${p}` : base);
  const others = INDUSTRY_PAGES.filter((x) => x.slug !== ind.slug);

  const ld = ldJson([
    {
      "@type": "CollectionPage",
      name: `Cơ hội kinh doanh ngành ${ind.name}`,
      description: ind.intro,
      url: `${SITE_URL}${base}`,
      inLanguage: "vi-VN",
      publisher: orgRef,
      ...(data?.items.length
        ? { mainEntity: { "@type": "ItemList", numberOfItems: data.total, itemListElement: data.items.map((o, i) => ({ "@type": "ListItem", position: (page - 1) * PAGE_SIZE + i + 1, url: `${SITE_URL}/co-hoi/${o.code}`, name: o.title })) } }
        : {}),
    },
    breadcrumbLd([["Trang chủ", "/"], ["Cơ hội", "/co-hoi"], [ind.name, base]]),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <section className="pub-hero">
        <div className="container">
          <nav className="pub-crumb" aria-label="Đường dẫn"><a href="/co-hoi">Cơ hội</a><span>/</span><b>{ind.name}</b></nav>
          <span className="pub-live"><i />{data ? `${data.total} cơ hội ${ind.name.toLowerCase()} đang mở bán` : `Cơ hội ngành ${ind.name}`}</span>
          <h1 className="h-display">Cơ hội kinh doanh ngành <b>{ind.name}</b></h1>
          <p className="pub-hero-sub">{ind.intro}</p>
          <div className="ind-meta">
            <div>
              <h2>Nhu cầu thường gặp</h2>
              <ul>{ind.needs.map((x) => <li key={x}><svg className="icon"><use href="#i-check" /></svg>{x}</li>)}</ul>
            </div>
            <div>
              <h2>Phù hợp với</h2>
              <p>{ind.sellers}</p>
              <p className="ind-note">Xem trước tóm tắt và điểm chất lượng miễn phí. Tên bên có nhu cầu và đầu mối liên hệ mở khoá khi mua phiếu.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="pub-list">
        <div className="container">
          {!data ? (
            <p className="pub-empty">Không tải được danh sách cơ hội. Vui lòng thử lại sau ít phút.</p>
          ) : !data.items.length ? (
            <div className="pub-empty">
              <b>Chưa có cơ hội ngành {ind.name} đang mở bán.</b>
              <span>Thành viên gửi yêu cầu tìm cơ hội theo ngành — LeadScan quét và báo ngay khi có cơ hội khớp.</span>
              <a className="btn btn-primary btn-sm" href="/#dang-ky">Đăng ký nhận cơ hội ngành này</a>
            </div>
          ) : (
            <>
              <h2 className="ind-h2">{ind.name}: <b>{data.total}</b> cơ hội đang mở · mới nhất trước</h2>
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

          <nav className="ind-others" aria-label="Cơ hội theo ngành khác">
            <h2>Cơ hội theo ngành khác</h2>
            <div className="pub-chips wrap">
              <a href="/co-hoi">Tất cả ngành</a>
              {others.map((x) => <a key={x.slug} href={`/co-hoi/nganh/${x.slug}`}>{x.name}</a>)}
            </div>
          </nav>
        </div>
      </section>

      <section className="cta pub-band">
        <div className="cta-dots" />
        <div className="container cta-grid">
          <h2>Bạn bán hàng cho ngành <b><em>{ind.name}</em>?</b></h2>
          <p>Đăng ký thành viên, đăng nhu cầu tìm khách hàng — LeadScan báo khi có cơ hội khớp. Biết doanh nghiệp đang cần mua? Đăng lên sàn với vai trò đối tác.</p>
          <div className="cta-actions">
            <a className="btn btn-primary" href="/#dang-ky">Đăng ký thành viên</a>
            <a className="btn btn-ghost" href="/doi-tac#dang-ky">Đăng ký đối tác</a>
          </div>
        </div>
      </section>
    </>
  );
}
