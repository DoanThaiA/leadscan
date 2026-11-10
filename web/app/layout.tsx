import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://leadscan.net";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "LeadScan B2B – Scan cơ hội kinh doanh cho doanh nghiệp bằng AI",
  description:
    "LeadScanB2B.com: chọn tiêu chí cơ hội bạn muốn tìm, AI quét hơn 10 nhóm nguồn dữ liệu, làm giàu và chấm điểm từng cơ hội kinh doanh. Phiếu cơ hội chỉ từ 29.000đ.",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "vi_VN",
    siteName: "LeadScan B2B",
    url: "/",
    title: "LeadScan B2B – Scan cơ hội kinh doanh cho doanh nghiệp bằng AI",
    description: "Chọn tiêu chí → AI thu thập đa nguồn → Enrich & Scoring → mua phiếu cơ hội từ 29.000đ.",
  },
  twitter: { card: "summary_large_image" },
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
