import type { Metadata } from "next";

import { daysLeft, fmtDay, fmtVnd, parseLocal, type EventCard } from "@/lib/events";
import { fetchEvents } from "@/lib/events-server";
import { breadcrumbLd, ldJson } from "@/lib/seo";

export const dynamic = "force-dynamic"; // luôn lấy danh sách mới nhất từ API

const DESC =
  "Các sự kiện kết nối giao thương, business matching và chia sẻ kinh nghiệm quản trị dành cho doanh nghiệp. Xem chương trình chi tiết và đăng ký tham dự trực tuyến.";

const OG_IMAGE = { url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "Sự kiện LeadScan B2B" };

export const metadata: Metadata = {
  title: "Sự kiện – LeadScan B2B",
  description: DESC,
  alternates: { canonical: "/su-kien" },
  openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: "/su-kien", title: "Sự kiện – LeadScan B2B", description: DESC, images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", images: [OG_IMAGE.url] },
};

const STEPS = [
  ["Điền thông tin", "Họ tên, liên hệ và nhu cầu xúc tiến hợp tác; đính kèm profile doanh nghiệp dạng PDF."],
  ["Chuyển khoản", "Quét mã QR hiện ra ngay sau khi đăng ký — số tiền và nội dung đã điền sẵn."],
  ["Tải ảnh biên lai", "Hệ thống đọc ảnh và so khớp mã đăng ký cùng số tiền để xác nhận."],
  ["Nhận xác nhận", "Ban tổ chức tổng hợp nhu cầu và ghép cặp kết nối trước ngày diễn ra."],
] as const;

export default async function EventsPage() {
  const events = await fetchEvents();
  const n = events?.length ?? 0;

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ldJson([breadcrumbLd([["Trang chủ", "/"], ["Sự kiện", "/su-kien"]])]) }} />

      <section className="cr-hero">
        <div className="container cr-hero-grid">
          <div>
            <span className="pill"><i className="cr-dot" aria-hidden="true" />Sự kiện &amp; kết nối</span>
            <h1 className="h-display">Gặp đúng người, <b>mở đúng cơ hội</b></h1>
            <p className="cr-lead">
              Các buổi business matching, tham quan doanh nghiệp và chia sẻ kinh nghiệm thực chiến — nơi doanh nghiệp giới thiệu
              năng lực, nêu nhu cầu và chốt cơ hội hợp tác ngay tại chỗ.
            </p>
            <div className="cr-cta">
              <a href="#danh-sach" className="btn btn-primary">Xem sự kiện sắp diễn ra <svg className="icon"><use href="#i-arrow" /></svg></a>
              <a href="#cach-dang-ky" className="btn btn-outline">Cách đăng ký</a>
            </div>
          </div>

          <div className="cr-art" aria-hidden="true">
            <div className="card cr-art-main">
              <small>Đang mở đăng ký</small>
              <strong>{n > 0 ? `${n} sự kiện` : "Sắp mở"}</strong>
              <div className="chips">
                {["Business matching", "Chia sẻ kinh nghiệm", "Kết nối giao thương"].map((d) => <span key={d} className="chip on">{d}</span>)}
              </div>
            </div>
            <div className="card cr-art-row">
              <span className="cr-art-ic"><svg className="icon"><use href="#i-users" /></svg></span>
              <div><b>Ghép cặp theo nhu cầu</b><small>Nhu cầu gửi trước, trao đổi đúng người</small></div>
            </div>
            <div className="card cr-art-row">
              <span className="cr-art-ic green"><svg className="icon"><use href="#i-check" /></svg></span>
              <div><b>Đăng ký &amp; thanh toán online</b><small>Quét QR, tải biên lai, xác nhận ngay</small></div>
            </div>
          </div>
        </div>
      </section>

      <section className="section cr-jobs" id="danh-sach">
        <div className="container">
          <div className="cr-head">
            <div>
              <span className="pill-tag">Sắp diễn ra</span>
              <h2 className="h-display h2">Sự kiện <b>đang mở đăng ký</b></h2>
            </div>
            <p>Chọn sự kiện để xem chương trình chi tiết, nhu cầu kết nối của các bên và đăng ký tham dự.</p>
          </div>

          {events === null ? (
            <div className="cr-empty">
              <svg className="icon"><use href="#i-info" /></svg>
              <h3>Chưa tải được danh sách sự kiện</h3>
              <p>Hệ thống đang bận. Vui lòng tải lại trang sau ít phút.</p>
            </div>
          ) : !events.length ? (
            <div className="cr-empty">
              <svg className="icon"><use href="#i-ticket" /></svg>
              <h3>Chưa có sự kiện nào đang mở</h3>
              <p>Sự kiện mới sẽ được đăng tại đây. Bạn quay lại sau nhé.</p>
            </div>
          ) : (
            <div className="cr-grid">
              {events.map((e) => <EventItem key={e.slug} event={e} />)}
            </div>
          )}
        </div>
      </section>

      <section className="section" id="cach-dang-ky">
        <div className="container">
          <div className="cr-head">
            <div>
              <span className="pill-tag">Cách đăng ký</span>
              <h2 className="h-display h2">Bốn bước, <b>làm xong trong 3 phút</b></h2>
            </div>
          </div>
          <ol className="cr-steps">
            {STEPS.map(([t, d], i) => (
              <li key={t}>
                <span className="cr-step-n">BƯỚC {String(i + 1).padStart(2, "0")}</span>
                <h3>{t}</h3>
                <p>{d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </>
  );
}

function EventItem({ event: e }: { event: EventCard }) {
  const when = parseLocal(e.starts_at);
  const left = daysLeft(e.deadline);
  const href = `/su-kien/${e.slug}`;
  const fees = [e.fee_member, e.fee_guest].filter((x) => x > 0);
  const fee = fees.length ? `${fmtVnd(Math.min(...fees))}${Math.max(...fees) !== Math.min(...fees) ? ` – ${fmtVnd(Math.max(...fees))}` : ""}` : "Miễn phí";

  return (
    <a className={e.cover_image ? "cr-job has-cover" : "cr-job"} href={href}>
      {e.cover_image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="cr-job-cover" src={e.cover_image} alt="" loading="lazy" />
      ) : null}
      <div className="cr-job-top">
        <span className="pill-tag">{e.host || "Sự kiện"}{e.partner ? ` × ${e.partner}` : ""}</span>
        {left !== null && left >= 0 ? <span className={left <= 3 ? "cr-due soon" : "cr-due"}>{left === 0 ? "Hạn đăng ký hôm nay" : `Còn ${left} ngày đăng ký`}</span> : null}
      </div>
      <h3>{e.title}</h3>
      {e.summary ? <p>{e.summary}</p> : null}
      <ul className="cr-meta">
        {when ? <li><svg className="icon"><use href="#i-calc" /></svg>{when.day}{when.time ? ` · ${when.time}` : ""}</li> : null}
        {e.venue ? <li><svg className="icon"><use href="#i-map" /></svg>{e.venue}</li> : null}
        <li><svg className="icon"><use href="#i-ticket" /></svg>{fee}</li>
        {e.deadline ? <li><svg className="icon"><use href="#i-clipboard" /></svg>Hạn đăng ký {fmtDay(e.deadline)}</li> : null}
      </ul>
      <span className="link-arrow">Xem chi tiết &amp; đăng ký <svg className="icon" style={{ width: 16, height: 16 }}><use href="#i-arrow" /></svg></span>
    </a>
  );
}
