import type { NextConfig } from "next";

// Khi chạy dev (hoặc không có Nginx phía trước), Next.js chuyển tiếp /api/* sang backend FastAPI.
// Trên VPS, Nginx định tuyến /api thẳng tới backend nên không đi qua đây.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async redirects() {
    // "Kho doanh nghiệp" đã gộp vào phân hệ làm giàu theo MST
    // Trang quản trị cẩm nang đã thành "Bài viết" theo danh mục
    return [
      { source: "/admin/kho-doanh-nghiep/:path*", destination: "/admin/lam-giau", permanent: false },
      { source: "/admin/cam-nang", destination: "/admin/bai-viet", permanent: false },
      { source: "/admin/cam-nang/:path*", destination: "/admin/bai-viet/:path*", permanent: false },
    ];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_INTERNAL_URL}/api/:path*` }];
  },
};

export default nextConfig;
