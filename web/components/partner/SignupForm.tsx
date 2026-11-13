"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import { lookupBusiness, normalizeTaxCode } from "@/lib/business-lookup";

type Errors = Record<string, string>;

// Khớp INDUSTRIES / AREAS ở backend/app/registration_form.py (dùng chung danh mục với cổng thành viên)
const INDUSTRIES = [
  "Sản xuất công nghiệp", "Bao bì & in ấn", "Nhựa & cao su", "Điện tử & linh kiện", "Cơ khí & máy móc",
  "Hoá chất & vật tư", "Dệt may & da giày", "Xuất nhập khẩu", "Thương mại & phân phối", "Logistics & vận tải",
  "Xây dựng & vật liệu", "Thực phẩm & đồ uống", "Nông sản & thuỷ sản", "Dịch vụ B2B", "Công nghệ thông tin",
];
const REGIONS = [
  "Toàn quốc", "Miền Bắc", "Miền Trung", "Miền Nam", "Hà Nội", "TP. Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Bắc Ninh",
  "Bắc Giang", "Hải Dương", "Hưng Yên", "Vĩnh Phúc", "Thái Nguyên", "Quảng Ninh", "Đồng Nai", "Bình Dương", "Long An",
  "Bà Rịa - Vũng Tàu", "Cần Thơ",
];
const ORDER = ["full_name", "phone", "email", "password", "kind", "org_name", "org_tax_code", "agree"];

function validate(f: FormData, kind: string): Errors {
  const v = (n: string) => String(f.get(n) ?? "").trim();
  const e: Errors = {};
  if (v("full_name").length < 2) e.full_name = "Vui lòng nhập họ và tên.";
  if (!/^(0|\+?84)\d{9,10}$/.test(v("phone").replace(/[\s.\-()]/g, ""))) e.phone = "Số điện thoại chưa đúng định dạng.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v("email"))) e.email = "Email chưa đúng định dạng.";
  if (String(f.get("password") ?? "").length < 8) e.password = "Mật khẩu cần ít nhất 8 ký tự.";
  if (!kind) e.kind = "Vui lòng chọn Cá nhân hoặc Tổ chức.";
  if (kind === "org") {
    if (!v("org_name")) e.org_name = "Vui lòng nhập tên tổ chức.";
    if (!normalizeTaxCode(v("org_tax_code"))) e.org_tax_code = "Mã số thuế gồm 10 hoặc 13 chữ số.";
  }
  if (f.get("agree") === null) e.agree = "Bạn cần đồng ý Điều khoản đối tác và Chính sách bảo mật.";
  return e;
}

