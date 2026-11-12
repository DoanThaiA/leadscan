"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Icon, ScoreChip, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, qs } from "@/lib/admin/api";
import { fmtDate, fmtDateTime, fmtNum, fromNow } from "@/lib/admin/format";
import type { SubmissionQueue } from "@/lib/admin/partners";
import { SUB_BADGE } from "@/lib/partner/submissions";

const PAGE = 20;
const TABS: [string, string][] = [
  ["queue", "Hàng đợi"],
  ["verified", "Đạt xác minh"],
  ["published", "Đã xuất bản"],
  ["supplement", "Đóng góp bổ sung"],
  ["duplicate", "Trùng"],
  ["rejected", "Không đạt"],
  ["all", "Tất cả"],
];

function Queue() {
  const { meta } = useAdmin();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const status = params.get("status") ?? "queue";
  const assigned = params.get("assigned") ?? "";
  const partnerId = params.get("partner_id") ?? "";
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [search, setSearch] = useState(q);
  const [data, setData] = useState<SubmissionQueue | null>(null);
  const [error, setError] = useState("");

  function setParams(next: Record<string, string | number | undefined>) {
    const merged = { status: status === "queue" ? undefined : status, assigned, partner_id: partnerId, q, page: page > 1 ? page : undefined, ...next };
    router.replace(pathname + qs(merged), { scroll: false });
  }

  useEffect(() => {
    if (search === q) return;
    const t = setTimeout(() => setParams({ q: search.trim(), page: undefined }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => {
    document.title = "Xác minh cơ hội đối tác · Quản trị LeadScan";
    setData(null);
    api.get<SubmissionQueue>("/partner-submissions" + qs({ status, assigned, partner_id: partnerId, q, page, page_size: PAGE })).then(setData, (e) => setError(e.message));
  }, [status, assigned, partnerId, q, page]);

  const tabCount = (k: string) => {
    if (!data) return null;
    if (k === "queue") return data.queue;
    if (k === "all") return Object.values(data.counts).reduce((a, b) => a + b, 0);
    return data.counts[k] ?? 0;
  };
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Xác minh cơ hội đối tác</h1>
          <p>Kiểm tra trùng, chấm điểm, quyết định Đạt / Trùng / Không đạt — SLA 2 ngày làm việc</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {data && data.overdue > 0 ? <div className="adm-alert warn" style={{ marginBottom: 16 }}><b>{data.overdue}</b> cơ hội quá hạn xác minh.</div> : null}
      {partnerId ? <div className="adm-alert ok" style={{ marginBottom: 16 }}>Đang lọc theo 1 đối tác · <button className="adm-btn sm" onClick={() => setParams({ partner_id: undefined })}>Bỏ lọc</button></div> : null}

      <section className="adm-card">
        <div className="adm-tabs" role="tablist" aria-label="Lọc theo trạng thái">
          {TABS.map(([k, label]) => {
            const n = tabCount(k);
            return (
              <button key={k} role="tab" aria-selected={status === k} className={status === k ? "on" : undefined} onClick={() => setParams({ status: k === "queue" ? undefined : k, page: undefined })}>
                {label}{n !== null ? <span>{fmtNum(n)}</span> : null}
              </button>
            );
          })}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo mã GT-, doanh nghiệp, MST, nhu cầu, mã/tên đối tác…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm cơ hội đối tác" />
          </div>
          <select className="adm-input" style={{ width: 200 }} value={assigned} onChange={(e) => setParams({ assigned: e.target.value, page: undefined })} aria-label="Người xác minh">
            <option value="">Mọi người xác minh</option>
            <option value="me">Của tôi</option>
            <option value="none">Chưa giao</option>
            {meta.staff.map((s) => <option key={s.id} value={String(s.id)}>{s.full_name}</option>)}
          </select>
        </div>

        {!data ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} h={22} />)}</div>
        ) : !data.items.length ? (
          <div className="adm-empty">{status === "queue" ? "Hàng đợi trống — không có cơ hội chờ xác minh." : "Không có cơ hội phù hợp bộ lọc."}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Cơ hội</th><th>Đối tác</th><th>Điểm</th><th>Trùng</th><th>Trạng thái</th><th>Người xác minh</th><th>{status === "queue" ? "Hạn" : "Gửi"}</th></tr></thead>
              <tbody>
                {data.items.map((s) => {
                  const href = `/admin/xac-minh-doi-tac/${s.id}`;
                  return (
                    <tr key={s.id} className="link" onClick={() => router.push(href)}>
                      <td style={{ maxWidth: 360 }}>
                        <Link className="name" href={href} onClick={(e) => e.stopPropagation()}>{s.title || s.company_name}</Link>
                        {s.title ? <div className="sub">{s.company_name}</div> : null}
                        <div className="sub" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.kind_label} · {s.industry} · {s.province}</div>
                        <div className="sub mono">{s.code}{s.tax_code ? ` · MST ${s.tax_code}` : ""}</div>
                      </td>
                      <td><div>{s.partner.full_name}</div><div className="sub mono">{s.partner.code}</div></td>
                      <td><ScoreChip score={s.score ?? s.auto_score} /></td>
                      <td>{s.dup_same ? <StatusBadge status="rejected" label={`Nghi trùng (${s.dup_same})`} />
                        : s.dup_similar ? <StatusBadge status="contacted" label={`Gần giống (${s.dup_similar})`} />
                        : s.dup_count ? <span className="muted" title="Cùng doanh nghiệp, nhu cầu khác">{s.dup_count} cơ hội khác</span>
                        : <span className="muted">—</span>}</td>
                      <td><StatusBadge status={SUB_BADGE[s.status]} label={s.status_label} /></td>
                      <td>{s.assigned_to?.full_name ?? <span className="muted">Chưa giao</span>}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {status === "queue"
                          ? <span style={{ color: s.overdue ? "var(--danger)" : undefined, fontWeight: s.overdue ? 600 : undefined }} title={fmtDateTime(s.sla_due_at)}>{s.overdue ? "Quá hạn " : ""}{fmtDate(s.sla_due_at)}</span>
                          : <span title={fmtDateTime(s.created_at)}>{fromNow(s.created_at)}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > 0 ? (
          <div className="adm-pager">
            <span>{fmtNum((page - 1) * PAGE + 1)}–{fmtNum(Math.min(page * PAGE, data.total))} / {fmtNum(data.total)} cơ hội</span>
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

export default function PartnerSubmissionsPage() {
  return (
    <Suspense>
      <Queue />
    </Suspense>
  );
}
