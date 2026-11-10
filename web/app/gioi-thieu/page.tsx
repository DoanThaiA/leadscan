import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/Logo";

/* Trang giới thiệu — dựng theo mẫu "LeadScan Company Profile" (3 mảng: đào tạo AI · LeadScan.net · phần mềm & chuyển đổi số).
   Ảnh và logo khách hàng nằm trong web/public/gioi-thieu. Viethome chưa có logo → hiện chữ (thay bằng ảnh khi có). */

const DESC =
  "LeadScan & MCV Network: đào tạo AI thực chiến cho doanh nghiệp, nền tảng AI tìm kiếm cơ hội kinh doanh B2B LeadScan.net và dịch vụ phát triển phần mềm, chuyển đổi số tích hợp AI theo yêu cầu.";

export const metadata: Metadata = {
  title: "Giới thiệu – LeadScan B2B",
  description: DESC,
  alternates: { canonical: "/gioi-thieu" },
  openGraph: {
    type: "website",
    locale: "vi_VN",
    siteName: "LeadScan B2B",
    url: "/gioi-thieu",
    title: "Giới thiệu – LeadScan B2B",
    description: DESC,
    images: [{ url: "/gioi-thieu/dao-tao-khai-giang.webp", width: 900, height: 600, alt: "Lớp đào tạo AI cho doanh nghiệp" }],
  },
};

const CONTACT = "mailto:contact@leadscanb2b.com";

/* Biểu tượng nét (cùng phong cách sprite landing: stroke 2, bo tròn) cho các mục chưa có trong IconSprite */
const P: Record<string, ReactNode> = {
  code: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M2 20h20M10 8l-2 2 2 2M14 8l2 2-2 2" /></>,
  puzzle: <path d="M10 3h4v3a2 2 0 1 0 4 0V3h3v7h-3a2 2 0 1 0 0 4h3v7h-7v-3a2 2 0 1 0-4 0v3H3v-7h3a2 2 0 1 0 0-4H3V3h7z" />,
  cloud: <><path d="M7 18a5 5 0 0 1-.6-9.96A6 6 0 0 1 18 9a4.5 4.5 0 0 1-.5 9H16" /><path d="M12 12v9M9 15l3-3 3 3" /></>,
  erp: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4M7 9h3M7 12h6M14 9h3" /></>,
  crm: <><circle cx="9" cy="8" r="3" /><path d="M3 20a6 6 0 0 1 12 0" /><circle cx="17" cy="9" r="2.5" /><path d="M16 14.2A5 5 0 0 1 21 19" /></>,
  hrm: <><circle cx="12" cy="7" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /><path d="M12 13l-1.5 3 1.5 5 1.5-5z" /></>,
  wms: <><path d="M3 10l9-6 9 6v10H3z" /><path d="M7 20v-7h10v7M7 16h10" /></>,
  srm: <><circle cx="9" cy="20" r="1.5" /><circle cx="18" cy="20" r="1.5" /><path d="M2 3h3l2.6 12.4a1.5 1.5 0 0 0 1.5 1.1h8.8a1.5 1.5 0 0 0 1.5-1.1L21 7H6" /></>,
  ecom: <><path d="M5 8h14l-1 13H6z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></>,
  ticket: <><path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4z" /><path d="M14 6v12" strokeDasharray="2 2" /></>,
  uni: <><path d="M3 9l9-5 9 5-9 5z" /><path d="M6 11v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5M21 9v6" /></>,
  growth: <><path d="M3 3v18h18" /><path d="M7 15l4-4 3 3 6-6M15 8h5v5" /></>,
  coins: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
};
function Ic({ n, size = 22 }: { n: string; size?: number }) {
  return <svg className="icon" viewBox="0 0 24 24" style={{ width: size, height: size }} aria-hidden="true">{P[n]}</svg>;
}
function Sprite({ id, size = 22 }: { id: string; size?: number }) {
  return <svg className="icon" style={{ width: size, height: size }} aria-hidden="true"><use href={`#${id}`} /></svg>;
}

