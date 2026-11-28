"use client";

import { type FormEvent, type ReactNode, useState } from "react";

import { RichText } from "@/components/careers/RichText";
import { errFields, errMsg } from "@/lib/admin/api";
import { EVENT_SECTIONS, EVENT_STATUS, type EventAdmin, type EventSectionKey, type EventsMeta } from "@/lib/events";

import { CoverImageField } from "./CoverImageField";
import { Field, Icon } from "./ui";

type Values = Record<string, string>;

const TEXT_KEYS = [
  "site", "title", "slug", "status", "subtitle", "summary", "host", "partner", "starts_at", "ends_at", "venue", "address",
  "deadline", "ticket_total", "tickets_sold", "cover_image", "banner_image", "fee_member", "fee_guest", "fee_note",
  "bank_bin", "bank_name", "account_no", "account_name", "contact_name", "contact_phone", "notify_email",
  ...EVENT_SECTIONS.map(([k]) => k),
] as const;

const PLACEHOLDER: Record<EventSectionKey, string> = {
  intro: "Tinh thần chương trình, thông tin chung (thời gian, địa điểm, thành phần, đầu mối), mục tiêu và kết quả mong đợi.",
  agenda: "- **14:30 – 15:00** · Đón khách, check-in\n- **15:00 – 15:10** · Khai mạc\n- …",
  content: "## Bên A chia sẻ\n- …\n\n## Bên B chia sẻ\n- …\n\n## Câu hỏi gợi ý\n1. …",
  matching: "## 1. Nhóm nhu cầu thứ nhất — đầu mối …\n- …\n\n## 2. Nhóm nhu cầu thứ hai\n- …",
  notes: "## Mốc chuẩn bị\n- …\n\n## Khi đăng ký, vui lòng\n- …\n\n## Liên hệ\n- …",
};

/** "2026-12-02T14:00:00" → "2026-12-02T14:00" cho ô <input type="datetime-local"> */
const toLocalInput = (v: string | null | undefined) => (v ? String(v).slice(0, 16) : "");

function initialValues(e?: EventAdmin): Values {
  const v: Values = {};
  for (const k of TEXT_KEYS) {
    const x = e?.[k as keyof EventAdmin];
    v[k] = x === null || x === undefined ? "" : String(x);
  }
  v.starts_at = toLocalInput(e?.starts_at);
  v.ends_at = toLocalInput(e?.ends_at);
  v.status ||= "draft";
  v.site ||= "leadscan";
  v.fee_member ||= "0";
  v.fee_guest ||= "0";
  v.tickets_sold ||= "0";
  return v;
}

const digits = (s: string) => s.replace(/\D/g, "");

