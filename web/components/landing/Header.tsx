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

/**
 * base: tiền tố cho link neo khi dùng ngoài trang chủ (vd "/" trên /tuyen-dung → "/#bang-gia").
 * extra: link thêm vào menu (vd mục "Tuyển dụng" đang xem).
 */
type NavLink = { href: string; label: string; active?: boolean };

/** Trang riêng luôn có trên menu (không phải link neo trong trang chủ). */
const PAGES: NavLink[] = [{ href: "/gioi-thieu", label: "Giới thiệu" }, { href: "/co-hoi", label: "Cơ hội" }];

export default function Header({ base = "", extra = [] }: { base?: string; extra?: NavLink[] }) {
  const links: NavLink[] = [...PAGES, ...LINKS.map(([href, label]) => ({ href: base + href, label }))];
  for (const e of extra) {
    const i = links.findIndex((l) => l.href === e.href); // trùng link sẵn có → thay tại chỗ (vd đánh dấu đang xem)
    if (i >= 0) links[i] = e;
    else links.push(e);
  }
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
        <a href={`${base}#bang-gia`}>
          Bắt đầu ngay chỉ với <b>1 ly trà sữa full topping</b>{" "}
          <svg className="icon" style={{ width: 14, height: 14 }}><use href="#i-arrow" /></svg>
        </a>
      </div>

      <header id="top" className={scrolled ? "scrolled" : undefined}>
        <div className="container nav">
          <a href={base || "#top"} className="logo" aria-label={base ? "LeadScan – trang chủ" : "LeadScan – về đầu trang"}>
            <Logo height={26} />
          </a>
          <nav className="nav-links" aria-label="Điều hướng chính">
            {links.map((l) => (
              <a key={l.href} href={l.href} className={l.active ? "on" : undefined} aria-current={l.active ? "page" : undefined}>{l.label}</a>
            ))}
          </nav>
          <div className="nav-actions">
            <a href="/thanh-vien/dang-nhap" className="login">Đăng nhập</a>
            <a href={`${base}#dang-ky`} className="btn btn-primary btn-sm">Đăng ký thành viên</a>
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
          {links.map((l) => (
            <a key={l.href} href={l.href} onClick={close}>{l.label}</a>
          ))}
          <a href="/thanh-vien/dang-nhap" onClick={close}>Đăng nhập</a>
          <a href={`${base}#dang-ky`} className="btn btn-primary" onClick={close}>Đăng ký thành viên</a>
        </div>
      </header>
    </>
  );
}
