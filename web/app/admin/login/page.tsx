"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import { Icon } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/admin/api";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/login", { email: String(fd.get("email")), password: String(fd.get("password")) });
      const next = params.get("next");
      router.replace(next && next.startsWith("/admin") && !next.startsWith("/admin/login") ? next : "/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đăng nhập được.");
      setBusy(false);
    }
  }

  return (
    <form className="adm-card" onSubmit={onSubmit}>
      <div className="adm-logo">
        <span className="mark"><Icon name="scan" /></span>LeadScan<small>Admin</small>
      </div>
      <div style={{ textAlign: "center" }}>
        <h1>Đăng nhập quản trị</h1>
        <p className="muted" style={{ marginTop: 4 }}>Dành cho nhân viên LeadScan</p>
      </div>
      {error ? <div className="adm-alert" role="alert">{error}</div> : null}
      <div className="adm-field">
        <label htmlFor="email">Email</label>
        <input className="adm-input" id="email" name="email" type="email" autoComplete="username" required autoFocus />
      </div>
      <div className="adm-field">
        <label htmlFor="password">Mật khẩu</label>
        <input className="adm-input" id="password" name="password" type="password" autoComplete="current-password" required />
      </div>
      <button className="adm-btn primary" type="submit" disabled={busy} style={{ height: 40 }}>
        {busy ? "Đang đăng nhập…" : "Đăng nhập"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="adm-login">
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
