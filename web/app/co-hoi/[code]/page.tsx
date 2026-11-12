import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import BuyButton, { ShareButton } from "@/components/public-opp/BuyButton";
import { daysLeft, fetchPublicOpp, fmtDay, vnd } from "@/lib/public-opps";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ code: string }> };

const getOpp = cache(fetchPublicOpp); // generateMetadata và trang dùng chung 1 lần gọi API

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const o = await getOpp((await params).code);
  if (!o) return { title: "Không tìm thấy cơ hội – LeadScan B2B" };
  const title = `${o.title} – Cơ hội B2B LeadScan`;
  const description = (o.summary || `${o.industry} · ${o.province}`).slice(0, 200);
  return {
    title, description,
    alternates: { canonical: `/co-hoi/${o.code}` },
    robots: o.status === "published" ? undefined : { index: false },
    openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: `/co-hoi/${o.code}`, title, description,
      images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }] },
    twitter: { card: "summary_large_image", title, description, images: ["/brand/leadscan-og.jpg"] },
  };
}

export default async function PublicOppPage({ params }: Props) {
  const o = await getOpp((await params).code);
  if (!o) notFound();
  const left = daysLeft(o.deadline);
  const locked = [
    "Tên doanh nghiệp / bên có nhu cầu",
    "Mô tả chi tiết nhu cầu",
    o.contact_count ? `${o.contact_count} đầu mối liên hệ (họ tên, chức vụ, điện thoại, email)` : "Đầu mối liên hệ (khi có)",
    o.attachment_counts?.images ? `${o.attachment_counts.images} ảnh` : "",
    o.attachment_counts?.files ? `${o.attachment_counts.files} tài liệu` : "",
    "Link nguồn tin",
  ].filter(Boolean);

  return (
    <section className="section pub-detail">
      <div className="container">
        <a className="link-arrow" href="/co-hoi" style={{ marginBottom: 18 }}>← Tất cả cơ hội</a>
        <div className="pub-detail-grid">
          <article>
            <div className="pub-card-top">
              <span className="pill-tag">{o.industry || "Cơ hội B2B"}</span>
              <span className="mono pub-code">{o.code}</span>
            </div>
            <h1 className="h-display">{o.title}</h1>
            {o.summary && o.summary.trim() !== o.title.trim() ? <p className="pub-summary">{o.summary}</p> : null}
            <dl className="pub-facts">
              {o.province ? <><dt>Khu vực</dt><dd>{o.province}{o.region && o.region !== o.province ? ` · ${o.region}` : ""}</dd></> : null}
              {o.source_type ? <><dt>Nguồn</dt><dd>{o.source_type}</dd></> : null}
              {o.scale ? <><dt>Quy mô / số lượng</dt><dd>{o.scale}</dd></> : null}
              {o.estimated_value ? <><dt>Giá trị ước tính</dt><dd>{o.estimated_value}</dd></> : null}
              {o.deadline ? <><dt>Hạn chót</dt><dd>{fmtDay(o.deadline)}{left !== null ? (left < 0 ? " (đã quá hạn)" : ` · còn ${left} ngày`) : ""}</dd></> : null}
              {o.enrich_round ? <><dt>Làm giàu thông tin</dt><dd>Vòng {o.enrich_round}</dd></> : null}
              {o.published_at ? <><dt>Mở bán</dt><dd>{fmtDay(o.published_at)}</dd></> : null}
            </dl>
            <div className="pub-locked">
              <b><svg className="icon"><use href="#i-shield" /></svg> Mở khoá khi mua phiếu</b>
              <ul>{locked.map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
          </article>

          <aside className="pub-buy">
            <small>Giá phiếu từ</small>
            <b className="pub-price">{vnd(o.price_from)}</b>
            <span className="pub-note">Giá thành viên tính theo mức phù hợp với doanh nghiệp của bạn.</span>
            <span className="pub-note">{o.sold_out ? "Phiếu đã hết lượt mua." : o.exclusive ? "Phiếu độc quyền — chỉ 1 thành viên mua." : `Còn ${o.remaining}/${o.max_buyers} lượt mua.`}</span>
            <BuyButton id={o.id} code={o.code} disabled={o.sold_out} />
            <ShareButton title={o.title} />
          </aside>
        </div>
      </div>
    </section>
  );
}
