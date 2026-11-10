"use client";

import { type FormEvent, useState } from "react";

import { RichText } from "@/components/careers/RichText";
import { errFields, errMsg } from "@/lib/admin/api";
import { JOB_SECTIONS, JOB_STATUS, JOB_TYPES, type JobAdmin, type JobSectionKey, type JobsMeta } from "@/lib/careers";

import { CoverImageField } from "./CoverImageField";
import { Field, Icon } from "./ui";

type Values = Record<string, string>;

const TEXT_KEYS = [
  "title", "slug", "status", "subtitle", "department", "location", "employment_type", "salary", "work_time",
  "reports_to", "quantity", "deadline", "cover_image", "summary", "apply_email",
  ...JOB_SECTIONS.map(([k]) => k),
] as const;

const PLACEHOLDER: Record<JobSectionKey, string> = {
  objective: "Vai trò của vị trí trong đội ngũ và kết quả chính cần đạt được.",
  description: "## A. Nhóm công việc thứ nhất\n- Đầu việc cụ thể\n- Đầu việc cụ thể\n\n## B. Nhóm công việc thứ hai\n- …",
  requirements: "## Kinh nghiệm & chuyên môn\n- …\n\n## Tư duy & thái độ\n- …\n\n## Ưu tiên\n- …",
  benefits: "- Thu nhập: lương cứng + thưởng theo kết quả\n- Đóng BHXH, BHYT, BHTN đầy đủ theo luật\n- Nghỉ phép năm, lương tháng 13\n- …",
  how_to_apply: "Gửi hồ sơ bằng form ứng tuyển bên dưới, gồm:\n- CV (link hoặc file PDF/DOC)\n- Portfolio / sản phẩm tiêu biểu (nếu có)",
};

/** Nội dung mẫu giúp soạn nhanh bài mới (sửa lại theo vị trí thực tế) */
const TEMPLATE: Values = {
  objective: "Mô tả ngắn vai trò của vị trí và mục tiêu chính trong 6–12 tháng đầu.",
  description: PLACEHOLDER.description,
  requirements: PLACEHOLDER.requirements,
  benefits: PLACEHOLDER.benefits,
  how_to_apply: PLACEHOLDER.how_to_apply,
};

function initialValues(j?: JobAdmin): Values {
  const v: Values = {};
  for (const k of TEXT_KEYS) {
    const x = j?.[k as keyof JobAdmin];
    v[k] = x === null || x === undefined ? "" : String(x);
  }
  v.status ||= "draft";
  v.employment_type ||= "full_time";
  return v;
}

