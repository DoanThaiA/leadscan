import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://leadscan.net";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "LeadScan B2B – Sàn kết nối cơ hội kinh doanh B2B",
  description:
    "Người mua đăng nhu cầu tìm khách hàng, đối tác đăng cơ hội mình biết. LeadScan kiểm duyệt, chấm điểm và kết nối hai bên. Xem trước miễn phí, phiếu cơ hội từ 29.000đ.",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "vi_VN",
    siteName: "LeadScan B2B",
    url: "/",
    title: "LeadScan B2B – Sàn kết nối cơ hội kinh doanh B2B",
    description: "Người mua đăng nhu cầu, đối tác đăng cơ hội, LeadScan kiểm duyệt và kết nối. Đối tác tham gia miễn phí.",
    images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }],
  },
  twitter: { card: "summary_large_image", images: ["/brand/leadscan-og.jpg"] },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#004B87",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // Script trong <head> đổi "no-js" → "js" trước khi vẽ trang (hiệu ứng hiện dần chỉ bật khi có JS)
    <html lang="vi" className="no-js" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.replace('no-js','js')" }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
