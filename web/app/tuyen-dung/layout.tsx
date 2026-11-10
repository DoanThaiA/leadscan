import "../landing.css";
import "./careers.css";

import type { ReactNode } from "react";

import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import IconSprite from "@/components/landing/IconSprite";

export default function CareersLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <IconSprite />
      <Header base="/" extra={[{ href: "/tuyen-dung", label: "Tuyển dụng", active: true }]} />
      <main id="main">{children}</main>
      <Footer base="/" />
    </>
  );
}
