/**
 * Các trang chạy chung hệ thống sự kiện (đồng bộ với backend/app/sites.py).
 *   leadscan → leadscan.net (trang chính)
 *   c89      → c89.leadscan.net — cổng sự kiện CLB CEO 1989
 *   epc      → epc.leadscan.net — cổng sự kiện EPC
 * Cổng chỉ có trang sự kiện + admin đăng sự kiện. Màu lấy từ logo của từng đơn vị.
 */

export type SiteKey = "leadscan" | "c89" | "epc";
export const PORTALS: SiteKey[] = ["c89", "epc"];
export const SITE_HEADER = "x-leadscan-site";

export interface SiteBrand {
  key: SiteKey;
  name: string; // tên đầy đủ
  short: string; // nhãn ngắn trong bảng admin
  url: string;
  tagline: string;
  logo: string; // logo đầy đủ (biểu tượng + chữ)
  mark: string; // chỉ biểu tượng (favicon, đầu trang admin)
  /** Màu chính (chữ, liên kết) và màu nhấn (nút chính) — ghi đè biến màu của landing.css */
  primary: string;
  primaryDark: string;
  primary100: string;
  primary50: string;
  accent: string;
  accentDark: string;
  accent100: string;
  accent50: string;
  onAccent: string; // màu chữ trên nút chính
}

export const SITES: Record<SiteKey, SiteBrand> = {
  leadscan: {
    key: "leadscan",
    name: "LeadScan",
    short: "LeadScan",
    url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://leadscan.net",
    tagline: "Sàn kết nối cơ hội kinh doanh B2B",
    logo: "/brand/leadscan-logo-1200.png",
    mark: "/icon1.png",
    primary: "#004B87",
    primaryDark: "#00355F",
    primary100: "#DCE8F4",
    primary50: "#EEF4FA",
    accent: "#FFCD00",
    accentDark: "#E6B800",
    accent100: "#FFF0B3",
    accent50: "#FFF8DB",
    onAccent: "#004B87",
  },
  c89: {
    key: "c89",
    name: "CLB CEO 1989",
    short: "CEO 1989",
    url: process.env.NEXT_PUBLIC_C89_URL ?? "https://c89.leadscan.net",
    tagline: "Kết nối – Chia sẻ – Cùng phát triển",
    logo: "/sites/c89/logo.png",
    mark: "/sites/c89/mark.png",
    // xanh navy của chữ "1989" + xanh lá của biểu tượng
    primary: "#233A7B",
    primaryDark: "#182A5C",
    primary100: "#DDE3F1",
    primary50: "#EFF2F9",
    accent: "#12A14A",
    accentDark: "#0E873D",
    accent100: "#CDEFD9",
    accent50: "#EAF8EF",
    onAccent: "#FFFFFF",
  },
  epc: {
    key: "epc",
    name: "EPC",
    short: "EPC",
    url: process.env.NEXT_PUBLIC_EPC_URL ?? "https://epc.leadscan.net",
    tagline: "Go Far Together",
    logo: "/sites/epc/logo.png",
    mark: "/sites/epc/mark.png",
    // xanh navy + cam của logo EPC
    primary: "#1A4079",
    primaryDark: "#112D57",
    primary100: "#DCE4F0",
    primary50: "#EEF2F8",
    accent: "#E8600F",
    accentDark: "#C9520C",
    accent100: "#FDE0CC",
    accent50: "#FEF1E8",
    onAccent: "#FFFFFF",
  },
};

export const isSiteKey = (v: unknown): v is SiteKey => typeof v === "string" && v in SITES;

export const siteOf = (v: string | null | undefined): SiteBrand => SITES[isSiteKey(v) ? v : "leadscan"];

/** Biến CSS ghi đè bảng màu LeadScan (landing.css, admin.css) bằng màu của trang */
export function themeVars(s: SiteBrand): Record<string, string> {
  return {
    "--blue": s.primary,
    "--blue-800": s.primaryDark,
    "--blue-100": s.primary100,
    "--blue-50": s.primary50,
    "--yellow": s.accent,
    "--yellow-600": s.accentDark,
    "--yellow-100": s.accent100,
    "--yellow-50": s.accent50,
    "--on-accent": s.onAccent,
    // bảng màu trang quản trị (admin.css)
    "--brand": s.primary,
    "--brand-600": s.primary,
    "--brand-100": s.primary100,
    "--brand-50": s.primary50,
    "--brand-hover": s.primaryDark,
    "--brand-800": s.primaryDark,
    "--accent": s.accent,
    "--accent-600": s.accentDark,
    "--accent-100": s.accent100,
    "--accent-50": s.accent50,
  };
}
