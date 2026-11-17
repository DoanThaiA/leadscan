import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import TopicPage, { pageOf, TOPIC_PAGE_SIZE, topicMetadata } from "@/components/public-opp/TopicPage";
import { AREA_PAGES } from "@/lib/areas";
import { INDUSTRY_PAGES, industryBySlug } from "@/lib/industries";
import { fetchPublicOpps } from "@/lib/public-opps";

// Trang đích SEO cho từng ngành: nội dung riêng + danh sách cơ hội đang mở của ngành đó.
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | undefined>> };

const getList = cache((name: string, page: number) => fetchPublicOpps({ industry: name, page: String(page), page_size: String(TOPIC_PAGE_SIZE) }));

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const ind = industryBySlug((await params).slug);
  if (!ind) return { title: "Không tìm thấy ngành – LeadScan B2B" };
  const page = pageOf(await searchParams);
  const data = await getList(ind.name, page);
  const n = data?.total ?? 0;
  return topicMetadata({
    base: `/co-hoi/nganh/${ind.slug}`, page, data,
    title: `${ind.name}: ${n ? `${n} cơ hội` : "cơ hội"} kinh doanh B2B đang mở | LeadScan`,
    description: `Cập nhật ${ind.keyword} đã được LeadScan xác minh và chấm điểm. ${ind.needs.slice(0, 2).join("; ")}… Xem tóm tắt miễn phí.`.slice(0, 300),
  });
}

export default async function IndustryPage({ params, searchParams }: Props) {
  const ind = industryBySlug((await params).slug);
  if (!ind) notFound();
  const page = pageOf(await searchParams);
  const data = await getList(ind.name, page);
  return (
    <TopicPage
      base={`/co-hoi/nganh/${ind.slug}`} name={ind.name} crumbLabel={ind.name}
      h1={<>Cơ hội kinh doanh ngành <b>{ind.name}</b></>}
      live={data ? `${data.total} cơ hội ${ind.name.toLowerCase()} đang mở bán` : `Cơ hội ngành ${ind.name}`}
      intro={ind.intro}
      boxes={[
        { title: "Nhu cầu thường gặp", items: ind.needs },
        { title: "Phù hợp với", text: ind.sellers, note: "Xem trước tóm tắt và điểm chất lượng miễn phí. Tên bên có nhu cầu và đầu mối liên hệ mở khoá khi mua phiếu." },
      ]}
      data={data} page={page}
      emptyTitle={`Chưa có cơ hội ngành ${ind.name} đang mở bán.`}
      listTitle={<>{ind.name}: <b>{data?.total ?? 0}</b> cơ hội đang mở · mới nhất trước</>}
      others={[
        { title: "Cơ hội theo ngành khác", links: [["/co-hoi", "Tất cả ngành"], ...INDUSTRY_PAGES.filter((x) => x.slug !== ind.slug).map((x) => [`/co-hoi/nganh/${x.slug}`, x.name] as [string, string])] },
        { title: "Cơ hội theo khu vực", links: AREA_PAGES.map((x) => [`/co-hoi/khu-vuc/${x.slug}`, x.name] as [string, string]) },
      ]}
      cta={{
        title: <>Bạn bán hàng cho ngành <b><em>{ind.name}</em>?</b></>,
        text: "Đăng ký thành viên, đăng nhu cầu tìm khách hàng — LeadScan báo khi có cơ hội khớp. Biết doanh nghiệp đang cần mua? Đăng lên sàn với vai trò đối tác.",
      }}
    />
  );
}
