"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { type BusinessInfo, lookupBusiness, normalizeTaxCode } from "@/lib/business-lookup";

type Errors = Record<string, string>;
type Lookup =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ok"; info: BusinessInfo }
  | { state: "error"; message: string };

const REQUIRED: Record<string, string> = {
  company_name: "Vui lòng nhập tên doanh nghiệp.",
  province: "Vui lòng nhập tỉnh/thành.",
  contact_name: "Vui lòng nhập họ tên người liên hệ.",
};
// Thứ tự dùng để cuộn tới lỗi đầu tiên
const FIELDS = [
  "tax_code", "company_name", "industries", "company_size", "province", "website",
  "contact_name", "email", "phone", "password", "password_confirm", "agree",
];
// Ngành hàng gợi ý — khớp INDUSTRIES ở backend/app/registration_form.py
const INDUSTRIES = [
  "Sản xuất công nghiệp", "Bao bì & in ấn", "Nhựa & cao su", "Điện tử & linh kiện", "Cơ khí & máy móc",
  "Hoá chất & vật tư", "Dệt may & da giày", "Xuất nhập khẩu", "Thương mại & phân phối", "Logistics & vận tải",
  "Xây dựng & vật liệu", "Thực phẩm & đồ uống", "Nông sản & thuỷ sản", "Dịch vụ B2B", "Công nghệ thông tin",
];
const MAX_INDUSTRIES = 8;

/** Ngành đã tích + ngành tự nhập (cách nhau dấu phẩy), bỏ trùng */
function pickIndustries(form: HTMLFormElement): string[] {
  const { val, all } = readForm(form);
  const out: string[] = [];
  for (const x of [...all("industries"), ...val("industry_other").split(",")]) {
    const v = x.trim();
    if (v && !out.some((o) => o.toLowerCase() === v.toLowerCase())) out.push(v);
  }
  return out;
}

function readForm(form: HTMLFormElement) {
  const fd = new FormData(form);
  const val = (n: string) => String(fd.get(n) ?? "").trim();
  const all = (n: string) => fd.getAll(n).map(String);
  return { val, all, agree: fd.get("agree") !== null };
}

function validate(form: HTMLFormElement): Errors {
  const { val, agree } = readForm(form);
  const er: Errors = {};
  for (const [n, msg] of Object.entries(REQUIRED)) if (!val(n)) er[n] = msg;
  const inds = pickIndustries(form);
  if (!inds.length) er.industries = "Vui lòng chọn ít nhất 1 ngành hàng.";
  else if (inds.length > MAX_INDUSTRIES) er.industries = `Chọn tối đa ${MAX_INDUSTRIES} ngành hàng.`;
  if (!val("company_size")) er.company_size = "Vui lòng chọn quy mô.";
  if (!/^\d{10}(-?\d{3})?$/.test(val("tax_code").replace(/[^\d-]/g, ""))) er.tax_code = "Mã số thuế gồm 10 hoặc 13 chữ số.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(val("email"))) er.email = "Email chưa đúng định dạng.";
  if (!/^(0|\+84)\d{9,10}$/.test(val("phone").replace(/[\s.\-()]/g, ""))) er.phone = "Số điện thoại chưa đúng định dạng.";
  const pw = String(new FormData(form).get("password") ?? "");
  if (pw.length < 8) er.password = "Mật khẩu cần ít nhất 8 ký tự.";
  else if (String(new FormData(form).get("password_confirm") ?? "") !== pw) er.password_confirm = "Mật khẩu nhập lại không khớp.";
  const w = val("website");
  if (w && !/^(https?:\/\/)?([\w-]+\.)+[a-z]{2,}(\/.*)?$/i.test(w)) er.website = "Website chưa đúng định dạng.";
  if (!agree) er.agree = "Bạn cần đồng ý điều khoản để tiếp tục.";
  return er;
}