type Brand = { name: string; src?: string; h?: number };
function Logos({ items }: { items: Brand[] }) {
  return (
    <ul className="ab-logos">
      {items.map((b) => (
        <li key={b.name} title={b.name}>
          {b.src ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={b.src} alt={b.name} style={{ height: b.h }} loading="lazy" />
          ) : (
            <span className="ab-wordmark">{b.name}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

const TRAIN_POINTS = [
  "Trực tiếp đào tạo AI thực chiến cho đội kinh doanh, marketing và vận hành",
  "Trọng tâm năng suất, marketing automation và thiết kế lại quy trình (workflow)",
  "Workshop may đo theo bài toán thực tế của từng doanh nghiệp",
];

const TRAIN_PHOTOS = [
  { src: "/gioi-thieu/dao-tao-khai-giang.webp", alt: "Khai giảng lớp AI ứng dụng cho doanh nghiệp", w: 900, h: 600 },
  { src: "/gioi-thieu/dao-tao-ai-thuc-chien.webp", alt: "Chia sẻ AI thực chiến cho Kinh doanh & Marketing", w: 900, h: 675 },
  { src: "/gioi-thieu/dao-tao-workshop.webp", alt: "Workshop AI theo bài toán doanh nghiệp", w: 675, h: 900 },
];

const PROGRAMS = [
  "Khai giảng chương trình AI ứng dụng cho doanh nghiệp",
  "Đào tạo AI thực chiến tại Ngọc Sơn Hafuco",
  "Chia sẻ AI & vận hành cùng cộng đồng CEO 1989",
  "Ứng dụng AI cho xuất nhập khẩu & thương mại quốc tế",
  "Lớp tài chính số kết hợp AI",
  "Đào tạo AI cho doanh nghiệp khoáng sản Lào Cai",
];

const SEGMENTS = [
  { icon: "i-factory", t: "Sản xuất", d: "Nhà máy, dự án cần nguyên vật liệu, linh kiện, bao bì, gia công" },
  { icon: "i-globe", t: "Xuất nhập khẩu", d: "Nhu cầu đăng mua, đối tác hội chợ, doanh nghiệp FDI mới" },
  { icon: "i-cart", t: "Thương mại & phân phối", d: "Đại lý, chuỗi bán lẻ, khách sỉ đang mở rộng" },
  { icon: "i-brief", t: "Dịch vụ B2B & nhà thầu", d: "Gói thầu, dự án, doanh nghiệp mới thành lập" },
];

const LEADSCAN_CLIENTS: Brand[] = [
  { name: "Wepac", src: "/gioi-thieu/logo-wepac.png", h: 30 },
  { name: "TLC Lighting", src: "/gioi-thieu/logo-tlc-lighting.png", h: 34 },
  { name: "Tasco", src: "/gioi-thieu/logo-tasco.png", h: 20 },
  { name: "BIDV", src: "/gioi-thieu/logo-bidv.png", h: 30 },
  { name: "Cchat", src: "/gioi-thieu/logo-cchat.png", h: 32 },
];

const SERVICES = [
  { icon: "code", t: "Thiết kế & phát triển theo yêu cầu, tích hợp AI", d: "Phần mềm may đo theo quy trình riêng của doanh nghiệp, gắn trợ lý AI và tự động hoá ngay trong nghiệp vụ." },
  { icon: "puzzle", t: "Nhóm giải pháp quản trị", d: "ERP, CRM, HRM, WMS, SRM, E-com Ops — triển khai từng phân hệ hoặc kết nối thành một hệ thống thống nhất." },
  { icon: "cloud", t: "Tư vấn chuyển đổi số trọn gói", d: "Khảo sát, tư vấn lộ trình, triển khai, đào tạo người dùng và đồng hành vận hành sau go-live." },
];

const MODULES = [
  { icon: "erp", t: "ERP", d: "Quản trị nguồn lực tổng thể" },
  { icon: "crm", t: "CRM", d: "Khách hàng & bán hàng" },
  { icon: "hrm", t: "HRM", d: "Nhân sự, chấm công, lương" },
  { icon: "wms", t: "WMS", d: "Quản lý kho vận" },
  { icon: "srm", t: "SRM", d: "Nhà cung cấp & mua hàng" },
  { icon: "ecom", t: "E-com Ops", d: "Vận hành TMĐT đa kênh" },
];

const SOFTWARE_CLIENTS: Brand[] = [
  { name: "Stavian Group", src: "/gioi-thieu/logo-stavian.png", h: 42 },
  { name: "Cchat", src: "/gioi-thieu/logo-cchat.png", h: 30 },
  { name: "TLC Lighting", src: "/gioi-thieu/logo-tlc-lighting.png", h: 32 },
  { name: "K-Hair", src: "/gioi-thieu/logo-k-hair.png", h: 54 },
  { name: "DrC Group", src: "/gioi-thieu/logo-drcung.png", h: 54 },
  { name: "VNPT", src: "/gioi-thieu/logo-vnpt.png", h: 26 },
  { name: "BIDV", src: "/gioi-thieu/logo-bidv.png", h: 30 },
  { name: "Viethome" },
  { name: "Modero", src: "/gioi-thieu/logo-modero.png", h: 36 },
];

const TEAM = [
  { icon: "uni", t: "Nhân sự chất lượng cao", d: "Chuyên gia, kỹ sư trẻ được đào tạo từ các trường đại học hàng đầu." },
  { icon: "growth", t: "Vận hành hiệu quả", d: "Ứng dụng Scrum, Agile và OKR trong quản trị, tối ưu hiệu suất." },
  { icon: "bot", t: "Con người & AI", d: "Lấy con người làm trung tâm, AI làm đòn bẩy phát triển." },
];

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  name: "Giới thiệu LeadScan B2B",
  url: "https://leadscan.net/gioi-thieu",
  about: { "@type": "Organization", name: "LeadScan B2B", url: "https://leadscan.net/", email: "contact@leadscanb2b.com" },
  mainEntity: {
    "@type": "Person",
    name: "Tony Phúc",
    jobTitle: "Founder & CEO",
    worksFor: { "@type": "Organization", name: "MCV Network", url: "https://mcv.network/" },
    image: "https://leadscan.net/gioi-thieu/tony-phuc.webp",
  },
};

export default function AboutPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      <section className="ab-hero">
        <div className="container">
          <h1>
            <span className="sr-only">Giới thiệu LeadScan</span>
            <Logo variant="logo-reverse" height={64} className="ab-hero-logo" />
          </h1>
          <p className="ab-hero-tag">Scan đúng cơ hội kinh doanh cho doanh nghiệp bạn</p>
        </div>
      </section>
      <section className="ab-band">
        <div className="container">
          <p className="ab-band-title">Nền tảng AI tìm kiếm, làm giàu và chấm điểm <b>cơ hội kinh doanh B2B</b></p>
          <nav className="ab-jump" aria-label="Các mảng hoạt động">
            <a href="#dao-tao-ai"><b>01</b>Đào tạo AI doanh nghiệp</a>
            <a href="#leadscan"><b>02</b>LeadScan.net</a>
            <a href="#phan-mem"><b>03</b>Phần mềm & chuyển đổi số</a>
            <a href="#doi-ngu"><b>04</b>Năng lực đội ngũ</a>
          </nav>
        </div>
      </section>

      <div className="ab-wrap">
        {/* 01 — Đào tạo AI */}
        <section id="dao-tao-ai" className="container ab-sec">
          <div className="ab-card">
            <h2 className="ab-title"><span className="ab-num">01</span>Đào tạo AI doanh nghiệp</h2>

            <div className="ab-founder">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className="ab-portrait" src="/gioi-thieu/tony-phuc.webp" alt="Tony Phúc – Founder & CEO MCV Network" width={595} height={597} />
              <div className="ab-bio">
                <h3>Tony Phúc</h3>
                <p className="ab-role">Founder & CEO MCV Network</p>
                <p>
                  15 năm kinh nghiệm trong công nghệ, martech, thương mại số và vận hành sản phẩm. Anh từng tham gia điều hành và xây dựng tại
                  <b> Phong Vũ</b>, <b>Vnshop</b> và <b>Miraway</b>.
                </p>
                <p>
                  Song song với việc xây dựng doanh nghiệp, anh trực tiếp thiết kế và đứng lớp các chương trình AI thực chiến cho đội ngũ kinh doanh,
                  marketing và vận hành — giúp lãnh đạo đưa AI vào công việc hằng ngày, không dừng ở lý thuyết.
                </p>
                <div className="ab-tags">
                  {["Phong Vũ", "Vnshop", "Miraway", "Martech", "Thương mại số"].map((t) => <span key={t} className="pill-tag">{t}</span>)}
                </div>
              </div>
              <ul className="ab-checks">
                {TRAIN_POINTS.map((t) => <li key={t}><Sprite id="i-check" size={16} />{t}</li>)}
              </ul>
            </div>

            <div className="ab-photos">
              {TRAIN_PHOTOS.map((p) => (
                <figure key={p.src}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={p.src} alt={p.alt} width={p.w} height={p.h} loading="lazy" />
                  <figcaption>{p.alt}</figcaption>
                </figure>
              ))}
            </div>

            <div className="ab-programs">
              <h4>Một số chương trình đã triển khai</h4>
              <ul>{PROGRAMS.map((t) => <li key={t}>{t}</li>)}</ul>
              <a href={`${CONTACT}?subject=${encodeURIComponent("Đăng ký workshop / đào tạo AI cho doanh nghiệp")}`} className="btn btn-outline btn-sm">
                Đặt lịch workshop cho doanh nghiệp <Sprite id="i-arrow" size={16} />
              </a>
            </div>
          </div>
        </section>

        {/* 02 — LeadScan.net */}
        <section id="leadscan" className="container ab-sec">
          <div className="ab-card ab-dark">
            <div className="ab-ls-top">
              <div>
                <h2 className="ab-title"><span className="ab-num">02</span>LeadScan.net</h2>
                <p className="ab-ls-lead">
                  Hệ thống AI tìm kiếm cơ hội kinh doanh B2B. Bạn mô tả cơ hội cần tìm — AI quét hơn 10 nhóm nguồn dữ liệu, làm giàu thông tin
                  và chấm điểm từng cơ hội; bạn chọn mua đúng phiếu mình cần.
                </p>
                <div className="ab-ls-cta">
                  <a href="/#dang-ky" className="btn btn-primary">Đăng ký thành viên <Sprite id="i-arrow" size={16} /></a>
                  <a href="/" className="btn ab-btn-ghost">Khám phá LeadScan</a>
                </div>
              </div>
              <div className="ab-price">
                <small>Phiếu cơ hội chỉ từ</small>
                <strong>29.000đ</strong>
                <ul>
                  <li><Ic n="ticket" size={20} />Trả tiền theo chất lượng cơ hội</li>
                  <li><Ic n="coins" size={20} />Phí thành viên 89.000đ/năm được trừ dần vào phiếu đã mua</li>
                </ul>
              </div>
            </div>

            <ul className="ab-segs">
              {SEGMENTS.map((s) => (
                <li key={s.t}>
                  <Sprite id={s.icon} size={34} />
                  <b>{s.t}</b>
                  <span>{s.d}</span>
                </li>
              ))}
            </ul>

            <div className="ab-clients ab-clients-ls">
              <p>Khách hàng đang sử dụng</p>
              <Logos items={LEADSCAN_CLIENTS} />
            </div>
          </div>
        </section>

        {/* 03 — Phần mềm & chuyển đổi số */}
        <section id="phan-mem" className="container ab-sec">
          <div className="ab-card">
            <h2 className="ab-title"><span className="ab-num">03</span>Phát triển phần mềm & chuyển đổi số</h2>
            <p className="ab-sub">Phần mềm và chuyển đổi số theo yêu cầu doanh nghiệp, tích hợp AI.</p>

            <div className="ab-sw">
              <ul className="ab-services">
                {SERVICES.map((s) => (
                  <li key={s.t}>
                    <span className="ab-svc-ic"><Ic n={s.icon} size={26} /></span>
                    <div><b>{s.t}</b><p>{s.d}</p></div>
                  </li>
                ))}
              </ul>
              <ul className="ab-modules">
                {MODULES.map((m) => (
                  <li key={m.t}>
                    <Ic n={m.icon} size={38} />
                    <b>{m.t}</b>
                    <span>{m.d}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="ab-clients">
              <p className="ab-clients-title">Khách hàng tiêu biểu</p>
              <Logos items={SOFTWARE_CLIENTS} />
            </div>
          </div>
        </section>

        {/* 04 — Năng lực đội ngũ */}
        <section id="doi-ngu" className="container ab-sec">
          <div className="ab-card ab-dark ab-team">
            <div className="ab-team-text">
              <h2 className="ab-title"><span className="ab-num">04</span>Năng lực đội ngũ</h2>
              <p className="ab-motto">Con người xuất sắc – Được AI tăng lực – Kiến tạo tương lai</p>
              <ul className="ab-team-list">
                {TEAM.map((x) => (
                  <li key={x.t}>
                    {x.icon === "bot" ? <Sprite id="i-bot" size={34} /> : <Ic n={x.icon} size={34} />}
                    <div><b>{x.t}</b><p>{x.d}</p></div>
                  </li>
                ))}
              </ul>
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="ab-team-photo" src="/gioi-thieu/doi-ngu.webp" alt="Đội ngũ LeadScan" width={1400} height={1052} loading="lazy" />
          </div>
        </section>
      </div>

      <section className="cta ab-cta">
        <div className="container">
          <h2>Cùng trao đổi bài toán của doanh nghiệp bạn</h2>
          <p>Đào tạo AI cho đội ngũ, tìm khách hàng B2B bằng LeadScan hay xây phần mềm riêng — hãy kể cho chúng tôi nghe bạn đang cần gì.</p>
          <div className="ab-cta-btns">
            <a href={`${CONTACT}?subject=${encodeURIComponent("Tư vấn giải pháp cho doanh nghiệp")}`} className="btn btn-primary">Liên hệ tư vấn <Sprite id="i-arrow" size={16} /></a>
            <a href="/#dang-ky" className="btn btn-light">Đăng ký thành viên LeadScan</a>
          </div>
        </div>
      </section>
    </>
  );
}
