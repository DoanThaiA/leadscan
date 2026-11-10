"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { AdminProvider, useAdmin } from "@/components/admin/AdminContext";
import { Icon, initials } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import { Logo } from "@/components/brand/Logo";

const NAV = [
  { href: "/admin", label: "Tổng quan", icon: "home", exact: true },
  { href: "/admin/khach-hang", label: "Khách hàng", icon: "building" },
  { href: "/admin/co-hoi", label: "Cơ hội & phiếu", icon: "grid" },
  { href: "/admin/kho-doanh-nghiep", label: "Kho doanh nghiệp (AI)", icon: "scan" },
  { href: "/admin/thanh-toan", label: "Thanh toán", icon: "card" },
  { href: "/admin/hoa-don", label: "Hoá đơn", icon: "receipt" },
  { href: "/admin/yeu-cau-tim-co-hoi", label: "Yêu cầu tìm cơ hội", icon: "search" },
  { href: "/admin/enrich", label: "Yêu cầu enrich", icon: "spark" },
  { href: "/admin/tuyen-dung", label: "Tuyển dụng", icon: "brief" },
  { href: "/admin/nhan-vien", label: "Nhân viên", icon: "users", adminOnly: true },
  { href: "/admin/tai-khoan", label: "Tài khoản của tôi", icon: "key" },
];

function Shell({ children }: { children: ReactNode }) {
  const { user, meta } = useAdmin();
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [path]);

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
        <nav className="adm-nav" aria-label="Quản trị">
          {NAV.filter((n) => !n.adminOnly || user.role === "admin").map((n) => {
            const on = n.exact ? path === n.href : path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className={on ? "on" : undefined} aria-current={on ? "page" : undefined}>
                <Icon name={n.icon} />
                {n.label}
              </Link>
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
