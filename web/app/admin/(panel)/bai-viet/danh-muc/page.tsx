"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { notifySectionsChanged } from "@/components/admin/ArticleForm";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtNum } from "@/lib/admin/format";
import { type ArticleSection, sectionHref, slugify } from "@/lib/blog";

interface SectionRow extends ArticleSection {
  counts: Record<string, number>; // theo trạng thái bài: draft / published
  total: number;
  live: number; // đang hiện công khai
  is_default: boolean;
}

type Form = { name: string; slug: string; description: string; sort_order: string; is_active: boolean };
const EMPTY: Form = { name: "", slug: "", description: "", sort_order: "", is_active: true };

export default function SectionsPage() {
  const { user } = useAdmin();
  const [rows, setRows] = useState<SectionRow[] | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<SectionRow | "new" | null>(null);
  const [f, setF] = useState<Form>(EMPTY);
  const [formErr, setFormErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get<{ items: SectionRow[] }>("/article-sections").then((r) => setRows(r.items), (e) => setError(errMsg(e)));
  useEffect(() => {
    document.title = "Danh mục bài viết · Quản trị LeadScan";
    load();
  }, []);

  function open(row: SectionRow | "new") {
    setEditing(row);
    setFormErr("");
    setF(row === "new"
      ? { ...EMPTY, sort_order: String(Math.max(0, ...(rows ?? []).map((r) => r.sort_order)) + 1) }
      : { name: row.name, slug: row.slug, description: row.description, sort_order: String(row.sort_order), is_active: row.is_active });
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setFormErr("");
    const body = { ...f, sort_order: Number(f.sort_order) || 0 };
    try {
      if (editing === "new") await api.post("/article-sections", body);
      else await api.put(`/article-sections/${editing.id}`, body);
      setEditing(null);
      await load();
      notifySectionsChanged();
    } catch (err) {
      setFormErr(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(row: SectionRow) {
    if (!confirm(`Xoá danh mục “${row.name}”?`)) return;
    try {
      await api.del(`/article-sections/${row.id}`);
      await load();
      notifySectionsChanged();
    } catch (err) {
      alert(errMsg(err));
    }
  }

  const isNew = editing === "new";
  const previewSlug = isNew ? f.slug.trim() ? slugify(f.slug) : slugify(f.name) : f.slug;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Danh mục bài viết</h1>
          <p>Mỗi danh mục (Cẩm nang, Tuyển dụng, Tin tức…) có trang riêng và chứa các bài viết liên quan. Bấm tên danh mục để xem bài trong đó.</p>
        </div>
        <div className="adm-actions">
          <button className="adm-btn primary" onClick={() => open("new")}><Icon name="plus" size={16} /> Thêm danh mục</button>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        {!rows ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr><th>Danh mục</th><th>Trang công khai</th><th style={{ textAlign: "right" }}>Đang hiện</th><th style={{ textAlign: "right" }}>Bản nháp</th><th>Trạng thái</th><th>Thứ tự</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td style={{ minWidth: 220 }}>
                      <Link className="name" href={`/admin/bai-viet?danh_muc=${r.id}`}>{r.name}</Link>
                      <div className="sub">{r.description || <span className="muted">Chưa có mô tả</span>}</div>
                    </td>
                    <td><a className="mono" href={sectionHref(r.slug)} target="_blank" rel="noopener">{sectionHref(r.slug)}</a></td>
                    <td style={{ textAlign: "right" }}>{fmtNum(r.live)}</td>
                    <td style={{ textAlign: "right" }}>{fmtNum(r.counts.draft ?? 0)}</td>
                    <td>{r.is_active ? <span className="adm-badge s-active">Đang bật</span> : <span className="adm-badge s-suspended">Đang ẩn</span>}</td>
                    <td>{r.sort_order}</td>
                    <td>
                      <div className="adm-actions" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
                        <Link className="adm-btn sm" href={`/admin/bai-viet/moi?danh_muc=${r.id}`}><Icon name="plus" size={14} /> Viết bài</Link>
                        <button className="adm-btn sm ghost" onClick={() => open(r)} aria-label={`Sửa danh mục ${r.name}`}><Icon name="edit" size={14} /> Sửa</button>
                        {user.role === "admin" && !r.is_default ? (
                          <button className="adm-btn sm ghost" onClick={() => remove(r)} aria-label={`Xoá danh mục ${r.name}`} title={r.total ? "Danh mục còn bài viết, chuyển bài đi trước khi xoá" : "Xoá danh mục"}><Icon name="trash" size={14} /></button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Dialog
        open={editing !== null}
        title={isNew ? "Thêm danh mục" : "Sửa danh mục"}
        onClose={() => setEditing(null)}
        footer={
          <>
            <button type="button" className="adm-btn ghost" onClick={() => setEditing(null)}>Huỷ</button>
            <button type="submit" form="sec-form" className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : isNew ? "Tạo danh mục" : "Lưu"}</button>
          </>
        }
      >
        <form id="sec-form" onSubmit={save} className="adm-form" noValidate>
          {formErr ? <div className="adm-alert full">{formErr}</div> : null}
          <Field label="Tên danh mục *" full htmlFor="sec-name">
            <input id="sec-name" className="adm-input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} maxLength={100} placeholder="VD: Tuyển dụng" autoFocus />
          </Field>
          <Field label="Đường dẫn" full htmlFor="sec-slug">
            {isNew ? (
              <div className="job-slug"><span>/bai-viet/</span><input id="sec-slug" className="adm-input" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value })} maxLength={80} placeholder={slugify(f.name) || "Để trống = tự tạo từ tên"} /></div>
            ) : (
              <input id="sec-slug" className="adm-input mono" value={sectionHref(f.slug)} readOnly disabled />
            )}
            <span className="muted" style={{ fontSize: 12.5 }}>
              {isNew ? `Trang danh mục: /bai-viet/${previewSlug || "…"}. Không đổi được sau khi tạo (để link đã chia sẻ không bị gãy).` : "Đường dẫn cố định sau khi tạo."}
            </span>
          </Field>
          <Field label="Mô tả ngắn" full htmlFor="sec-desc">
            <textarea id="sec-desc" className="adm-input" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} maxLength={400} style={{ minHeight: 70 }} placeholder="Hiện ở đầu trang danh mục và trên Google" />
          </Field>
          <Field label="Thứ tự hiển thị" htmlFor="sec-order">
            <input id="sec-order" className="adm-input" type="number" min={0} max={9999} value={f.sort_order} onChange={(e) => setF({ ...f, sort_order: e.target.value })} />
          </Field>
          <Field label="Hiển thị công khai" htmlFor="sec-active">
            <label style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 38 }}>
              <input id="sec-active" type="checkbox" checked={f.is_active} disabled={!isNew && editing?.is_default} onChange={(e) => setF({ ...f, is_active: e.target.checked })} />
              {f.is_active ? "Đang bật" : "Ẩn danh mục và mọi bài trong đó"}
            </label>
          </Field>
        </form>
      </Dialog>
    </>
  );
}
