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
  // đến từ "Dùng mã ngay" của popup khuyến mãi (…/nap-tien?ma=MA): báo rõ vì sao cần đăng nhập
  const promo = /[?&]ma=([A-Za-z0-9_-]{1,30})/.exec(params.get("next") ?? "")?.[1]?.toUpperCase();
  const [busy, setBusy] = useState(false);
  // 1 tài khoản cho cả 2 cổng: email chỉ có hồ sơ đối tác → cho chọn vào cổng đối tác hoặc đăng ký thành viên
  const [partnerOnly, setPartnerOnly] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const r = await mapi.post<{ portals?: { member: boolean }; redirect?: string }>("/auth/login", { email: String(fd.get("email")), password: String(fd.get("password")) });
      if (r.portals && !r.portals.member) {
        setPartnerOnly(r.redirect || "/doi-tac/tong-quan");
        setBusy(false);
        return;
      }
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

  if (partnerOnly)
    return (
      <div className="adm-card">
        <Link href="/" className="adm-logo"><Logo height={28} /></Link>
        <div style={{ textAlign: "center" }}>
          <h1>Bạn đã đăng nhập</h1>
          <p className="muted" style={{ marginTop: 6 }}>
            Tài khoản này đang là <b>đối tác</b>, chưa có hồ sơ thành viên doanh nghiệp. Bạn có thể vào cổng đối tác, hoặc đăng ký thành viên
            bằng <b>đúng email và mật khẩu này</b> để dùng chung 1 tài khoản cho cả 2 cổng.
          </p>
        </div>
        <a className="adm-btn primary" href={partnerOnly} style={{ height: 40, justifyContent: "center" }}>Vào cổng đối tác</a>
        <a className="adm-btn" href="/#dang-ky" style={{ height: 40, justifyContent: "center" }}>Đăng ký thành viên doanh nghiệp</a>
      </div>
    );

  return (
    <form className="adm-card" onSubmit={onSubmit}>
      <Link href="/" className="adm-logo">
        <Logo height={28} />
      </Link>
      <div style={{ textAlign: "center" }}>
        <h1>Đăng nhập thành viên</h1>
        <p className="muted" style={{ marginTop: 4 }}>Xem kho cơ hội, mua phiếu và quản lý điểm</p>
        <p className="muted" style={{ marginTop: 4, fontSize: 12.5 }}>Một tài khoản LeadScan dùng cho cả cổng thành viên và cổng đối tác.</p>
      </div>
      {promo ? (
        <div className="adm-alert ok" role="status">
          Đăng nhập để dùng mã khuyến mãi <b>{promo}</b> — mã sẽ được áp dụng sẵn khi bạn thanh toán.
        </div>
      ) : null}
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
      <button className="adm-btn primary" type="submit" disabled={busy} style={{ height: 40 }}>{busy ? "Đang đăng nhập…" : promo ? "Đăng nhập và dùng mã" : "Đăng nhập"}</button>
      <p className="muted" style={{ textAlign: "center", fontSize: 13 }}>
        Chưa có tài khoản? <a href="/#dang-ky" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Đăng ký thành viên</a>
      </p>
      <p className="muted" style={{ textAlign: "center", fontSize: 13, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
        Bạn là đối tác giới thiệu cơ hội? <a href="/doi-tac/dang-nhap" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Vào cổng đối tác</a>
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
