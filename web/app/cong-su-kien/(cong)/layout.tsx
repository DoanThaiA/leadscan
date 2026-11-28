import "../../landing.css";
import "../../tuyen-dung/careers.css";
import "../../su-kien/events.css";
import "./portal.css";

import type { ReactNode } from "react";

import IconSprite from "@/components/landing/IconSprite";
import { currentSite } from "@/lib/site-server";
import { SITES } from "@/lib/sites";

/** Khung trang công khai của cổng sự kiện: đầu trang có logo cổng, chân trang gọn. */
export default async function PortalPublicLayout({ children }: { children: ReactNode }) {
  const site = await currentSite();
  const year = new Date().getFullYear();
  return (
    <>
      <IconSprite />
      <header className="pt-header">
        <div className="container pt-header-in">
          <a href="/" className="pt-brand" aria-label={`Trang sự kiện ${site.name}`}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={site.logo} alt={site.name} className="pt-logo" />
            <span className="pt-brand-tx">
              <b>Sự kiện</b>
              <small>{site.name}</small>
            </span>
          </a>
          <nav className="pt-nav" aria-label="Điều hướng">
            <a href="/#danh-sach">Sự kiện đang mở</a>
            <a href="/#cach-dang-ky">Cách đăng ký</a>
            <a href="/#danh-sach" className="btn btn-primary pt-cta">Đăng ký tham dự</a>
          </nav>
        </div>
      </header>
      <main id="main">{children}</main>
      <footer className="pt-footer">
        <div className="container pt-footer-in">
          <div className="pt-footer-brand">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={site.mark} alt="" aria-hidden="true" />
            <div>
              <b>{site.name}</b>
              <span>{site.tagline}</span>
            </div>
          </div>
          <p className="pt-footer-note">
            © {year} {site.name}. Đăng ký và thanh toán vận hành trên nền tảng{" "}
            <a href={SITES.leadscan.url} target="_blank" rel="noopener">LeadScan</a>.
          </p>
        </div>
      </footer>
    </>
  );
}
