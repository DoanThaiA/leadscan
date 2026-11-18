"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { AdminProvider, useAdmin } from "@/components/admin/AdminContext";
import { Icon, initials } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import { Logo } from "@/components/brand/Logo";

type NavItem = { href: string; label: string; icon: string; exact?: boolean; adminOnly?: boolean; enrich?: boolean };
type NavGroup = { id: string; label: string; items: NavItem[] };

// Menu chia theo nhóm nghiệp vụ. Nhóm không có label (Tổng quan) luôn hiện, không thu gọn.
const NAV: NavGroup[] = [
  { id: "home", label: "", items: [{ href: "/admin", label: "Tổng quan", icon: "home", exact: true }] },
  {
    id: "users", label: "Người dùng", items: [
      { href: "/admin/khach-hang", label: "Khách hàng", icon: "building" },
      { href: "/admin/doi-tac", label: "Đối tác", icon: "users" },
      { href: "/admin/nhan-vien", label: "Nhân viên", icon: "user", adminOnly: true },
    ],
  },
  {
    id: "opps", label: "Cơ hội", items: [
      { href: "/admin/co-hoi", label: "Cơ hội & phiếu", icon: "grid" },
      { href: "/admin/yeu-cau-tim-co-hoi", label: "Yêu cầu tìm cơ hội", icon: "search" },
      { href: "/admin/xac-minh-doi-tac", label: "Xác minh cơ hội đối tác", icon: "flag" },
      { href: "/admin/enrich", label: "Yêu cầu enrich", icon: "spark" },
      { href: "/admin/lam-giau", label: "Làm giàu theo MST", icon: "layers", enrich: true },
    ],
  },
  {
    id: "money", label: "Tài chính", items: [
      { href: "/admin/thanh-toan", label: "Thanh toán", icon: "card" },
      { href: "/admin/hoa-don", label: "Hoá đơn", icon: "receipt" },
      { href: "/admin/khuyen-mai", label: "Khuyến mãi", icon: "tag" },
      { href: "/admin/rut-tien-doi-tac", label: "Rút tiền đối tác", icon: "wallet" },
    ],
  },
  {
    id: "content", label: "Biên tập nội dung", items: [
      { href: "/admin/bai-viet", label: "Bài viết", icon: "note", exact: true },
      { href: "/admin/bai-viet/danh-muc", label: "Danh mục bài viết", icon: "bookmark" },
      { href: "/admin/tuyen-dung", label: "Tin tuyển dụng", icon: "brief" },
    ],
  },
  { id: "me", label: "Cá nhân", items: [{ href: "/admin/tai-khoan", label: "Tài khoản của tôi", icon: "key" }] },
];

/** Trang đang mở thuộc mục nào: khớp đường dẫn dài nhất (để /admin/bai-viet/danh-muc không sáng cả "Bài viết") */
function activeHref(path: string, items: NavItem[]): string {
  let best = "";
  for (const n of items) {
    const hit = n.exact ? path === n.href : path === n.href || path.startsWith(n.href + "/");
    if (hit && n.href.length > best.length) best = n.href;
  }
  // "Bài viết" đánh dấu exact để không nuốt trang danh mục, nhưng trang soạn / sửa bài vẫn thuộc "Bài viết"
  if (!best && path.startsWith("/admin/bai-viet/")) best = "/admin/bai-viet";
  return best;
}

const COLLAPSE_KEY = "ls_adm_nav_closed";

function Shell({ children }: { children: ReactNode }) {
  const { user, meta } = useAdmin();
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [path]);

  // Nhóm người dùng đã thu gọn — nhớ trên trình duyệt này
  const [closed, setClosed] = useState<string[]>([]);
  useEffect(() => {
    try {
      setClosed(JSON.parse(localStorage.getItem(COLLAPSE_KEY) || "[]"));
    } catch {
      /* trình duyệt chặn bộ nhớ → mở hết */
    }
  }, []);
  function toggle(id: string) {
    setClosed((c) => {
      const next = c.includes(id) ? c.filter((x) => x !== id) : [...c, id];
      try {
        localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next));
      } catch {
        /* bỏ qua */
      }
      return next;
    });
  }

  const groups = NAV
    .map((g) => ({ ...g, items: g.items.filter((n) => (!n.adminOnly || user.role === "admin") && (!n.enrich || user.enrich_access)) }))
    .filter((g) => g.items.length);
  const active = activeHref(path, groups.flatMap((g) => g.items));

  async function logout() {
    await api.post("/auth/logout").catch(() => {});
    router.replace("/admin/login");
  }

  return (
    <div className="adm-shell">
      <div className="adm-mtop">
        <button className="adm-btn ghost sm" aria-label="Mở menu" onClick={() => setOpen(true)}>
          <Icon name="menu" />
        </button>
        <Link href="/admin" aria-label="LeadScan Admin"><Logo variant="mark" height={26} /></Link>
        <span style={{ width: 30 }} />
      </div>
      {open ? <div className="adm-scrim" onClick={() => setOpen(false)} /> : null}

      <aside className={open ? "adm-side open" : "adm-side"}>
        <Link href="/admin" className="adm-logo">
          <Logo height={24} /><small>Admin</small>
        </Link>
        <nav className="adm-nav grouped" aria-label="Quản trị">
          {groups.map((g) => {
            const hasActive = g.items.some((n) => n.href === active);
            const isOpen = !g.label || hasActive || !closed.includes(g.id);
            return (
              <div key={g.id} className="adm-nav-group">
                {g.label ? (
                  <button
                    type="button"
                    className="adm-nav-hd"
                    aria-expanded={isOpen}
                    onClick={() => toggle(g.id)}
                    disabled={hasActive}
                    title={hasActive ? undefined : isOpen ? "Thu gọn" : "Mở rộng"}
                  >
                    {g.label}
                    {hasActive ? null : <span className={isOpen ? "chev open" : "chev"} aria-hidden="true">›</span>}
                  </button>
                ) : null}
                {isOpen
                  ? g.items.map((n) => {
                    const on = n.href === active;
                    return (
                      <Link key={n.href} href={n.href} className={on ? "on" : undefined} aria-current={on ? "page" : undefined}>
                        <Icon name={n.icon} />
                        {n.label}
                      </Link>
                    );
                  })
                  : null}
              </div>
            );
          })}
        </nav>
        <div className="adm-side-foot">
          <div className="adm-me">
            <span className="adm-avatar">{initials(user.full_name)}</span>
            <div>
              <b>{user.full_name}</b>
              <span>{meta.roles[user.role]}</span>
            </div>
          </div>
          <a className="adm-btn sm" href="/" target="_blank" rel="noopener">
            <Icon name="external" size={14} /> Xem landing page
          </a>
          <button className="adm-btn sm ghost" onClick={logout}>
            <Icon name="logout" size={14} /> Đăng xuất
          </button>
        </div>
      </aside>

      <main className="adm-main">{children}</main>
    </div>
  );
}

export default function PanelLayout({ children }: { children: ReactNode }) {
  return (
    <AdminProvider fallback={<div className="adm-empty" style={{ paddingTop: 120 }}>Đang tải…</div>}>
      <Shell>{children}</Shell>
    </AdminProvider>
  );
}
