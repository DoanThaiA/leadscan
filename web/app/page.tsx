import "./landing.css";

import Cta from "@/components/landing/Cta";
import Faq from "@/components/landing/Faq";
import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import Hero from "@/components/landing/Hero";
import HowItWorks from "@/components/landing/HowItWorks";
import IconSprite from "@/components/landing/IconSprite";
import Join from "@/components/landing/Join";
import LandingEffects from "@/components/landing/LandingEffects";
import MobileCta from "@/components/landing/MobileCta";
import PromoPopup from "@/components/landing/PromoPopup";
import Register from "@/components/landing/Register";
import { getReward } from "@/lib/partner/reward-server";

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", name: "LeadScan B2B", url: "https://leadscan.net/", email: "contact@leadscan.net", telephone: "+84877770788" },
    {
      "@type": "Service",
      name: "Sàn kết nối cơ hội kinh doanh B2B",
      description: "Người mua đăng nhu cầu, đối tác đăng cơ hội; LeadScan kiểm duyệt, chấm điểm và kết nối hai bên.",
      provider: { "@type": "Organization", name: "LeadScan B2B" },
      areaServed: "VN",
      offers: [
        { "@type": "Offer", name: "Thành viên LeadScan (1 năm)", price: "89000", priceCurrency: "VND" },
        {
          "@type": "Offer",
          name: "Phiếu cơ hội",
          priceSpecification: { "@type": "PriceSpecification", minPrice: "29000", maxPrice: "100000000", priceCurrency: "VND" },
        },
      ],
    },
  ],
};

export default async function LandingPage() {
  const reward = await getReward();
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <IconSprite />
      <Header />
      <main id="main">
        <Hero />
        <HowItWorks />
        <Join reward={reward} />
        <Register />
        <Faq reward={reward} />
        <Cta />
      </main>
      <Footer />
      <MobileCta />
      <LandingEffects />
      <PromoPopup />
    </>
  );
}
