import "./landing.css";

import Audience from "@/components/landing/Audience";
import Cta from "@/components/landing/Cta";
import Faq from "@/components/landing/Faq";
import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import Hero from "@/components/landing/Hero";
import IconSprite from "@/components/landing/IconSprite";
import LandingEffects from "@/components/landing/LandingEffects";
import MobileCta from "@/components/landing/MobileCta";
import Pricing from "@/components/landing/Pricing";
import Register from "@/components/landing/Register";
import Sources from "@/components/landing/Sources";
import Stats from "@/components/landing/Stats";
import Tickets from "@/components/landing/Tickets";
import Workflow from "@/components/landing/Workflow";

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", name: "LeadScan B2B", url: "https://leadscan.net/", email: "contact@leadscanb2b.com" },
    {
      "@type": "Service",
      name: "Scan cơ hội kinh doanh B2B",
      provider: { "@type": "Organization", name: "LeadScan B2B" },
      areaServed: "VN",
      offers: [
        { "@type": "Offer", name: "Thành viên LeadScan (1 năm)", price: "10000000", priceCurrency: "VND" },
        {
          "@type": "Offer",
          name: "Phiếu cơ hội",
          priceSpecification: { "@type": "PriceSpecification", minPrice: "29000", maxPrice: "100000000", priceCurrency: "VND" },
        },
      ],
    },
  ],
};

export default function LandingPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <IconSprite />
      <Header />
      <main id="main">
        <Hero />
        <Audience />
        <Workflow />
        <Sources />
        <Stats />
        <Tickets />
        <Pricing />
        <Register />
        <Faq />
        <Cta />
      </main>
      <Footer />
      <MobileCta />
      <LandingEffects />
    </>
  );
}
