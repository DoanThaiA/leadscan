"use client";

import { type FormEvent, useEffect, useState } from "react";

import { Field } from "@/components/admin/ui";
import { usePartner } from "@/components/partner/PartnerContext";
import { fmtDate } from "@/lib/admin/format";
import { errFields, errMsg, papi } from "@/lib/partner/api";

export default function PartnerAccountPage() {
  const { me } = usePartner();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Tài khoản · Đối tác LeadScan";
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    setErrors({});
    setMsg(null);
    if (f.new_password.length < 8) return setErrors({ new_password: "Mật khẩu mới cần ít nhất 8 ký tự." });
    if (f.new_password !== f.confirm) return setErrors({ confirm: "Mật khẩu nhập lại không khớp." });
    setBusy(true);
    try {
      await papi.post("/auth/password", { current_password: f.current_password, new_password: f.new_password });
      form.reset();
      setMsg({ ok: true, text: "Đã đổi mật khẩu." });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
      setErrors(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="adm-head"><div><h1>Tài khoản</h1><p>{me.email}</p></div></div>
      <div className="adm-grid side">
        <section className="adm-card">
          <div className="hd"><h2>Thông tin đối tác</h2></div>
          <div className="bd">
            <dl className="adm-kv">
              <dt>Mã đối tác</dt><dd className="mono"><b>{me.code}</b></dd>
              <dt>Họ và tên</dt><dd>{me.full_name}</dd>
              <dt>Hình thức</dt><dd>{me.kind_label}</dd>
              {me.kind === "org" ? (<><dt>Tổ chức</dt><dd>{me.org_name}</dd><dt>Mã số thuế</dt><dd className="mono">{me.org_tax_code}</dd></>) : null}
              <dt>Email đăng nhập</dt><dd>{me.email}</dd>
              <dt>Điện thoại / Zalo</dt><dd>{me.phone} <span className="muted">· đã xác thực {fmtDate(me.phone_verified_at)}</span></dd>
              <dt>Hạng</dt><dd>{me.tier_label}</dd>
              <dt>Ngành hay tiếp xúc</dt><dd>{me.industries.length ? me.industries.join(", ") : "—"}</dd>
              <dt>Khu vực</dt><dd>{me.regions.length ? me.regions.join(", ") : "—"}</dd>
            </dl>
            <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
              Cần đổi số điện thoại hoặc thông tin tổ chức? Vui lòng liên hệ LeadScan. Hồ sơ thanh toán (định danh, MST, ngân hàng) chỉ cần khi bạn rút tiền lần đầu.
            </p>
          </div>
        </section>
        <section className="adm-card">
          <div className="hd"><h2>Đổi mật khẩu</h2></div>
          <form className="bd" onSubmit={submit} style={{ display: "grid", gap: 14 }} noValidate>
            {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
            <Field label="Mật khẩu hiện tại" error={errors.current_password} htmlFor="p-cur">
              <input id="p-cur" className="adm-input" type="password" name="current_password" autoComplete="current-password" />
            </Field>
            <Field label="Mật khẩu mới (≥ 8 ký tự)" error={errors.new_password} htmlFor="p-new">
              <input id="p-new" className="adm-input" type="password" name="new_password" autoComplete="new-password" />
            </Field>
            <Field label="Nhập lại mật khẩu mới" error={errors.confirm} htmlFor="p-cf">
              <input id="p-cf" className="adm-input" type="password" name="confirm" autoComplete="new-password" />
            </Field>
            <div className="adm-actions"><button className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Đổi mật khẩu"}</button></div>
          </form>
        </section>
      </div>
    </>
  );
}
