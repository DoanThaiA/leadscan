"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Icon, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum, fromNow } from "@/lib/admin/format";
import type { AdminPartner, PartnerPage } from "@/lib/admin/partners";

const PAGE_SIZE = 20;

function PartnerList() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const verified = params.get("verified") ?? "";
  const status = params.get("status") ?? "";
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  const [search, setSearch] = useState(q);
  const [data, setData] = useState<PartnerPage | null>(null);
  const [error, setError] = useState("");

  function setParams(next: Record<string, string | number | undefined>) {
    const merged = { verified, status, q, page: page > 1 ? page : undefined, ...next };
    router.replace(pathname + qs(merged), { scroll: false });
  }

  useEffect(() => {
    if (search === q) return;
    const t = setTimeout(() => setParams({ q: search.trim(), page: undefined }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => {
    document.title = "Đối tác · Quản trị LeadScan";
    setData(null);
    api.get<PartnerPage>("/partners" + qs({ verified, status, q, page, page_size: PAGE_SIZE })).then(setData, (e) => setError(e.message));
  }, [verified, status, q, page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const tabs: [string, string, string, number | undefined][] = [
    ["", "", "Tất cả", data?.counts.all],
    ["no", "active", "Chờ xác thực SĐT", data?.counts.unverified],
    ["yes", "", "Đã kích hoạt", undefined],
    ["", "locked", "Tạm khoá", undefined],
  ];

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Đối tác</h1>
          <p>Người giới thiệu cơ hội qua cổng /doi-tac — tài khoản tách riêng với thành viên</p>
        </div>
        <div className="adm-actions">
          <a className="adm-btn" href="/admin/doi-tac/cau-hinh"><Icon name="target" size={14} /> Cấu hình thưởng</a>
          <a className="adm-btn" href="/doi-tac" target="_blank" rel="noopener"><Icon name="external" size={14} /> Trang đối tác</a>
        </div>
      </div>

      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {data && data.counts.unverified > 0 ? (
        <div className="adm-alert warn" style={{ marginBottom: 16 }}>
          {fmtNum(data.counts.unverified)} đối tác chưa xác thực SĐT. Khi chưa có nhà cung cấp SMS, gọi/nhắn Zalo đúng số rồi bấm <b>Xác nhận SĐT</b> trong trang chi tiết.
        </div>
      ) : null}

      <section className="adm-card">
        <div className="adm-tabs" role="tablist" aria-label="Lọc đối tác">
          {tabs.map(([v, s, label, n]) => {
            const on = verified === v && status === s;
            return (
              <button key={label} role="tab" aria-selected={on} className={on ? "on" : undefined} onClick={() => setParams({ verified: v, status: s, page: undefined })}>
                {label}{n !== undefined ? <span>{fmtNum(n)}</span> : null}
              </button>
            );
          })}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tên, mã đối tác, email, SĐT, tổ chức, MST…" value={search}
              onChange={(e) => setSearch(e.target.value)} aria-label="Tìm đối tác" />
          </div>
        </div>

        {!data ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} h={22} />)}</div>
        ) : !data.items.length ? (
          <div className="adm-empty">{q || verified || status ? "Không có đối tác phù hợp bộ lọc." : "Chưa có đối tác nào đăng ký."}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Đối tác</th><th>Liên hệ</th><th>Hình thức</th><th>SĐT</th><th>Hạng</th><th>Trạng thái</th><th>Đăng ký</th></tr></thead>
              <tbody>
                {data.items.map((p: AdminPartner) => {
                  const href = `/admin/doi-tac/${p.id}`;
                  return (
                    <tr key={p.id} className="link" onClick={() => router.push(href)}>
                      <td>
                        <a className="name" href={href} onClick={(e) => { e.preventDefault(); router.push(href); }}>{p.full_name}</a>
                        <div className="sub mono">{p.code}</div>
                      </td>
                      <td><div>{p.email}</div><div className="sub">{p.phone}</div></td>
                      <td>{p.kind_label}{p.kind === "org" ? <div className="sub">{p.org_name}</div> : null}</td>
                      <td>{p.phone_verified ? <StatusBadge status="active" label="Đã xác thực" /> : <StatusBadge status="contacted" label="Chờ xác thực" />}</td>
                      <td>{p.tier_label}</td>
                      <td><StatusBadge status={p.status === "locked" ? "suspended" : "active"} label={p.status_label} /></td>
                      <td title={fmtDateTime(p.created_at)} style={{ whiteSpace: "nowrap" }}>{fromNow(p.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total > 0 ? (
          <div className="adm-pager">
            <span>{fmtNum((page - 1) * PAGE_SIZE + 1)}–{fmtNum(Math.min(page * PAGE_SIZE, data.total))} / {fmtNum(data.total)} đối tác</span>
            <div>
              <button className="adm-btn sm" disabled={page <= 1} onClick={() => setParams({ page: page - 1 > 1 ? page - 1 : undefined })}>← Trước</button>
              <button className="adm-btn sm" disabled={page >= pages} onClick={() => setParams({ page: page + 1 })}>Sau →</button>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}

export default function PartnersPage() {
  return (
    <Suspense>
      <PartnerList />
    </Suspense>
  );
}
