import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/seo";

// Trang công khai cho Google đọc; khu quản trị, cổng thành viên và API thì không.
// Cổng đối tác (/doi-tac/tong-quan…) vẫn để Google vào đọc thẻ noindex — không chặn ở đây vì /doi-tac là trang công khai.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/admin", "/thanh-vien", "/api/"] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
