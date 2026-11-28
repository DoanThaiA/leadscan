import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import { RichText } from "@/components/careers/RichText";
import RegisterFlow from "@/components/events/RegisterFlow";
import { EVENT_SECTIONS, daysLeft, fmtDay, fmtRange, fmtVnd, parseLocal, type EventPublic } from "@/lib/events";
import { fetchEvent, fetchEvents } from "@/lib/events-server";
import { SITE_URL, breadcrumbLd, ldJson } from "@/lib/seo";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

const getEvent = cache(fetchEvent); // generateMetadata và trang dùng chung 1 lần gọi API

/** Bỏ ký hiệu định dạng (##, -, **) để đưa vào mô tả SEO / JSON-LD */
const plain = (s: string) => s.replace(/^#{2,3}\s+|^[-•*+]\s+|\*\*/gm, "").trim();

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const e = await getEvent((await params).slug);
  if (!e) return { title: "Không tìm thấy sự kiện – LeadScan B2B" };
  const title = `${e.title} – Sự kiện`;
  const description = (e.summary || e.subtitle || plain(e.intro)).slice(0, 200);
  const image = e.cover_image || "/brand/leadscan-og.jpg";
  return {
    title,
    description,
    alternates: { canonical: `/su-kien/${e.slug}` },
    robots: e.is_open ? undefined : { index: false },
    openGraph: {
      type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: `/su-kien/${e.slug}`, title, description,
      images: [{ url: image, alt: e.title }],
    },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

/** Dữ liệu có cấu trúc cho Google (thẻ sự kiện trong kết quả tìm kiếm) */
function eventLd(e: EventPublic) {
  const offers = [
    ["Thành viên CLB", e.fee_member],
    ["Khách mời ngoài CLB", e.fee_guest],
  ]
    .filter(([, v]) => typeof v === "number")
    .map(([name, price]) => ({
      "@type": "Offer",
      name,
      price: String(price),
      priceCurrency: "VND",
      availability: e.is_open ? "https://schema.org/InStock" : "https://schema.org/SoldOut",
      url: `${SITE_URL}/su-kien/${e.slug}`,
      ...(e.deadline ? { validThrough: `${e.deadline}T23:59:59+07:00` } : {}),
    }));
  return {
    "@context": "https://schema.org",
    "@type": "BusinessEvent",
    name: e.title,
    description: plain(e.summary || e.intro).slice(0, 500),
    ...(e.starts_at ? { startDate: `${e.starts_at}+07:00` } : {}),
    ...(e.ends_at ? { endDate: `${e.ends_at}+07:00` } : {}),
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    eventStatus: "https://schema.org/EventScheduled",
    ...(e.cover_image ? { image: [new URL(e.cover_image, SITE_URL).toString()] } : {}),
    location: {
      "@type": "Place",
      name: e.venue || "Việt Nam",
      address: { "@type": "PostalAddress", streetAddress: e.address || e.venue || "Việt Nam", addressCountry: "VN" },
    },
    ...(e.host ? { organizer: { "@type": "Organization", name: e.host } } : {}),
    ...(e.capacity ? { maximumAttendeeCapacity: e.capacity } : {}),
    offers,
  };
}

export default async function EventDetailPage({ params }: Props) {
  const { slug } = await params;
  const e = await getEvent(slug);
  if (!e) notFound();
  const others = ((await fetchEvents()) ?? []).filter((x) => x.slug !== e.slug).slice(0, 3);
  const sections = EVENT_SECTIONS.filter(([k]) => e[k]);
  const left = daysLeft(e.deadline);
  const when = parseLocal(e.starts_at);

  const info: [string, string, string][] = (
    [
      ["i-calc", "Thời gian", fmtRange(e.starts_at, e.ends_at)],
      ["i-map", "Địa điểm", [e.venue, e.address].filter(Boolean).join(" – ")],
      ["i-users", "Chủ trì", e.host],
      ["i-factory", "Chủ nhà", e.partner],
      ["i-ticket", "Phí thành viên CLB", e.fee_member > 0 ? `${fmtVnd(e.fee_member)}/người` : "Miễn phí"],
      ["i-ticket", "Phí khách mời ngoài CLB", e.fee_guest > 0 ? `${fmtVnd(e.fee_guest)}/người` : "Miễn phí"],
      ["i-user", "Quy mô dự kiến", e.capacity ? `${e.capacity} người` : ""],
      ["i-clipboard", "Hạn đăng ký", e.deadline ? `${fmtDay(e.deadline)}${left !== null && left >= 0 && e.is_open ? ` (còn ${left} ngày)` : ""}` : ""],
      ["i-phone", "Đầu mối liên hệ", [e.contact_name, e.contact_phone].filter(Boolean).join(" – ")],
    ] as [string, string, string][]
  ).filter(([, , v]) => v);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(eventLd(e)).replace(/</g, "\\u003c") }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ldJson([breadcrumbLd([["Trang chủ", "/"], ["Sự kiện", "/su-kien"], [e.title, `/su-kien/${e.slug}`]])]) }} />

      <section className="cr-dhero">
        <div className="container">
          <nav className="cr-crumb" aria-label="Breadcrumb">
            <a href="/">Trang chủ</a><span aria-hidden="true">/</span><a href="/su-kien">Sự kiện</a><span aria-hidden="true">/</span><span aria-current="page">{e.title}</span>
          </nav>
          <div className="cr-dhero-tags">
            <span className="pill"><i className="cr-dot" aria-hidden="true" />{e.host || "Sự kiện"}{e.partner ? ` × ${e.partner}` : ""}</span>
            {when ? <span className="pill-tag">{when.day}</span> : null}
            {e.is_open && left !== null && left >= 0 ? <span className={left <= 3 ? "cr-due soon" : "cr-due"}>{left === 0 ? "Hạn đăng ký hôm nay" : `Còn ${left} ngày đăng ký`}</span> : null}
          </div>
          <h1 className="h-display">{e.title}</h1>
          {e.subtitle ? <p className="cr-sub">{e.subtitle}</p> : null}
          <p className="cr-salary">
            <svg className="icon"><use href="#i-ticket" /></svg>
            <span>
              Phí tham dự: <b>{e.fee_member > 0 ? fmtVnd(e.fee_member) : "Miễn phí"}</b> (thành viên CLB) ·{" "}
              <b>{e.fee_guest > 0 ? fmtVnd(e.fee_guest) : "Miễn phí"}</b> (khách mời ngoài CLB)
              {e.fee_note ? <><br />{e.fee_note}</> : null}
            </span>
          </p>
          {e.is_open ? (
            <div className="cr-cta">
              <a href="#dang-ky" className="btn btn-primary">Đăng ký tham dự <svg className="icon"><use href="#i-arrow" /></svg></a>
              <a href="#noi-dung" className="btn btn-outline">Xem chương trình</a>
            </div>
          ) : (
            <div className="cr-closed" role="status"><svg className="icon"><use href="#i-info" /></svg>Sự kiện này đã ngừng nhận đăng ký. <a href="/su-kien">Xem các sự kiện khác →</a></div>
          )}
        </div>
      </section>

      {e.cover_image ? (
        <div className="container cr-cover ev-cover">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={e.cover_image} alt={e.title} fetchPriority="high" />
        </div>
      ) : null}

      <section className="cr-body" id="noi-dung">
        <div className="container cr-detail">
          <article className="cr-article">
            {sections.length ? (
              sections.map(([k, label], i) => (
                <section key={k} className="cr-sec">
                  <div className="cr-num" aria-hidden="true">{String(i + 1).padStart(2, "0")}</div>
                  <div className="cr-sec-bd">
                    <h2>{label}</h2>
                    <RichText text={e[k]} />
                    {k === "content" && e.banner_image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img className="ev-inline-img" src={e.banner_image} alt={`Minh hoạ ${e.title}`} loading="lazy" />
                    ) : null}
                  </div>
                </section>
              ))
            ) : (
              <p className="cr-sub">{e.summary || "Nội dung chương trình đang được cập nhật."}</p>
            )}
          </article>

          <aside className="cr-aside">
            <div className="cr-info">
              <h3>Thông tin chung</h3>
              <dl>
                {info.map(([ic, label, value]) => (
                  <div key={label}>
                    <dt><svg className="icon"><use href={`#${ic}`} /></svg>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              {e.is_open ? <a href="#dang-ky" className="btn btn-primary">Đăng ký tham dự</a> : null}
            </div>
          </aside>
        </div>
      </section>

      {e.is_open ? (
        <section className="section cr-apply" id="dang-ky">
          <div className="container reg-grid">
            <div className="reg-side">
              <span className="pill-tag">Đăng ký</span>
              <h2 className="h-display" style={{ marginTop: 16 }}>Giữ chỗ và <b>gửi nhu cầu kết nối</b></h2>
              <p>Ban tổ chức tổng hợp nhu cầu của tất cả người đăng ký để ghép cặp trước, nên phần giao thương tại sự kiện đi thẳng vào trao đổi.</p>
              <ol className="reg-next">
                <li><b>Điền thông tin &amp; nhu cầu</b>Kèm profile doanh nghiệp dạng PDF nếu có.</li>
                <li><b>Chuyển khoản phí tham dự</b>Quét mã QR hiện ra — số tiền và nội dung đã điền sẵn.</li>
                <li><b>Tải ảnh biên lai</b>Hệ thống đọc ảnh và đối soát mã đăng ký, số tiền để xác nhận.</li>
              </ol>
              <div className="reg-trust">
                <span><svg className="icon"><use href="#i-shield" /></svg>Thông tin chỉ dùng cho việc tổ chức và kết nối tại sự kiện</span>
                <span><svg className="icon"><use href="#i-check" /></svg>Nhận email xác nhận ngay sau khi đăng ký</span>
              </div>
            </div>
            <div className="form-card">
              <RegisterFlow event={e} />
            </div>
          </div>
        </section>
      ) : null}

      {others.length ? (
        <section className="section cr-others">
          <div className="container">
            <div className="cr-head">
              <div>
                <span className="pill-tag">Sự kiện khác</span>
                <h2 className="h-display h2">Cơ hội <b>kết nối tiếp theo</b></h2>
              </div>
              <a href="/su-kien" className="link-arrow">Xem tất cả <svg className="icon" style={{ width: 16, height: 16 }}><use href="#i-arrow" /></svg></a>
            </div>
            <div className="cr-grid">
              {others.map((o) => (
                <a key={o.slug} className="cr-job" href={`/su-kien/${o.slug}`}>
                  <div className="cr-job-top"><span className="pill-tag">{o.host || "Sự kiện"}</span></div>
                  <h3>{o.title}</h3>
                  {o.summary ? <p>{o.summary}</p> : null}
                  <span className="link-arrow">Xem chi tiết <svg className="icon" style={{ width: 16, height: 16 }}><use href="#i-arrow" /></svg></span>
                </a>
              ))}
            </div>
          </div>
        </section>
      ) : null}
    </>
  );
}
