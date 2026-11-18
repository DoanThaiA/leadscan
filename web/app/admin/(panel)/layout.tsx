"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, Suspense, useEffect, useState } from "react";

import { AdminProvider, useAdmin } from "@/components/admin/AdminContext";
import { SECTIONS_CHANGED } from "@/components/admin/ArticleForm";
import { Icon, initials } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import { Logo } from "@/components/brand/Logo";

// tree: "articles" = mục cha xổ xuống các danh mục bài viết (tải từ API)
type NavItem = { href: string; label: string; icon: string; exact?: boolean; adminOnly?: boolean; enrich?: boolean; tree?: "articles" };
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
    id: "content", label: "Nội dung", items: [
      { href: "/admin/bai-viet", label: "Bài viết", icon: "note", tree: "articles" },
      { href: "/admin/tuyen-dung", label: "Tin tuyển dụng", icon: "brief" },
    ],
  },
  { id: "me", label: "Cá nhân", items: [{ href: "/admin/tai-khoan", label: "Tài khoản của tôi", icon: "key" }] },
];

/** Trang đang mở thuộc mục nào: khớp đường dẫn dài nhất */
function activeHref(path: string, items: NavItem[]): string {
  let best = "";
  for (const n of items) {
    const hit = n.exact ? path === n.href : path === n.href || path.startsWith(n.href + "/");
    if (hit && n.href.length > best.length) best = n.href;
  }
  return best;
}

interface NavSection {
  id: number;
  name: string;
  is_active: boolean;
  total: number;
}

/** Mục "Bài viết": bấm để xổ xuống Tất cả bài viết · từng danh mục (kèm số bài) · Quản lý danh mục */
function ArticlesTree({ item, active }: { item: NavItem; active: boolean }) {
  const path = usePathname();
  const params = useSearchParams();
  const [sections, setSections] = useState<NavSection[] | null>(null);
  const [open, setOpen] = useState(active);

  useEffect(() => {
    if (active) setOpen(true);
  }, [active]);

  useEffect(() => {
    const load = () => api.get<{ items: NavSection[] }>("/article-sections").then((r) => setSections(r.items), () => {});
    load();
    window.addEventListener(SECTIONS_CHANGED, load); // thêm / sửa / xoá danh mục hoặc bài → cập nhật menu
    return () => window.removeEventListener(SECTIONS_CHANGED, load);
  }, []);

  // Danh mục đang xem: ?danh_muc= ở danh sách bài và trang viết bài mới
  const listing = path === item.href || path === `${item.href}/moi`;
  const cur = listing ? params.get("danh_muc") ?? "" : null;
  const manage = path === `${item.href}/danh-muc`;

  return (
    <div className="adm-nav-tree">
      <div className={active ? "adm-nav-parent in" : "adm-nav-parent"}>
        <Link href={item.href} onClick={() => setOpen(true)} aria-current={path === item.href && !cur ? "page" : undefined}>
          <Icon name={item.icon} />
          {item.label}
        </Link>
        <button type="button" className="adm-nav-caret" aria-expanded={open} aria-label={open ? "Thu gọn danh mục bài viết" : "Xem danh mục bài viết"} onClick={() => setOpen((o) => !o)}>
          <span className={open ? "chev open" : "chev"} aria-hidden="true">›</span>
        </button>
      </div>
      {open ? (
        <div className="adm-nav-sub">
          <Link href={item.href} className={cur === "" ? "on" : undefined} aria-current={cur === "" ? "page" : undefined}>Tất cả bài viết</Link>
          {sections === null ? <span className="adm-nav-note">Đang tải…</span> : null}
          {(sections ?? []).map((s) => {
            const on = cur === String(s.id);
            return (
              <Link key={s.id} href={`${item.href}?danh_muc=${s.id}`} className={on ? "on" : undefined} aria-current={on ? "page" : undefined} title={s.is_active ? undefined : "Danh mục đang ẩn trên trang web"}>
                <span className={s.is_active ? undefined : "off"}>{s.name}</span>
                <small>{s.total}</small>
              </Link>
            );
          })}
          <Link href={`${item.href}/danh-muc`} className={manage ? "on manage" : "manage"} aria-current={manage ? "page" : undefined}>
            <Icon name="edit" size={13} /> Quản lý danh mục
          </Link>
        </div>
      ) : null}
    </div>
  );
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
                    if (n.tree === "articles") {
                      // useSearchParams cần Suspense; trong lúc chờ hiện link thường
                      const plain = <Link href={n.href} className={on ? "on" : undefined}><Icon name={n.icon} />{n.label}</Link>;
                      return <Suspense key={n.href} fallback={plain}><ArticlesTree item={n} active={on} /></Suspense>;
                    }
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
