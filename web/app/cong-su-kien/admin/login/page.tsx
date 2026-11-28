"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useEffect, useState } from "react";

import { useSite } from "@/components/sites/SiteContext";
import { api, ApiError } from "@/lib/admin/api";

function LoginForm() {
  const site = useSite();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = `Đăng nhập · Quản trị ${site.name}`;
  }, [site.name]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/login", { email: String(fd.get("email")), password: String(fd.get("password")) });
      const next = params.get("next");
      router.replace(next && next.startsWith("/admin") && !next.startsWith("/admin/login") ? next : "/admin/su-kien");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đăng nhập được.");
      setBusy(false);
    }
  }

  return (
    <form className="adm-card" onSubmit={onSubmit}>
      <div className="adm-logo" style={{ justifyContent: "center" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={site.logo} alt={site.name} style={{ height: 88, width: "auto" }} />
      </div>
      <div style={{ textAlign: "center" }}>
        <h1>Quản trị sự kiện</h1>
        <p className="muted" style={{ marginTop: 4 }}>Dành cho ban tổ chức {site.name}</p>
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
      <p className="muted" style={{ fontSize: 12.5, textAlign: "center" }}>Chưa có tài khoản? Liên hệ quản trị viên LeadScan để được cấp.</p>
    </form>
  );
}

export default function PortalLoginPage() {
  return (
    <div className="adm-login">
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
