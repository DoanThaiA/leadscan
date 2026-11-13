"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { Icon, initials } from "@/components/admin/ui";
import { Logo } from "@/components/brand/Logo";
import { PartnerProvider, usePartner } from "@/components/partner/PartnerContext";
import { papi } from "@/lib/partner/api";

// Menu cổng (brief mục 8.2).
const NAV = [
  { href: "/doi-tac/tong-quan", label: "Tổng quan", icon: "home" },
  { href: "/doi-tac/gui-co-hoi", label: "Gửi cơ hội", icon: "plus" },
  { href: "/doi-tac/co-hoi", label: "Cơ hội của tôi", icon: "grid" },
  { href: "/doi-tac/vi", label: "Ví hoa hồng", icon: "wallet" },
  { href: "/doi-tac/rut-tien", label: "Rút tiền", icon: "card" },
  { href: "/doi-tac/ho-so-thanh-toan", label: "Hồ sơ thanh toán", icon: "lock" },
  { href: "/doi-tac/tai-khoan", label: "Tài khoản", icon: "user" },
  { href: "/doi-tac/chinh-sach", label: "Chính sách & hướng dẫn", icon: "note" },
];

function Shell({ children }: { children: ReactNode }) {
  const { me } = usePartner();
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);

  async function logout() {
    await papi.post("/auth/logout").catch(() => {});
    router.replace("/doi-tac/dang-nhap");
  }

  return (
    <div className="adm-shell">
      <div className="adm-mtop">
        <button className="adm-btn ghost sm" aria-label="Mở menu" onClick={() => setOpen(true)}><Icon name="menu" /></button>
        <Link href="/doi-tac/tong-quan" aria-label="Cổng Đối tác LeadScan" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Logo variant="mark" height={26} /><span className="ptn-label">Cổng Đối tác</span>
        </Link>
        <span style={{ width: 34 }} />
      </div>
      {open ? <div className="adm-scrim" onClick={() => setOpen(false)} /> : null}

      <aside className={open ? "adm-side open" : "adm-side"}>
        <Link href="/doi-tac/tong-quan" className="adm-logo" style={{ flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
          <Logo height={24} />
          <span className="ptn-label" style={{ justifySelf: "start" }}>Cổng Đối tác</span>
        </Link>
        <nav className="adm-nav" aria-label="Cổng đối tác">
          {NAV.map((n) => {
            const on = path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className={on ? "on" : undefined} aria-current={on ? "page" : undefined}>
                <Icon name={n.icon} />
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ptn-code">
          <small>Mã đối tác</small>
          <b>{me.code}</b>
          <span>Hạng {me.tier_label}</span>
        </div>
        <div className="adm-side-foot">
          <div className="adm-me">
            <span className="adm-avatar">{initials(me.full_name)}</span>
            <div style={{ minWidth: 0 }}>
              <b>{me.full_name}</b>
              <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{me.kind === "org" ? me.org_name : me.email}</span>
            </div>
          </div>
          {me.portals?.member ? (
            <a className="adm-btn sm" href="/thanh-vien" title="Cùng 1 tài khoản — không cần đăng nhập lại"><Icon name="building" size={14} /> Sang cổng thành viên</a>
          ) : null}
          <button className="adm-btn sm ghost" onClick={logout}><Icon name="logout" size={14} /> Đăng xuất</button>
        </div>
      </aside>

      <main className="adm-main">{children}</main>
    </div>
  );
}

export default function PartnerPortalLayout({ children }: { children: ReactNode }) {
  return (
    <PartnerProvider fallback={<div className="adm-empty" style={{ paddingTop: 120 }}>Đang tải…</div>}>
      <Shell>{children}</Shell>
    </PartnerProvider>
  );
}
