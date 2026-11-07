"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/brand/Logo";

const LINKS = [
  ["#doi-tuong", "Giải pháp"],
  ["#quy-trinh", "Quy trình"],
  ["#phieu-co-hoi", "Phiếu cơ hội"],
  ["#bang-gia", "Bảng giá"],
  ["#faq", "Hỏi đáp"],
] as const;

export default function Header() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const close = () => setOpen(false);

  return (
    <>
      <a href="#main" className="skip">Bỏ qua tới nội dung chính</a>
      <div className="announce">
        <a href="#bang-gia">
          Phí thành viên <b>10.000.000đ/năm</b> được trừ dần khi mua phiếu cơ hội · Phiếu chỉ từ <b>29.000đ</b>{" "}
          <svg className="icon" style={{ width: 14, height: 14 }}><use href="#i-arrow" /></svg>
        </a>
      </div>

      <header id="top" className={scrolled ? "scrolled" : undefined}>
        <div className="container nav">
          <a href="#top" className="logo" aria-label="LeadScan – về đầu trang">
            <Logo height={26} />
          </a>
          <nav className="nav-links" aria-label="Điều hướng chính">
            {LINKS.map(([href, label]) => (
              <a key={href} href={href}>{label}</a>
            ))}
          </nav>
          <div className="nav-actions">
            <a href="/thanh-vien/dang-nhap" className="login">Đăng nhập</a>
            <a href="#dang-ky" className="btn btn-primary btn-sm">Đăng ký thành viên</a>
          </div>
          <button
            className="burger"
            id="burger"
            aria-label={open ? "Đóng menu" : "Mở menu"}
            aria-expanded={open}
            aria-controls="mobileMenu"
            onClick={() => setOpen((o) => !o)}
          >
            <svg className="icon" style={{ width: 26, height: 26 }}><use href="#i-menu" /></svg>
          </button>
        </div>
        <div className={open ? "mobile-menu open" : "mobile-menu"} id="mobileMenu">
          {LINKS.map(([href, label]) => (
            <a key={href} href={href} onClick={close}>{label}</a>
          ))}
          <a href="/thanh-vien/dang-nhap" onClick={close}>Đăng nhập</a>
          <a href="#dang-ky" className="btn btn-primary" onClick={close}>Đăng ký thành viên</a>
        </div>
      </header>
    </>
  );
}
