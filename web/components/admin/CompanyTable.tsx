"use client";

import { useRouter } from "next/navigation";

import { fromNow, fmtDateTime } from "@/lib/admin/format";
import type { CompanyListItem } from "@/lib/admin/types";

import { Skeleton, StatusBadge } from "./ui";

export function CompanyTable({
  items,
  statuses,
  empty = "Chưa có khách hàng nào.",
}: {
  items: CompanyListItem[] | undefined;
  statuses: Record<string, string>;
  empty?: string;
}) {
  const router = useRouter();
  if (!items) {
    return (
      <div className="bd" style={{ display: "grid", gap: 12 }}>
        {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} h={22} />)}
      </div>
    );
  }
  if (!items.length) return <div className="adm-empty">{empty}</div>;

  return (
    <div className="adm-table-wrap">
      <table className="adm-table">
        <thead>
          <tr>
            <th>Doanh nghiệp</th>
            <th>Người liên hệ</th>
            <th>Ngành · Tỉnh/thành</th>
            <th>Trạng thái</th>
            <th>Phụ trách</th>
            <th>Đăng ký</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => {
            const href = `/admin/khach-hang/${c.id}`;
            return (
              <tr key={c.id} className="link" onClick={() => router.push(href)}>
                <td>
                  <a className="name" href={href} title={c.name} onClick={(e) => { e.preventDefault(); router.push(href); }}>
                    {c.name}
                  </a>
                  <div className="sub mono">{c.code} · MST {c.tax_code}</div>
                </td>
                <td>
                  {c.primary_contact ? (
                    <>
                      <div>{c.primary_contact.full_name}</div>
                      <div className="sub">{c.primary_contact.phone || c.primary_contact.email}</div>
                    </>
                  ) : "—"}
                </td>
                <td>
                  <div>{c.industry}</div>
                  <div className="sub">{c.province}</div>
                </td>
                <td><StatusBadge status={c.status} label={statuses[c.status]} /></td>
                <td>{c.assigned_to?.full_name ?? <span className="muted">Chưa giao</span>}</td>
                <td title={fmtDateTime(c.created_at)} style={{ whiteSpace: "nowrap" }}>{fromNow(c.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
