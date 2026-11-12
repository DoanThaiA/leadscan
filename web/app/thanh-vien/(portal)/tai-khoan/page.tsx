"use client";

import { type FormEvent, useEffect, useState } from "react";

import { Field, Icon, Skeleton } from "@/components/admin/ui";
import { type MemberMe, useMember } from "@/components/member/MemberContext";
import { MultiSelect } from "@/components/member/MultiSelect";
import { fmtDate } from "@/lib/admin/format";
import { errFields, errMsg, mapi } from "@/lib/member/api";

interface Profile {
  full_name: string;
  email: string;
  company_name: string;
  tax_code: string;
  industries: string[];
  company_size: string;
  province: string;
  address: string;
  website: string;
  contact_name: string;
  contact_position: string;
  contact_phone: string;
  options: { industries: string[]; sizes: string[]; max_industries: number };
}
type Editable = Omit<Profile, "email" | "tax_code" | "options">;

const PROVINCES = ["Hà Nội", "TP. Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "Bắc Ninh", "Bắc Giang", "Hải Dương", "Hưng Yên", "Vĩnh Phúc",
  "Thái Nguyên", "Quảng Ninh", "Đồng Nai", "Bình Dương", "Long An", "Bà Rịa - Vũng Tàu"];

const pick = (p: Profile): Editable => ({
  full_name: p.full_name, company_name: p.company_name, industries: p.industries, company_size: p.company_size, province: p.province,
  address: p.address, website: p.website, contact_name: p.contact_name, contact_position: p.contact_position, contact_phone: p.contact_phone,
});

