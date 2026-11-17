import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import TopicPage, { pageOf, TOPIC_PAGE_SIZE, topicMetadata } from "@/components/public-opp/TopicPage";
import { AREA_PAGES, areaBySlug, articleAreasFor } from "@/lib/areas";
import { fetchArticles } from "@/lib/blog";
import { INDUSTRY_PAGES } from "@/lib/industries";
import { fetchPublicOpps } from "@/lib/public-opps";

// Trang đích SEO cho từng tỉnh / miền: nội dung riêng + cơ hội đang mở ở khu vực đó.
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | undefined>> };

/** "Miền Nam" → "miền Nam" khi đứng giữa câu; tên tỉnh giữ nguyên */
const inSentence = (a: { kind: string; name: string }) => (a.kind === "region" ? a.name.replace(/^Miền/, "miền") : a.name);

const getList = cache((terms: string, page: number) => fetchPublicOpps({ places: terms, page: String(page), page_size: String(TOPIC_PAGE_SIZE) }));

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const a = areaBySlug((await params).slug);
  if (!a) return { title: "Không tìm thấy khu vực – LeadScan B2B" };
  const page = pageOf(await searchParams);
  const data = await getList(a.terms.join("|"), page);
  const n = data?.total ?? 0;
  const label = inSentence(a);
  return topicMetadata({
    base: `/co-hoi/khu-vuc/${a.slug}`, page, data,
    title: `Doanh nghiệp ${label} đang cần mua: ${n ? `${n} cơ hội` : "cơ hội"} B2B | LeadScan`,
    description: `Nhu cầu mua hàng, dự án, nhà máy mới tại ${label} đã được LeadScan xác minh và chấm điểm. Ngành nổi bật: ${a.sectors} Xem tóm tắt miễn phí.`.slice(0, 300),
  });
}

export default async function AreaPage({ params, searchParams }: Props) {
  const a = areaBySlug((await params).slug);
  if (!a) notFound();
  const page = pageOf(await searchParams);
  const data = await getList(a.terms.join("|"), page);
  const where = inSentence(a);
  const guides = await fetchArticles({ areas: articleAreasFor(a.slug).join(","), page_size: "4" });
  return (
    <TopicPage
      base={`/co-hoi/khu-vuc/${a.slug}`} name={a.name} crumbLabel={a.name}
      h1={<>Doanh nghiệp {a.kind === "region" ? "" : "tại "}<b>{where}</b> đang cần mua</>}
      live={data ? `${data.total} cơ hội tại ${where} đang mở bán` : `Cơ hội tại ${where}`}
      intro={a.intro}
      boxes={[
        { title: a.kind === "region" ? "Trung tâm kinh tế" : "Khu công nghiệp tiêu biểu", items: a.hubs },
        { title: "Ngành nổi bật", text: a.sectors, note: "Xem trước tóm tắt và điểm chất lượng miễn phí. Tên bên có nhu cầu và đầu mối liên hệ mở khoá khi mua phiếu." },
      ]}
      data={data} page={page}
      emptyTitle={`Chưa có cơ hội tại ${where} đang mở bán.`}
      listTitle={<>{a.name}: <b>{data?.total ?? 0}</b> cơ hội đang mở · mới nhất trước</>}
      others={[
        ...(guides?.items.length ? [{ title: `Cẩm nang tìm khách hàng tại ${where}`, links: [...guides.items.map((g) => [`/cam-nang/${g.slug}`, g.title] as [string, string]), [`/cam-nang/khu-vuc/${a.slug}`, "Xem tất cả cẩm nang khu vực này →"] as [string, string]] }] : []),
        { title: "Cơ hội theo khu vực khác", links: [["/co-hoi", "Tất cả khu vực"], ...AREA_PAGES.filter((x) => x.slug !== a.slug).map((x) => [`/co-hoi/khu-vuc/${x.slug}`, x.name] as [string, string])] },
        { title: "Cơ hội theo ngành", links: INDUSTRY_PAGES.map((x) => [`/co-hoi/nganh/${x.slug}`, x.name] as [string, string]) },
      ]}
      cta={{
        title: <>Bạn tìm khách hàng tại <b><em>{where}</em>?</b></>,
        text: "Đăng ký thành viên, đăng nhu cầu theo khu vực — LeadScan báo khi có cơ hội khớp. Biết doanh nghiệp đang cần mua tại đây? Đăng lên sàn với vai trò đối tác.",
      }}
    />
  );
}
