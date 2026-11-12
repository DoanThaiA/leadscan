"use client";

import { type FormEvent, useState } from "react";

import { errFields, errMsg } from "@/lib/admin/api";
import type { Opp, OppContact } from "@/lib/commerce";

import { type AttachItem, AttachmentsEditor } from "./AttachmentsEditor";
import { Field, Icon } from "./ui";

const REGIONS = ["Miền Bắc", "Miền Trung", "Miền Nam", "Toàn quốc", "Quốc tế"];
const SOURCES = ["App đăng mua", "Dự án & gói thầu", "Nhà máy / FDI mới", "Hội chợ & triển lãm", "Mạng xã hội & nhóm chat", "Website doanh nghiệp", "Nguồn chính thống", "Email hỏi hàng", "Kết nối giao thương"];

type ContactDraft = Omit<OppContact, "id">;
const emptyContact = (): ContactDraft => ({ full_name: "", title: "", phone: "", email: "", note: "" });

export function OppForm({ initial, onSubmit, submitLabel }: { initial?: Opp; onSubmit: (body: Record<string, unknown>) => Promise<void>; submitLabel: string }) {
  const [contacts, setContacts] = useState<ContactDraft[]>(initial?.contacts?.length ? initial.contacts.map(({ id: _, ...c }) => c) : [emptyContact()]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<AttachItem[]>([]);
  const o = initial;
  const uploading = files.some((f) => !f.att && !f.error);
  const failed = files.filter((f) => f.error).length;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (uploading) {
      setMsg("Đang tải tệp đính kèm lên — vui lòng đợi xong rồi lưu.");
      return;
    }
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    const num = (k: string) => Number(String(f[k] ?? "").replace(/\D/g, "") || 0);
    const body = {
      ...f,
      deadline: f.deadline || null,
      enrich_round: num("enrich_round"),
      price: num("price"),
      max_buyers: num("max_buyers"),
      contacts: contacts.filter((c) => Object.values(c).some((v) => v.trim())),
      attachment_ids: files.filter((x) => x.att).map((x) => x.att!.id), // đúng thứ tự hiển thị
      attachment_captions: Object.fromEntries(files.filter((x) => x.att).map((x) => [x.att!.id, x.caption.trim()])),
    };
    setBusy(true);
    setErrors({});
    setMsg("");
    try {
      await onSubmit(body);
    } catch (err) {
      setMsg(errMsg(err));
      setErrors(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  const setC = (i: number, k: keyof ContactDraft, v: string) => setContacts((cs) => cs.map((c, j) => (j === i ? { ...c, [k]: v } : c)));

  return (
    <form onSubmit={submit} noValidate className="adm-grid">
      {msg ? <div className="adm-alert">{msg}</div> : null}
      <div className="adm-grid side">
        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><div><h2>Phần xem trước</h2><p className="muted" style={{ fontSize: 12.5 }}>Thành viên nào cũng thấy</p></div></div>
            <div className="bd adm-form">
              <Field label="Tiêu đề nhu cầu" error={errors.title} full htmlFor="o-title">
                <input id="o-title" className="adm-input" name="title" defaultValue={o?.title} maxLength={200} placeholder="Ví dụ: Cần 200.000 hộp carton 5 lớp/tháng" aria-invalid={!!errors.title} />
              </Field>
              <Field label="Tóm tắt (không lộ tên bên mua)" error={errors.summary} full htmlFor="o-sum">
                <textarea id="o-sum" className="adm-input" name="summary" defaultValue={o?.summary} maxLength={3000} />
              </Field>
              <Field label="Ngành" error={errors.industry} htmlFor="o-ind"><input id="o-ind" className="adm-input" name="industry" defaultValue={o?.industry} maxLength={100} /></Field>
              <Field label="Tỉnh/thành" error={errors.province} htmlFor="o-prov"><input id="o-prov" className="adm-input" name="province" defaultValue={o?.province} maxLength={80} /></Field>
              <Field label="Khu vực" error={errors.region} htmlFor="o-reg">
                <select id="o-reg" className="adm-input" name="region" defaultValue={o?.region ?? ""}><option value="">—</option>{REGIONS.map((r) => <option key={r}>{r}</option>)}</select>
              </Field>
              <Field label="Nguồn tin" error={errors.source_type} htmlFor="o-src">
                <select id="o-src" className="adm-input" name="source_type" defaultValue={o?.source_type ?? ""}><option value="">—</option>{SOURCES.map((s) => <option key={s}>{s}</option>)}</select>
              </Field>
              <Field label="Quy mô / số lượng" error={errors.scale} htmlFor="o-scale"><input id="o-scale" className="adm-input" name="scale" defaultValue={o?.scale} maxLength={150} placeholder="~200.000 hộp/tháng" /></Field>
              <Field label="Giá trị ước tính" error={errors.estimated_value} htmlFor="o-val"><input id="o-val" className="adm-input" name="estimated_value" defaultValue={o?.estimated_value} maxLength={100} placeholder="2–3 tỷ/năm" /></Field>
              <Field label="Hạn chót" error={errors.deadline} htmlFor="o-dl"><input id="o-dl" className="adm-input" type="date" name="deadline" defaultValue={o?.deadline ?? ""} /></Field>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><div><h2>Phần mở khoá sau khi mua</h2><p className="muted" style={{ fontSize: 12.5 }}>Chỉ người đã mua phiếu mới thấy</p></div></div>
            <div className="bd adm-form">
              <Field label="Bên có nhu cầu (tên đơn vị)" error={errors.buyer_name} full htmlFor="o-buyer"><input id="o-buyer" className="adm-input" name="buyer_name" defaultValue={o?.buyer_name} maxLength={200} /></Field>
              <Field label="Mô tả chi tiết" error={errors.detail} full htmlFor="o-detail"><textarea id="o-detail" className="adm-input" name="detail" defaultValue={o?.detail} maxLength={10000} style={{ minHeight: 120 }} /></Field>
              <Field label="Link nguồn" error={errors.source_url} full htmlFor="o-url"><input id="o-url" className="adm-input" name="source_url" defaultValue={o?.source_url} maxLength={500} /></Field>
              <div className="full at-field">
                <div className="at-label">
                  <span>Ảnh &amp; tài liệu</span>
                  <small className="muted">Ảnh chụp yêu cầu, bản vẽ, báo giá, hồ sơ thầu… — người mua xem và tải sau khi mua phiếu</small>
                </div>
                <AttachmentsEditor initial={o?.attachments ?? []} onChange={setFiles} />
              </div>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd">
              <h2>Đầu mối liên hệ ({contacts.length})</h2>
              <button type="button" className="adm-btn sm" onClick={() => setContacts((c) => [...c, emptyContact()])} disabled={contacts.length >= 20}><Icon name="plus" size={14} /> Thêm đầu mối</button>
            </div>
            <div className="bd" style={{ display: "grid", gap: 16 }}>
              {contacts.map((c, i) => (
                <div key={i} className="adm-form" style={{ paddingBottom: 14, borderBottom: "1px solid var(--line-2)" }}>
                  <Field label={`Đầu mối ${i + 1} — họ tên`} htmlFor={`c${i}-n`}><input id={`c${i}-n`} className="adm-input" value={c.full_name} onChange={(e) => setC(i, "full_name", e.target.value)} maxLength={100} /></Field>
                  <Field label="Chức vụ" htmlFor={`c${i}-t`}><input id={`c${i}-t`} className="adm-input" value={c.title} onChange={(e) => setC(i, "title", e.target.value)} maxLength={100} placeholder="Trưởng phòng mua hàng" /></Field>
                  <Field label="Điện thoại" htmlFor={`c${i}-p`}><input id={`c${i}-p`} className="adm-input" value={c.phone} onChange={(e) => setC(i, "phone", e.target.value)} maxLength={30} /></Field>
                  <Field label="Email" htmlFor={`c${i}-e`}><input id={`c${i}-e`} className="adm-input" value={c.email} onChange={(e) => setC(i, "email", e.target.value)} maxLength={150} /></Field>
                  <Field label="Ghi chú" full htmlFor={`c${i}-o`}><input id={`c${i}-o`} className="adm-input" value={c.note} onChange={(e) => setC(i, "note", e.target.value)} maxLength={300} /></Field>
                  <div className="full adm-actions"><button type="button" className="adm-btn sm ghost danger" onClick={() => setContacts((cs) => cs.filter((_, j) => j !== i))}><Icon name="trash" size={14} /> Bỏ đầu mối này</button></div>
                </div>
              ))}
              {!contacts.length ? <p className="muted">Chưa có đầu mối.</p> : null}
            </div>
          </section>
        </div>

        <div className="adm-grid" style={{ position: "sticky", top: 16 }}>
          <section className="adm-card">
            <div className="hd"><h2>Bán phiếu</h2></div>
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              <Field label="Trạng thái" error={errors.status} htmlFor="o-st">
                <select id="o-st" className="adm-input" name="status" defaultValue={o?.status ?? "draft"}>
                  <option value="draft">Nháp (chưa hiện cho khách)</option>
                  <option value="published">Đang bán</option>
                  <option value="closed">Đã đóng</option>
                </select>
              </Field>
              <Field label="Giá cơ bản (điểm)" error={errors.price} htmlFor="o-price"><input id="o-price" className="adm-input" name="price" inputMode="numeric" defaultValue={o?.price ?? 29000} aria-describedby="o-price-hint" /><small id="o-price-hint" className="muted" style={{ fontSize: 11.5 }}>Giá thành viên trả = giá cơ bản × hệ số điểm phù hợp × độ gấp của hạn chót × độ đủ thông tin × giá trị đơn hàng ước tính — xem và chỉnh ở <a href="/admin/co-hoi/cong-thuc-gia" target="_blank" rel="noopener" style={{ textDecoration: "underline" }}>Công thức giá</a>.</small></Field>
              <Field label="Số lượt bán tối đa (1 = độc quyền)" error={errors.max_buyers} htmlFor="o-max"><input id="o-max" className="adm-input" name="max_buyers" inputMode="numeric" defaultValue={o?.max_buyers ?? 3} /></Field>
              <Field label="Vòng enrich" error={errors.enrich_round} htmlFor="o-er"><input id="o-er" className="adm-input" name="enrich_round" inputMode="numeric" defaultValue={o?.enrich_round ?? 0} /></Field>
              {o ? <p className="muted" style={{ fontSize: 12.5 }}>Đã bán {o.sold_count}/{o.max_buyers} lượt.</p> : null}
            </div>
          </section>
          <section className="adm-card">
            <div className="hd"><div><h2>Điểm &amp; giá theo khách</h2><p className="muted" style={{ fontSize: 12.5 }}>Phiếu không nhập điểm</p></div></div>
            <div className="bd" style={{ display: "grid", gap: 8 }}>
              <p className="muted" style={{ fontSize: 13 }}>
                Hệ thống tự so khớp phiếu với các phiếu tìm cơ hội của khách (tiêu chí + từ khoá + ngữ nghĩa) và chấm điểm riêng cho từng khách. Giá phiếu ở trên là <b>giá cơ bản</b>: khách điểm cao trả cao hơn, điểm thấp trả thấp hơn.
              </p>
              {o ? <p style={{ fontSize: 13 }}>Hiện khớp <b>{o.match_count ?? 0}</b> khách hàng.</p> : <p className="muted" style={{ fontSize: 12.5 }}>Sau khi lưu ở trạng thái “Đang bán”, phiếu tự được so khớp với các phiếu tìm cơ hội đang có.</p>}
            </div>
          </section>
          {failed ? <p className="muted" style={{ fontSize: 12.5 }}>{failed} tệp tải lỗi sẽ không được lưu — bấm “Thử lại” hoặc bỏ tệp đó.</p> : null}
          <button className="adm-btn primary" style={{ height: 42 }} disabled={busy || uploading}>{busy ? "Đang lưu…" : uploading ? "Đang tải tệp lên…" : submitLabel}</button>
        </div>
      </div>
    </form>
  );
}
