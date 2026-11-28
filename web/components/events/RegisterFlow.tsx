"use client";

import QRCode from "qrcode";
import { type ChangeEvent, type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  ATTENDEE_TYPES,
  type EventPublic,
  type RegistrationState,
  fmtSize,
  fmtVnd,
} from "@/lib/events";

type Errors = Record<string, string>;

const FIELDS = ["full_name", "phone", "email", "company", "position", "attendee_type", "needs", "profile_file", "agree"];
const NEEDS_MAX = 5000;
const PDF_EXT = /\.pdf$/i;
const IMG_EXT = /\.(jpe?g|png|webp)$/i;

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

const storeKey = (slug: string) => `ls_event_${slug}`;

/** Đăng ký tham dự 3 bước: điền form → quét QR chuyển khoản → tải ảnh biên lai để đối soát. */
export default function RegisterFlow({ event: e }: { event: EventPublic }) {
  const [reg, setReg] = useState<RegistrationState | null>(null);
  const [loading, setLoading] = useState(true);
  const boxRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);

  // Quay lại trang (hoặc mở link ?ma=…) → lấy lại đơn đang dang dở để tiếp tục thanh toán
  useEffect(() => {
    const fromUrl = new URLSearchParams(location.search).get("ma");
    let code = fromUrl || "";
    if (!code) {
      try {
        code = localStorage.getItem(storeKey(e.slug)) ?? "";
      } catch {}
    }
    if (!code) return setLoading(false);
    fetch(`/api/events/registrations/${encodeURIComponent(code)}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: RegistrationState | null) => d && setReg(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [e.slug]);

  const onRegistered = useCallback(
    (state: RegistrationState) => {
      setReg(state);
      try {
        localStorage.setItem(storeKey(e.slug), state.code);
      } catch {}
    },
    [e.slug],
  );

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    boxRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [reg?.status, reg?.code]);

  function reset() {
    try {
      localStorage.removeItem(storeKey(e.slug));
    } catch {}
    setReg(null);
  }

  if (loading) return <div className="ev-step-note">Đang tải…</div>;

  return (
    <div ref={boxRef}>
      <Steps current={reg ? (reg.status === "new" ? 2 : 3) : 1} />
      {!reg ? (
        <RegisterForm event={e} onDone={onRegistered} />
      ) : (
        <PayPanel event={e} reg={reg} onChange={setReg} onReset={reset} />
      )}
    </div>
  );
}

function Steps({ current }: { current: number }) {
  const labels = ["Điền thông tin", "Chuyển khoản", "Xác nhận"];
  return (
    <ol className="ev-steps" aria-label="Các bước đăng ký">
      {labels.map((l, i) => {
        const n = i + 1;
        return (
          <li key={l} className={n < current ? "done" : n === current ? "on" : undefined} aria-current={n === current ? "step" : undefined}>
            <span className="n">{n < current ? "✓" : n}</span>
            {l}
          </li>
        );
      })}
    </ol>
  );
}

// ------------------------------------------------------------------ bước 1: form

function RegisterForm({ event: e, onDone }: { event: EventPublic; onDone: (s: RegistrationState) => void }) {
  const formRef = useRef<HTMLFormElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const startedAt = useRef(0);
  const [errors, setErrors] = useState<Errors>({});
  const [banner, setBanner] = useState("");
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState("member");
  const [needsLen, setNeedsLen] = useState(0);
  const maxMb = e.profile_max_mb || 10;

  useEffect(() => {
    startedAt.current = Date.now();
  }, []);

  function showErrors(er: Errors) {
    setErrors(er);
    const first = FIELDS.find((n) => er[n]);
    const el = first ? (formRef.current?.elements.namedItem(first === "profile_file" ? "needs" : first) as HTMLElement | null) : null;
    if (el) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      setTimeout(() => el.focus({ preventScroll: true }), 250);
    }
    return Boolean(first);
  }

  function clearError(ev: FormEvent<HTMLFormElement>) {
    const name = (ev.target as HTMLInputElement).name;
    if (name && errors[name]) setErrors(({ [name]: _, ...rest }) => rest);
  }

  function pickFile(ev: ChangeEvent<HTMLInputElement>) {
    const f = ev.target.files?.[0] ?? null;
    setErrors(({ profile_file: _a, ...rest }) => rest);
    if (f && !PDF_EXT.test(f.name)) {
      setErrors((er) => ({ ...er, profile_file: "Chỉ nhận file PDF." }));
      ev.target.value = "";
      return setFile(null);
    }
    if (f && f.size > maxMb * 1024 * 1024) {
      setErrors((er) => ({ ...er, profile_file: `Profile tối đa ${maxMb} MB.` }));
      ev.target.value = "";
      return setFile(null);
    }
    setFile(f);
  }

  async function onSubmit(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    const val = (n: string) => String(fd.get(n) ?? "").trim();
    setBanner("");

    const er: Errors = {};
    if (val("full_name").length < 2) er.full_name = "Vui lòng nhập họ và tên.";
    if (!/^(0|\+84)\d{9,10}$/.test(val("phone").replace(/[\s.\-()]/g, ""))) er.phone = "Số điện thoại chưa đúng định dạng.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(val("email"))) er.email = "Email chưa đúng định dạng.";
    if (val("needs").length < 10) er.needs = "Vui lòng mô tả nhu cầu xúc tiến hợp tác (ít nhất 10 ký tự).";
    if (fd.get("agree") === null) er.agree = "Bạn cần đồng ý để ban tổ chức xử lý thông tin đăng ký.";
    if (showErrors(er)) return;

    setBusy(true);
    try {
      const body = {
        full_name: val("full_name"),
        phone: val("phone"),
        email: val("email"),
        company: val("company"),
        position: val("position"),
        attendee_type: val("attendee_type") || "member",
        needs: val("needs"),
        profile_file: file ? { name: file.name, data: await readAsDataUrl(file) } : null,
        website_url: val("website_url"),
        elapsed_ms: Date.now() - startedAt.current,
      };
      const r = await fetch(`/api/events/${encodeURIComponent(e.slug)}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(90000),
      });
      let j: { ok?: boolean; message?: string; fields?: Errors } & Partial<RegistrationState> = {};
      try {
        j = await r.json();
      } catch {}
      if (r.ok && j.ok && j.code) {
        onDone(j as RegistrationState);
      } else {
        if (j.fields && Object.keys(j.fields).length) showErrors(j.fields);
        setBanner(j.message || (r.status === 413 ? `Profile tối đa ${maxMb} MB.` : "Chưa gửi được đăng ký, vui lòng thử lại."));
      }
    } catch {
      setBanner("Không kết nối được máy chủ. Kiểm tra mạng và thử lại.");
    } finally {
      setBusy(false);
    }
  }

  const err = (n: string) => (errors[n] ? <span className="err show" id={`${n}-err`}>{errors[n]}</span> : null);
  const aria = (n: string) => ({ "aria-invalid": Boolean(errors[n]), "aria-describedby": errors[n] ? `${n}-err` : undefined });
  const fee = kind === "guest" ? e.fee_guest : e.fee_member;

  return (
    <form ref={formRef} onSubmit={onSubmit} onInput={clearError} noValidate>
      <h3 className="cr-form-title">Đăng ký tham dự</h3>
      <p className="cr-form-sub">Các mục có dấu <span className="req">*</span> là bắt buộc. Nhu cầu bạn điền sẽ được ban tổ chức dùng để ghép cặp kết nối trước sự kiện.</p>
      {banner ? <div className="form-alert show" role="alert">{banner}</div> : null}

      <div className="fgrid">
        <div className="fld full">
          <label htmlFor="ev-name">Họ và tên <span className="req">*</span></label>
          <input id="ev-name" name="full_name" type="text" autoComplete="name" maxLength={100} placeholder="Nguyễn Văn A" {...aria("full_name")} />
          {err("full_name")}
        </div>
        <div className="fld">
          <label htmlFor="ev-phone">Số điện thoại <span className="req">*</span></label>
          <input id="ev-phone" name="phone" type="tel" autoComplete="tel" inputMode="tel" maxLength={20} placeholder="09xx xxx xxx" {...aria("phone")} />
          {err("phone")}
        </div>
        <div className="fld">
          <label htmlFor="ev-email">Email <span className="req">*</span></label>
          <input id="ev-email" name="email" type="email" autoComplete="email" maxLength={150} placeholder="ban@email.com" {...aria("email")} />
          {err("email")}
        </div>
        <div className="fld">
          <label htmlFor="ev-company">Doanh nghiệp <span className="opt-t">(không bắt buộc)</span></label>
          <input id="ev-company" name="company" type="text" autoComplete="organization" maxLength={200} placeholder="Công ty TNHH ABC" {...aria("company")} />
          {err("company")}
        </div>
        <div className="fld">
          <label htmlFor="ev-position">Chức vụ <span className="opt-t">(không bắt buộc)</span></label>
          <input id="ev-position" name="position" type="text" autoComplete="organization-title" maxLength={120} placeholder="Giám đốc" {...aria("position")} />
          {err("position")}
        </div>

        <div className="fld full">
          <span className="lbl">Hình thức tham dự <span className="req">*</span></span>
          <div className="ev-radios">
            {Object.entries(ATTENDEE_TYPES).map(([k, label]) => (
              <label key={k} className={kind === k ? "ev-radio on" : "ev-radio"}>
                <input type="radio" name="attendee_type" value={k} checked={kind === k} onChange={() => setKind(k)} />
                <span>
                  <b>{label}</b>
                  <small>{fmtVnd(k === "guest" ? e.fee_guest : e.fee_member)}/người</small>
                </span>
              </label>
            ))}
          </div>
          {err("attendee_type")}
        </div>

        <div className="fld full">
          <label htmlFor="ev-needs">Nhu cầu xúc tiến{e.partner ? ` với ${e.partner}` : " hợp tác"} <span className="req">*</span></label>
          <textarea
            id="ev-needs"
            name="needs"
            rows={5}
            maxLength={NEEDS_MAX}
            placeholder={`Bạn có thể cung cấp gì cho ${e.partner || "đối tác"} (sản phẩm, dịch vụ, năng lực) và muốn mua / hợp tác gì? Nêu càng cụ thể, ban tổ chức càng ghép cặp chính xác.`}
            onChange={(ev) => setNeedsLen(ev.target.value.length)}
            {...aria("needs")}
          />
          <span className="hint" style={{ textAlign: "right" }}>{needsLen}/{NEEDS_MAX}</span>
          {err("needs")}
        </div>

        {e.file_upload ? (
          <div className="fld full">
            <span className="lbl">Profile doanh nghiệp <span className="opt-t">(PDF – tối đa {maxMb} MB, không bắt buộc)</span></span>
            {file ? (
              <div className="cr-file">
                <svg className="icon"><use href="#i-clipboard" /></svg>
                <div><b>{file.name}</b><small>{fmtSize(file.size)}</small></div>
                <button type="button" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ""; }} aria-label="Bỏ file profile">Bỏ chọn</button>
              </div>
            ) : (
              <label className={errors.profile_file ? "cr-drop bad" : "cr-drop"}>
                <input ref={fileRef} type="file" name="profile_file_input" accept=".pdf,application/pdf" onChange={pickFile} />
                <svg className="icon"><use href="#i-plus" /></svg>
                <span><b>Đính kèm profile PDF</b> từ máy của bạn</span>
              </label>
            )}
            {err("profile_file")}
          </div>
        ) : null}
      </div>

      <div className="hp" aria-hidden="true">
        <label>Website<input type="text" name="website_url" tabIndex={-1} autoComplete="off" /></label>
      </div>

      <label className="agree">
        <input type="checkbox" name="agree" {...aria("agree")} />
        <span>Tôi đồng ý để ban tổ chức lưu trữ và sử dụng thông tin trên cho việc tổ chức và kết nối tại sự kiện.</span>
      </label>
      {err("agree")}

      <div className="form-actions">
        <button type="submit" className={busy ? "btn btn-primary loading" : "btn btn-primary"} disabled={busy}>
          <span className="spin" aria-hidden="true" />
          {busy ? "Đang gửi…" : fee > 0 ? `Đăng ký và lấy mã QR · ${fmtVnd(fee)}` : "Gửi đăng ký"}
        </button>
        <small>{fee > 0 ? "Bước tiếp theo: quét mã QR để chuyển phí tham dự." : "Sự kiện này không thu phí tham dự."}</small>
      </div>
    </form>
  );
}

