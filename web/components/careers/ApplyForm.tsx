"use client";

import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { fmtSize } from "@/lib/careers";

type Errors = Record<string, string>;
const FIELDS = ["full_name", "phone", "email", "cv_url", "cv_file", "portfolio_url", "intro", "agree"];
const CV_EXT = /\.(pdf|docx?)$/i;
const INTRO_MAX = 3000;

function validUrl(v: string) {
  return /^(https?:\/\/)?[^\s/]+\.[^\s/]+(\/\S*)?$/i.test(v);
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

export default function ApplyForm({
  slug,
  title,
  maxMb = 5,
  allowFile = true,
}: {
  slug: string;
  title: string;
  maxMb?: number;
  allowFile?: boolean; // false khi máy chủ chưa cấu hình kho lưu CV (Cloudflare R2) → chỉ nhận link CV
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const doneRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const startedAt = useRef(0);
  const [errors, setErrors] = useState<Errors>({});
  const [banner, setBanner] = useState("");
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [introLen, setIntroLen] = useState(0);
  const [done, setDone] = useState<{ name: string; email: string } | null>(null);

  useEffect(() => {
    startedAt.current = Date.now();
  }, []);

  useEffect(() => {
    if (!done) return;
    doneRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    doneRef.current?.focus({ preventScroll: true });
  }, [done]);

  function showErrors(er: Errors) {
    setErrors(er);
    const first = FIELDS.find((n) => er[n]);
    const el = first ? (formRef.current?.elements.namedItem(first === "cv_file" ? "cv_url" : first) as HTMLElement | null) : null;
    if (el) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      setTimeout(() => el.focus({ preventScroll: true }), 250);
    }
    return Boolean(first);
  }

  function clearError(e: FormEvent<HTMLFormElement>) {
    const name = (e.target as HTMLInputElement).name;
    if (name && errors[name]) setErrors(({ [name]: _, ...rest }) => rest);
  }

  function pickFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setErrors(({ cv_file: _a, cv_url: _b, ...rest }) => rest);
    if (f && !CV_EXT.test(f.name)) {
      setErrors((er) => ({ ...er, cv_file: "Chỉ nhận file PDF, DOC hoặc DOCX." }));
      e.target.value = "";
      return setFile(null);
    }
    if (f && f.size > maxMb * 1024 * 1024) {
      setErrors((er) => ({ ...er, cv_file: `File CV tối đa ${maxMb} MB.` }));
      e.target.value = "";
      return setFile(null);
    }
    setFile(f);
  }

  function removeFile() {
    setFile(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const val = (n: string) => String(fd.get(n) ?? "").trim();
    setBanner("");

    const er: Errors = {};
    if (val("full_name").length < 2) er.full_name = "Vui lòng nhập họ và tên.";
    if (!/^(0|\+84)\d{9,10}$/.test(val("phone").replace(/[\s.\-()]/g, ""))) er.phone = "Số điện thoại chưa đúng định dạng.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(val("email"))) er.email = "Email chưa đúng định dạng.";
    if (!val("cv_url") && !file) er.cv_url = allowFile ? "Vui lòng gửi link CV hoặc tải file CV lên." : "Vui lòng gửi link CV.";
    else if (val("cv_url") && !validUrl(val("cv_url"))) er.cv_url = "Link CV chưa đúng định dạng.";
    if (val("portfolio_url") && !validUrl(val("portfolio_url"))) er.portfolio_url = "Đường dẫn chưa đúng định dạng.";
    if (fd.get("agree") === null) er.agree = "Bạn cần đồng ý để LeadScan xử lý hồ sơ.";
    if (showErrors(er)) return;

    setBusy(true);
    try {
      const body = {
        full_name: val("full_name"),
        phone: val("phone"),
        email: val("email"),
        cv_url: val("cv_url"),
        portfolio_url: val("portfolio_url"),
        intro: val("intro"),
        cv_file: file ? { name: file.name, data: await readAsDataUrl(file) } : null,
        website_url: val("website_url"),
        elapsed_ms: Date.now() - startedAt.current,
      };
      const r = await fetch(`/api/jobs/${encodeURIComponent(slug)}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(60000),
      });
      let j: { ok?: boolean; message?: string; fields?: Errors } = {};
      try {
        j = await r.json();
      } catch {}
      if (r.ok && j.ok) {
        setDone({ name: body.full_name, email: body.email });
      } else {
        if (j.fields && Object.keys(j.fields).length) showErrors(j.fields);
        setBanner(j.message || (r.status === 413 ? `File CV tối đa ${maxMb} MB.` : "Chưa gửi được hồ sơ, vui lòng thử lại."));
      }
    } catch {
      setBanner("Không kết nối được máy chủ. Kiểm tra mạng và thử lại.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="reg-done show" ref={doneRef} tabIndex={-1} role="status">
        <div className="tick"><svg className="icon"><use href="#i-check" /></svg></div>
        <h3>Đã gửi hồ sơ!</h3>
        <p>
          Cảm ơn <b>{done.name}</b> đã ứng tuyển vị trí <b>{title}</b>. LeadScan đã gửi email xác nhận tới <b>{done.email}</b> và sẽ
          liên hệ trong 3–5 ngày làm việc nếu hồ sơ phù hợp.
        </p>
        <a href="/tuyen-dung#vi-tri" className="btn btn-outline">Xem vị trí khác</a>
      </div>
    );
  }

  const err = (n: string) => (errors[n] ? <span className="err show" id={`${n}-err`}>{errors[n]}</span> : null);
  const aria = (n: string) => ({ "aria-invalid": Boolean(errors[n]), "aria-describedby": errors[n] ? `${n}-err` : undefined });

  return (
    <form ref={formRef} onSubmit={onSubmit} onInput={clearError} noValidate>
      <h3 className="cr-form-title">Ứng tuyển {title}</h3>
      <p className="cr-form-sub">Điền thông tin và gửi CV của bạn. Các mục có dấu <span className="req">*</span> là bắt buộc.</p>
      {banner ? <div className="form-alert show" role="alert">{banner}</div> : null}

      <div className="fgrid">
        <div className="fld full">
          <label htmlFor="ap-name">Họ và tên <span className="req">*</span></label>
          <input id="ap-name" name="full_name" type="text" autoComplete="name" maxLength={100} placeholder="Nguyễn Văn A" {...aria("full_name")} />
          {err("full_name")}
        </div>
        <div className="fld">
          <label htmlFor="ap-phone">Số điện thoại <span className="req">*</span></label>
          <input id="ap-phone" name="phone" type="tel" autoComplete="tel" inputMode="tel" maxLength={20} placeholder="09xx xxx xxx" {...aria("phone")} />
          {err("phone")}
        </div>
        <div className="fld">
          <label htmlFor="ap-email">Email <span className="req">*</span></label>
          <input id="ap-email" name="email" type="email" autoComplete="email" maxLength={150} placeholder="ban@email.com" {...aria("email")} />
          {err("email")}
        </div>

        <div className="fld full">
          <label htmlFor="ap-cv">Link CV <span className="req">*</span></label>
          <input id="ap-cv" name="cv_url" type="url" maxLength={500} placeholder="https://drive.google.com/…" {...aria("cv_url")} />
          <span className="hint">Link Google Drive / OneDrive – bật quyền xem “Bất kỳ ai có đường liên kết”.{allowFile ? " Hoặc tải file CV bên dưới." : ""}</span>
          {err("cv_url")}
        </div>

        {allowFile ? <div className="fld full">
          <span className="lbl">File CV <span className="opt-t">(PDF, DOC, DOCX – tối đa {maxMb} MB)</span></span>
          {file ? (
            <div className="cr-file">
              <svg className="icon"><use href="#i-clipboard" /></svg>
              <div><b>{file.name}</b><small>{fmtSize(file.size)}</small></div>
              <button type="button" onClick={removeFile} aria-label="Bỏ file CV">Bỏ chọn</button>
            </div>
          ) : (
            <label className={errors.cv_file ? "cr-drop bad" : "cr-drop"}>
              <input ref={fileRef} type="file" name="cv_file_input" accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={pickFile} />
              <svg className="icon"><use href="#i-plus" /></svg>
              <span><b>Chọn file CV</b> từ máy của bạn</span>
            </label>
          )}
          {err("cv_file")}
        </div> : null}

        <div className="fld full">
          <label htmlFor="ap-pf">Link Portfolio / sản phẩm <span className="opt-t">(không bắt buộc)</span></label>
          <input id="ap-pf" name="portfolio_url" type="url" maxLength={500} placeholder="https://…" {...aria("portfolio_url")} />
          {err("portfolio_url")}
        </div>

        <div className="fld full">
          <label htmlFor="ap-intro">Giới thiệu ngắn <span className="opt-t">(không bắt buộc)</span></label>
          <textarea
            id="ap-intro"
            name="intro"
            rows={4}
            maxLength={INTRO_MAX}
            placeholder="Kinh nghiệm nổi bật, lý do bạn phù hợp với vị trí, thời gian có thể bắt đầu…"
            onChange={(e) => setIntroLen(e.target.value.length)}
          />
          <span className="hint" style={{ textAlign: "right" }}>{introLen}/{INTRO_MAX}</span>
        </div>
      </div>

      <div className="hp" aria-hidden="true">
        <label>Website<input type="text" name="website_url" tabIndex={-1} autoComplete="off" /></label>
      </div>

      <label className="agree">
        <input type="checkbox" name="agree" {...aria("agree")} />
        <span>Tôi đồng ý để LeadScan lưu trữ và sử dụng thông tin trên cho mục đích tuyển dụng.</span>
      </label>
      {err("agree")}

      <div className="form-actions">
        <button type="submit" className={busy ? "btn btn-primary loading" : "btn btn-primary"} disabled={busy}>
          <span className="spin" aria-hidden="true" />
          {busy ? "Đang gửi…" : "Gửi hồ sơ ứng tuyển"}
        </button>
        <small>Hồ sơ được gửi trực tiếp tới bộ phận tuyển dụng LeadScan.</small>
      </div>
    </form>
  );
}
