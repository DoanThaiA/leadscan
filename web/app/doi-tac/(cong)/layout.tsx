import "../../admin/admin.css";
import "./partner.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: { default: "Cổng Đối tác LeadScan", template: "%s · Đối tác LeadScan" },
  robots: { index: false, follow: false },
};

/** Cổng đối tác: dùng chung bộ giao diện quản trị nhưng nhấn VÀNG (class ptn) để không nhầm với cổng thành viên. */
export default function PartnerAreaLayout({ children }: { children: ReactNode }) {
  return <div className="adm ptn">{children}</div>;
}
