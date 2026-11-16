"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Thanh chuyển trang trong phân hệ Làm giàu theo MST — chỉ hiện mục vai trò được dùng. */
const ITEMS: { href: string; label: string; cap: string; exact?: boolean }[] = [
  { href: "/admin/lam-giau", label: "Hồ sơ doanh nghiệp", cap: "a.read", exact: true },
  { href: "/admin/lam-giau/nhap-lo", label: "Lô MST", cap: "batch.read" },
  { href: "/admin/lam-giau/nhap-nguon", label: "Nhập nguồn chính thức", cap: "data.import" },
  { href: "/admin/lam-giau/niem-yet", label: "Niêm yết & quản trị", cap: "a.read" },
  { href: "/admin/lam-giau/nguoi", label: "Người & quan hệ", cap: "b.list" },
  { href: "/admin/lam-giau/canh-bao", label: "Theo dõi & cảnh báo", cap: "a.read" },
  { href: "/admin/lam-giau/bao-cao", label: "Báo cáo thị trường", cap: "a.read" },
  { href: "/admin/lam-giau/tuan-thu", label: "Tuân thủ", cap: "compliance.read" },
  { href: "/admin/lam-giau/vong", label: "Vòng thu thập", cap: "run.read" },
  { href: "/admin/lam-giau/thu-cong", label: "Hàng đợi thủ công", cap: "manual.work" },
  { href: "/admin/lam-giau/nguon", label: "Nguồn & cấu hình", cap: "a.read" },
];

export function EnrichNav({ caps }: { caps: string[] }) {
  const path = usePathname();
  return (
    <nav className="adm-tabs er-nav" aria-label="Làm giàu theo MST">
      {ITEMS.filter((i) => caps.includes(i.cap)).map((i) => {
        const on = i.exact ? path === i.href || /^\/admin\/lam-giau\/\d/.test(path) : path.startsWith(i.href);
        return (
          <Link key={i.href} href={i.href} className={on ? "on" : undefined} aria-current={on ? "page" : undefined}>
            {i.label}
          </Link>
        );
      })}
    </nav>
  );
}
