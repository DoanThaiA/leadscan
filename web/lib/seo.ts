/** Hằng số & dữ liệu có cấu trúc (schema.org) dùng chung cho SEO. */

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://leadscan.net").replace(/\/$/, "");
export const SITE_NAME = "LeadScan";

const ORG_ID = `${SITE_URL}/#organization`;
const SITE_ID = `${SITE_URL}/#website`;

/** Tổ chức + website: giúp Google hiện đúng tên trang "LeadScan" và logo trong kết quả tìm kiếm. */
export const organizationLd = {
  "@type": "Organization",
  "@id": ORG_ID,
  name: "LeadScan B2B",
  alternateName: ["LeadScan", "LeadScan.net"],
  url: `${SITE_URL}/`,
  logo: { "@type": "ImageObject", url: `${SITE_URL}/brand/leadscan-logo-1200.png` },
  email: "contact@leadscan.net",
  telephone: "+84877770788",
  address: { "@type": "PostalAddress", streetAddress: "169 Nguyễn Ngọc Vũ", addressLocality: "Phường Yên Hòa", addressRegion: "Hà Nội", addressCountry: "VN" },
  contactPoint: [{ "@type": "ContactPoint", contactType: "customer support", telephone: "+84877770788", email: "contact@leadscan.net", areaServed: "VN", availableLanguage: ["vi"] }],
  parentOrganization: { "@type": "Organization", name: "MCV Network", url: "https://mcv.network/" },
};

export const websiteLd = {
  "@type": "WebSite",
  "@id": SITE_ID,
  name: SITE_NAME,
  alternateName: ["LeadScan B2B", "LeadScan.net"],
  url: `${SITE_URL}/`,
  inLanguage: "vi-VN",
  publisher: { "@id": ORG_ID },
};

export const orgRef = { "@id": ORG_ID };

/** Đường dẫn breadcrumb: [["Trang chủ", "/"], ["Cơ hội", "/co-hoi"], …] */
export function breadcrumbLd(items: [string, string][]) {
  return {
    "@type": "BreadcrumbList",
    itemListElement: items.map(([name, path], i) => ({ "@type": "ListItem", position: i + 1, name, item: `${SITE_URL}${path}` })),
  };
}

export function faqLd(items: { q: string; a: string }[]) {
  return {
    "@type": "FAQPage",
    mainEntity: items.map(({ q, a }) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })),
  };
}

/** Chuỗi JSON-LD an toàn để nhúng vào <script> (chặn "</script>" trong dữ liệu). */
export function ldJson(graph: object[]): string {
  return JSON.stringify({ "@context": "https://schema.org", "@graph": graph }).replace(/</g, "\\u003c");
}
