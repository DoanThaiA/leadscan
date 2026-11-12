"use client";

import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/Logo";

const LINKS = [
  ["#ban-la-ai", "Bạn là ai?"],
  ["#cach-hoat-dong", "Cách hoạt động"],
  ["#quyen-loi", "Quyền lợi"],
  ["#co-hoi-duoc-nhan", "Cơ hội được nhận"],
  ["#hoi-dap", "Hỏi đáp"],
] as const;

/** Header trang /doi-tac: nút đăng nhập dẫn tới CỔNG ĐỐI TÁC (không phải cổng thành viên). */
export default function PartnerHeader() {
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
      <div className="announce ptl-announce">
        <a href="/">Bạn là doanh nghiệp đang tìm khách hàng? <b>Xem LeadScan cho thành viên</b>{" "}
          <svg className="icon" style={{ width: 14, height: 14 }}><use href="#i-arrow" /></svg>
        </a>
      </div>
      <header id="top" className={scrolled ? "scrolled" : undefined}>
        <div className="container nav">
          <a href="#top" className="logo ptl-logo" aria-label="Đối tác LeadScan – về đầu trang">
            <Logo height={26} />
            <span className="ptl-tag">Đối tác</span>
          </a>
          <nav className="nav-links" aria-label="Điều hướng trang đối tác">
            {LINKS.map(([href, label]) => <a key={href} href={href}>{label}</a>)}
          </nav>
          <div className="nav-actions">
            <a href="/doi-tac/dang-nhap" className="login">Đăng nhập đối tác</a>
            <a href="#dang-ky" className="btn btn-primary btn-sm">Đăng ký đối tác</a>
          </div>
          <button className="burger" aria-label={open ? "Đóng menu" : "Mở menu"} aria-expanded={open} aria-controls="ptlMenu" onClick={() => setOpen((o) => !o)}>
            <svg className="icon" style={{ width: 26, height: 26 }}><use href="#i-menu" /></svg>
          </button>
        </div>
        <div className={open ? "mobile-menu open" : "mobile-menu"} id="ptlMenu">
          {LINKS.map(([href, label]) => <a key={href} href={href} onClick={close}>{label}</a>)}
          <a href="/doi-tac/dang-nhap" onClick={close}>Đăng nhập đối tác</a>
          <a href="#dang-ky" className="btn btn-primary" onClick={close}>Đăng ký đối tác</a>
        </div>
      </header>
    </>
  );
}
