"use client";

import { useEffect } from "react";

import { usePartner } from "@/components/partner/PartnerContext";
import { PartnerTerms } from "@/components/partner/PartnerTerms";
import { faq } from "@/lib/partner/content";

export default function PartnerPolicyPage() {
  const { reward } = usePartner();
  useEffect(() => {
    document.title = "Chính sách & hướng dẫn · Đối tác LeadScan";
  }, []);

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Chính sách & hướng dẫn</h1>
          <p>Cơ hội thế nào được nhận, cách tính thưởng, rút tiền và hỏi đáp</p>
        </div>
      </div>
      <div className="adm-grid side">
        <section className="adm-card">
          <div className="hd"><h2>Điều khoản đối tác</h2></div>
          <PartnerTerms reward={reward} />
        </section>
        <section className="adm-card">
          <div className="hd"><h2>Hỏi đáp</h2></div>
          <div className="ptn-doc">
            {faq(reward).map((f, i) => (
              <details key={f.q} open={i === 0}>
                <summary>{f.q}</summary>
                <p>{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
