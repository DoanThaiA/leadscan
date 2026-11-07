"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import { Icon } from "@/components/admin/ui";
import { errMsg, mapi } from "@/lib/member/api";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    if (f.password.length < 8) return setMsg({ ok: false, text: "Mật khẩu cần ít nhất 8 ký tự." });
    if (f.password !== f.confirm) return setMsg({ ok: false, text: "Mật khẩu nhập lại không khớp." });
    setBusy(true);
    try {
      await mapi.post("/auth/reset", { token, password: f.password });
      setMsg({ ok: true, text: "Đã đặt mật khẩu mới. Bạn có thể đăng nhập ngay." });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="adm-card" onSubmit={onSubmit}>
      <Link href="/" className="adm-logo"><span className="mark"><Icon name="scan" /></span>LeadScan<small>B2B</small></Link>
      <h1 style={{ textAlign: "center" }}>Đặt mật khẩu mới</h1>
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
      {msg?.ok ? (
        <Link className="adm-btn primary" href="/thanh-vien/dang-nhap" style={{ height: 40 }}>Đăng nhập</Link>
      ) : (
        <>
          <div className="adm-field">
            <label htmlFor="pw">Mật khẩu mới (≥ 8 ký tự)</label>
            <input className="adm-input" id="pw" name="password" type="password" autoComplete="new-password" required autoFocus />
          </div>
          <div className="adm-field">
            <label htmlFor="cf">Nhập lại mật khẩu</label>
            <input className="adm-input" id="cf" name="confirm" type="password" autoComplete="new-password" required />
          </div>
          <button className="adm-btn primary" disabled={busy || !token} style={{ height: 40 }}>{busy ? "Đang lưu…" : "Đặt mật khẩu"}</button>
          {!token ? <p className="adm-err">Liên kết thiếu mã xác thực. Hãy mở đúng liên kết trong email.</p> : null}
        </>
      )}
    </form>
  );
}

export default function ResetPage() {
  return (
    <div className="adm-login">
      <Suspense>
        <ResetForm />
      </Suspense>
    </div>
  );
}
