"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";
import type { AdminPartnerDetail } from "@/lib/admin/partners";

interface Ev {
  id: number;
  kind: string;
  kind_label: string;
  content: string;
  actor: string | null;
  partner: { id: number; code: string; full_name: string } | null;
  submission: { id: number; code: string } | null;
  created_at: string;
}

const KINDS: [string, string][] = [["", "Tất cả"], ["account", "Tài khoản"], ["submission", "Cơ hội & xác minh"], ["money", "Ví & hoa hồng"], ["payout", "Rút tiền"], ["fraud", "Cờ gian lận"]];
const PAGE = 50;

/** Nhật ký chung (brief mục 9): mọi thay đổi trạng thái và số dư — ai, khi nào, vì sao — để đối soát, giải quyết khiếu nại. */
function EventLog() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const kind = params.get("kind") ?? "";
  const q = params.get("q") ?? "";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const partnerId = params.get("partner_id") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  const [search, setSearch] = useState(q);
  const [data, setData] = useState<{ total: number; items: Ev[] } | null>(null);
  const [partner, setPartner] = useState<{ code: string; full_name: string } | null>(null);
  const [error, setError] = useState("");

  function setParams(next: Record<string, string | number | undefined>) {
    const merged = { kind, q, from, to, partner_id: partnerId, page: page > 1 ? page : undefined, ...next };
    router.replace(pathname + qs(merged), { scroll: false });
  }

  useEffect(() => {
    if (search.trim() === q) return;
    const t = setTimeout(() => setParams({ q: search.trim(), page: undefined }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  useEffect(() => {
    document.title = "Nhật ký đối tác · Quản trị LeadScan";
  }, []);

  useEffect(() => {
    setPartner(null);
    if (partnerId) api.get<AdminPartnerDetail>(`/partners/${partnerId}`).then((p) => setPartner({ code: p.code, full_name: p.full_name }), () => setPartner({ code: `#${partnerId}`, full_name: "" }));
  }, [partnerId]);

  useEffect(() => {
    setData(null);
    api.get<{ total: number; items: Ev[] }>("/partner-reports/events" + qs({ kind, q, from, to, partner_id: partnerId, page, page_size: PAGE })).then(
      (d) => { setData(d); setError(""); },
      (e) => setError(errMsg(e)),
    );
  }, [kind, q, from, to, partnerId, page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  const filtered = !!(kind || q || from || to || partnerId);
  const csvHref = "/api/admin/partner-reports/events" + qs({ kind, q, from, to, partner_id: partnerId, format: "csv" });

  return (
    <>
      <div className="adm-head">
        <div>
          <Link href={partnerId ? `/admin/doi-tac/${partnerId}` : "/admin/doi-tac"} className="muted" style={{ fontSize: 13 }}>← {partnerId && partner ? partner.code : "Đối tác"}</Link>
          <h1 style={{ marginTop: 4 }}>Nhật ký đối tác</h1>
          <p>Mọi thay đổi trạng thái và số dư — ai, khi nào, vì sao. Chỉ thêm, không sửa / xoá.</p>
        </div>
        <div className="adm-actions">
          <a className="adm-btn" href={csvHref}><Icon name="download" size={14} /> Tải CSV</a>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs" role="tablist" aria-label="Loại nhật ký">
          {KINDS.map(([k, label]) => <button key={k} role="tab" aria-selected={kind === k} className={kind === k ? "on" : undefined} onClick={() => setParams({ kind: k, page: undefined })}>{label}</button>)}
        </div>
        <div className="adm-toolbar" style={{ flexWrap: "wrap" }}>
          <div className="adm-search"><Icon name="search" /><input className="adm-input" type="search" placeholder="Tìm nội dung, mã / tên đối tác…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm trong nhật ký" /></div>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>Từ
            <input className="adm-input" type="date" style={{ width: 160 }} value={from} max={to || undefined} onChange={(e) => setParams({ from: e.target.value, page: undefined })} aria-label="Từ ngày" />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>đến
            <input className="adm-input" type="date" style={{ width: 160 }} value={to} min={from || undefined} onChange={(e) => setParams({ to: e.target.value, page: undefined })} aria-label="Đến ngày" />
          </label>
          {partnerId ? (
            <span className="adm-badge s-new" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              Đối tác {partner ? `${partner.code}${partner.full_name ? ` · ${partner.full_name}` : ""}` : "…"}
              <button type="button" onClick={() => setParams({ partner_id: undefined, page: undefined })} aria-label="Bỏ lọc đối tác" style={{ background: "none", border: 0, cursor: "pointer", color: "inherit", padding: 0 }}>✕</button>
            </span>
          ) : null}
          {filtered ? <button className="adm-btn sm ghost" onClick={() => { setSearch(""); router.replace(pathname, { scroll: false }); }}>Xoá bộ lọc</button> : null}
        </div>
        {!data ? <div className="bd" style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>
          : !data.items.length ? <div className="adm-empty">{filtered ? "Không có mục nào phù hợp bộ lọc." : "Chưa có nhật ký."}</div> : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Thời điểm</th><th>Đối tác</th><th>Loại</th><th>Nội dung</th><th>Người thực hiện</th></tr></thead>
              <tbody>
                {data.items.map((e) => (
                  <tr key={e.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.created_at)}</td>
                    <td>
                      {e.partner ? (
                        <>
                          <Link href={`/admin/doi-tac/${e.partner.id}`} className="mono" style={{ color: "var(--brand-600)" }}>{e.partner.code}</Link>
                          <div className="sub">{e.partner.full_name}</div>
                          {!partnerId ? <button type="button" className="sub" onClick={() => setParams({ partner_id: e.partner!.id, page: undefined })} style={{ background: "none", border: 0, padding: 0, cursor: "pointer", textDecoration: "underline" }}>Chỉ xem đối tác này</button> : null}
                        </>
                      ) : "—"}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}><span className={`adm-badge ${e.kind === "fraud_flag" || e.kind === "credit_error" ? "s-rejected" : "s-suspended"}`}>{e.kind_label}</span></td>
                    <td>{e.content}{e.submission ? <div className="sub"><Link href={`/admin/xac-minh-doi-tac/${e.submission.id}`} className="mono" style={{ color: "var(--brand-600)" }}>{e.submission.code}</Link></div> : null}</td>
                    <td>{e.actor ?? <span className="muted">Đối tác / hệ thống</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > 0 ? (
          <div className="adm-pager">
            <span>{fmtNum((page - 1) * PAGE + 1)}–{fmtNum(Math.min(page * PAGE, data.total))} / {fmtNum(data.total)} mục</span>
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

export default function PartnerEventLogPage() {
  return (
    <Suspense>
      <EventLog />
    </Suspense>
  );
}
