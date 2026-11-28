import { SITE_BADGE } from "@/lib/events";

/** Nhãn "LeadScan" / "CEO 1989" / "EPC" cho biết sự kiện / đăng ký đến từ trang nào */
export function SiteBadge({ site }: { site: string }) {
  const b = SITE_BADGE[site] ?? { label: site, color: "#475569", bg: "#F1F5F9" };
  return (
    <span className="adm-badge" style={{ color: b.color, background: b.bg, whiteSpace: "nowrap" }}>
      {b.label}
    </span>
  );
}
