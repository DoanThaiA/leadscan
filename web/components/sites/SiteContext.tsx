"use client";

import { createContext, type ReactNode, useContext } from "react";

import { type SiteBrand, type SiteKey, SITES } from "@/lib/sites";

const Ctx = createContext<SiteKey>("leadscan");

/** Cho component phía trình duyệt biết đang ở trang nào (layout cổng sự kiện đặt; ngoài cổng mặc định LeadScan). */
export function SiteProvider({ site, children }: { site: SiteKey; children: ReactNode }) {
  return <Ctx.Provider value={site}>{children}</Ctx.Provider>;
}

export function useSite(): SiteBrand {
  return SITES[useContext(Ctx)];
}

/** "Quản trị LeadScan" / "Quản trị CLB CEO 1989" — dùng cho tiêu đề tab của trang quản trị */
export function useAdminBrand(): string {
  return `Quản trị ${useSite().name}`;
}
