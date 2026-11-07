"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Icon } from "@/components/admin/ui";
import { errMsg, mapi } from "@/lib/member/api";

export default function ForgotPage() {
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email"));
    setBusy(true);
    try {
      const r = await mapi.post<{ message: string }>("/auth/forgot", { email });
      setMsg({ ok: true, text: r.message });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="adm-login">
      <form className="adm-card" onSubmit={onSubmit}>
        <Link href="/" className="adm-logo"><span className="mark"><Icon name="scan" /></span>LeadScan<small>B2B</small></Link>
        <div style={{ textAlign: "center" }}>
          <h1>Quên mật khẩu</h1>
          <p className="muted" style={{ marginTop: 4 }}>Nhập email đăng ký, chúng tôi gửi liên kết đặt lại mật khẩu.</p>
        </div>
        {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
        <div className="adm-field">
          <label htmlFor="email">Email</label>
          <input className="adm-input" id="email" name="email" type="email" required autoFocus />
        </div>
        <button className="adm-btn primary" disabled={busy} style={{ height: 40 }}>{busy ? "Đang gửi…" : "Gửi liên kết"}</button>
        <Link href="/thanh-vien/dang-nhap" className="muted" style={{ textAlign: "center" }}>← Quay lại đăng nhập</Link>
      </form>
    </div>
  );
}
