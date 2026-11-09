import "../admin/admin.css";
import "./member.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: { default: "Thành viên LeadScan", template: "%s · LeadScan B2B" },
  robots: { index: false, follow: false },
};

export default function MemberRootLayout({ children }: { children: ReactNode }) {
  return <div className="adm">{children}</div>;
}
