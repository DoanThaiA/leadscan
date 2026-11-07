"use client";

import { type FormEvent, useEffect, useState } from "react";

import { Field } from "@/components/admin/ui";
import { useMember } from "@/components/member/MemberContext";
import { fmtDate } from "@/lib/admin/format";
import { errFields, errMsg, mapi } from "@/lib/member/api";

export default function MemberAccountPage() {
  const { me } = useMember();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Tài khoản · LeadScan B2B";
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    setErrors({});
    setMsg(null);
    if (f.new_password !== f.confirm) return setErrors({ confirm: "Mật khẩu nhập lại không khớp." });
    setBusy(true);
    try {
      await mapi.post("/auth/password", { current_password: f.current_password, new_password: f.new_password });
      form.reset();
      setMsg({ ok: true, text: "Đã đổi mật khẩu." });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
      setErrors(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  const c = me.company;
  return (
    <>
      <div className="adm-head"><div><h1>Tài khoản</h1><p>{me.email}</p></div></div>
      <div className="adm-grid side">
        <section className="adm-card">
          <div className="hd"><h2>Doanh nghiệp</h2></div>
          <div className="bd">
            <dl className="adm-kv">
              <dt>Tên doanh nghiệp</dt><dd><b>{c.name}</b></dd>
              <dt>Mã khách hàng</dt><dd className="mono">{c.code}</dd>
              <dt>Mã số thuế</dt><dd className="mono">{c.tax_code}</dd>
              <dt>Địa chỉ</dt><dd>{c.address || "—"}</dd>
              <dt>Thành viên</dt><dd>{c.membership_active ? `Hiệu lực đến ${fmtDate(c.membership_expires_at)}` : "Chưa kích hoạt"}</dd>
              <dt>Người dùng</dt><dd>{me.full_name}</dd>
            </dl>
            <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>Cần thay đổi thông tin doanh nghiệp? Vui lòng liên hệ LeadScan để được cập nhật.</p>
          </div>
        </section>
        <section className="adm-card">
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