export default function RegisterForm() {
  const formRef = useRef<HTMLFormElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const doneRef = useRef<HTMLDivElement>(null);
  const startedAt = useRef(0);
  const [errors, setErrors] = useState<Errors>({});
  const [banner, setBanner] = useState("");
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState<string | null>(null);
  const [loggedIn, setLoggedIn] = useState(false);
  const [lookup, setLookup] = useState<Lookup>({ state: "idle" });
  const lookupCtl = useRef<AbortController | null>(null);
  const lookupTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastLooked = useRef(""); // MST đã tra gần nhất — tránh gọi lại khi gõ thêm ký tự không đổi giá trị

  useEffect(() => {
    startedAt.current = Date.now();
    return () => {
      lookupCtl.current?.abort();
      if (lookupTimer.current) clearTimeout(lookupTimer.current);
    };
  }, []);

  /** Điền tên, địa chỉ, tỉnh/thành từ kết quả tra MST vào các ô tương ứng */
  function fillFromBusiness(info: BusinessInfo) {
    const form = formRef.current;
    if (!form) return;
    const set = (name: string, value: string) => {
      const el = form.elements.namedItem(name) as HTMLInputElement | null;
      if (el && value) el.value = value;
    };
    set("company_name", info.name);
    set("address", info.address);
    set("province", info.province);
    setErrors(({ company_name: _a, province: _p, tax_code: _t, ...rest }) => rest);
  }

  async function runLookup(raw: string, force = false) {
    const tax = normalizeTaxCode(raw);
    if (!tax) {
      if (force) setLookup({ state: "error", message: "Mã số thuế gồm 10 hoặc 13 chữ số." });
      return;
    }
    if (!force && tax === lastLooked.current) return;
    lastLooked.current = tax;
    lookupCtl.current?.abort();
    const ctl = new AbortController();
    lookupCtl.current = ctl;
    setLookup({ state: "loading" });
    try {
      const r = await lookupBusiness(tax, ctl.signal);
      if (ctl.signal.aborted) return;
      if (r.ok) {
        fillFromBusiness(r.data);
        setLookup({ state: "ok", info: r.data });
      } else {
        if (r.reason === "rate_limited" || r.reason === "network") lastLooked.current = ""; // cho phép thử lại
        setLookup({ state: "error", message: r.message });
      }
    } catch {
      // bị huỷ do người dùng gõ tiếp — bỏ qua
    }
  }

  // Tự tra cứu khi người dùng nhập đủ 10/13 số (chờ ngừng gõ 600ms)
  function onTaxInput(raw: string) {
    if (lookupTimer.current) clearTimeout(lookupTimer.current);
    if (!normalizeTaxCode(raw)) {
      lookupCtl.current?.abort();
      lastLooked.current = "";
      setLookup({ state: "idle" });
      return;
    }
    lookupTimer.current = setTimeout(() => runLookup(raw), 600);
  }

  useEffect(() => {
    if (banner) alertRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [banner]);

  useEffect(() => {
    if (!code) return;
    doneRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    doneRef.current?.focus({ preventScroll: true });
  }, [code]);

  function showErrors(er: Errors): boolean {
    setErrors(er);
    const first = FIELDS.find((n) => er[n]);
    const el = first ? (formRef.current?.elements.namedItem(first) as HTMLElement | null) : null;
    if (el) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      setTimeout(() => el.focus({ preventScroll: true }), 250);
    }
    return Boolean(first);
  }

  // Xoá lỗi của ô khi người dùng sửa
  function clearError(e: FormEvent<HTMLFormElement>) {
    let name = (e.target as HTMLInputElement).name;
    if (name === "industry_other") name = "industries";
    if (name && errors[name]) setErrors(({ [name]: _, ...rest }) => rest);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBanner("");
    if (showErrors(validate(form))) return;

    const { val } = readForm(form);
    const body = {
      company_name: val("company_name"), tax_code: val("tax_code"), industries: pickIndustries(form),
      company_size: val("company_size"), province: val("province"), address: val("address"),
      website: val("website"), contact_name: val("contact_name"), position: val("position"),
      email: val("email"), phone: val("phone"),
      agree: true, website_url: val("website_url"), elapsed_ms: Date.now() - startedAt.current,
      password: String(new FormData(form).get("password") ?? ""),
      password_confirm: String(new FormData(form).get("password_confirm") ?? ""),
    };

    setBusy(true);
    try {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), 30000);
      const r = await fetch("/api/registrations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ctl.signal,
      });
      clearTimeout(timer);
      let j: { ok?: boolean; code?: string; message?: string; fields?: Errors } = {};
      try {
        j = await r.json();
      } catch {}
      if (r.ok && j.ok && j.code) {
        // Đăng nhập luôn để khách vào cổng thành viên thanh toán phí ngay
        const login = await fetch("/api/member/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: body.email, password: body.password }),
        }).catch(() => null);
        setLoggedIn(!!login?.ok);
        setCode(j.code);
      } else if (j.fields && Object.keys(j.fields).length) {
        showErrors(j.fields);
        setBanner(j.message || "Vui lòng kiểm tra lại thông tin.");
      } else {
        setBanner(j.message || "Không gửi được đăng ký. Vui lòng thử lại sau ít phút.");
      }
    } catch {
      setBanner("Không kết nối được máy chủ. Vui lòng kiểm tra mạng và thử lại.");
    } finally {
      setBusy(false);
    }
  }

  const inv = (name: string) =>
    errors[name] ? { "aria-invalid": true as const, "aria-describedby": `e_${name}` } : {};
  const err = (name: string) => (
    <span className={errors[name] ? "err show" : "err"} id={`e_${name}`}>
      {errors[name] ?? ""}
    </span>
  );

  return (
    <>
      <form
        id="regForm"
        ref={formRef}
        noValidate
        autoComplete="on"
        onSubmit={onSubmit}
        onInput={clearError}
        onChange={clearError}
        style={code ? { display: "none" } : undefined}
      >
        <div className={banner ? "form-alert show" : "form-alert"} id="regAlert" role="alert" ref={alertRef}>
          {banner}
        </div>


            <fieldset className="fs">
              <legend><i>1</i>Thông tin doanh nghiệp</legend>
              <div className="fgrid">
                <div className="fld full"><label htmlFor="tax_code">Mã số thuế <span className="req">*</span></label>
                  <div className="tax-row">
                    <input type="text" id="tax_code" name="tax_code" inputMode="numeric" maxLength={14} placeholder="10 hoặc 13 chữ số" {...inv("tax_code")}
                      onChange={(e) => onTaxInput(e.currentTarget.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); runLookup(e.currentTarget.value, true); } }} />
                    <button type="button" className="btn btn-outline" disabled={lookup.state === "loading"}
                      onClick={() => runLookup((formRef.current?.elements.namedItem("tax_code") as HTMLInputElement | null)?.value ?? "", true)}>
                      {lookup.state === "loading" ? "Đang tra…" : "Tra cứu"}
                    </button>
                  </div>
                  {err("tax_code")}
                  <span className={`tax-note ${lookup.state}`} role="status" aria-live="polite">
                    {lookup.state === "idle" && "Nhập mã số thuế để tự điền tên doanh nghiệp, địa chỉ và tỉnh/thành."}
                    {lookup.state === "loading" && "Đang tra cứu thông tin doanh nghiệp…"}
                    {lookup.state === "ok" && (
                      lookup.info.active
                        ? <>Đã điền thông tin của <b>{lookup.info.name}</b>. Bạn có thể chỉnh sửa nếu cần.</>
                        : <>Đã điền thông tin của <b>{lookup.info.name}</b> — lưu ý trạng thái thuế: <b>{lookup.info.status}</b>.</>
                    )}
                    {lookup.state === "error" && lookup.message}
                  </span></div>
                <div className="fld full"><label htmlFor="company_name">Tên doanh nghiệp <span className="req">*</span></label><input type="text" id="company_name" name="company_name" maxLength={150} autoComplete="organization" placeholder="Công ty TNHH ABC" {...inv("company_name")} />{err("company_name")}</div>
                <div className="fld"><label htmlFor="company_size">Quy mô nhân sự <span className="req">*</span></label>
                  <select id="company_size" name="company_size" {...inv("company_size")}><option value="">Chọn quy mô…</option><option>Dưới 10 nhân sự</option><option>10–49 nhân sự</option><option>50–199 nhân sự</option><option>200–499 nhân sự</option><option>Từ 500 nhân sự</option></select>{err("company_size")}</div>
                <div className="fld"><label htmlFor="province">Tỉnh/thành <span className="req">*</span></label><input type="text" id="province" name="province" maxLength={80} autoComplete="address-level1" placeholder="Hà Nội" list="provinceList" {...inv("province")} />{err("province")}
                  <datalist id="provinceList"><option value="Hà Nội" /><option value="TP. Hồ Chí Minh" /><option value="Hải Phòng" /><option value="Đà Nẵng" /><option value="Cần Thơ" /><option value="Bắc Ninh" /><option value="Bắc Giang" /><option value="Hải Dương" /><option value="Hưng Yên" /><option value="Vĩnh Phúc" /><option value="Thái Nguyên" /><option value="Quảng Ninh" /><option value="Đồng Nai" /><option value="Bình Dương" /><option value="Long An" /><option value="Bà Rịa - Vũng Tàu" /></datalist></div>
                <div className="fld full"><span className="lbl" id="l_industries">Ngành hàng <span className="req">*</span> <span className="opt-t">(chọn nhiều)</span></span>
                  <div className="checks" role="group" aria-labelledby="l_industries" {...(errors.industries ? { "aria-describedby": "e_industries" } : {})}>
                    {INDUSTRIES.map((x, i) => (
                      <label key={x}><input type="checkbox" name="industries" value={x} {...(i === 0 ? { id: "industries" } : {})} /><span>{x}</span></label>
                    ))}
                  </div>
                  <input type="text" id="industry_other" name="industry_other" maxLength={120} placeholder="Ngành khác (nếu có), cách nhau dấu phẩy" aria-label="Ngành hàng khác" style={{ marginTop: 4 }} />
                  {err("industries")}</div>
                <div className="fld full"><label htmlFor="address">Địa chỉ <span className="opt-t">(không bắt buộc)</span></label><input type="text" id="address" name="address" maxLength={200} autoComplete="street-address" placeholder="Số nhà, đường, quận/huyện" /></div>
                <div className="fld full"><label htmlFor="website">Website <span className="opt-t">(không bắt buộc)</span></label><input type="url" id="website" name="website" maxLength={200} autoComplete="url" placeholder="congtyabc.vn" {...inv("website")} />{err("website")}</div>
              </div>
            </fieldset>

            <fieldset className="fs">
              <legend><i>2</i>Người liên hệ</legend>
              <div className="fgrid">
                <div className="fld"><label htmlFor="contact_name">Họ và tên <span className="req">*</span></label><input type="text" id="contact_name" name="contact_name" maxLength={100} autoComplete="name" placeholder="Nguyễn Văn A" {...inv("contact_name")} />{err("contact_name")}</div>
                <div className="fld"><label htmlFor="position">Chức vụ <span className="opt-t">(không bắt buộc)</span></label><input type="text" id="position" name="position" maxLength={100} autoComplete="organization-title" placeholder="Giám đốc kinh doanh" /></div>
                <div className="fld"><label htmlFor="email">Email <span className="req">*</span></label><input type="email" id="email" name="email" maxLength={150} autoComplete="email" placeholder="ten@congty.vn" {...inv("email")} />{err("email")}</div>
                <div className="fld"><label htmlFor="phone">Điện thoại / Zalo <span className="req">*</span></label><input type="tel" id="phone" name="phone" maxLength={20} autoComplete="tel" placeholder="0901 234 567" {...inv("phone")} />{err("phone")}</div>
                <div className="fld"><label htmlFor="password">Mật khẩu đăng nhập <span className="req">*</span></label><input type="password" id="password" name="password" maxLength={200} autoComplete="new-password" placeholder="Tối thiểu 8 ký tự" {...inv("password")} />{err("password")}</div>
                <div className="fld"><label htmlFor="password_confirm">Nhập lại mật khẩu <span className="req">*</span></label><input type="password" id="password_confirm" name="password_confirm" maxLength={200} autoComplete="new-password" {...inv("password_confirm")} />{err("password_confirm")}</div>
              </div>
            </fieldset>

            <div className="hp" aria-hidden="true"><label>Để trống<input type="text" name="website_url" tabIndex={-1} autoComplete="off" /></label></div>

            <label className="agree"><input type="checkbox" id="agree" name="agree" {...inv("agree")} /><span>Tôi đồng ý với <a href="#">Điều khoản sử dụng</a> và <a href="#">Chính sách bảo mật</a> của LeadScan B2B, và đồng ý để LeadScan liên hệ về dịch vụ.</span></label>
            {err("agree")}
        <div className="form-actions">
          <button type="submit" className={busy ? "btn btn-primary loading" : "btn btn-primary"} id="regSubmit" disabled={busy}>
            <span className="spin" aria-hidden="true"></span>
            <span id="regLabel">{busy ? "Đang gửi…" : "Gửi đăng ký thành viên"}</span>
          </button>
          <small>Gửi đăng ký chưa phát sinh chi phí. Sau khi đăng nhập, vào mục <b>Cơ hội phù hợp</b> để gửi yêu cầu tìm cơ hội cho doanh nghiệp mình.</small>
        </div>
      </form>

      <div className={code ? "reg-done show" : "reg-done"} id="regDone" role="status" tabIndex={-1} ref={doneRef}>
        <div className="tick"><svg className="icon"><use href="#i-check" /></svg></div>
        <h3>Đăng ký thành công!</h3>
        <p>Cảm ơn bạn. Tài khoản thành viên đã được tạo với email bạn đăng ký. Thanh toán phí thành viên 89.000đ để nhận 89.000 điểm và bắt đầu mua phiếu cơ hội.</p>
        <div className="reg-code" id="regCode">{code ?? ""}</div><br />
        <a href={loggedIn ? "/thanh-vien/nap-tien" : "/thanh-vien/dang-nhap"} className="btn btn-primary">
          {loggedIn ? "Thanh toán phí thành viên" : "Đăng nhập cổng thành viên"}
        </a>
      </div>
    </>
  );
}
