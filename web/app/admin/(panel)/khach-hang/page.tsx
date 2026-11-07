"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { CompanyTable } from "@/components/admin/CompanyTable";
import { Icon } from "@/components/admin/ui";
import { api, qs } from "@/lib/admin/api";
import { fmtNum } from "@/lib/admin/format";
import type { CompanyListItem, Page, Stats } from "@/lib/admin/types";

const PAGE_SIZE = 20;

function CompanyList() {
  const { meta } = useAdmin();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const status = params.get("status") ?? "";
  const assigned = params.get("assigned") ?? "";
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  const [search, setSearch] = useState(q);
  const [data, setData] = useState<Page<CompanyListItem> | null>(null);
  const [counts, setCounts] = useState<Stats["by_status"] | null>(null);
  const [error, setError] = useState("");

  function setParams(next: Record<string, string | number | undefined>) {
    const merged = { status, assigned, q, page: page > 1 ? page : undefined, ...next };
    router.replace(pathname + qs(merged), { scroll: false });
  }

  // tìm kiếm có độ trễ 300ms
  useEffect(() => {
    if (search === q) return;
    const t = setTimeout(() => setParams({ q: search.trim(), page: undefined }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => {
    document.title = "Khách hàng · Quản trị LeadScan";
    setData(null);
    api
      .get<Page<CompanyListItem>>("/companies" + qs({ status, assigned, q, page, page_size: PAGE_SIZE }))
      .then(setData, (e) => setError(e.message));
  }, [status, assigned, q, page]);

  useEffect(() => {
    api.get<Stats>("/stats").then((s) => setCounts(s.by_status), () => {});
  }, []);

  const totalAll = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : null;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Khách hàng</h1>
          <p>Doanh nghiệp đăng ký thành viên từ landing page</p>
        </div>
      </div>

      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        <div className="adm-tabs" role="tablist" aria-label="Lọc theo trạng thái">
          <button role="tab" aria-selected={!status} className={!status ? "on" : undefined} onClick={() => setParams({ status: "", page: undefined })}>
            Tất cả{totalAll !== null ? <span>{fmtNum(totalAll)}</span> : null}
          </button>
          {Object.entries(meta.statuses).map(([key, label]) => (
            <button key={key} role="tab" aria-selected={status === key} className={status === key ? "on" : undefined} onClick={() => setParams({ status: key, page: undefined })}>
              {label}
              {counts ? <span>{fmtNum(counts[key] ?? 0)}</span> : null}
            </button>
          ))}
        </div>

        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input
              className="adm-input"
              type="search"
              placeholder="Tìm theo tên, mã đăng ký, MST, email, số điện thoại…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Tìm khách hàng"
            />
          </div>
          <select className="adm-input" style={{ width: 200 }} value={assigned} onChange={(e) => setParams({ assigned: e.target.value, page: undefined })} aria-label="Lọc theo người phụ trách">
            <option value="">Mọi người phụ trách</option>
            <option value="me">Của tôi</option>
            <option value="none">Chưa giao</option>
            {meta.staff.map((s) => (
              <option key={s.id} value={String(s.id)}>{s.full_name}</option>
            ))}
          </select>
        </div>

        <CompanyTable items={data?.items} statuses={meta.statuses} empty={q || status || assigned ? "Không có khách hàng phù hợp bộ lọc." : "Chưa có khách hàng nào."} />

        {data && data.total > 0 ? (
          <div className="adm-pager">
            <span>
              {fmtNum((page - 1) * PAGE_SIZE + 1)}–{fmtNum(Math.min(page * PAGE_SIZE, data.total))} / {fmtNum(data.total)} khách hàng
            </span>
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

export default function CompaniesPage() {
  return (
    <Suspense>
      <CompanyList />
    </Suspense>
  );
}
