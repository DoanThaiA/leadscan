"use client";

import { useEffect, useRef, useState } from "react";

import { Logo } from "@/components/brand/Logo";
import { DEFAULT_SECTION, sectionHref } from "@/lib/blog";

const LINKS = [
  ["#cach-hoat-dong", "Cách hoạt động"],
  ["#tham-gia", "Người mua & Đối tác"],
] as const;

/**
 * base: tiền tố cho link neo khi dùng ngoài trang chủ (vd "/" trên /tuyen-dung → "/#bang-gia").
 * extra: link thêm vào menu (vd mục "Tuyển dụng" đang xem).
 */
type NavLink = { href: string; label: string; active?: boolean; posts?: boolean };

/** Trang riêng luôn có trên menu (không phải link neo trong trang chủ). posts = xổ xuống các danh mục bài viết. */
const PAGES: NavLink[] = [{ href: "/gioi-thieu", label: "Giới thiệu" }, { href: "/co-hoi", label: "Cơ hội" }, { href: "/bai-viet", label: "Bài viết", posts: true }];

type PostSection = { slug: string; name: string; count: number };
// Hiện ngay khi chưa tải xong danh mục; Cẩm nang luôn có trang riêng
const FALLBACK_SECTIONS: PostSection[] = [{ slug: DEFAULT_SECTION, name: "Cẩm nang", count: 0 }];

export default function Header({ base = "", extra = [] }: { base?: string; extra?: NavLink[] }) {
  const links: NavLink[] = [...PAGES, ...LINKS.map(([href, label]) => ({ href: base + href, label }))];
  for (const e of extra) {
    const i = links.findIndex((l) => l.href === e.href); // trùng link sẵn có → thay tại chỗ (vd đánh dấu đang xem)
    if (i >= 0) links[i] = { ...links[i], ...e };
    else links.push(e);
  }
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [sections, setSections] = useState<PostSection[]>(FALLBACK_SECTIONS);
  const [drop, setDrop] = useState(false); // menu "Bài viết" đang mở (rê chuột / bấm / bàn phím)
  const dropRef = useRef<HTMLDivElement>(null);
  const hovering = useRef(false); // chuột đang ở trên menu → bấm mũi tên không đóng menu vừa mở do rê chuột

  // Danh mục bài viết đang bật: chỉ hiện danh mục đã có bài (Cẩm nang luôn hiện)
  useEffect(() => {
    fetch("/api/articles/sections")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { items: PostSection[] } | null) => {
        if (d?.items) setSections(d.items.filter((x) => x.count > 0 || x.slug === DEFAULT_SECTION));
      })
      .catch(() => {});
  }, []);

  // Bấm ra ngoài → đóng menu xổ
  useEffect(() => {
    if (!drop) return;
    const onDown = (e: PointerEvent) => {
      if (!dropRef.current?.contains(e.target as Node)) setDrop(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [drop]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        setDrop(false);
      }
    };
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
        <a href="/doi-tac">
          Biết cơ hội B2B? Đăng lên sàn, <b>nhận ít nhất 1 ly cafe</b>{" "}
          <svg className="icon" style={{ width: 14, height: 14 }}><use href="#i-arrow" /></svg>
        </a>
      </div>

      <header id="top" className={scrolled ? "scrolled" : undefined}>
        <div className="container nav">
          <a href={base || "#top"} className="logo" aria-label={base ? "LeadScan – trang chủ" : "LeadScan – về đầu trang"}>
            <Logo height={26} />
          </a>
          <nav className="nav-links" aria-label="Điều hướng chính">
            {links.map((l) =>
              l.posts ? (
                <div
                  key={l.href}
                  ref={dropRef}
                  className={drop ? "nav-drop open" : "nav-drop"}
                  onPointerEnter={(e) => {
                    if (e.pointerType !== "mouse") return; // cảm ứng: chỉ mở khi bấm mũi tên
                    hovering.current = true;
                    setDrop(true);
                  }}
                  onPointerLeave={(e) => {
                    if (e.pointerType !== "mouse") return;
                    hovering.current = false;
                    setDrop(false);
                  }}
                >
                  <a href={l.href} className={l.active ? "on" : undefined} aria-current={l.active ? "page" : undefined}>{l.label}</a>
                  <button type="button" className="nav-drop-btn" aria-expanded={drop} aria-controls="navPosts" aria-label="Danh mục bài viết" onClick={() => setDrop((d) => hovering.current || !d)}>
                    <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  </button>
                  <div className="nav-drop-menu" id="navPosts" role="menu" aria-label="Danh mục bài viết">
                    {sections.map((x) => (
                      <a key={x.slug} role="menuitem" href={sectionHref(x.slug)} onClick={() => setDrop(false)}>
                        {x.name}
                        {x.count ? <span>{x.count}</span> : null}
                      </a>
                    ))}
                    <a role="menuitem" href={l.href} className="all" onClick={() => setDrop(false)}>Tất cả bài viết →</a>
                  </div>
                </div>
              ) : (
                <a key={l.href} href={l.href} className={l.active ? "on" : undefined} aria-current={l.active ? "page" : undefined}>{l.label}</a>
              ),
            )}
          </nav>
          <div className="nav-actions">
            <a href="/thanh-vien/dang-nhap" className="login">Đăng nhập</a>
            <a href="/doi-tac#dang-ky" className="btn btn-outline btn-sm">Đăng ký đối tác</a>
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
            <div key={l.href}>
              <a href={l.href} onClick={close}>{l.label}</a>
              {l.posts ? (
                <div className="mobile-sub">
                  {sections.map((x) => <a key={x.slug} href={sectionHref(x.slug)} onClick={close}>{x.name}</a>)}
                </div>
              ) : null}
            </div>
          ))}
          <a href="/thanh-vien/dang-nhap" onClick={close}>Đăng nhập</a>
          <a href={`${base}#dang-ky`} className="btn btn-primary" onClick={close}>Đăng ký thành viên</a>
          <a href="/doi-tac#dang-ky" className="btn btn-outline" onClick={close}>Đăng ký đối tác</a>
        </div>
      </header>
    </>
  );
}