/** Thông tin tài khoản & doanh nghiệp: xem / tự sửa (trừ mã số thuế và email đăng nhập) + đổi mật khẩu. */
export default function MemberAccountPage() {
  const { me, setMe } = useMember();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Editable | null>(null);
  const [pErrors, setPErrors] = useState<Record<string, string>>({});
  const [pMsg, setPMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pBusy, setPBusy] = useState(false);

  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Tài khoản · LeadScan B2B";
    mapi.get<Profile>("/profile").then(setProfile, (e) => setPMsg({ ok: false, text: errMsg(e) }));
  }, []);

  function startEdit() {
    if (!profile) return;
    setForm(pick(profile));
    setPErrors({});
    setPMsg(null);
    setEditing(true);
  }

  const set = <K extends keyof Editable>(k: K, v: Editable[K]) => setForm((f) => (f ? { ...f, [k]: v } : f));

  async function saveProfile(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!form || !profile) return;
    const er: Record<string, string> = {};
    if (!form.full_name.trim()) er.full_name = "Vui lòng nhập họ tên.";
    if (!form.company_name.trim()) er.company_name = "Vui lòng nhập tên doanh nghiệp.";
    if (!form.province.trim()) er.province = "Vui lòng nhập tỉnh/thành.";
    if (!form.contact_name.trim()) er.contact_name = "Vui lòng nhập họ tên người liên hệ.";
    if (!form.industries.length) er.industries = "Vui lòng chọn ít nhất 1 ngành hàng.";
    else if (form.industries.length > profile.options.max_industries) er.industries = `Chọn tối đa ${profile.options.max_industries} ngành hàng.`;
    if (form.contact_phone.trim() && !/^(0|\+?84)\d{9,10}$/.test(form.contact_phone.replace(/[\s.\-()]/g, ""))) er.contact_phone = "Số điện thoại chưa đúng định dạng.";
    setPErrors(er);
    setPMsg(null);
    if (Object.keys(er).length) return setPMsg({ ok: false, text: "Vui lòng kiểm tra lại thông tin." });
    setPBusy(true);
    try {
      const r = await mapi.put<{ me: MemberMe; profile: Profile; changed: number }>("/profile", form);
      setProfile(r.profile);
      setMe(r.me);
      setEditing(false);
      setPMsg({ ok: true, text: r.changed ? "Đã lưu thông tin." : "Không có thay đổi nào." });
    } catch (err) {
      setPMsg({ ok: false, text: errMsg(err) });
      setPErrors(errFields(err));
    } finally {
      setPBusy(false);
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const f = Object.fromEntries(new FormData(formEl)) as Record<string, string>;
    setErrors({});
    setMsg(null);
    if (f.new_password !== f.confirm) return setErrors({ confirm: "Mật khẩu nhập lại không khớp." });
    setBusy(true);
    try {
      await mapi.post("/auth/password", { current_password: f.current_password, new_password: f.new_password });
      formEl.reset();
      setMsg({ ok: true, text: "Đã đổi mật khẩu." });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
      setErrors(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  const c = me.company;
  const p = profile;
  const text = (k: keyof Editable, label: string, opts: { max: number; placeholder?: string; full?: boolean; type?: string; list?: string; autoComplete?: string }) => (
    <Field label={label} error={pErrors[k]} full={opts.full} htmlFor={`p-${k}`}>
      <input id={`p-${k}`} className="adm-input" type={opts.type ?? "text"} value={String(form?.[k] ?? "")} maxLength={opts.max} placeholder={opts.placeholder}
        list={opts.list} autoComplete={opts.autoComplete} aria-invalid={!!pErrors[k]} onChange={(e) => set(k, e.target.value as never)} />
    </Field>
  );

  return (
    <>
      <div className="adm-head"><div><h1>Tài khoản</h1><p>{me.email}</p></div></div>
      <div className="adm-grid side">
        <section className="adm-card">
          <div className="hd">
            <h2>Thông tin doanh nghiệp</h2>
            {!editing && p ? <button className="adm-btn sm" onClick={startEdit}><Icon name="edit" size={14} /> Sửa thông tin</button> : null}
          </div>
          <div className="bd">
            {pMsg ? <div className={pMsg.ok ? "adm-alert ok" : "adm-alert"} role="status" style={{ marginBottom: 14 }}>{pMsg.text}</div> : null}
            {!p ? <div style={{ display: "grid", gap: 10 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={20} />)}</div> : !editing || !form ? (
              <dl className="adm-kv">
                <dt>Tên doanh nghiệp</dt><dd><b style={{ overflowWrap: "anywhere" }}>{p.company_name}</b></dd>
                <dt>Mã khách hàng</dt><dd className="mono">{c.code}</dd>
                <dt>Mã số thuế</dt><dd className="mono">{p.tax_code}</dd>
                <dt>Ngành hàng</dt><dd>{p.industries.join(", ") || "—"}</dd>
                <dt>Quy mô</dt><dd>{p.company_size || "—"}</dd>
                <dt>Địa chỉ</dt><dd>{[p.address, p.province].filter(Boolean).join(", ") || "—"}</dd>
                <dt>Website</dt><dd>{p.website ? <a href={p.website} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand-600)", overflowWrap: "anywhere" }}>{p.website}</a> : "—"}</dd>
                <dt>Người liên hệ</dt><dd>{p.contact_name || "—"}{p.contact_position ? ` · ${p.contact_position}` : ""}{p.contact_phone ? <div className="muted">{p.contact_phone}</div> : null}</dd>
                <dt>Người dùng</dt><dd>{p.full_name}</dd>
                <dt>Thành viên</dt><dd>{c.membership_active ? `Hiệu lực đến ${fmtDate(c.membership_expires_at)}` : "Chưa kích hoạt"}</dd>
              </dl>
            ) : (
              <form onSubmit={saveProfile} noValidate style={{ display: "grid", gap: 18 }}>
                <fieldset className="adm-form-grid" style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
                  <legend className="muted" style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", marginBottom: 8 }}>Doanh nghiệp</legend>
                  <div style={{ gridColumn: "1 / -1" }}>{text("company_name", "Tên doanh nghiệp *", { max: 150, full: true })}</div>
                  <Field label="Mã số thuế" htmlFor="p-tax">
                    <input id="p-tax" className="adm-input mono" value={p.tax_code} disabled readOnly />
                    <span className="muted" style={{ fontSize: 12 }}>Cần đổi mã số thuế? Liên hệ LeadScan.</span>
                  </Field>
                  <Field label="Quy mô *" error={pErrors.company_size} htmlFor="p-size">
                    <select id="p-size" className="adm-input" value={form.company_size} onChange={(e) => set("company_size", e.target.value)} aria-invalid={!!pErrors.company_size}>
                      {!p.options.sizes.includes(form.company_size) ? <option value="">— Chọn quy mô —</option> : null}
                      {p.options.sizes.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  </Field>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <MultiSelect icon="factory" label={`Ngành hàng * (tối đa ${p.options.max_industries})`} options={p.options.industries} value={form.industries}
                      onChange={(v) => set("industries", v)} placeholder="Gõ ngành hàng, vd: bao bì, nhựa…" allowCustom />
                    {pErrors.industries ? <span className="adm-err">{pErrors.industries}</span> : null}
                  </div>
                  {text("province", "Tỉnh/thành *", { max: 80, list: "p-provinces", autoComplete: "address-level1" })}
                  <datalist id="p-provinces">{PROVINCES.map((x) => <option key={x} value={x} />)}</datalist>
                  {text("address", "Địa chỉ", { max: 200, autoComplete: "street-address" })}
                  <div style={{ gridColumn: "1 / -1" }}>{text("website", "Website", { max: 200, placeholder: "vd. congty.vn", type: "url", full: true })}</div>
                </fieldset>

                <fieldset style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
                  <legend className="muted" style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", marginBottom: 8 }}>Người liên hệ chính</legend>
                  {text("contact_name", "Họ tên *", { max: 100, autoComplete: "name" })}
                  {text("contact_position", "Chức vụ", { max: 100, autoComplete: "organization-title" })}
                  {text("contact_phone", "Số điện thoại", { max: 20, type: "tel", autoComplete: "tel" })}
                </fieldset>

                <fieldset style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
                  <legend className="muted" style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", marginBottom: 8 }}>Người dùng</legend>
                  {text("full_name", "Họ tên người dùng *", { max: 100 })}
                  <Field label="Email đăng nhập" htmlFor="p-email">
                    <input id="p-email" className="adm-input" value={p.email} disabled readOnly />
                    <span className="muted" style={{ fontSize: 12 }}>Cần đổi email đăng nhập? Liên hệ LeadScan.</span>
                  </Field>
                </fieldset>

                <div className="adm-actions">
                  <button type="button" className="adm-btn" disabled={pBusy} onClick={() => { setEditing(false); setPErrors({}); setPMsg(null); }}>Huỷ</button>
                  <button className="adm-btn primary" disabled={pBusy}>{pBusy ? "Đang lưu…" : "Lưu thông tin"}</button>
                </div>
              </form>
            )}
          </div>
        </section>
        <section className="adm-card" style={{ alignSelf: "start" }}>
          <div className="hd"><h2>Đổi mật khẩu</h2></div>
          <form className="bd" onSubmit={submit} style={{ display: "grid", gap: 14 }} noValidate>
            {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
            <Field label="Mật khẩu hiện tại" error={errors.current_password} htmlFor="m-cur">
              <input id="m-cur" className="adm-input" type="password" name="current_password" autoComplete="current-password" />
            </Field>
            <Field label="Mật khẩu mới (≥ 10 ký tự)" error={errors.new_password} htmlFor="m-new">
              <input id="m-new" className="adm-input" type="password" name="new_password" autoComplete="new-password" />
            </Field>
            <Field label="Nhập lại mật khẩu mới" error={errors.confirm} htmlFor="m-cf">
              <input id="m-cf" className="adm-input" type="password" name="confirm" autoComplete="new-password" />
            </Field>
            <div className="adm-actions"><button className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Đổi mật khẩu"}</button></div>
          </form>
        </section>
      </div>
    </>
  );
}