export function EventForm({
  initial,
  meta,
  onSubmit,
  submitLabel,
}: {
  initial?: EventAdmin;
  meta: EventsMeta | null;
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
    const body: Record<string, unknown> = {
      ...v,
      starts_at: v.starts_at || null,
      ends_at: v.ends_at || null,
      deadline: v.deadline || null,
      ticket_total: digits(v.ticket_total) ? Number(digits(v.ticket_total)) : null,
      tickets_sold: Number(digits(v.tickets_sold) || 0),
      fee_member: Number(digits(v.fee_member) || 0),
      fee_guest: Number(digits(v.fee_guest) || 0),
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

  const input = (k: string, label: string, opts: { full?: boolean; max?: number; placeholder?: string; type?: string } = {}) => (
    <Field label={label} error={errors[k]} full={opts.full} htmlFor={`e-${k}`}>
      <input
        id={`e-${k}`}
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

  const bank = meta?.default_bank;
  const usingDefault = !v.bank_bin && !v.account_no && bank?.bank_bin && bank?.account_no;

  return (
    <form onSubmit={submit} noValidate className="adm-grid">
      {msg ? <div className="adm-alert">{msg}</div> : null}
      <div className="adm-grid side">
        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><div><h2>Thông tin sự kiện</h2><p className="muted" style={{ fontSize: 12.5 }}>Hiện ở thẻ danh sách và cột “Thông tin chung”</p></div></div>
            <div className="bd adm-form">
              {input("title", "Tên sự kiện *", { full: true, max: 200, placeholder: "VD: Business Matching CLB CEO1989 × Coolmate" })}
              <Field label="Đường dẫn" error={errors.slug} full htmlFor="e-slug">
                <div className="job-slug">
                  <span>/su-kien/</span>
                  <input id="e-slug" className="adm-input" value={v.slug} onChange={set("slug")} maxLength={160} placeholder="Để trống = tự tạo từ tên sự kiện" />
                </div>
              </Field>
              {input("subtitle", "Mô tả ngắn dưới tiêu đề", { full: true, max: 300, placeholder: "VD: Chia sẻ kinh nghiệm thực chiến trong vận hành, quản trị và mở rộng" })}
              <Field label="Tóm tắt trên thẻ danh sách" error={errors.summary} full htmlFor="e-summary">
                <textarea id="e-summary" className="adm-input" value={v.summary} onChange={set("summary")} maxLength={1000} rows={3} placeholder="1–2 câu mô tả sự kiện." />
              </Field>
              {input("host", "Đơn vị chủ trì", { max: 200, placeholder: "CLB CEO1989" })}
              {input("partner", "Đơn vị phối hợp / chủ nhà", { max: 200, placeholder: "Coolmate" })}
              {input("starts_at", "Bắt đầu (giờ Việt Nam)", { type: "datetime-local" })}
              {input("ends_at", "Kết thúc", { type: "datetime-local" })}
              {input("venue", "Địa điểm", { max: 200, placeholder: "Văn phòng Coolmate" })}
              {input("address", "Địa chỉ", { full: true, max: 300, placeholder: "Tòa nhà BMM, Km2 Đường Phùng Hưng, Hà Đông, Hà Nội" })}
              {input("deadline", "Hạn đăng ký", { type: "date" })}
              {input("contact_name", "Đầu mối liên hệ", { max: 120, placeholder: "Mr Phúc (CLB CEO1989)" })}
              {input("contact_phone", "Điện thoại đầu mối", { max: 20, placeholder: "0909802998" })}
            </div>
          </section>

          <section className="adm-card">
            <div className="hd">
              <div>
                <h2>Vé tham dự</h2>
                <p className="muted" style={{ fontSize: 12.5 }}>Trang sự kiện hiện Tổng người tham dự · Đã đăng ký · Còn lại. Hết chỗ thì tự đóng form.</p>
              </div>
            </div>
            <div className="bd adm-form">
              {input("ticket_total", "Tổng số vé (người)", { placeholder: "100 — để trống = không giới hạn" })}
              {input("tickets_sold", "Vé đã bán ngoài form", { placeholder: "0" })}
              <p className="muted" style={{ fontSize: 12.5, gridColumn: "1 / -1" }}>
                “Vé đã bán ngoài form” là vé bạn bán trực tiếp (chuyển khoản riêng, bán tại CLB…). Đã đăng ký = số này + đăng ký trên web chưa huỷ
                {initial?.tickets ? <> (hiện <b>{initial.tickets.web}</b> đăng ký trên web → tổng <b>{initial.tickets.registered}</b>{initial.tickets.remaining !== null ? <>, còn <b>{initial.tickets.remaining}</b> chỗ</> : null})</> : null}.
              </p>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><div><h2>Phí tham dự</h2><p className="muted" style={{ fontSize: 12.5 }}>Để 0 = miễn phí, hệ thống bỏ qua bước thanh toán</p></div></div>
            <div className="bd adm-form">
              {input("fee_member", "Phí thành viên CLB (đ)", { placeholder: "500000" })}
              {input("fee_guest", "Phí khách mời ngoài CLB (đ)", { placeholder: "600000" })}
              {input("fee_note", "Ghi chú về phí", { full: true, max: 300, placeholder: "VD: Đóng phí trước ngày 01/12 để ban tổ chức chốt danh sách." })}
            </div>
          </section>

          <section className="adm-card">
            <div className="hd">
              <div>
                <h2>Tài khoản nhận phí</h2>
                <p className="muted" style={{ fontSize: 12.5 }}>Dùng để sinh mã VietQR cho người đăng ký. Để trống = dùng tài khoản thu chung của hệ thống.</p>
              </div>
            </div>
            <div className="bd adm-form">
              {usingDefault ? (
                <div className="adm-field full">
                  <div className="adm-alert ok">Đang dùng tài khoản thu chung: <b>{bank?.bank_name || bank?.bank_bin}</b> – {bank?.account_no} ({bank?.account_name}).</div>
                </div>
              ) : null}
              {input("bank_bin", "Mã BIN ngân hàng (NAPAS)", { max: 10, placeholder: "970418 = BIDV · 970436 = Vietcombank" })}
              {input("bank_name", "Tên ngân hàng", { max: 100, placeholder: "BIDV" })}
              {input("account_no", "Số tài khoản", { max: 40, placeholder: "12010001234567" })}
              {input("account_name", "Chủ tài khoản", { max: 120, placeholder: "CLB CEO1989" })}
            </div>
          </section>

          <section className="adm-card">
            <div className="hd">
              <div>
                <h2>Nội dung trang sự kiện</h2>
                <p className="muted" style={{ fontSize: 12.5 }}>Định dạng nhẹ: <code>## tiêu đề nhỏ</code>, <code>- gạch đầu dòng</code>, <code>1. danh sách số</code>, <code>**chữ đậm**</code></p>
              </div>
              <button type="button" className="adm-btn sm" onClick={() => setPreview((p) => !p)}>
                <Icon name={preview ? "edit" : "note"} size={14} /> {preview ? "Soạn thảo" : "Xem trước"}
              </button>
            </div>
            <div className="bd adm-form">
              {EVENT_SECTIONS.map(([k, label]) => (
                <Field key={k} label={label} error={errors[k]} full htmlFor={`e-${k}`}>
                  {preview ? (
                    <div className="job-preview">{v[k].trim() ? <RichText text={v[k]} /> : <p className="muted">Chưa có nội dung.</p>}</div>
                  ) : (
                    <textarea id={`e-${k}`} className="adm-input" value={v[k]} onChange={set(k)} rows={k === "intro" ? 8 : 10} maxLength={20000} placeholder={PLACEHOLDER[k]} />
                  )}
                </Field>
              ))}
            </div>
          </section>
        </div>

        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><div><h2>Đăng bài</h2></div></div>
            <div className="bd adm-form">
              {meta?.scope === null ? (
                <Field label="Trang đăng" error={errors.site} full htmlFor="e-site">
                  <select id="e-site" className="adm-input" value={v.site} onChange={set("site")}>
                    {Object.entries(meta.sites).map(([k, s]) => <option key={k} value={k}>{s.name} — {s.url.replace(/^https?:\/\//, "")}</option>)}
                  </select>
                </Field>
              ) : null}
              <Field label="Trạng thái" error={errors.status} full htmlFor="e-status">
                <select id="e-status" className="adm-input" value={v.status} onChange={set("status")}>
                  {Object.entries(EVENT_STATUS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                </select>
              </Field>
              <p className="muted" style={{ fontSize: 12.5, gridColumn: "1 / -1" }}>
                {v.status === "published"
                  ? "Hiện trên /su-kien và nhận đăng ký tới hết hạn đăng ký."
                  : v.status === "closed"
                    ? "Giữ link cũ nhưng không nhận đăng ký mới."
                    : "Chỉ bạn xem được, chưa hiện trên trang web."}
              </p>
              {input("notify_email", "Email nhận đăng ký", { full: true, max: 200, placeholder: meta?.event_email || "Để trống = dùng email mặc định" })}
              <div className="adm-actions" style={{ gridColumn: "1 / -1" }}>
                <button className="adm-btn primary" type="submit" disabled={busy}>{busy ? "Đang lưu…" : submitLabel}</button>
              </div>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><div><h2>Ảnh</h2></div></div>
            <div className="bd adm-form">
              <CoverImageField
                value={v.cover_image}
                error={errors.cover_image}
                onChange={(url) => setV((s) => ({ ...s, cover_image: url }))}
                endpoint="/events/covers"
                label="Ảnh bìa / poster"
                hint="JPG, PNG, WebP. Hiện ở đầu trang, thẻ danh sách và khi chia sẻ link."
                id="e-cover_image"
                placeholder="Hoặc dán đường dẫn: /su-kien/ten-anh.webp hoặc https://…"
              />
              <CoverImageField
                value={v.banner_image}
                error={errors.banner_image}
                onChange={(url) => setV((s) => ({ ...s, banner_image: url }))}
                endpoint="/events/covers"
                label="Ảnh minh hoạ trong bài"
                hint="Chèn dưới mục “Khung nội dung chia sẻ”. Bỏ trống nếu không cần."
                id="e-banner_image"
                placeholder="Hoặc dán đường dẫn: /su-kien/ten-anh.webp hoặc https://…"
              />
            </div>
          </section>
        </div>
      </div>
    </form>
  );
}

/** Cảnh báo cấu hình còn thiếu (email, kho tệp R2, OCR) — hiện ở đầu các trang sự kiện của admin. */
export function EventWarning({ meta }: { meta: EventsMeta | null }) {
  // chỉ nhân viên LeadScan (trang tổng hợp) cần xem cảnh báo cấu hình máy chủ; ban tổ chức ở cổng không sửa được
  if (!meta || meta.scope !== null) return null;
  const items: ReactNode[] = [];
  if (!meta.storage_ready)
    items.push(<>Chưa cấu hình Cloudflare R2 — form đăng ký <b>chưa nhận được profile PDF và ảnh chuyển khoản</b>.</>);
  if (!meta.ocr_ready)
    items.push(<>Chưa đặt <code>OCR_SPACE_API_KEY</code> — ảnh chuyển khoản vào thẳng “Chờ đối soát” để bạn xác nhận thủ công.</>);
  if (!meta.mail_ready)
    items.push(<>Chưa cấu hình gửi email (Resend/SMTP) — đăng ký vẫn lưu tại đây nhưng <b>chưa gửi được email</b>.</>);
  else if (!meta.event_email)
    items.push(<>Chưa có email nhận đăng ký mặc định. Đặt <code>LEADSCAN_EVENT_EMAIL</code> trên máy chủ, hoặc điền “Email nhận đăng ký” trong từng sự kiện.</>);
  if (!items.length) return null;
  return (
    <div className="adm-alert" style={{ marginBottom: 16 }}>
      {items.map((x, i) => <div key={i}>{x}</div>)}
    </div>
  );
}
