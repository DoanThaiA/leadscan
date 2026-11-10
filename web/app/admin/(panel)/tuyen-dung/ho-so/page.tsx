"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { MailWarning } from "@/components/admin/JobForm";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum, fromNow } from "@/lib/admin/format";
import { APP_STATUS, APP_STATUS_CLASS, fmtSize, type JobAdminListItem, type JobApplication, type JobsMeta } from "@/lib/careers";

interface Resp {
  total: number;
  items: JobApplication[];
  counts: Record<string, number>;
}

const PAGE_SIZE = 20;
const cvHref = (a: JobApplication) => `/api/admin/job-applications/${a.id}/cv`;

export default function ApplicationsPage() {
  const { user } = useAdmin();
  const [jobs, setJobs] = useState<JobAdminListItem[]>([]);
  const [meta, setMeta] = useState<JobsMeta | null>(null);
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [d, setD] = useState<Resp | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<JobApplication | null>(null);
  const [ready, setReady] = useState(false);

  // ?job= lọc theo bài, ?id= mở thẳng hồ sơ (link trong email gửi người tuyển dụng)
  useEffect(() => {
    document.title = "Hồ sơ ứng tuyển · Quản trị LeadScan";
    const p = new URLSearchParams(location.search);
    setJobId(p.get("job") ?? "");
    const id = p.get("id");
    if (id) api.get<JobApplication>(`/job-applications/${id}`).then(setOpen, (e) => setError(errMsg(e)));
    api.get<{ items: JobAdminListItem[] }>("/jobs").then((r) => setJobs(r.items), () => {});
    api.get<JobsMeta>("/jobs/meta").then(setMeta, () => {});
    setReady(true);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(() => {
    if (!ready) return;
    api.get<Resp>("/job-applications" + qs({ job_id: jobId, status, q, page, page_size: PAGE_SIZE })).then(setD, (e) => setError(errMsg(e)));
  }, [ready, jobId, status, q, page]);

  useEffect(() => {
    setD(null);
    load();
  }, [load]);

  function changed(a: JobApplication | null, removedId?: number) {
    setOpen(a);
    if (a) setD((cur) => (cur ? { ...cur, items: cur.items.map((x) => (x.id === a.id ? a : x)) } : cur));
    if (removedId || a) load(); // cập nhật số đếm trên tab
  }

  const all = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;
  const pages = d ? Math.max(1, Math.ceil(d.total / PAGE_SIZE)) : 1;

  return (
    <>
      <Link href="/admin/tuyen-dung" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Tuyển dụng</Link>
      <div className="adm-head">
        <div>
          <h1>Hồ sơ ứng tuyển</h1>
          <p>Ứng viên gửi từ trang tuyển dụng. Mỗi hồ sơ đồng thời được email về hộp thư tuyển dụng{meta?.recruit_email ? <> (<b>{meta.recruit_email}</b>)</> : null}.</p>
        </div>
      </div>
      <MailWarning meta={meta} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!status ? "on" : undefined} onClick={() => { setStatus(""); setPage(1); }}>Tất cả{all !== null ? <span>{fmtNum(all)}</span> : null}</button>
          {Object.entries(APP_STATUS).map(([k, v]) => (
            <button key={k} className={status === k ? "on" : undefined} onClick={() => { setStatus(k); setPage(1); }}>
              {v}{d ? <span>{fmtNum(d.counts[k] ?? 0)}</span> : null}
            </button>
          ))}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tên, email, SĐT, vị trí…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm hồ sơ" />
          </div>
          <select className="adm-input" style={{ width: "auto", maxWidth: 280 }} value={jobId} onChange={(e) => { setJobId(e.target.value); setPage(1); }} aria-label="Lọc theo vị trí">
            <option value="">Mọi vị trí</option>
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3, 4].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">{q || status || jobId ? "Không có hồ sơ nào khớp bộ lọc." : "Chưa có hồ sơ ứng tuyển nào."}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Ứng viên</th><th>Vị trí</th><th>CV</th><th>Trạng thái</th><th>Email</th><th>Nhận lúc</th></tr></thead>
              <tbody>
                {d.items.map((a) => (
                  <tr key={a.id} className="link" onClick={() => setOpen(a)}>
                    <td>
                      <button type="button" className="name" style={{ background: "none", border: 0, padding: 0, font: "inherit", cursor: "pointer", textAlign: "left" }} onClick={(e) => { e.stopPropagation(); setOpen(a); }}>{a.full_name}</button>
                      <div className="sub">{a.phone} · {a.email}</div>
                    </td>
                    <td>{a.job_title}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="job-cv">
                        {a.cv_filename ? <a className="adm-btn sm" href={cvHref(a)} download><Icon name="download" size={13} /> File</a> : null}
                        {a.cv_url ? <a className="adm-btn sm" href={a.cv_url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={13} /> Link</a> : null}
                      </div>
                    </td>
                    <td><span className={`adm-badge ${APP_STATUS_CLASS[a.status] ?? ""}`}>{APP_STATUS[a.status] ?? a.status}</span></td>
                    <td>{a.email_sent_at ? <span className="adm-badge s-active">Đã gửi</span> : <span className="adm-badge s-rejected">Chưa gửi</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }} title={fmtDateTime(a.created_at)}>{fromNow(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d && d.total > 0 ? (
          <div className="adm-pager">
            <span>{fmtNum(d.total)} hồ sơ{pages > 1 ? ` · trang ${page}/${pages}` : ""}</span>
            {pages > 1 ? (
              <div>
                <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
                <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      {open ? <ApplicationDialog key={open.id} a={open} canDelete={user.role === "admin"} onChange={changed} /> : null}
    </>
  );
}

function ApplicationDialog({
  a,
  canDelete,
  onChange,
}: {
  a: JobApplication;
  canDelete: boolean;
  onChange: (a: JobApplication | null, removedId?: number) => void;
}) {
  const [status, setStatus] = useState(a.status);
  const [note, setNote] = useState(a.note);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function run(kind: string, fn: () => Promise<void>) {
    setBusy(kind);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
    } finally {
      setBusy("");
    }
  }

  const save = () =>
    run("save", async () => {
      onChange(await api.patch<JobApplication>(`/job-applications/${a.id}`, { status, note }));
      setMsg({ ok: true, text: "Đã lưu." });
    });
  const resend = () =>
    run("resend", async () => {
      onChange(await api.post<JobApplication>(`/job-applications/${a.id}/resend`));
      setMsg({ ok: true, text: "Đã gửi hồ sơ về hộp thư tuyển dụng." });
    });
  const remove = () => {
    if (!confirm(`Xoá vĩnh viễn hồ sơ của ${a.full_name} (kèm file CV)? Không thể hoàn tác.`)) return;
    run("delete", async () => {
      await api.del(`/job-applications/${a.id}`);
      onChange(null, a.id);
    });
  };

  return (
    <Dialog
      open
      title={a.full_name}
      onClose={() => onChange(null)}
      footer={
        <>
          {canDelete ? <button className="adm-btn danger" style={{ marginRight: "auto" }} onClick={remove} disabled={!!busy}><Icon name="trash" size={14} /> Xoá</button> : null}
          <button className="adm-btn" onClick={() => onChange(null)}>Đóng</button>
          <button className="adm-btn primary" onClick={save} disabled={!!busy || (status === a.status && note === a.note)}>{busy === "save" ? "Đang lưu…" : "Lưu"}</button>
        </>
      }
    >
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"}>{msg.text}</div> : null}
      <dl className="adm-dl">
        <div><dt>Vị trí</dt><dd>{a.job_slug ? <a href={`/tuyen-dung/${a.job_slug}`} target="_blank" rel="noopener" style={{ color: "var(--brand-600)" }}>{a.job_title}</a> : a.job_title}</dd></div>
        <div><dt>Điện thoại</dt><dd><a href={`tel:${a.phone}`}>{a.phone}</a></dd></div>
        <div><dt>Email</dt><dd><a href={`mailto:${a.email}`} style={{ color: "var(--brand-600)" }}>{a.email}</a></dd></div>
        <div>
          <dt>CV</dt>
          <dd className="job-cv">
            {a.cv_filename ? <a className="adm-btn sm" href={cvHref(a)} download><Icon name="download" size={13} /> {a.cv_filename} ({fmtSize(a.cv_size)})</a> : null}
            {a.cv_url ? <a className="adm-btn sm" href={a.cv_url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={13} /> Mở link CV</a> : null}
          </dd>
        </div>
        {a.portfolio_url ? <div><dt>Portfolio</dt><dd><a href={a.portfolio_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand-600)", wordBreak: "break-all" }}>{a.portfolio_url}</a></dd></div> : null}
        <div><dt>Nhận lúc</dt><dd>{fmtDateTime(a.created_at)}</dd></div>
        <div>
          <dt>Email tuyển dụng</dt>
          <dd style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {a.email_sent_at ? <span className="adm-badge s-active">Đã gửi {fmtDateTime(a.email_sent_at)}</span> : <span className="adm-badge s-rejected">Chưa gửi</span>}
            <button className="adm-btn sm" onClick={resend} disabled={!!busy}><Icon name="refresh" size={13} /> {busy === "resend" ? "Đang gửi…" : a.email_sent_at ? "Gửi lại" : "Gửi ngay"}</button>
          </dd>
        </div>
      </dl>
      {a.intro ? (
        <div className="adm-field">
          <span className="lbl">Giới thiệu ngắn</span>
          <div className="job-intro">{a.intro}</div>
        </div>
      ) : null}
      <Field label="Trạng thái xử lý" htmlFor="ap-status">
        <select id="ap-status" className="adm-input" value={status} onChange={(e) => setStatus(e.target.value)}>
          {Object.entries(APP_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </Field>
      <Field label="Ghi chú nội bộ" htmlFor="ap-note">
        <textarea id="ap-note" className="adm-input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={5000} placeholder="Nhận xét, lịch phỏng vấn…" />
      </Field>
    </Dialog>
  );
}
