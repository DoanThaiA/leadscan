import "../landing.css";
import "./cam-nang.css";

import type { ReactNode } from "react";

import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import IconSprite from "@/components/landing/IconSprite";

/** Cẩm nang (blog SEO): bài hướng dẫn tìm khách hàng B2B, chương trình đối tác, kiến thức ngành. */
export default function BlogLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <IconSprite />
      <Header base="/" extra={[{ href: "/cam-nang", label: "Cẩm nang", active: true }]} />
      <main id="main">{children}</main>
      <Footer base="/" />
    </>
  );
}
