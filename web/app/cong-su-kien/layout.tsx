import type { Metadata } from "next";
import type { CSSProperties, ReactNode } from "react";

import { SiteProvider } from "@/components/sites/SiteContext";
import { currentSite } from "@/lib/site-server";
import { themeVars } from "@/lib/sites";

/**
 * Gốc của 2 cổng sự kiện c89.leadscan.net / epc.leadscan.net (proxy.ts chuyển mọi đường dẫn của cổng vào đây).
 * Đổi bảng màu sang màu logo của cổng, đặt tên miền / tên / biểu tượng riêng cho thẻ meta.
 */
export async function generateMetadata(): Promise<Metadata> {
  const site = await currentSite();
  const title = `Sự kiện ${site.name}`;
  const description = `Các sự kiện, buổi kết nối giao thương và chia sẻ kinh nghiệm của ${site.name}. Xem chương trình và đăng ký tham dự trực tuyến.`;
  return {
    metadataBase: new URL(site.url),
    applicationName: title,
    title: { default: title, template: `%s · ${site.name}` },
    description,
    alternates: { canonical: "/" },
    icons: { icon: [{ url: site.mark, type: "image/png" }], apple: [{ url: `/sites/${site.key}/icon-192.png` }] },
    openGraph: { type: "website", locale: "vi_VN", siteName: title, url: "/", title, description, images: [{ url: site.logo, alt: site.name }] },
    twitter: { card: "summary", title, description, images: [site.logo] },
  };
}

export default async function PortalRootLayout({ children }: { children: ReactNode }) {
  const site = await currentSite();
  return (
    <SiteProvider site={site.key}>
      <div className={`pt-root pt-${site.key}`} style={themeVars(site) as CSSProperties}>
        {children}
      </div>
    </SiteProvider>
  );
}
