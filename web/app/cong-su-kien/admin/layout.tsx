import "../../admin/admin.css";
import "../../admin/attachments.css";
import "../../admin/jobs.css";
import "./portal-admin.css";

import type { Metadata } from "next";
import type { CSSProperties, ReactNode } from "react";

import { currentSite } from "@/lib/site-server";
import { themeVars } from "@/lib/sites";

export async function generateMetadata(): Promise<Metadata> {
  const site = await currentSite();
  return {
    title: { absolute: `Quản trị sự kiện ${site.name}`, template: `%s · Quản trị ${site.name}` },
    robots: { index: false, follow: false },
  };
}

/** Trang quản trị của cổng sự kiện (c89 / epc): chỉ đăng sự kiện và xử lý đăng ký của cổng. */
export default async function PortalAdminLayout({ children }: { children: ReactNode }) {
  const site = await currentSite();
  // admin.css khai báo bảng màu ngay trên .adm → màu cổng phải đặt trực tiếp lên phần tử này mới đè được
  return (
    <div className="adm adm-portal" style={themeVars(site) as CSSProperties}>
      {children}
    </div>
  );
}
