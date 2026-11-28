"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { AdminProvider, useAdmin } from "@/components/admin/AdminContext";
import { Icon, initials } from "@/components/admin/ui";
import { useSite } from "@/components/sites/SiteContext";
import { api } from "@/lib/admin/api";

// Cổng chỉ quản lý sự kiện: 3 mục, không có khách hàng / thanh toán / bài viết của LeadScan
const NAV = [
  { href: "/admin/su-kien", label: "Sự kiện", icon: "ticket" },
  { href: "/admin/su-kien/dang-ky", label: "Đăng ký sự kiện", icon: "users" },
  { href: "/admin/tai-khoan", label: "Tài khoản của tôi", icon: "key" },
];

function active(path: string): string {
  if (path.startsWith("/admin/su-kien/dang-ky")) return "/admin/su-kien/dang-ky";
  if (path.startsWith("/admin/su-kien")) return "/admin/su-kien";
  if (path.startsWith("/admin/tai-khoan")) return "/admin/tai-khoan";
  return "";
}

function Shell({ children }: { children: ReactNode }) {
  const site = useSite();
  const { user, meta } = useAdmin();
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const on = active(path);

  useEffect(() => setOpen(false), [path]);

  async function logout() {
    await api.post("/auth/logout").catch(() => {});
    router.replace("/admin/login");
  }

  const logo = (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={site.mark} alt="" aria-hidden="true" style={{ height: 30, width: "auto" }} />
      <span style={{ display: "grid", lineHeight: 1.15 }}>
        <b style={{ fontSize: 14, color: "var(--ink)" }}>{site.name}</b>
        <small style={{ margin: 0, width: "fit-content" }}>Quản trị sự kiện</small>
      </span>
    </>
  );

  return (
    <div className="adm-shell">
      <div className="adm-mtop">
        <button className="adm-btn ghost sm" aria-label="Mở menu" onClick={() => setOpen(true)}>
          <Icon name="menu" />
        </button>
        <Link href="/admin/su-kien" aria-label={`Quản trị ${site.name}`} style={{ display: "flex", gap: 8, alignItems: "center" }}>{logo}</Link>
        <span style={{ width: 30 }} />
      </div>
      {open ? <div className="adm-scrim" onClick={() => setOpen(false)} /> : null}

      <aside className={open ? "adm-side open" : "adm-side"}>
        <Link href="/admin/su-kien" className="adm-logo" style={{ gap: 10 }}>{logo}</Link>
        <nav className="adm-nav" aria-label="Quản trị sự kiện">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={on === n.href ? "on" : undefined} aria-current={on === n.href ? "page" : undefined}>
              <Icon name={n.icon} />
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="adm-side-foot">
          <div className="adm-me">
            <span className="adm-avatar">{initials(user.full_name)}</span>
            <div>
              <b>{user.full_name}</b>
              <span>{user.site ? meta.roles[user.role] : "Quản trị viên LeadScan"}</span>
            </div>
          </div>
          <a className="adm-btn sm" href="/" target="_blank" rel="noopener">
            <Icon name="external" size={14} /> Xem trang sự kiện
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

export default function PortalPanelLayout({ children }: { children: ReactNode }) {
  return (
    <AdminProvider fallback={<div className="adm-empty" style={{ paddingTop: 120 }}>Đang tải…</div>}>
      <Shell>{children}</Shell>
    </AdminProvider>
  );
}
