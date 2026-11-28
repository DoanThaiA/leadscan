import { type NextRequest, NextResponse } from "next/server";

/**
 * Một bản web chạy cho cả 3 trang: leadscan.net và 2 cổng sự kiện c89.leadscan.net / epc.leadscan.net.
 *
 * Trang của request: biến môi trường SITE của container (docker-compose: web-c89, web-epc) → nếu không có thì
 * theo tên miền (c89.* / epc.*, kể cả c89.localhost khi chạy thử). Proxy luôn GHI ĐÈ header x-leadscan-site
 * (khách tự gửi cũng không có tác dụng) để trang render phía máy chủ và /api khi chạy dev biết đang ở trang nào.
 *
 * Ở cổng sự kiện, mọi đường dẫn được chuyển vào thư mục app/cong-su-kien:
 *   /  và /su-kien      → danh sách sự kiện của cổng
 *   /su-kien/<slug>     → chi tiết + đăng ký
 *   /admin/...          → trang quản trị sự kiện của cổng
 *   đường dẫn khác      → 404 (cổng chỉ để đăng sự kiện)
 * Trên production, Nginx chuyển /api thẳng vào FastAPI (không qua đây) và tự đặt header x-leadscan-site.
 */
const PORTALS = ["c89", "epc"];
const HEADER = "x-leadscan-site";
const PORTAL_DIR = "/cong-su-kien";

function siteOf(req: NextRequest): string {
  const env = (process.env.SITE ?? "").trim().toLowerCase();
  if (PORTALS.includes(env)) return env;
  const host = (req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "").toLowerCase();
  const sub = host.split(":")[0].split(".")[0];
  return PORTALS.includes(sub) ? sub : "leadscan";
}

export function proxy(req: NextRequest) {
  const site = siteOf(req);
  const headers = new Headers(req.headers);
  headers.set(HEADER, site);
  const { pathname } = req.nextUrl;

  if (pathname.startsWith("/api/")) return NextResponse.next({ request: { headers } });

  if (site === "leadscan") {
    // thư mục nội bộ của cổng không mở trên leadscan.net
    if (pathname === PORTAL_DIR || pathname.startsWith(`${PORTAL_DIR}/`)) {
      return NextResponse.rewrite(new URL("/khong-tim-thay", req.url), { request: { headers } });
    }
    return NextResponse.next({ request: { headers } });
  }

  const url = req.nextUrl.clone();
  url.pathname = pathname === "/" || pathname === "/su-kien" ? PORTAL_DIR : PORTAL_DIR + pathname;
  return NextResponse.rewrite(url, { request: { headers } });
}

export const config = {
  // bỏ qua tệp tĩnh (có dấu chấm: ảnh, css, robots.txt…) và tài nguyên build của Next. Slug sự kiện không có dấu chấm.
  matcher: ["/((?!_next/static|_next/image|.*\\..*).*)"],
};
