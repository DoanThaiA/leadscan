"use client";

import { type FormEvent, useState } from "react";

import { errFields, errMsg } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { AI_STATUS, type KnowledgeCompany, KNOWLEDGE_SOURCE } from "@/lib/knowledge";

import { Field, Icon } from "./ui";

const NUM_FIELDS = ["founded_year", "rank", "rank_year"] as const;

export function KnowledgeForm({
  initial,
  onSubmit,
  submitLabel,
}: {
  initial?: KnowledgeCompany;
  onSubmit: (body: Record<string, unknown>) => Promise<void>;
  submitLabel: string;
}) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const k = initial;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    const body: Record<string, unknown> = { ...f, tax_code: f.tax_code?.trim() || null };
    for (const n of NUM_FIELDS) {
      const v = String(f[n] ?? "").replace(/\D/g, "");
      body[n] = v ? Number(v) : null;
    }
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

  const text = (name: keyof KnowledgeCompany, label: string, opts: { full?: boolean; max?: number; placeholder?: string; type?: string } = {}) => (
    <Field label={label} error={errors[name]} full={opts.full} htmlFor={`k-${name}`}>
      <input
        id={`k-${name}`}
        className="adm-input"
        name={name}
        type={opts.type ?? "text"}
        defaultValue={(k?.[name] as string | number | null | undefined) ?? ""}
        maxLength={opts.max}
        placeholder={opts.placeholder}
        aria-invalid={!!errors[name]}
      />
    </Field>
  );

  const extra = Object.entries(k?.extra ?? {});

  return (
    <form onSubmit={submit} noValidate className="adm-grid">
      {msg ? <div className="adm-alert">{msg}</div> : null}
      <div className="adm-grid side">
        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><div><h2>Giới thiệu chung</h2><p className="muted" style={{ fontSize: 12.5 }}>Thông tin doanh nghiệp để AI dựa vào khi quét</p></div></div>
            <div className="bd adm-form">
              {text("name", "Tên doanh nghiệp", { full: true, max: 300 })}
              {text("name_en", "Tên tiếng Anh", { full: true, max: 300 })}
              {text("tax_code", "Mã số thuế", { max: 20, placeholder: "10 hoặc 13 số" })}
              {text("stock_code", "Mã chứng khoán", { max: 20, placeholder: "Để trống nếu chưa niêm yết" })}
              {text("industry", "Ngành nghề", { full: true, max: 200 })}
              {text("address", "Trụ sở chính", { full: true, max: 500 })}
              {text("province", "Tỉnh/thành", { max: 80 })}
              {text("founded_year", "Năm thành lập", { max: 4 })}
              {text("phone", "Điện thoại", { max: 100 })}
              {text("fax", "Fax", { max: 100 })}
              {text("email", "Email", { max: 200 })}
              {text("website", "Website", { max: 300, placeholder: "https://" })}
              {text("ceo_name", "Tổng giám đốc / CEO", { max: 150 })}
              {text("logo_url", "Link logo", { max: 500 })}
              <Field label="Giới thiệu" error={errors.description} full htmlFor="k-desc">
                <textarea id="k-desc" className="adm-input" name="description" defaultValue={k?.description} maxLength={20000} style={{ minHeight: 180 }} />
              </Field>
            </div>
          </section>

          {extra.length ? (
            <section className="adm-card">
              <div className="hd"><div><h2>Thông tin khác từ nguồn</h2><p className="muted" style={{ fontSize: 12.5 }}>Các dòng chưa có ô riêng, giữ nguyên để tham khảo</p></div></div>
              <div className="bd">
                <dl className="adm-dl">
                  {extra.map(([label, value]) => (
                    <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
                  ))}
                </dl>
              </div>
            </section>
          ) : null}
        </div>

        <div className="adm-grid" style={{ position: "sticky", top: 16, alignSelf: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>AI quét</h2></div>
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              <Field label="Trạng thái" error={errors.ai_status} htmlFor="k-ai">
                <select id="k-ai" className="adm-input" name="ai_status" defaultValue={k?.ai_status ?? "pending"}>
                  {Object.entries(AI_STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
              <Field label="Kết quả / lỗi lần quét gần nhất" error={errors.ai_note} htmlFor="k-ainote">
                <textarea id="k-ainote" className="adm-input" name="ai_note" defaultValue={k?.ai_note} maxLength={5000} />
              </Field>
              {k?.ai_scanned_at ? <p className="muted" style={{ fontSize: 12.5 }}>Quét lần cuối: {fmtDateTime(k.ai_scanned_at)}</p> : null}
              <Field label="Ghi chú nội bộ" error={errors.note} htmlFor="k-note">
                <textarea id="k-note" className="adm-input" name="note" defaultValue={k?.note} maxLength={5000} />
              </Field>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Xếp hạng & nguồn</h2></div>
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {text("rank", "Hạng", { max: 6 })}
                {text("rank_year", "Năm xếp hạng", { max: 4 })}
              </div>
              {text("rank_list", "Bảng xếp hạng", { max: 200 })}
              {text("rank_label", "Ghi nhận tại nguồn", { max: 100 })}
              <Field label="Nguồn" error={errors.source} htmlFor="k-src">
                <select id="k-src" className="adm-input" name="source" defaultValue={k?.source ?? "manual"}>
                  {Object.entries(KNOWLEDGE_SOURCE).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
              {text("source_url", "Link nguồn", { max: 500 })}
              {k?.source_url ? (
                <a className="adm-btn sm" href={k.source_url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={14} /> Mở trang nguồn</a>
              ) : null}
              {k?.crawled_at ? <p className="muted" style={{ fontSize: 12.5 }}>Lấy từ nguồn lúc {fmtDateTime(k.crawled_at)}</p> : null}
            </div>
          </section>

          <button className="adm-btn primary" type="submit" disabled={busy}>{busy ? "Đang lưu…" : submitLabel}</button>
        </div>
      </div>
    </form>
  );
}
