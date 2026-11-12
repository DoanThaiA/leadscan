"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import { Logo } from "@/components/brand/Logo";
import { errMsg, papi, type PartnerMe } from "@/lib/partner/api";

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
      const me = await papi.post<PartnerMe>("/auth/login", { email: String(fd.get("email")), password: String(fd.get("password")) });
      if (!me.email_verified) return router.replace("/doi-tac/xac-thuc");
      const next = params.get("next");
      const ok = next && next.startsWith("/doi-tac/") && !/dang-nhap|xac-thuc/.test(next);
      router.replace(ok ? next : "/doi-tac/tong-quan");
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  }

  return (
    <form className="adm-card" onSubmit={onSubmit}>
      <a href="/doi-tac" className="adm-logo"><Logo height={28} /></a>
      <span className="ptn-label">Cổng Đối tác</span>
      <div style={{ textAlign: "center" }}>
        <h1>Đăng nhập đối tác</h1>
        <p className="muted" style={{ marginTop: 4 }}>Gửi cơ hội, theo dõi trạng thái và ví hoa hồng</p>
      </div>
      {error ? <div className="adm-alert" role="alert">{error}</div> : null}
      <div className="adm-field">
        <label htmlFor="email">Email</label>
        <input className="adm-input" id="email" name="email" type="email" autoComplete="username" required autoFocus />
      </div>
      <div className="adm-field">
        <label htmlFor="password" style={{ display: "flex", justifyContent: "space-between" }}>
          Mật khẩu <Link href="/doi-tac/quen-mat-khau" style={{ color: "var(--brand-600)", fontWeight: 500 }}>Quên mật khẩu?</Link>
        </label>
        <input className="adm-input" id="password" name="password" type="password" autoComplete="current-password" required />
      </div>
      <button className="adm-btn primary" type="submit" disabled={busy} style={{ height: 40 }}>{busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
      <p className="muted" style={{ textAlign: "center", fontSize: 13 }}>
        Chưa có tài khoản? <a href="/doi-tac#dang-ky" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Đăng ký đối tác</a>
      </p>
      <p className="ptn-switch">Bạn là thành viên mua phiếu? <a href="/thanh-vien/dang-nhap">Đăng nhập cổng thành viên</a></p>
    </form>
  );
}

export default function PartnerLoginPage() {
  return (
    <div className="adm-login">
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
