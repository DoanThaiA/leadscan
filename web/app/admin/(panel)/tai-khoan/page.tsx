"use client";

import { type FormEvent, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Field } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/admin/api";

export default function AccountPage() {
  const { user, meta } = useAdmin();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Tài khoản · Quản trị LeadScan";
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    setErrors({});
    setMsg(null);
    if (f.new_password !== f.confirm) {
      setErrors({ confirm: "Mật khẩu nhập lại không khớp." });
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/password", { current_password: f.current_password, new_password: f.new_password });
      form.reset();
      setMsg({ ok: true, text: "Đã đổi mật khẩu." });
    } catch (err) {
      if (err instanceof ApiError) {
        setMsg({ ok: false, text: err.message });
        setErrors(err.fields);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Tài khoản của tôi</h1>
          <p>{user.full_name} · {user.email} · {meta.roles[user.role]}</p>
        </div>
      </div>
      <section className="adm-card" style={{ maxWidth: 520 }}>
        <div className="hd"><h2>Đổi mật khẩu</h2></div>
        <form className="bd" onSubmit={submit} style={{ display: "grid", gap: 14 }} noValidate>
          {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
          <Field label="Mật khẩu hiện tại" error={errors.current_password} htmlFor="a-cur">
            <input id="a-cur" className="adm-input" type="password" name="current_password" autoComplete="current-password" />
          </Field>
          <Field label="Mật khẩu mới (≥ 10 ký tự)" error={errors.new_password} htmlFor="a-new">
            <input id="a-new" className="adm-input" type="password" name="new_password" autoComplete="new-password" minLength={10} />
          </Field>
          <Field label="Nhập lại mật khẩu mới" error={errors.confirm} htmlFor="a-cf">
            <input id="a-cf" className="adm-input" type="password" name="confirm" autoComplete="new-password" />
          </Field>
          <div className="adm-actions">
            <button className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Đổi mật khẩu"}</button>
          </div>
        </form>
      </section>
    </>
  );
}