/** Form đăng ký đối tác — 7 trường (brief mục 7.2). Thành công → đã đăng nhập, chuyển sang bước nhập mã OTP gửi qua email. */
export default function SignupForm() {
  const formRef = useRef<HTMLFormElement>(null);
  const startedAt = useRef(0);
  const [kind, setKind] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [banner, setBanner] = useState("");
  const [busy, setBusy] = useState(false);
  const [taxNote, setTaxNote] = useState("");

  useEffect(() => {
    startedAt.current = Date.now();
  }, []);

  function showErrors(er: Errors) {
    setErrors(er);
    const first = ORDER.find((n) => er[n]);
    const el = first ? (formRef.current?.querySelector<HTMLElement>(`[name="${first}"]`) ?? null) : null;
    if (el) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      setTimeout(() => el.focus({ preventScroll: true }), 250);
    }
  }

  function clearError(e: FormEvent<HTMLFormElement>) {
    const name = (e.target as HTMLInputElement).name;
    if (name && errors[name]) setErrors(({ [name]: _, ...rest }) => rest);
  }

  async function lookupOrg() {
    const el = formRef.current?.elements.namedItem("org_tax_code") as HTMLInputElement | null;
    const tax = normalizeTaxCode(el?.value ?? "");
    if (!tax) return setTaxNote("Mã số thuế gồm 10 hoặc 13 chữ số.");
    setTaxNote("Đang tra cứu…");
    const r = await lookupBusiness(tax);
    if (r.ok) {
      const name = formRef.current?.elements.namedItem("org_name") as HTMLInputElement | null;
      if (name) name.value = r.data.name;
      setErrors(({ org_name: _a, org_tax_code: _b, ...rest }) => rest);
      setTaxNote(`Đã điền tên: ${r.data.name}`);
    } else setTaxNote(r.message);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBanner("");
    const f = new FormData(e.currentTarget);
    const er = validate(f, kind);
    if (Object.keys(er).length) return showErrors(er);
    const v = (n: string) => String(f.get(n) ?? "").trim();
    const body = {
      full_name: v("full_name"), phone: v("phone"), email: v("email"), password: String(f.get("password") ?? ""),
      kind, org_name: v("org_name"), org_tax_code: v("org_tax_code"),
      industries: f.getAll("industries").map(String), regions: f.getAll("regions").map(String),
      agree: true, website_url: v("website_url"), elapsed_ms: Date.now() - startedAt.current,
    };
    setBusy(true);
    try {
      const r = await fetch("/api/partner/auth/register", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      let j: { detail?: string; fields?: Errors } = {};
      try {
        j = await r.json();
      } catch {}
      if (r.ok) {
        location.href = "/doi-tac/xac-thuc";
        return;
      }
      if (j.fields && Object.keys(j.fields).length) showErrors(j.fields);
      setBanner(j.detail || "Không gửi được đăng ký. Vui lòng thử lại sau ít phút.");
    } catch {
      setBanner("Không kết nối được máy chủ. Vui lòng kiểm tra mạng và thử lại.");
    }
    setBusy(false);
  }

  const inv = (n: string) => (errors[n] ? { "aria-invalid": true as const, "aria-describedby": `pe_${n}` } : {});
  const err = (n: string) => <span className={errors[n] ? "err show" : "err"} id={`pe_${n}`}>{errors[n] ?? ""}</span>;

  return (
    <form ref={formRef} noValidate onSubmit={onSubmit} onInput={clearError} onChange={clearError} className="ptl-form">
      <div className={banner ? "form-alert show" : "form-alert"} role="alert">{banner}</div>

      <div className="fgrid">
        <div className="fld full">
          <label htmlFor="p_full_name">Họ và tên <span className="req">*</span></label>
          <input type="text" id="p_full_name" name="full_name" maxLength={100} autoComplete="name" placeholder="Nguyễn Văn A" {...inv("full_name")} />
          {err("full_name")}
        </div>
        <div className="fld">
          <label htmlFor="p_phone">Điện thoại / Zalo <span className="req">*</span></label>
          <input type="tel" id="p_phone" name="phone" maxLength={20} autoComplete="tel" placeholder="0901 234 567" {...inv("phone")} />
          {err("phone")}
        </div>
        <div className="fld">
          <label htmlFor="p_email">Email <span className="req">*</span> <span className="opt-t">(dùng để đăng nhập)</span></label>
          <input type="email" id="p_email" name="email" maxLength={150} autoComplete="email" placeholder="ten@email.com" {...inv("email")} />
          {err("email")}
        </div>
        <div className="fld full">
          <label htmlFor="p_password">Mật khẩu <span className="req">*</span></label>
          <input type="password" id="p_password" name="password" maxLength={200} autoComplete="new-password" placeholder="Tối thiểu 8 ký tự" {...inv("password")} />
          {err("password")}
          <span className="hint">Đã là thành viên LeadScan? Nhập đúng email và mật khẩu đang dùng — 1 tài khoản cho cả 2 cổng.</span>
        </div>

        <div className="fld full">
          <span className="lbl" id="p_l_kind">Bạn là <span className="req">*</span></span>
          <div className="ptl-seg" role="radiogroup" aria-labelledby="p_l_kind" {...(errors.kind ? { "aria-describedby": "pe_kind" } : {})}>
            {[["personal", "Cá nhân"], ["org", "Tổ chức"]].map(([k, label]) => (
              <label key={k} className={kind === k ? "on" : undefined}>
                <input type="radio" name="kind" value={k} checked={kind === k} onChange={() => setKind(k)} />
                {label}
              </label>
            ))}
          </div>
          {err("kind")}
        </div>
        {kind === "org" ? (
          <>
            <div className="fld">
              <label htmlFor="p_org_tax_code">Mã số thuế tổ chức <span className="req">*</span></label>
              <div className="tax-row">
                <input type="text" id="p_org_tax_code" name="org_tax_code" inputMode="numeric" maxLength={14} placeholder="10 hoặc 13 chữ số" {...inv("org_tax_code")} />
                <button type="button" className="btn btn-outline" onClick={lookupOrg}>Tra cứu</button>
              </div>
              {err("org_tax_code")}
              {taxNote ? <span className="tax-note" role="status">{taxNote}</span> : null}
            </div>
            <div className="fld">
              <label htmlFor="p_org_name">Tên tổ chức <span className="req">*</span></label>
              <input type="text" id="p_org_name" name="org_name" maxLength={200} autoComplete="organization" placeholder="Hiệp hội / Công ty…" {...inv("org_name")} />
              {err("org_name")}
            </div>
          </>
        ) : null}

        <details className="fld full ptl-more">
          <summary>Ngành, khu vực bạn hay tiếp xúc <span className="opt-t">(không bắt buộc — giúp gợi ý loại cơ hội)</span></summary>
          <span className="lbl">Ngành hàng</span>
          <div className="checks">
            {INDUSTRIES.map((x) => (
              <label key={x}><input type="checkbox" name="industries" value={x} /><span>{x}</span></label>
            ))}
          </div>
          <span className="lbl" style={{ marginTop: 10 }}>Khu vực</span>
          <div className="checks">
            {REGIONS.map((x) => (
              <label key={x}><input type="checkbox" name="regions" value={x} /><span>{x}</span></label>
            ))}
          </div>
        </details>
      </div>

      <div className="hp" aria-hidden="true"><label>Để trống<input type="text" name="website_url" tabIndex={-1} autoComplete="off" /></label></div>

      <label className="agree">
        <input type="checkbox" name="agree" {...inv("agree")} />
        <span>Tôi đồng ý với <a href="/doi-tac/dieu-khoan" target="_blank">Điều khoản đối tác</a> và <a href="/doi-tac/dieu-khoan#bao-mat" target="_blank">Chính sách bảo mật</a> của LeadScan.</span>
      </label>
      {err("agree")}

      <div className="form-actions">
        <button type="submit" className={busy ? "btn btn-primary loading" : "btn btn-primary"} disabled={busy}>
          <span className="spin" aria-hidden="true"></span>
          <span>{busy ? "Đang gửi…" : "Đăng ký đối tác"}</span>
        </button>
        <small>Miễn phí. Sau khi đăng ký, nhập mã OTP gửi tới email của bạn để kích hoạt tài khoản. Không hỏi CCCD hay tài khoản ngân hàng ở bước này.</small>
      </div>
    </form>
  );
}
