"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import { errMsg, mapi } from "@/lib/member/api";
import { Logo } from "@/components/brand/Logo";

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
      await mapi.post("/auth/login", { email: String(fd.get("email")), password: String(fd.get("password")) });
      const next = params.get("next");
      // quay lại trang trong cổng, hoặc trang cơ hội công khai đang xem (/co-hoi/<mã>?mua=1 → tiếp tục mua)
      const ok = next && (next.startsWith("/thanh-vien") || next.startsWith("/co-hoi/")) && !next.includes("dang-nhap") && !next.startsWith("//");
      if (ok && next.startsWith("/co-hoi/")) location.href = next;
      else router.replace(ok ? next : "/thanh-vien");
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  }

  return (
    <form className="adm-card" onSubmit={onSubmit}>
      <Link href="/" className="adm-logo">
        <Logo height={28} />
      </Link>
      <div style={{ textAlign: "center" }}>
        <h1>Đăng nhập thành viên</h1>
        <p className="muted" style={{ marginTop: 4 }}>Xem kho cơ hội, mua phiếu và quản lý điểm</p>
      </div>
      {error ? <div className="adm-alert" role="alert">{error}</div> : null}
      <div className="adm-field">
        <label htmlFor="email">Email</label>
        <input className="adm-input" id="email" name="email" type="email" autoComplete="username" required autoFocus />
      </div>
      <div className="adm-field">
        <label htmlFor="password" style={{ display: "flex", justifyContent: "space-between" }}>
          Mật khẩu <Link href="/thanh-vien/quen-mat-khau" style={{ color: "var(--brand-600)", fontWeight: 500 }}>Quên mật khẩu?</Link>
        </label>
        <input className="adm-input" id="password" name="password" type="password" autoComplete="current-password" required />
      </div>
      <button className="adm-btn primary" type="submit" disabled={busy} style={{ height: 40 }}>{busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
      <p className="muted" style={{ textAlign: "center", fontSize: 13 }}>
        Chưa có tài khoản? <a href="/#dang-ky" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Đăng ký thành viên</a>
      </p>
      <p className="muted" style={{ textAlign: "center", fontSize: 13, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
        Bạn là đối tác giới thiệu cơ hội? <a href="/doi-tac/dang-nhap" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Đăng nhập cổng đối tác</a>
      </p>
    </form>
  );
}

export default function MemberLoginPage() {
  return (
    <div className="adm-login">
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