// ------------------------------------------------------------------ bước 2 & 3: thanh toán và đối soát

function Copy({ label, value }: { label: string; value: string }) {
  const [done, setDone] = useState(false);
  if (!value) return null;
  return (
    <div className="ev-copy">
      <small>{label}</small>
      <b>{value}</b>
      <button
        type="button"
        onClick={() => {
          navigator.clipboard?.writeText(value).then(
            () => {
              setDone(true);
              setTimeout(() => setDone(false), 1800);
            },
            () => {},
          );
        }}
      >
        {done ? "Đã chép" : "Chép"}
      </button>
    </div>
  );
}

function PayPanel({
  event: e,
  reg,
  onChange,
  onReset,
}: {
  event: EventPublic;
  reg: RegistrationState;
  onChange: (s: RegistrationState) => void;
  onReset: () => void;
}) {
  const [qr, setQr] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState("");
  const [fieldErr, setFieldErr] = useState("");
  const imgRef = useRef<HTMLInputElement>(null);
  const p = reg.payment;
  const maxMb = e.proof_max_mb || 8;

  useEffect(() => {
    setQr("");
    if (p.qr_payload) QRCode.toDataURL(p.qr_payload, { width: 456, margin: 1, errorCorrectionLevel: "M" }).then(setQr, () => {});
  }, [p.qr_payload]);

  function pick(ev: ChangeEvent<HTMLInputElement>) {
    const f = ev.target.files?.[0] ?? null;
    setFieldErr("");
    if (f && !IMG_EXT.test(f.name)) {
      ev.target.value = "";
      setImage(null);
      return setFieldErr("Chỉ nhận ảnh JPG, PNG hoặc WEBP.");
    }
    if (f && f.size > maxMb * 1024 * 1024) {
      ev.target.value = "";
      setImage(null);
      return setFieldErr(`Ảnh tối đa ${maxMb} MB.`);
    }
    setImage(f);
  }

  async function send() {
    if (!image) return setFieldErr("Vui lòng chọn ảnh chụp màn hình giao dịch.");
    setBusy(true);
    setBanner("");
    setFieldErr("");
    try {
      const r = await fetch(`/api/events/registrations/${encodeURIComponent(reg.code)}/proof`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: { name: image.name, data: await readAsDataUrl(image) } }),
        signal: AbortSignal.timeout(120000),
      });
      let j: { ok?: boolean; message?: string; fields?: Errors } & Partial<RegistrationState> = {};
      try {
        j = await r.json();
      } catch {}
      if (r.ok && j.ok && j.code) {
        setImage(null);
        if (imgRef.current) imgRef.current.value = "";
        onChange(j as RegistrationState);
      } else {
        setFieldErr(j.fields?.image ?? "");
        setBanner(j.message || "Chưa gửi được ảnh, vui lòng thử lại.");
      }
    } catch {
      setBanner("Không kết nối được máy chủ. Kiểm tra mạng và thử lại.");
    } finally {
      setBusy(false);
    }
  }

  if (reg.status === "paid") {
    return (
      <div className="reg-done show" role="status">
        <div className="tick"><svg className="icon"><use href="#i-check" /></svg></div>
        <h3>Đã xác nhận đăng ký!</h3>
        <p>
          Cảm ơn <b>{reg.full_name}</b>. Đăng ký <b>{reg.code}</b> cho sự kiện <b>{e.title}</b> đã được ghi nhận
          {reg.amount > 0 ? <> và hệ thống đã đối soát đủ <b>{fmtVnd(reg.amount)}</b></> : null}. Thông tin xác nhận đã gửi tới <b>{reg.email}</b>.
        </p>
        <p className="ev-step-note">Hẹn gặp bạn tại {e.venue || "sự kiện"}{e.address ? ` – ${e.address}` : ""}.</p>
        <button type="button" className="btn btn-outline" onClick={onReset}>Đăng ký thêm người khác</button>
      </div>
    );
  }

  const waiting = reg.status === "review";

  return (
    <div className="ev-pay">
      <div className="ev-pay-hd">
        <div>
          <h3 className="cr-form-title">{waiting ? "Ban tổ chức đang đối soát" : "Chuyển khoản phí tham dự"}</h3>
          <p className="cr-form-sub">
            Mã đăng ký của bạn: <b className="ev-code">{reg.code}</b> · {ATTENDEE_TYPES[reg.attendee_type] ?? reg.attendee_type} ·{" "}
            <b>{fmtVnd(reg.amount)}</b>
          </p>
        </div>
      </div>

      {banner ? <div className="form-alert show" role="alert">{banner}</div> : null}
      {waiting ? (
        <div className="ev-note warn" role="status">
          <b>Đã nhận ảnh chuyển khoản.</b> {reg.ocr_message || "Ban tổ chức sẽ đối soát và xác nhận cho bạn."} Bạn có thể tải lại ảnh rõ hơn nếu cần.
        </div>
      ) : null}

      {!p.configured ? (
        <div className="ev-note warn">
          Ban tổ chức chưa công bố tài khoản nhận phí trên hệ thống. Vui lòng liên hệ{" "}
          {e.contact_name ? <b>{e.contact_name}</b> : "ban tổ chức"}
          {e.contact_phone ? <> – <a href={`tel:${e.contact_phone}`}>{e.contact_phone}</a></> : null} để được hướng dẫn chuyển khoản, giữ nguyên mã{" "}
          <b>{reg.code}</b>.
        </div>
      ) : (
        <div className="ev-pay-grid">
          <div className="ev-qr">
            {p.qr_payload ? (
              qr ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={qr} alt={`Mã VietQR chuyển ${fmtVnd(reg.amount)} tới ${p.account_name}`} />
              ) : (
                <div className="ev-qr-ph">Đang tạo mã QR…</div>
              )
            ) : (
              <div className="ev-qr-ph">Chuyển khoản theo thông tin bên cạnh</div>
            )}
            <span>Mở app ngân hàng → Quét mã QR</span>
          </div>
          <div className="ev-bank">
            <Copy label="Ngân hàng" value={p.bank_name || "—"} />
            <Copy label="Số tài khoản" value={p.account_no} />
            <Copy label="Chủ tài khoản" value={p.account_name} />
            <Copy label="Số tiền" value={String(reg.amount)} />
            <Copy label="Nội dung chuyển khoản" value={p.transfer_content} />
            <p className="ev-step-note">
              Giữ đúng nội dung <b>{p.transfer_content}</b> để hệ thống đối soát tự động. Quét mã QR thì nội dung và số tiền đã điền sẵn.
            </p>
          </div>
        </div>
      )}

      <div className="ev-upload">
        <h4>Tải ảnh chụp màn hình đã chuyển khoản</h4>
        <p className="cr-form-sub">
          {e.file_upload
            ? `Ảnh JPG, PNG hoặc WEBP, tối đa ${maxMb} MB. Hệ thống đọc chữ trong ảnh (OCR) và so khớp mã đăng ký cùng số tiền để xác nhận ngay.`
            : "Hệ thống chưa bật nhận ảnh. Vui lòng gửi ảnh chuyển khoản cho ban tổ chức qua điện thoại hoặc email."}
        </p>
        {e.file_upload ? (
          <>
            {image ? (
              <div className="cr-file">
                <svg className="icon"><use href="#i-camera" /></svg>
                <div><b>{image.name}</b><small>{fmtSize(image.size)}</small></div>
                <button type="button" onClick={() => { setImage(null); if (imgRef.current) imgRef.current.value = ""; }} aria-label="Bỏ ảnh đã chọn">Bỏ chọn</button>
              </div>
            ) : (
              <label className={fieldErr ? "cr-drop bad" : "cr-drop"}>
                <input ref={imgRef} type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" onChange={pick} />
                <svg className="icon"><use href="#i-plus" /></svg>
                <span><b>Chọn ảnh biên lai</b> từ máy hoặc điện thoại</span>
              </label>
            )}
            {fieldErr ? <span className="err show">{fieldErr}</span> : null}
            <div className="form-actions">
              <button type="button" className={busy ? "btn btn-primary loading" : "btn btn-primary"} disabled={busy || !image} onClick={send}>
                <span className="spin" aria-hidden="true" />
                {busy ? "Đang kiểm tra ảnh…" : waiting ? "Gửi lại ảnh" : "Gửi ảnh và xác nhận"}
              </button>
              <small>Chưa chuyển khoản? Bạn có thể quay lại trang này bất cứ lúc nào để tiếp tục.</small>
            </div>
          </>
        ) : null}
        <button type="button" className="ev-link-btn" onClick={onReset}>Đăng ký cho người khác</button>
      </div>
    </div>
  );
}
