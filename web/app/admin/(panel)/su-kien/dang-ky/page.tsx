"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { EventWarning } from "@/components/admin/EventForm";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum, fromNow } from "@/lib/admin/format";
import {
  ATTENDEE_TYPES,
  OCR_STATUS,
  REG_STATUS,
  REG_STATUS_CLASS,
  fmtSize,
  fmtVnd,
  type EventAdminListItem,
  type EventRegistration,
  type EventsMeta,
} from "@/lib/events";

interface Resp {
  total: number;
  items: EventRegistration[];
  counts: Record<string, number>;
  revenue: number;
}

const PAGE_SIZE = 20;
const profileHref = (r: EventRegistration) => `/api/admin/event-registrations/${r.id}/profile`;
const proofHref = (r: EventRegistration) => `/api/admin/event-registrations/${r.id}/proof`;

export default function EventRegistrationsPage() {
  const { user } = useAdmin();
  const [events, setEvents] = useState<EventAdminListItem[]>([]);
  const [meta, setMeta] = useState<EventsMeta | null>(null);
  const [eventId, setEventId] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [d, setD] = useState<Resp | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<EventRegistration | null>(null);
  const [ready, setReady] = useState(false);

  // ?su_kien= lọc theo sự kiện, ?id= mở thẳng 1 đăng ký (link trong email báo ban tổ chức)
  useEffect(() => {
    document.title = "Đăng ký sự kiện · Quản trị LeadScan";
    const p = new URLSearchParams(location.search);
    setEventId(p.get("su_kien") ?? "");
    const id = p.get("id");
    if (id) api.get<EventRegistration>(`/event-registrations/${id}`).then(setOpen, (e) => setError(errMsg(e)));
    api.get<{ items: EventAdminListItem[] }>("/events").then((r) => setEvents(r.items), () => {});
    api.get<EventsMeta>("/events/meta").then(setMeta, () => {});
    setReady(true);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(() => {
    if (!ready) return;
    api.get<Resp>("/event-registrations" + qs({ event_id: eventId, status, q, page, page_size: PAGE_SIZE })).then(setD, (e) => setError(errMsg(e)));
  }, [ready, eventId, status, q, page]);

  useEffect(() => {
    setD(null);
    load();
  }, [load]);

  function changed(r: EventRegistration | null, removedId?: number) {
    setOpen(r);
    if (r) setD((cur) => (cur ? { ...cur, items: cur.items.map((x) => (x.id === r.id ? r : x)) } : cur));
    if (removedId || r) load();
  }

  const all = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;
  const pages = d ? Math.max(1, Math.ceil(d.total / PAGE_SIZE)) : 1;

  return (
    <>
      <Link href="/admin/su-kien" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Sự kiện</Link>
      <div className="adm-head">
        <div>
          <h1>Đăng ký sự kiện</h1>
          <p>
            Người tham dự gửi từ trang sự kiện: thông tin liên hệ, nhu cầu xúc tiến, profile PDF và ảnh chuyển khoản.
            Ảnh được đọc bằng OCR và so khớp mã đăng ký cùng số tiền; không khớp thì chờ bạn đối soát.
          </p>
        </div>
        <Link href="/admin/su-kien/check-in" className="adm-btn primary"><Icon name="ticket" size={14} /> Check-in</Link>
      </div>
      <EventWarning meta={meta} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!status ? "on" : undefined} onClick={() => { setStatus(""); setPage(1); }}>Tất cả{all !== null ? <span>{fmtNum(all)}</span> : null}</button>
          {Object.entries(REG_STATUS).map(([k, v]) => (
            <button key={k} className={status === k ? "on" : undefined} onClick={() => { setStatus(k); setPage(1); }}>
              {v}{d ? <span>{fmtNum(d.counts[k] ?? 0)}</span> : null}
            </button>
          ))}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tên, email, SĐT, doanh nghiệp, mã đăng ký…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm đăng ký" />
          </div>
          <select className="adm-input" style={{ width: "auto", maxWidth: 300 }} value={eventId} onChange={(e) => { setEventId(e.target.value); setPage(1); }} aria-label="Lọc theo sự kiện">
            <option value="">Mọi sự kiện</option>
            {events.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3, 4].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">{q || status || eventId ? "Không có đăng ký nào khớp bộ lọc." : "Chưa có đăng ký tham dự nào."}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Người đăng ký</th><th>Sự kiện</th><th>Mã · Phí</th><th>Tệp</th><th>Đối soát</th><th>Trạng thái</th><th>Nhận lúc</th></tr></thead>
              <tbody>
                {d.items.map((r) => (
                  <tr key={r.id} className="link" onClick={() => setOpen(r)}>
                    <td>
                      <button type="button" className="name" style={{ background: "none", border: 0, padding: 0, font: "inherit", cursor: "pointer", textAlign: "left" }} onClick={(e) => { e.stopPropagation(); setOpen(r); }}>{r.full_name}</button>
                      <div className="sub">{r.phone} · {r.email}{r.company ? ` · ${r.company}` : ""}</div>
                    </td>
                    <td>{r.event_title}<div className="sub">{ATTENDEE_TYPES[r.attendee_type] ?? r.attendee_type}</div></td>
                    <td style={{ whiteSpace: "nowrap" }}><span className="mono">{r.code}</span><div className="sub">{fmtVnd(r.amount)}</div></td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="job-cv">
                        {r.profile_filename ? <a className="adm-btn sm" href={profileHref(r)}><Icon name="download" size={13} /> Profile</a> : null}
                        {r.proof_filename ? <a className="adm-btn sm" href={proofHref(r)} target="_blank" rel="noopener"><Icon name="receipt" size={13} /> Biên lai</a> : null}
                        {!r.profile_filename && !r.proof_filename ? <span className="muted">—</span> : null}
                      </div>
                    </td>
                    <td><OcrBadge r={r} /></td>
                    <td>
                      <span className={`adm-badge ${REG_STATUS_CLASS[r.status] ?? ""}`}>{REG_STATUS[r.status] ?? r.status}</span>
                      {r.checked_in ? <div className="sub" title={r.checked_in_at ? fmtDateTime(r.checked_in_at) : undefined}>✓ Đã đến</div> : null}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }} title={fmtDateTime(r.created_at)}>{fromNow(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d && d.total > 0 ? (
          <div className="adm-pager">
            <span>{fmtNum(d.total)} đăng ký{pages > 1 ? ` · trang ${page}/${pages}` : ""} · đã thu {fmtVnd(d.revenue)}</span>
            {pages > 1 ? (
              <div>
                <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
                <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      {open ? <RegistrationDialog key={open.id} r={open} meta={meta} canDelete={user.role === "admin"} onChange={changed} /> : null}
    </>
  );
}

function OcrBadge({ r }: { r: EventRegistration }) {
  if (!r.proof_filename) return <span className="muted">Chưa có ảnh</span>;
  const cls = r.ocr_status === "matched" ? "s-active" : r.ocr_status === "mismatch" || r.ocr_status === "unreadable" ? "s-contacted" : r.ocr_status === "error" ? "s-rejected" : "";
  return <span className={`adm-badge ${cls}`} title={r.ocr_message}>{OCR_STATUS[r.ocr_status] ?? r.ocr_status}</span>;
}

function RegistrationDialog({
  r,
  meta,
  canDelete,
  onChange,
}: {
  r: EventRegistration;
  meta: EventsMeta | null;
  canDelete: boolean;
  onChange: (r: EventRegistration | null, removedId?: number) => void;
}) {
  const [status, setStatus] = useState(r.status);
  const [note, setNote] = useState(r.note);
  const [checkedIn, setCheckedIn] = useState(r.checked_in);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showText, setShowText] = useState(false);

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
      onChange(await api.patch<EventRegistration>(`/event-registrations/${r.id}`, { status, note, checked_in: checkedIn }));
      setMsg({ ok: true, text: "Đã lưu." });
    });
  const recheck = () =>
    run("recheck", async () => {
      const out = await api.post<EventRegistration>(`/event-registrations/${r.id}/recheck`);
      setStatus(out.status);
      onChange(out);
      setMsg({ ok: out.ocr_status === "matched", text: out.ocr_message || "Đã đọc lại ảnh." });
    });
  const resend = () =>
    run("resend", async () => {
      onChange(await api.post<EventRegistration>(`/event-registrations/${r.id}/resend`));
      setMsg({ ok: true, text: "Đã gửi đăng ký về hộp thư ban tổ chức." });
    });
  const remove = () => {
    if (!confirm(`Xoá vĩnh viễn đăng ký của ${r.full_name} (kèm profile và ảnh chuyển khoản)? Không thể hoàn tác.`)) return;
    run("delete", async () => {
      await api.del(`/event-registrations/${r.id}`);
      onChange(null, r.id);
    });
  };

  const dirty = status !== r.status || note !== r.note || checkedIn !== r.checked_in;
  const checks = r.ocr_checks ?? {};

  return (
    <Dialog
      open
      wide
      title={`${r.full_name} · ${r.code}`}
      onClose={() => onChange(null)}
      footer={
        <>
          {canDelete ? <button className="adm-btn danger" style={{ marginRight: "auto" }} onClick={remove} disabled={!!busy}><Icon name="trash" size={14} /> Xoá</button> : null}
          <button className="adm-btn" onClick={() => onChange(null)}>Đóng</button>
          <button className="adm-btn primary" onClick={save} disabled={!!busy || !dirty}>{busy === "save" ? "Đang lưu…" : "Lưu"}</button>
        </>
      }
    >
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"}>{msg.text}</div> : null}
      <dl className="adm-dl">
        <div><dt>Sự kiện</dt><dd>{r.event_slug ? <a href={`/su-kien/${r.event_slug}`} target="_blank" rel="noopener" style={{ color: "var(--brand-600)" }}>{r.event_title}</a> : r.event_title}</dd></div>
        <div><dt>Hình thức tham dự</dt><dd>{ATTENDEE_TYPES[r.attendee_type] ?? r.attendee_type} · <b>{fmtVnd(r.amount)}</b></dd></div>
        <div><dt>Điện thoại</dt><dd><a href={`tel:${r.phone}`}>{r.phone}</a></dd></div>
        <div><dt>Email</dt><dd><a href={`mailto:${r.email}`} style={{ color: "var(--brand-600)" }}>{r.email}</a></dd></div>
        {r.company ? <div><dt>Doanh nghiệp</dt><dd>{r.company}{r.position ? ` — ${r.position}` : ""}</dd></div> : null}
        <div><dt>Mã đăng ký / nội dung CK</dt><dd className="mono">{r.code}</dd></div>
        <div><dt>Đăng ký lúc</dt><dd>{fmtDateTime(r.created_at)}</dd></div>
        <div><dt>Thanh toán</dt><dd>{r.paid_at ? <span className="adm-badge s-active">Đã nhận {fmtDateTime(r.paid_at)}</span> : <span className="adm-badge s-rejected">Chưa ghi nhận</span>}</dd></div>
        <div>
          <dt>Email ban tổ chức</dt>
          <dd style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {r.email_sent_at ? <span className="adm-badge s-active">Đã gửi {fmtDateTime(r.email_sent_at)}</span> : <span className="adm-badge s-rejected">Chưa gửi</span>}
            <button className="adm-btn sm" onClick={resend} disabled={!!busy}><Icon name="refresh" size={13} /> {busy === "resend" ? "Đang gửi…" : r.email_sent_at ? "Gửi lại" : "Gửi ngay"}</button>
          </dd>
        </div>
      </dl>

      <div className="adm-field">
        <span className="lbl">Nhu cầu xúc tiến hợp tác</span>
        <div className="job-intro">{r.needs || "—"}</div>
      </div>

      <div className="adm-field">
        <span className="lbl">Tệp đính kèm</span>
        <div className="job-cv" style={{ flexWrap: "wrap" }}>
          {r.profile_filename ? (
            <a className="adm-btn sm" href={profileHref(r)}><Icon name="download" size={13} /> {r.profile_filename} ({fmtSize(r.profile_size)})</a>
          ) : <span className="muted">Không đính kèm profile</span>}
          {r.proof_filename ? (
            <a className="adm-btn sm" href={proofHref(r)} target="_blank" rel="noopener"><Icon name="receipt" size={13} /> Ảnh chuyển khoản ({fmtSize(r.proof_size)})</a>
          ) : <span className="muted">Chưa có ảnh chuyển khoản</span>}
        </div>
      </div>

      {r.proof_filename ? (
        <div className="adm-field">
          <span className="lbl">Đối soát bằng OCR</span>
          <div style={{ display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <OcrBadge r={r} />
              {["code", "amount", "account"].map((k) => (
                <span key={k} className={`adm-badge ${checks[k] ? "s-active" : ""}`}>
                  {checks[k] ? "✓" : "✕"} {k === "code" ? "Mã đăng ký" : k === "amount" ? "Số tiền" : "Số tài khoản"}
                </span>
              ))}
              {r.ocr_amount ? <span className="muted">Số tiền đọc được: {fmtVnd(r.ocr_amount)}</span> : null}
            </div>
            {r.ocr_message ? <p className="muted" style={{ fontSize: 13 }}>{r.ocr_message}{r.ocr_at ? ` · ${fmtDateTime(r.ocr_at)}` : ""}</p> : null}
            <div className="adm-actions" style={{ justifyContent: "flex-start" }}>
              <button className="adm-btn sm" onClick={recheck} disabled={!!busy || !meta?.ocr_ready} title={meta?.ocr_ready ? undefined : "Chưa đặt OCR_SPACE_API_KEY"}>
                <Icon name="refresh" size={13} /> {busy === "recheck" ? "Đang đọc ảnh…" : "Đọc lại ảnh"}
              </button>
              {r.ocr_text ? <button className="adm-btn sm" onClick={() => setShowText((s) => !s)}>{showText ? "Ẩn chữ đọc được" : "Xem chữ đọc được"}</button> : null}
            </div>
            {showText && r.ocr_text ? <pre className="job-intro" style={{ whiteSpace: "pre-wrap", fontSize: 12.5, maxHeight: 260, overflow: "auto" }}>{r.ocr_text}</pre> : null}
          </div>
        </div>
      ) : null}

      <Field label="Trạng thái" htmlFor="rg-status">
        <select id="rg-status" className="adm-input" value={status} onChange={(e) => setStatus(e.target.value)}>
          {Object.entries(REG_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </Field>
      <div className="adm-field">
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={checkedIn} onChange={(e) => setCheckedIn(e.target.checked)} />
          <span>Đã check-in tại sự kiện{r.checked_in && r.checked_in_at ? ` (${fmtDateTime(r.checked_in_at)})` : ""}</span>
        </label>
      </div>
      <Field label="Ghi chú nội bộ" htmlFor="rg-note">
        <textarea id="rg-note" className="adm-input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={5000} placeholder="Đã đối chiếu sao kê, ghi chú ghép cặp kết nối…" />
      </Field>
    </Dialog>
  );
}
