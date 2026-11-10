"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MailWarning } from "@/components/admin/JobForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";
import { fmtDay, JOB_STATUS, JOB_STATUS_CLASS, JOB_TYPES, type JobAdminListItem, type JobsMeta } from "@/lib/careers";

interface Resp {
  items: JobAdminListItem[];
  counts: Record<string, number>;
}

export default function JobsAdminPage() {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [d, setD] = useState<Resp | null>(null);
  const [meta, setMeta] = useState<JobsMeta | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<JobsMeta>("/jobs/meta").then(setMeta, () => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    document.title = "Tuyển dụng · Quản trị LeadScan";
    setD(null);
    api.get<Resp>("/jobs" + qs({ status, q })).then(setD, (e) => setError(errMsg(e)));
  }, [status, q]);

  const all = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Tuyển dụng</h1>
          <p>Đăng bài lên trang <a href="/tuyen-dung" target="_blank" rel="noopener" style={{ color: "var(--brand-600)" }}>/tuyen-dung</a>. Hồ sơ ứng viên được gửi về email tuyển dụng và lưu tại đây.</p>
        </div>
        <div className="adm-actions">
          <Link className="adm-btn" href="/admin/tuyen-dung/ho-so"><Icon name="users" size={16} /> Hồ sơ ứng tuyển</Link>
          <Link className="adm-btn primary" href="/admin/tuyen-dung/moi"><Icon name="plus" size={16} /> Đăng bài tuyển dụng</Link>
        </div>
      </div>
      <MailWarning meta={meta} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!status ? "on" : undefined} onClick={() => setStatus("")}>Tất cả{all !== null ? <span>{fmtNum(all)}</span> : null}</button>
          {Object.entries(JOB_STATUS).map(([k, v]) => (
            <button key={k} className={status === k ? "on" : undefined} onClick={() => setStatus(k)}>
              {v}{d ? <span>{fmtNum(d.counts[k] ?? 0)}</span> : null}
            </button>
          ))}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo vị trí, phòng ban, địa điểm…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm bài tuyển dụng" />
          </div>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">
            {q || status ? "Không có bài nào khớp bộ lọc." : <>Chưa có bài tuyển dụng. <Link href="/admin/tuyen-dung/moi" style={{ color: "var(--brand-600)" }}>Đăng bài đầu tiên →</Link></>}
          </div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Vị trí</th><th>Trạng thái</th><th>Hạn nộp</th><th>Hồ sơ</th><th>Cập nhật</th></tr></thead>
              <tbody>
                {d.items.map((j) => (
                  <tr key={j.id} className="link" onClick={() => router.push(`/admin/tuyen-dung/${j.id}`)}>
                    <td>
                      <Link className="name" href={`/admin/tuyen-dung/${j.id}`} onClick={(e) => e.stopPropagation()}>{j.title}</Link>
                      <div className="sub">{[j.department, JOB_TYPES[j.employment_type], j.location].filter(Boolean).join(" · ")}</div>
                    </td>
                    <td><span className={`adm-badge ${JOB_STATUS_CLASS[j.status] ?? ""}`}>{JOB_STATUS[j.status] ?? j.status}</span></td>
                    <td style={{ whiteSpace: "nowrap" }}>{j.deadline ? fmtDay(j.deadline) : <span className="muted">Không hạn</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {j.applications ? (
                        <Link href={`/admin/tuyen-dung/ho-so?job=${j.id}`} onClick={(e) => e.stopPropagation()} style={{ color: "var(--brand-600)", fontWeight: 600 }}>
                          {fmtNum(j.applications)} hồ sơ
                        </Link>
                      ) : <span className="muted">0</span>}
                      {j.applications_new ? <span className="job-new">{j.applications_new} mới</span> : null}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(j.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