export function JobForm({
  initial,
  meta,
  onSubmit,
  submitLabel,
}: {
  initial?: JobAdmin;
  meta: JobsMeta | null;
  onSubmit: (body: Record<string, unknown>) => Promise<void>;
  submitLabel: string;
}) {
  const [v, setV] = useState<Values>(() => initialValues(initial));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);

  const set = (k: string) => (e: { target: { value: string } }) => {
    const val = e.target.value;
    setV((s) => ({ ...s, [k]: val }));
    if (errors[k]) setErrors(({ [k]: _, ...rest }) => rest);
  };

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = v.quantity.replace(/\D/g, "");
    const body: Record<string, unknown> = { ...v, quantity: q ? Number(q) : null, deadline: v.deadline || null };
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

  const input = (k: string, label: string, opts: { full?: boolean; max?: number; placeholder?: string; type?: string } = {}) => (
    <Field label={label} error={errors[k]} full={opts.full} htmlFor={`j-${k}`}>
      <input
        id={`j-${k}`}
        className="adm-input"
        type={opts.type ?? "text"}
        value={v[k]}
        onChange={set(k)}
        maxLength={opts.max}
        placeholder={opts.placeholder}
        aria-invalid={!!errors[k]}
      />
    </Field>
  );

  const emptyContent = JOB_SECTIONS.every(([k]) => !v[k].trim());

  return (
    <form onSubmit={submit} noValidate className="adm-grid">
      {msg ? <div className="adm-alert">{msg}</div> : null}
      <div className="adm-grid side">
        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><div><h2>Thông tin vị trí</h2><p className="muted" style={{ fontSize: 12.5 }}>Hiện ở thẻ danh sách và cột “Thông tin chung”</p></div></div>
            <div className="bd adm-form">
              {input("title", "Tên vị trí *", { full: true, max: 200, placeholder: "VD: Chuyên viên Kinh doanh B2B" })}
              <Field label="Đường dẫn" error={errors.slug} full htmlFor="j-slug">
                <div className="job-slug">
                  <span>/tuyen-dung/</span>
                  <input id="j-slug" className="adm-input" value={v.slug} onChange={set("slug")} maxLength={160} placeholder="Để trống = tự tạo từ tên vị trí" />
                </div>
              </Field>
              {input("subtitle", "Mô tả ngắn dưới tiêu đề", { full: true, max: 300, placeholder: "VD: Phát triển khách hàng doanh nghiệp cho nền tảng LeadScan" })}
              {input("department", "Phòng ban", { max: 100, placeholder: "Kinh doanh, Marketing, Công nghệ…" })}
              <Field label="Hình thức" error={errors.employment_type} htmlFor="j-type">
                <select id="j-type" className="adm-input" value={v.employment_type} onChange={set("employment_type")}>
                  {Object.entries(JOB_TYPES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </Field>
              {input("location", "Địa điểm làm việc", { full: true, max: 300, placeholder: "Số nhà, đường, quận, thành phố" })}
              {input("salary", "Thu nhập", { max: 150, placeholder: "VD: 12 – 20 triệu/tháng + thưởng" })}
              {input("work_time", "Thời gian làm việc", { max: 200, placeholder: "VD: 8:30 – 17:30, thứ 2 – thứ 6" })}
              {input("reports_to", "Báo cáo trực tiếp", { max: 150, placeholder: "VD: Trưởng phòng Kinh doanh" })}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {input("quantity", "Số lượng", { max: 4, placeholder: "VD: 2" })}
                {input("deadline", "Hạn nộp", { type: "date" })}
              </div>
              <CoverImageField
                value={v.cover_image}
                error={errors.cover_image}
                onChange={(url) => {
                  setV((s) => ({ ...s, cover_image: url }));
                  if (errors.cover_image) setErrors(({ cover_image: _, ...rest }) => rest);
                }}
              />
              <Field label="Tóm tắt trên thẻ danh sách" error={errors.summary} full htmlFor="j-summary">
                <textarea id="j-summary" className="adm-input" value={v.summary} onChange={set("summary")} maxLength={1000} placeholder="1–2 câu giới thiệu vị trí" />
              </Field>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd">
              <div><h2>Nội dung bài đăng</h2><p className="muted" style={{ fontSize: 12.5 }}>Mục để trống sẽ không hiện. Đánh số 01, 02… tự động.</p></div>
              <div className="adm-actions">
                {emptyContent ? (
                  <button type="button" className="adm-btn sm" onClick={() => setV((s) => ({ ...s, ...TEMPLATE }))}><Icon name="spark" size={14} /> Dùng mẫu</button>
                ) : null}
                <div className="job-seg" role="tablist" aria-label="Chế độ xem">
                  <button type="button" role="tab" aria-selected={!preview} className={!preview ? "on" : undefined} onClick={() => setPreview(false)}>Soạn</button>
                  <button type="button" role="tab" aria-selected={preview} className={preview ? "on" : undefined} onClick={() => setPreview(true)}>Xem trước</button>
                </div>
              </div>
            </div>
            <div className="bd" style={{ display: "grid", gap: 16 }}>
              {!preview ? (
                <div className="job-hint">
                  <b>Cách định dạng:</b> dòng bắt đầu <code>## </code> = tiêu đề nhóm · <code>- </code> = gạch đầu dòng · <code>1. </code> = danh sách số ·{" "}
                  <code>**chữ đậm**</code> · dòng trống = đoạn mới.
                </div>
              ) : null}
              {JOB_SECTIONS.map(([k, label], i) =>
                preview ? (
                  v[k].trim() ? (
                    <div key={k} className="job-prev">
                      <h3><span>{String(JOB_SECTIONS.filter(([x]) => v[x].trim()).findIndex(([x]) => x === k) + 1).padStart(2, "0")}</span>{label}</h3>
                      <RichText text={v[k]} />
                    </div>
                  ) : null
                ) : (
                  <Field key={k} label={`${String(i + 1).padStart(2, "0")}. ${label}`} error={errors[k]} full htmlFor={`j-${k}`}>
                    <textarea
                      id={`j-${k}`}
                      className="adm-input"
                      value={v[k]}
                      onChange={set(k)}
                      maxLength={20000}
                      placeholder={PLACEHOLDER[k]}
                      style={{ minHeight: k === "objective" ? 90 : 170 }}
                      aria-invalid={!!errors[k]}
                    />
                  </Field>
                ),
              )}
              {preview && emptyContent ? <p className="muted">Chưa có nội dung.</p> : null}
            </div>
          </section>
        </div>

        <div className="adm-grid" style={{ position: "sticky", top: 16, alignSelf: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Đăng bài</h2></div>
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              <Field label="Trạng thái" error={errors.status} htmlFor="j-status">
                <select id="j-status" className="adm-input" value={v.status} onChange={set("status")}>
                  {Object.entries(JOB_STATUS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </Field>
              <p className="muted" style={{ fontSize: 12.5, marginTop: -6 }}>
                {v.status === "draft"
                  ? "Bản nháp chưa hiện trên trang tuyển dụng."
                  : v.status === "published"
                    ? "Hiện trên /tuyen-dung và nhận hồ sơ tới hết hạn nộp."
                    : "Ẩn khỏi danh sách, link cũ vẫn mở được nhưng không nhận hồ sơ."}
              </p>
              <Field label="Email nhận hồ sơ (riêng cho bài này)" error={errors.apply_email} htmlFor="j-email">
                <input id="j-email" className="adm-input" type="email" value={v.apply_email} onChange={set("apply_email")} maxLength={200} placeholder={meta?.recruit_email || "tuyendung@congty.vn"} />
              </Field>
              <p className="muted" style={{ fontSize: 12.5, marginTop: -6 }}>
                {meta?.recruit_email ? <>Để trống = gửi về <b>{meta.recruit_email}</b>.</> : <>Chưa có email nhận hồ sơ mặc định — điền email ở đây hoặc cấu hình <code>LEADSCAN_RECRUIT_EMAIL</code>.</>}
              </p>
              <button className="adm-btn primary" type="submit" disabled={busy}>{busy ? "Đang lưu…" : submitLabel}</button>
            </div>
          </section>
        </div>
      </div>
    </form>
  );
}

/** Cảnh báo khi hồ sơ ứng viên chưa gửi được về email (thiếu cấu hình) */
export function MailWarning({ meta }: { meta: JobsMeta | null }) {
  if (!meta || (meta.recruit_email && meta.mail_ready && meta.storage_ready)) return null;
  return (
    <div className="adm-alert" style={{ marginBottom: 16 }}>
      {!meta.storage_ready ? (
        <>Chưa cấu hình Cloudflare R2 — form ứng tuyển tạm <b>chỉ nhận link CV</b> (chưa tải được file CV lên thư mục <code>CV/</code>).</>
      ) : !meta.mail_ready ? (
        <>Chưa cấu hình gửi email (Resend/SMTP) — hồ sơ ứng viên vẫn được lưu tại đây nhưng <b>chưa gửi được về hộp thư</b>.</>
      ) : (
        <>Chưa có email nhận hồ sơ mặc định. Đặt <code>LEADSCAN_RECRUIT_EMAIL</code> trên máy chủ, hoặc điền “Email nhận hồ sơ” trong từng bài.</>
      )}
    </div>
  );
}
