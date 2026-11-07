"use client";

import { type FormEvent, useState } from "react";

import { errFields, errMsg } from "@/lib/admin/api";
import type { Opp, OppContact } from "@/lib/commerce";

import { Field, Icon } from "./ui";

const REGIONS = ["Miền Bắc", "Miền Trung", "Miền Nam", "Toàn quốc", "Quốc tế"];
const SOURCES = ["App đăng mua", "Dự án & gói thầu", "Nhà máy / FDI mới", "Hội chợ & triển lãm", "Mạng xã hội & nhóm chat", "Website doanh nghiệp", "Nguồn chính thống"];

type ContactDraft = Omit<OppContact, "id">;
const emptyContact = (): ContactDraft => ({ full_name: "", title: "", phone: "", email: "", note: "" });

export function OppForm({ initial, onSubmit, submitLabel }: { initial?: Opp; onSubmit: (body: Record<string, unknown>) => Promise<void>; submitLabel: string }) {
  const [contacts, setContacts] = useState<ContactDraft[]>(initial?.contacts?.length ? initial.contacts.map(({ id: _, ...c }) => c) : [emptyContact()]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const o = initial;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    const num = (k: string) => Number(String(f[k] ?? "").replace(/\D/g, "") || 0);
    const body = {
      ...f,
      deadline: f.deadline || null,
      score: num("score"),
      score_fit: num("score_fit"),
      score_urgency: num("score_urgency"),
      score_trust: num("score_trust"),
      enrich_round: num("enrich_round"),
      price: num("price"),
      max_buyers: num("max_buyers"),
      contacts: contacts.filter((c) => Object.values(c).some((v) => v.trim())),
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
              <Field label="Giá phiếu (điểm)" error={errors.price} htmlFor="o-price"><input id="o-price" className="adm-input" name="price" inputMode="numeric" defaultValue={o?.price ?? 29000} /></Field>
              <Field label="Số lượt bán tối đa (1 = độc quyền)" error={errors.max_buyers} htmlFor="o-max"><input id="o-max" className="adm-input" name="max_buyers" inputMode="numeric" defaultValue={o?.max_buyers ?? 3} /></Field>
              <Field label="Vòng enrich" error={errors.enrich_round} htmlFor="o-er"><input id="o-er" className="adm-input" name="enrich_round" inputMode="numeric" defaultValue={o?.enrich_round ?? 0} /></Field>
              {o ? <p className="muted" style={{ fontSize: 12.5 }}>Đã bán {o.sold_count}/{o.max_buyers} lượt.</p> : null}
            </div>
          </section>
          <section className="adm-card">
            <div className="hd"><div><h2>Điểm chất lượng</h2><p className="muted" style={{ fontSize: 12.5 }}>0–100 · sau này AI tự chấm</p></div></div>
            <div className="bd adm-form">
              <Field label="Tổng điểm" error={errors.score} full htmlFor="o-sc"><input id="o-sc" className="adm-input" name="score" inputMode="numeric" defaultValue={o?.score ?? 0} /></Field>
              <Field label="Khớp chân dung" error={errors.score_fit} htmlFor="o-sf"><input id="o-sf" className="adm-input" name="score_fit" inputMode="numeric" defaultValue={o?.score_fit ?? 0} /></Field>
              <Field label="Độ cấp thiết" error={errors.score_urgency} htmlFor="o-su"><input id="o-su" className="adm-input" name="score_urgency" inputMode="numeric" defaultValue={o?.score_urgency ?? 0} /></Field>
              <Field label="Độ tin cậy nguồn" error={errors.score_trust} full htmlFor="o-stt"><input id="o-stt" className="adm-input" name="score_trust" inputMode="numeric" defaultValue={o?.score_trust ?? 0} /></Field>
            </div>
          </section>
          <button className="adm-btn primary" style={{ height: 42 }} disabled={busy}>{busy ? "Đang lưu…" : submitLabel}</button>
        </div>
      </div>
    </form>
  );
}
