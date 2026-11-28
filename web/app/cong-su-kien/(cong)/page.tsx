import { EventCardItem } from "@/components/events/EventCardItem";
import { fetchEvents } from "@/lib/events-server";
import { currentSite } from "@/lib/site-server";

export const dynamic = "force-dynamic"; // luôn lấy danh sách mới nhất từ API

const STEPS = [
  ["Điền thông tin", "Họ tên, liên hệ và nhu cầu kết nối; đính kèm profile doanh nghiệp dạng PDF."],
  ["Chuyển khoản", "Quét mã QR hiện ra ngay sau khi đăng ký — số tiền và nội dung đã điền sẵn."],
  ["Tải ảnh biên lai", "Hệ thống đọc ảnh và so khớp mã đăng ký cùng số tiền để xác nhận."],
  ["Nhận xác nhận", "Ban tổ chức tổng hợp nhu cầu và ghép cặp kết nối trước ngày diễn ra."],
] as const;

/** Trang chủ cổng sự kiện (c89.leadscan.net/, epc.leadscan.net/): sự kiện đang mở của riêng cổng. */
export default async function PortalHomePage() {
  const [site, events] = await Promise.all([currentSite(), fetchEvents()]);
  const n = events?.length ?? 0;
  const next = events?.[0];
  const seats = (events ?? []).reduce((a, e) => a + (e.tickets?.remaining ?? 0), 0);

  return (
    <>
      <section className="pt-hero">
        <div className="container pt-hero-grid">
          <div>
            <span className="pill"><i className="cr-dot" aria-hidden="true" />{site.tagline}</span>
            <h1 className="h-display">Sự kiện của <b>{site.name}</b></h1>
            <p className="cr-lead">
              Gặp gỡ, chia sẻ kinh nghiệm thực chiến và kết nối giao thương giữa các doanh nghiệp. Xem chương trình, gửi nhu cầu hợp tác và giữ chỗ ngay trên trang.
            </p>
            <div className="cr-cta">
              <a href="#danh-sach" className="btn btn-primary">Xem sự kiện đang mở <svg className="icon"><use href="#i-arrow" /></svg></a>
              <a href="#cach-dang-ky" className="btn btn-outline">Cách đăng ký</a>
            </div>
          </div>
          <div className="pt-hero-card">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={site.logo} alt={site.name} className="pt-hero-logo" />
            <dl className="pt-hero-stats">
              <div><dt>Sự kiện đang mở</dt><dd>{n}</dd></div>
              <div><dt>Chỗ còn trống</dt><dd>{seats || "—"}</dd></div>
            </dl>
            {next ? (
              <a href={`/su-kien/${next.slug}`} className="pt-hero-next">
                <small>Sắp diễn ra</small>
                <b>{next.title}</b>
                <span>Xem chi tiết →</span>
              </a>
            ) : null}
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
              <p>Sự kiện mới của {site.name} sẽ được đăng tại đây. Bạn quay lại sau nhé.</p>
            </div>
          ) : (
            <div className="cr-grid">
              {events.map((e) => <EventCardItem key={e.slug} event={e} />)}
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
