import "../landing.css";
import "../cam-nang/cam-nang.css";

import type { ReactNode } from "react";

import Footer from "@/components/landing/Footer";
import Header from "@/components/landing/Header";
import IconSprite from "@/components/landing/IconSprite";

/** Bài viết theo danh mục (Tuyển dụng, Tin tức… do biên tập viên tạo). Danh mục Cẩm nang giữ trang riêng /cam-nang. */
export default function PostsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <IconSprite />
      <Header base="/" extra={[{ href: "/bai-viet", label: "Bài viết", active: true }]} />
      <main id="main">{children}</main>
      <Footer base="/" />
    </>
  );
}
