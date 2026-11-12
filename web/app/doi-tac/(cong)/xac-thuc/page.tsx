"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { Logo } from "@/components/brand/Logo";
import { ApiError, errMsg, type OtpSent, papi, type PartnerMe } from "@/lib/partner/api";

/** "nguyenvana@gmail.com" → "ng•••••••a@gmail.com" (khớp backend). */
function mask(email: string) {
  const [name, domain = ""] = email.split("@");
  if (name.length <= 2) return name.slice(0, 1) + "•".repeat(Math.max(0, name.length - 1)) + "@" + domain;
  return name.slice(0, 2) + "•".repeat(name.length - 3) + name.slice(-1) + "@" + domain;
}

/** Bước kích hoạt: nhập mã OTP gửi tới email đăng ký. Đã xác thực → vào cổng; chưa đăng nhập → trang đăng nhập. */
export default function VerifyEmailPage() {
  const router = useRouter();
  const [me, setMe] = useState<PartnerMe | null>(null);
  const [wait, setWait] = useState(0);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");

  useEffect(() => {
    papi.get<PartnerMe>("/auth/me").then(
      (m) => {
        if (m.email_verified) return router.replace("/doi-tac/tong-quan");
        setMe(m);
        setWait(m.otp_resend_after ?? 0);
      },
      () => router.replace("/doi-tac/dang-nhap?next=/doi-tac/xac-thuc"),
    );
  }, [router]);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  async function resend() {
    setMsg(null);
    try {
      const r = await papi.post<OtpSent>("/auth/otp/send");
      setWait(r.resend_after ?? 60);
      setMsg({ ok: true, text: `Đã gửi mã mới tới ${r.email}. Mã có hiệu lực ${r.ttl_minutes} phút.` });
    } catch (err) {
      const m = err instanceof ApiError ? /(\d+) giây/.exec(err.message) : null;
      if (m) setWait(Number(m[1]));
      setMsg({ ok: false, text: errMsg(err) });
    }
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!/^\d{6}$/.test(code)) return setMsg({ ok: false, text: "Mã xác thực gồm 6 chữ số." });
    setBusy(true);
    setMsg(null);
    try {
      await papi.post<PartnerMe>("/auth/otp/verify", { code });
      router.replace("/doi-tac/tong-quan");
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
      setBusy(false);
    }
  }

  async function logout() {
    await papi.post("/auth/logout").catch(() => {});
    router.replace("/doi-tac/dang-nhap");
  }

  if (!me) return <div className="adm-login"><div className="adm-empty">Đang tải…</div></div>;

  return (
    <div className="adm-login">
      <form className="adm-card" onSubmit={onSubmit}>
        <a href="/doi-tac" className="adm-logo"><Logo height={28} /></a>
        <span className="ptn-label">Cổng Đối tác</span>
        <div style={{ textAlign: "center" }}>
          <h1>Xác thực email</h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Nhập mã 6 số LeadScan gửi tới email <b style={{ color: "var(--ink)" }}>{mask(me.email)}</b> để kích hoạt tài khoản đối tác.
          </p>
        </div>
        {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} role="status">{msg.text}</div> : null}
        <div className="adm-field">
          <label htmlFor="otp">Mã xác thực</label>
          <input
            className="adm-input ptn-otp" id="otp" name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
            value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} autoFocus required
          />
        </div>
        <button className="adm-btn primary" type="submit" disabled={busy || code.length !== 6} style={{ height: 40 }}>
          {busy ? "Đang xác thực…" : "Xác thực & vào cổng đối tác"}
        </button>
        <div className="ptn-otp-meta">
          <span>Chưa nhận được mã?</span>
          <button type="button" className="ptn-linkbtn" onClick={resend} disabled={wait > 0}>
            {wait > 0 ? `Gửi lại sau ${wait}s` : "Gửi lại mã"}
          </button>
        </div>
        <p className="muted" style={{ fontSize: 12.5, textAlign: "center" }}>
          Không thấy email? Kiểm tra thư mục Spam / Quảng cáo, hoặc liên hệ LeadScan (hotline +848 7777 0788) để được kích hoạt. Sai email? Liên hệ LeadScan để cập nhật.
        </p>
        <p className="ptn-switch">
          Đăng nhập: {me.email} · <button type="button" className="ptn-linkbtn" onClick={logout}>Đăng xuất</button>
        </p>
      </form>
    </div>
  );
}
