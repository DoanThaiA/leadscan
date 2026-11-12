import "../landing.css";
import "./co-hoi.css";

import type { ReactNode } from "react";

import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import IconSprite from "@/components/landing/IconSprite";

/** Cơ hội công khai: ai cũng xem phần xem trước; mua phải đăng ký thành viên. */
export default function PublicOppLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <IconSprite />
      <Header base="/" extra={[{ href: "/co-hoi", label: "Cơ hội", active: true }]} />
      <main id="main">{children}</main>
      <Footer base="/" />
    </>
  );
}
