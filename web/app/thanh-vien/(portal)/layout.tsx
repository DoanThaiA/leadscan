"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { Icon, initials } from "@/components/admin/ui";
import { MemberProvider, useMember } from "@/components/member/MemberContext";
import { fmtPts } from "@/lib/commerce";
import { mapi } from "@/lib/member/api";
import { Logo } from "@/components/brand/Logo";

// Giữ khớp với ảnh minh hoạ dashboard ở trang chủ (components/landing/Hero.tsx)
const NAV = [
  { href: "/thanh-vien", label: "Tổng quan", icon: "home", exact: true },
  { href: "/thanh-vien/phu-hop", label: "Cơ hội phù hợp", icon: "scan" },
  { href: "/thanh-vien/kho", label: "Kho của tôi", icon: "bookmark" },
  { href: "/thanh-vien/phieu", label: "Phiếu đã mua", icon: "ticket" },
  { href: "/thanh-vien/co-hoi", label: "Tất cả cơ hội", icon: "grid" },
  { href: "/thanh-vien/vi", label: "Số dư tài khoản", icon: "wallet" },
  { href: "/thanh-vien/tai-khoan", label: "Tài khoản", icon: "user" },
];
const MEMBERSHIP_POINTS = 10_000_000;

function Shell({ children }: { children: ReactNode }) {
  const { me } = useMember();
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);

  async function logout() {
    await mapi.post("/auth/logout").catch(() => {});
    router.replace("/thanh-vien/dang-nhap");
  }

  return (
    <div className="adm-shell">
      <div className="adm-mtop">
        <button className="adm-btn ghost sm" aria-label="Mở menu" onClick={() => setOpen(true)}><Icon name="menu" /></button>
        <Link href="/thanh-vien" aria-label="LeadScan"><Logo variant="mark" height={26} /></Link>
        <Link href="/thanh-vien/vi" className="adm-balance" style={{ padding: "4px 10px", fontSize: 12.5 }}>{fmtPts(me.company.points_balance)}</Link>
      </div>
      {open ? <div className="adm-scrim" onClick={() => setOpen(false)} /> : null}

      <aside className={open ? "adm-side open" : "adm-side"}>
        <Link href="/thanh-vien" className="adm-logo">
          <Logo height={24} />
        </Link>
        <nav className="adm-nav" aria-label="Cổng thành viên">
          {NAV.map((n) => {
            const on = n.exact ? path === n.href : path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className={on ? "on" : undefined} aria-current={on ? "page" : undefined}>
                <Icon name={n.icon} />
                {n.label}
              </Link>
            );
          })}
        </nav>
        <Link href="/thanh-vien/vi" className="mt-credit">
          <small>Số dư thành viên còn lại</small>
          <b>{fmtPts(me.company.points_balance)}</b>
          <span className="bar"><i style={{ width: `${Math.min(100, Math.round((me.company.points_balance / MEMBERSHIP_POINTS) * 100))}%` }} /></span>
          <span style={{ fontSize: 12, color: me.company.membership_active ? "var(--ok)" : "var(--danger)" }}>
            {me.company.membership_active ? "Thành viên đang hiệu lực" : "Chưa kích hoạt thành viên"}
          </span>
        </Link>
        <div className="adm-side-foot">
          <div className="adm-me">
            <span className="adm-avatar">{initials(me.full_name)}</span>
            <div style={{ minWidth: 0 }}>
              <b>{me.full_name}</b>
              <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{me.company.name}</span>
            </div>
          </div>
          <button className="adm-btn sm ghost" onClick={logout}><Icon name="logout" size={14} /> Đăng xuất</button>
        </div>
      </aside>

      <main className="adm-main">
        {!me.company.membership_active && !path.startsWith("/thanh-vien/nap-tien") ? (
          <div className="adm-banner">
            <span>
              <b>Kích hoạt thành viên để mua phiếu cơ hội.</b> Phí 10.000.000đ/năm được cộng đủ 10.000.000 điểm vào ví.
            </span>
            <Link className="adm-btn primary" href="/thanh-vien/nap-tien">Thanh toán phí thành viên</Link>
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}

export default function PortalLayout({ children }: { children: ReactNode }) {
  return (
    <MemberProvider fallback={<div className="adm-empty" style={{ paddingTop: 120 }}>Đang tải…</div>}>
      <Shell>{children}</Shell>
    </MemberProvider>
  );
}
