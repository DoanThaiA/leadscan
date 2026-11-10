import "../landing.css";
import "./about.css";

import type { ReactNode } from "react";

import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import IconSprite from "@/components/landing/IconSprite";

export default function AboutLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <IconSprite />
      <Header base="/" extra={[{ href: "/gioi-thieu", label: "Giới thiệu", active: true }]} />
      <main id="main">{children}</main>
      <Footer base="/" />
    </>
  );
}
