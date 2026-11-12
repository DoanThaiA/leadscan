import type { Metadata } from "next";

import { Logo } from "@/components/brand/Logo";
import { PartnerTerms } from "@/components/partner/PartnerTerms";
import { getReward } from "@/lib/partner/reward-server";

export const metadata: Metadata = { title: "Điều khoản đối tác & Chính sách bảo mật" };

export default async function PartnerTermsPage() {
  const reward = await getReward();
  return (
    <div className="ptn-public">
      <div className="inner">
        <div className="top">
          <a href="/doi-tac" aria-label="Đối tác LeadScan"><Logo height={26} /></a>
          <span className="ptn-label">Cổng Đối tác</span>
        </div>
        <section className="adm-card">
          <div className="hd"><h1 style={{ fontSize: 20 }}>Điều khoản đối tác & Chính sách bảo mật</h1></div>
          <PartnerTerms reward={reward} />
        </section>
        <p className="muted" style={{ textAlign: "center", fontSize: 13 }}>
          <a href="/doi-tac" style={{ color: "var(--brand-600)", fontWeight: 600 }}>← Về trang Đối tác LeadScan</a>
        </p>
      </div>
    </div>
  );
}
