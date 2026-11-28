import "../landing.css";
import "../tuyen-dung/careers.css";
import "./events.css";

import type { ReactNode } from "react";

import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import IconSprite from "@/components/landing/IconSprite";

export default function EventsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <IconSprite />
      <Header base="/" extra={[{ href: "/su-kien", label: "Sự kiện", active: true }]} />
      <main id="main">{children}</main>
      <Footer base="/" />
    </>
  );
}
