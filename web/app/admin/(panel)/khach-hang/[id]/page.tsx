"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { AccountCard } from "@/components/admin/AccountCard";
import { useAdmin } from "@/components/admin/AdminContext";
import { Dialog, Field, Icon, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/admin/api";
import { fmtDateTime, fromNow } from "@/lib/admin/format";
import type { Activity, Company, Contact } from "@/lib/admin/types";

type Errors = Record<string, string>;

const ACT_ICON: Record<Activity["kind"], string> = {
  created: "spark",
  status: "flag",
  note: "note",
  update: "edit",
  assign: "user",
};

const errOf = (e: unknown): [string, Errors] =>
  e instanceof ApiError ? [e.message, e.fields] : ["Có lỗi xảy ra, vui lòng thử lại.", {}];

const formObj = (form: HTMLFormElement) => Object.fromEntries(new FormData(form)) as Record<string, string>;

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { meta, user } = useAdmin();
  const [c, setC] = useState<Company | null>(null);
  const [loadError, setLoadError] = useState("");
  const [flash, setFlash] = useState("");

  const load = useCallback(async () => {
    try {
      setC(await api.get<Company>(`/companies/${id}`));
    } catch (e) {
      setLoadError(errOf(e)[0]);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (c) document.title = `${c.name} · Quản trị LeadScan`;
  }, [c]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(""), 3000);
    return () => clearTimeout(t);
  }, [flash]);

  async function patch(body: Record<string, unknown>, okMsg = "Đã lưu") {
    const updated = await api.patch<Company>(`/companies/${id}`, body);
    setC(updated);
    setFlash(okMsg);
  }

  if (loadError) {
    return (
      <div className="adm-card adm-empty">
        <p>{loadError}</p>
        <p style={{ marginTop: 12 }}><Link className="adm-btn" href="/admin/khach-hang">← Về danh sách</Link></p>
      </div>
    );
  }
  if (!c) {
    return (
      <div style={{ display: "grid", gap: 16 }}>
        <Skeleton h={32} w="40%" />
        <Skeleton h={220} />
        <Skeleton h={180} />
      </div>
    );
  }

  return (
    <>
      <Link href="/admin/khach-hang" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}>
        <Icon name="back" size={16} /> Khách hàng
      </Link>
      <div className="adm-head">
        <div>
          <h1 style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            {c.name} <StatusBadge status={c.status} label={meta.statuses[c.status]} />
          </h1>
          <p>
            <span className="mono">{c.code}</span> · Đăng ký {fmtDateTime(c.created_at)} · Nguồn: {c.source}
          </p>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {flash ? <span className="adm-badge plain" style={{ background: "#e6f6ec", color: "#157f3b" }} role="status">{flash}</span> : null}
          <select
            className="adm-input"
            style={{ width: 160 }}
            aria-label="Trạng thái"
            value={c.status}
            onChange={(e) => patch({ status: e.target.value }, "Đã đổi trạng thái").catch((err) => alert(errOf(err)[0]))}
          >
            {Object.entries(meta.statuses).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select
            className="adm-input"
            style={{ width: 180 }}
            aria-label="Người phụ trách"
            value={c.assigned_to ? String(c.assigned_to.id) : ""}
            onChange={(e) =>
              patch(e.target.value ? { assigned_to_id: Number(e.target.value) } : { unassign: true }, "Đã giao việc").catch((err) => alert(errOf(err)[0]))
            }
          >
            <option value="">Chưa giao</option>
            {meta.staff.map((s) => <option key={s.id} value={String(s.id)}>{s.full_name}</option>)}
          </select>
          {user.role === "admin" ? <DeleteButton company={c} onDeleted={() => router.replace("/admin/khach-hang")} /> : null}
        </div>
      </div>

      <div className="adm-grid side">
        <div className="adm-grid">
          <CompanyInfo c={c} sizes={meta.sizes} onSave={(body) => patch(body)} />
          <ProfileCard c={c} onSaved={() => { load(); setFlash("Đã lưu chân dung cơ hội"); }} />
          <Contacts c={c} onChanged={() => { load(); setFlash("Đã cập nhật người liên hệ"); }} />
          <AccountCard companyId={c.id} onChanged={load} />
        </div>
        <Timeline c={c} onAdded={load} />
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ thông tin doanh nghiệp */

function CompanyInfo({ c, sizes, onSave }: { c: Company; sizes: string[]; onSave: (b: Record<string, string>) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [msg, setMsg] = useState("");

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setMsg("");
    try {
      await onSave(formObj(e.currentTarget));
      setEditing(false);
    } catch (err) {
      const [m, f] = errOf(err);
      setMsg(m);
      setErrors(f);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="adm-card">
      <div className="hd">
        <h2>Thông tin doanh nghiệp</h2>
        {!editing ? <button className="adm-btn sm" onClick={() => setEditing(true)}><Icon name="edit" size={14} /> Sửa</button> : null}
      </div>
      <div className="bd">
        {editing ? (
          <form className="adm-form" onSubmit={submit} noValidate>
            {msg ? <div className="adm-alert full">{msg}</div> : null}
            <Field label="Tên doanh nghiệp" error={errors.name} full htmlFor="f-name">
              <input id="f-name" className="adm-input" name="name" defaultValue={c.name} maxLength={150} aria-invalid={!!errors.name} />
            </Field>
            <Field label="Mã số thuế" error={errors.tax_code} htmlFor="f-tax">
              <input id="f-tax" className="adm-input" name="tax_code" defaultValue={c.tax_code} maxLength={14} inputMode="numeric" aria-invalid={!!errors.tax_code} />
            </Field>
            <Field label="Ngành hàng" error={errors.industry} htmlFor="f-ind">
              <input id="f-ind" className="adm-input" name="industry" defaultValue={c.industry} maxLength={100} aria-invalid={!!errors.industry} />
            </Field>
            <Field label="Quy mô nhân sự" error={errors.company_size} htmlFor="f-size">
              <select id="f-size" className="adm-input" name="company_size" defaultValue={c.company_size}>
                {sizes.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Tỉnh/thành" error={errors.province} htmlFor="f-prov">
              <input id="f-prov" className="adm-input" name="province" defaultValue={c.province} maxLength={80} aria-invalid={!!errors.province} />
            </Field>
            <Field label="Địa chỉ" error={errors.address} full htmlFor="f-addr">
              <input id="f-addr" className="adm-input" name="address" defaultValue={c.address} maxLength={200} />
            </Field>
            <Field label="Website" error={errors.website} full htmlFor="f-web">
              <input id="f-web" className="adm-input" name="website" defaultValue={c.website} maxLength={200} />
            </Field>
            <div className="adm-actions full">
              <button type="button" className="adm-btn" onClick={() => { setEditing(false); setErrors({}); setMsg(""); }}>Huỷ</button>
              <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Lưu thay đổi"}</button>
            </div>
          </form>
        ) : (
          <dl className="adm-kv">
            <dt>Mã số thuế</dt><dd className="mono">{c.tax_code}</dd>
            <dt>Ngành hàng</dt><dd>{c.industry}</dd>
            <dt>Quy mô</dt><dd>{c.company_size}</dd>
            <dt>Tỉnh/thành</dt><dd>{c.province}</dd>
            <dt>Địa chỉ</dt><dd>{c.address || "—"}</dd>
            <dt>Website</dt>
            <dd>{c.website ? <a href={c.website} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand-600)" }}>{c.website}</a> : "—"}</dd>
            <dt>IP đăng ký</dt><dd className="mono">{c.ip || "—"}</dd>
          </dl>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ chân dung cơ hội */

function ProfileCard({ c, onSaved }: { c: Company; onSaved: () => void }) {
  const { meta } = useAdmin();
  const p = c.profile;
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setMsg("");
    try {
      await api.put(`/companies/${c.id}/profile`, {
        offering: String(fd.get("offering") ?? ""),
        target_customers: String(fd.get("target_customers") ?? ""),
        target_regions: fd.getAll("target_regions").map(String),
        opp_types: fd.getAll("opp_types").map(String),
        expected_tickets: String(fd.get("expected_tickets") ?? ""),
        notes: String(fd.get("notes") ?? ""),
      });
      setEditing(false);
      onSaved();
    } catch (err) {
      setMsg(errOf(err)[0]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="adm-card">
      <div className="hd">
        <div>
          <h2>Chân dung cơ hội</h2>
          <p className="muted" style={{ fontSize: 12.5 }}>Đầu vào để AI tìm và chấm điểm cơ hội</p>
        </div>
        {!editing ? <button className="adm-btn sm" onClick={() => setEditing(true)}><Icon name="edit" size={14} /> Sửa</button> : null}
      </div>
      <div className="bd">
        {editing ? (
          <form className="adm-form" onSubmit={submit}>
            {msg ? <div className="adm-alert full">{msg}</div> : null}
            <Field label="Sản phẩm/dịch vụ cung cấp" full htmlFor="p-off">
              <textarea id="p-off" className="adm-input" name="offering" defaultValue={p?.offering} maxLength={2000} />
            </Field>
            <Field label="Khách hàng mục tiêu" full htmlFor="p-tgt">
              <textarea id="p-tgt" className="adm-input" name="target_customers" defaultValue={p?.target_customers} maxLength={2000} />
            </Field>
            <div className="adm-field full">
              <span className="lbl">Khu vực ưu tiên</span>
              <div className="adm-checks">
                {meta.regions.map((r) => (
                  <label key={r}><input type="checkbox" name="target_regions" value={r} defaultChecked={p?.target_regions.includes(r)} />{r}</label>
                ))}
              </div>
            </div>
            <div className="adm-field full">
              <span className="lbl">Loại cơ hội quan tâm</span>
              <div className="adm-checks">
                {meta.opp_types.map((o) => (
                  <label key={o}><input type="checkbox" name="opp_types" value={o} defaultChecked={p?.opp_types.includes(o)} />{o}</label>
                ))}
              </div>
            </div>
            <Field label="Dự kiến số phiếu mua/năm" htmlFor="p-tk">
              <select id="p-tk" className="adm-input" name="expected_tickets" defaultValue={p?.expected_tickets ?? ""}>
                <option value="">Chưa chọn</option>
                {meta.tickets.map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Ghi chú" full htmlFor="p-notes">
              <textarea id="p-notes" className="adm-input" name="notes" defaultValue={p?.notes} maxLength={2000} />
            </Field>
            <div className="adm-actions full">
              <button type="button" className="adm-btn" onClick={() => setEditing(false)}>Huỷ</button>
              <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Lưu chân dung"}</button>
            </div>
          </form>
        ) : p ? (
          <dl className="adm-kv">
            <dt>Sản phẩm/dịch vụ</dt><dd style={{ whiteSpace: "pre-wrap" }}>{p.offering || "—"}</dd>
            <dt>Khách hàng mục tiêu</dt><dd style={{ whiteSpace: "pre-wrap" }}>{p.target_customers || "—"}</dd>
            <dt>Khu vực ưu tiên</dt><dd>{p.target_regions.join(", ") || "—"}</dd>
            <dt>Loại cơ hội</dt><dd>{p.opp_types.join(", ") || "—"}</dd>
            <dt>Số phiếu/năm</dt><dd>{p.expected_tickets || "—"}</dd>
            <dt>Ghi chú</dt><dd style={{ whiteSpace: "pre-wrap" }}>{p.notes || "—"}</dd>
          </dl>
        ) : (
          <p className="muted">Chưa có chân dung cơ hội.</p>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ người liên hệ */

function Contacts({ c, onChanged }: { c: Company; onChanged: () => void }) {
  const [editing, setEditing] = useState<Contact | "new" | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  function close() {
    setEditing(null);
    setErrors({});
    setMsg("");
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = formObj(e.currentTarget);
    const body = { full_name: f.full_name, position: f.position, email: f.email, phone: f.phone, is_primary: f.is_primary === "on" };
    setBusy(true);
    setErrors({});
    setMsg("");
    try {
      if (editing === "new") await api.post(`/companies/${c.id}/contacts`, body);
      else if (editing) await api.patch(`/contacts/${editing.id}`, body);
      close();
      onChanged();
    } catch (err) {
      const [m, fl] = errOf(err);
      setMsg(m);
      setErrors(fl);
    } finally {
      setBusy(false);
    }
  }

  async function remove(ct: Contact) {
    if (!confirm(`Xoá người liên hệ ${ct.full_name}?`)) return;
    try {
      await api.del(`/contacts/${ct.id}`);
      onChanged();
    } catch (err) {
      alert(errOf(err)[0]);
    }
  }

  const cur = editing && editing !== "new" ? editing : null;

  return (
    <section className="adm-card">
      <div className="hd">
        <h2>Người liên hệ ({c.contacts.length})</h2>
        <button className="adm-btn sm" onClick={() => setEditing("new")}><Icon name="plus" size={14} /> Thêm</button>
      </div>
      <div className="bd" style={{ paddingTop: 4, paddingBottom: 4 }}>
        {c.contacts.map((ct) => (
          <div className="adm-contact" key={ct.id}>
            <div className="lines">
              <div>
                <b>{ct.full_name}</b>
                {ct.position ? <span className="muted"> · {ct.position}</span> : null}
                {ct.is_primary ? <span className="adm-badge role" style={{ marginLeft: 8 }}>Liên hệ chính</span> : null}
              </div>
              {ct.phone ? <a href={`tel:${ct.phone}`}>{ct.phone}</a> : null}
              {ct.email ? <a href={`mailto:${ct.email}`} className="muted">{ct.email}</a> : null}
            </div>
            <div style={{ display: "flex", gap: 4, alignItems: "flex-start" }}>
              <button className="adm-btn sm ghost" onClick={() => setEditing(ct)} aria-label={`Sửa ${ct.full_name}`}><Icon name="edit" size={14} /></button>
              <button className="adm-btn sm ghost danger" onClick={() => remove(ct)} aria-label={`Xoá ${ct.full_name}`}><Icon name="trash" size={14} /></button>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={editing !== null} title={editing === "new" ? "Thêm người liên hệ" : "Sửa người liên hệ"} onClose={close}>
        {editing !== null ? (
          <form className="adm-form" onSubmit={submit} noValidate key={cur?.id ?? "new"}>
            {msg ? <div className="adm-alert full">{msg}</div> : null}
            <Field label="Họ và tên" error={errors.full_name} full htmlFor="c-name">
              <input id="c-name" className="adm-input" name="full_name" defaultValue={cur?.full_name} maxLength={100} autoFocus aria-invalid={!!errors.full_name} />
            </Field>
            <Field label="Chức vụ" error={errors.position} full htmlFor="c-pos">
              <input id="c-pos" className="adm-input" name="position" defaultValue={cur?.position} maxLength={100} />
            </Field>
            <Field label="Email" error={errors.email} htmlFor="c-email">
              <input id="c-email" className="adm-input" name="email" type="email" defaultValue={cur?.email} maxLength={150} aria-invalid={!!errors.email} />
            </Field>
            <Field label="Điện thoại" error={errors.phone} htmlFor="c-phone">
              <input id="c-phone" className="adm-input" name="phone" type="tel" defaultValue={cur?.phone} maxLength={20} aria-invalid={!!errors.phone} />
            </Field>
            <label className="full" style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" name="is_primary" defaultChecked={cur?.is_primary ?? false} style={{ accentColor: "var(--brand)" }} /> Đặt làm liên hệ chính
            </label>
            <div className="adm-actions full">
              <button type="button" className="adm-btn" onClick={close}>Huỷ</button>
              <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Lưu"}</button>
            </div>
          </form>
        ) : null}
      </Dialog>
    </section>
  );
}

/* ------------------------------------------------------------------ ghi chú & lịch sử */

function Timeline({ c, onAdded }: { c: Company; onAdded: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      await api.post(`/companies/${c.id}/notes`, { content: text });
      setText("");
      onAdded();
    } catch (err) {
      setMsg(errOf(err)[0]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="adm-card">
      <div className="hd"><h2>Ghi chú & lịch sử</h2></div>
      <div className="bd" style={{ display: "grid", gap: 14 }}>
        <form onSubmit={add} style={{ display: "grid", gap: 8 }}>
          {msg ? <div className="adm-alert">{msg}</div> : null}
          <textarea
            className="adm-input"
            placeholder="Ghi chú cuộc gọi, nhu cầu, hẹn lịch…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={4000}
            aria-label="Nội dung ghi chú"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) add(e);
            }}
          />
          <div className="adm-actions">
            <span className="muted" style={{ fontSize: 12, marginRight: "auto", alignSelf: "center" }}>Ctrl + Enter để lưu</span>
            <button className="adm-btn primary sm" disabled={busy || !text.trim()}>{busy ? "Đang lưu…" : "Thêm ghi chú"}</button>
          </div>
        </form>
        <ul className="adm-timeline">
          {c.activities.map((a) => (
            <li key={a.id} className={`k-${a.kind}`}>
              <span className="dot"><Icon name={ACT_ICON[a.kind] ?? "note"} /></span>
              <div>
                <div className="txt">{a.content}</div>
                <div className="meta" title={fmtDateTime(a.created_at)}>
                  {a.actor?.full_name ?? "Hệ thống"} · {fromNow(a.created_at)}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ xoá (chỉ admin) */

function DeleteButton({ company, onDeleted }: { company: Company; onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function confirmDelete() {
    setBusy(true);
    try {
      await api.del(`/companies/${company.id}`);
      onDeleted();
    } catch (err) {
      alert(errOf(err)[0]);
      setBusy(false);
    }
  }
  return (
    <>
      <button className="adm-btn danger" onClick={() => setOpen(true)}><Icon name="trash" size={14} /> Xoá</button>
      <Dialog
        open={open}
        title="Xoá khách hàng?"
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="adm-btn" onClick={() => setOpen(false)}>Huỷ</button>
            <button className="adm-btn primary" style={{ background: "var(--danger)", borderColor: "var(--danger)" }} onClick={confirmDelete} disabled={busy}>
              {busy ? "Đang xoá…" : "Xoá vĩnh viễn"}
            </button>
          </>
        }
      >
        <p>
          Xoá <b>{company.name}</b> ({company.code}) cùng toàn bộ người liên hệ, chân dung và lịch sử. <b>Không thể hoàn tác.</b>
        </p>
        <p className="muted">Nếu chỉ muốn ngừng chăm sóc, hãy đổi trạng thái sang “Từ chối” hoặc “Tạm khoá”.</p>
      </Dialog>
    </>
  );
}
