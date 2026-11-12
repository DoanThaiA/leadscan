import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { cache } from "react";

import BuyButton, { ShareButton } from "@/components/public-opp/BuyButton";
import PublicOppCard, { OppBadges, SlotBar } from "@/components/public-opp/OppCard";
import { fetchPublicOpp, fmtDay, vnd } from "@/lib/public-opps";

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

const level = (n: number) => (n >= 80 ? "Cao" : n >= 60 ? "Khá" : n >= 40 ? "Trung bình" : "Thấp");

function Meter({ label, value, note }: { label: string; value: number | null; note: string }) {
  return (
    <div className="pub-meter">
      <div><span>{label}</span><b>{value === null ? "Riêng bạn" : `${value}/100 · ${level(value)}`}</b></div>
      <i className="pub-bar" aria-hidden="true"><i className={value === null ? "q" : undefined} style={{ width: `${value ?? 100}%` }} /></i>
      <small>{note}</small>
    </div>
  );
}

export default async function PublicOppPage({ params }: Props) {
  const o = await getOpp((await params).code);
  if (!o) notFound();
  const left = o.days_left;
  const imgs = o.attachment_counts?.images ?? 0, files = o.attachment_counts?.files ?? 0;

  const facts: [string, string, ReactNode][] = [
    ["map", "Khu vực", o.province ? `${o.province}${o.region && o.region !== o.province ? ` · ${o.region}` : ""}` : ""],
    ["layers", "Quy mô / số lượng", o.scale],
    ["wallet", "Giá trị ước tính", o.estimated_value],
    ["gauge", "Hạn chót", o.deadline ? <>{fmtDay(o.deadline)}{left !== null ? <em className={left >= 0 && left <= 7 ? "hot" : undefined}>{left < 0 ? " · đã quá hạn" : left === 0 ? " · hôm nay" : ` · còn ${left} ngày`}</em> : null}</> : ""],
    ["globe", "Nguồn tin", o.source_type],
    ["users", "Đầu mối liên hệ", o.contact_count ? `${o.contact_count} người — mở khoá khi mua` : ""],
  ];
  const unlock = [
    "Tên doanh nghiệp / bên có nhu cầu",
    "Mô tả chi tiết nhu cầu",
    o.contact_count ? `${o.contact_count} đầu mối: họ tên, chức vụ, điện thoại, email` : "Đầu mối liên hệ (khi có)",
    imgs ? `${imgs} ảnh hiện trường / tài liệu` : "",
    files ? `${files} tệp tài liệu kèm theo` : "",
    "Link nguồn tin gốc để tự kiểm chứng",
  ].filter(Boolean);
  const blurRows = Math.max(1, Math.min(o.contact_count, 3));

  return (
    <>
      <section className="pub-detail">
        <div className="container">
          <nav className="pub-crumb" aria-label="Đường dẫn"><a href="/co-hoi">Cơ hội</a><span>/</span>{o.industry ? <><a href={`/co-hoi?nganh=${encodeURIComponent(o.industry)}`}>{o.industry}</a><span>/</span></> : null}<b className="mono">{o.code}</b></nav>
          <div className="pub-detail-grid">
            <article>
              <div className="pub-badges"><span className="pub-ind">{o.industry || "Cơ hội B2B"}</span><OppBadges o={o} /></div>
              <h1 className="h-display">{o.title}</h1>
              {o.summary && o.summary.trim() !== o.title.trim() ? <p className="pub-summary">{o.summary}</p> : null}
              <p className="pub-posted">Mã <b className="mono">{o.code}</b>{o.published_at ? ` · mở bán ${fmtDay(o.published_at)}` : ""}{o.enrich_round ? ` · đã làm giàu thông tin ${o.enrich_round} vòng` : ""}</p>

              <div className="pub-tiles">
                {facts.filter(([, , v]) => v).map(([ic, k, v]) => (
                  <div key={k} className="pub-tile">
                    <span className="pub-tile-ic"><svg className="icon"><use href={`#i-${ic}`} /></svg></span>
                    <div><small>{k}</small><b>{v}</b></div>
                  </div>
                ))}
              </div>

              <h2 className="pub-h2">Chấm điểm cơ hội</h2>
              <div className="pub-meters">
                <Meter label="Độ tin cậy nguồn" value={o.trust} note="Theo loại nguồn, số vòng làm giàu, đầu mối và link nguồn." />
                <Meter label="Độ cấp thiết" value={o.urgency} note={o.deadline ? "Hạn chót càng gần, nhu cầu càng gấp." : "Chưa có hạn chót cụ thể."} />
                <Meter label="Độ phù hợp" value={null} note="Chấm riêng theo ngành, khu vực, năng lực của doanh nghiệp bạn khi là thành viên." />
              </div>

              <h2 className="pub-h2">Thông tin mở khoá khi mua phiếu</h2>
              <div className="pub-vault">
                <div className="pub-vault-rows" aria-hidden="true">
                  <div><small>Bên có nhu cầu</small><i className="pub-blur">Công ty Cổ phần •••••• Việt Nam</i></div>
                  {Array.from({ length: blurRows }, (_, i) => (
                    <div key={i}><small>Đầu mối {blurRows > 1 ? i + 1 : ""}</small><i className="pub-blur">Nguyễn Văn •• · Trưởng phòng mua hàng · 09•• ••• •••</i></div>
                  ))}
                  <div><small>Chi tiết nhu cầu</small><i className="pub-blur">Cần nhà cung cấp đáp ứng •••••• trong quý tới, ưu tiên •••••• có chứng nhận ••••</i></div>
                </div>
                <div className="pub-vault-over">
                  <span className="pub-lock"><svg className="icon"><use href="#i-shield" /></svg></span>
                  <b>Đã ẩn — chỉ người mua phiếu xem được</b>
                  <a className="btn btn-primary" href="#mua">Mua phiếu để mở khoá</a>
                </div>
              </div>
              <ul className="pub-checks">
                {unlock.map((x) => <li key={x}><svg className="icon"><use href="#i-check" /></svg>{x}</li>)}
              </ul>
            </article>

            <aside className="pub-buy" id="mua">
              <small>Giá phiếu từ</small>
              <b className="pub-price">{vnd(o.price_from)}</b>
              <span className="pub-note">Giá thành viên tính theo mức phù hợp với doanh nghiệp của bạn.</span>
              <SlotBar o={o} />
              <BuyButton id={o.id} code={o.code} disabled={o.sold_out} />
              <ShareButton title={o.title} />
              <ul className="pub-assure">
                <li><svg className="icon"><use href="#i-check" /></svg>Cơ hội được LeadScan kiểm duyệt trước khi mở bán</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Giới hạn {o.exclusive ? "1 người mua — độc quyền" : `${o.max_buyers} người mua — ít cạnh tranh`}</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Trả bằng điểm trong ví thành viên, mở khoá ngay</li>
              </ul>
            </aside>
          </div>

          {o.related?.length ? (
            <div className="pub-related">
              <div className="pub-related-hd">
                <h2 className="h-display">Cơ hội cùng ngành <b>{o.industry}</b></h2>
                <a className="link-arrow" href={`/co-hoi?nganh=${encodeURIComponent(o.industry)}`}>Xem tất cả <svg className="icon"><use href="#i-arrow" /></svg></a>
              </div>
              <div className="pub-grid">{o.related.map((r) => <PublicOppCard key={r.id} o={r} />)}</div>
            </div>
          ) : null}
        </div>
      </section>

      {!o.sold_out ? (
        <div className="pub-mbar">
          <div><small>Giá phiếu từ</small><b>{vnd(o.price_from)}</b></div>
          <a className="btn btn-primary" href="#mua">Mua phiếu</a>
        </div>
      ) : null}
    </>
  );
}
