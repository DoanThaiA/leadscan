import type { NextConfig } from "next";

// Khi chạy dev (hoặc không có Nginx phía trước), Next.js chuyển tiếp /api/* sang backend FastAPI.
// Trên VPS, Nginx định tuyến /api thẳng tới backend nên không đi qua đây.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_INTERNAL_URL}/api/:path*` }];
  },
};

export default nextConfig;
