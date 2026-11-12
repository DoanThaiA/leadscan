"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Logo } from "@/components/brand/Logo";
import { errMsg, papi } from "@/lib/partner/api";

export default function PartnerForgotPage() {
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email"));
    setBusy(true);
    try {
      const r = await papi.post<{ message: string }>("/auth/forgot", { email });
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
        <a href="/doi-tac" className="adm-logo"><Logo height={28} /></a>
        <span className="ptn-label">Cổng Đối tác</span>
        <div style={{ textAlign: "center" }}>
          <h1>Quên mật khẩu</h1>
          <p className="muted" style={{ marginTop: 4 }}>Nhập email đăng ký đối tác, chúng tôi gửi liên kết đặt lại mật khẩu.</p>
        </div>
        {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
        <div className="adm-field">
          <label htmlFor="email">Email</label>
          <input className="adm-input" id="email" name="email" type="email" required autoFocus />
        </div>
        <button className="adm-btn primary" disabled={busy} style={{ height: 40 }}>{busy ? "Đang gửi…" : "Gửi liên kết"}</button>
        <Link href="/doi-tac/dang-nhap" className="muted" style={{ textAlign: "center" }}>← Quay lại đăng nhập</Link>
      </form>
    </div>
  );
}
