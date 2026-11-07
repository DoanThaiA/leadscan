import type { MetadataRoute } from "next";

// Web app manifest: icon & màu khi "Thêm vào màn hình chính" (Brand Kit v1.0)
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "LeadScan",
    short_name: "LeadScan",
    description: "Scan đúng cơ hội kinh doanh B2B bằng AI",
    start_url: "/",
    display: "standalone",
    background_color: "#FFFFFF",
    theme_color: "#FA5320",
    icons: [
      { src: "/brand/leadscan-app-icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/brand/leadscan-app-icon.svg", sizes: "any", type: "image/svg+xml" },
    ],
  };
}
