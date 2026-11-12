"use client";

import { useEffect, useState } from "react";

/**
 * "Mua phiếu này" trên trang công khai. Đã đăng nhập thành viên → mở cơ hội trong cổng thành viên để mua.
 * Chưa đăng nhập → bắt đăng ký thành viên (hoặc đăng nhập), xong quay lại đúng cơ hội (?mua=1 tự tiếp tục).
 */
export default function BuyButton({ id, code, disabled }: { id: number; code: string; disabled?: boolean }) {
  const [state, setState] = useState<"idle" | "checking" | "need-login" | "error">("idle");
  const [error, setError] = useState("");
  const back = `/co-hoi/${code}?mua=1`;

  async function buy() {
    setState("checking");
    setError("");
    try {
      const me = await fetch("/api/member/auth/me", { credentials: "same-origin", cache: "no-store" });
      if (me.status === 401) return setState("need-login");
      if (!me.ok) throw new Error();
      const r = await fetch(`/api/member/opportunities/${id}/open-shared`, { method: "POST", credentials: "same-origin" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(typeof j.detail === "string" ? j.detail : "");
      }
      location.href = `/thanh-vien/co-hoi/${id}`;
    } catch (e) {
      setError((e instanceof Error && e.message) || "Không kết nối được máy chủ, vui lòng thử lại.");
      setState("error");
    }
  }

  useEffect(() => {
    // quay lại sau khi đăng nhập / đăng ký → tự tiếp tục mua
    if (!disabled && new URLSearchParams(location.search).get("mua") === "1") buy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (disabled) return <button className="btn btn-outline" disabled style={{ width: "100%" }}>Đã hết lượt mua</button>;

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <button className="btn btn-primary" style={{ width: "100%" }} onClick={buy} disabled={state === "checking"}>
        {state === "checking" ? "Đang mở…" : "Mua phiếu để mở khoá đầu mối"}
      </button>
      {state === "need-login" ? (
        <div className="pub-login" role="status">
          <b>Chỉ thành viên LeadScan mới mua được phiếu cơ hội.</b>
          <span>Đăng ký thành viên (khoảng 1 phút), phí 89.000đ/năm được cộng đủ thành điểm để mua phiếu.</span>
          <a className="btn btn-primary" href={`/?next=${encodeURIComponent(back)}#dang-ky`}>Đăng ký thành viên</a>
          <a className="link-arrow" href={`/thanh-vien/dang-nhap?next=${encodeURIComponent(back)}`}>Đã là thành viên? Đăng nhập</a>
        </div>
      ) : null}
      {state === "error" ? <p className="pub-err" role="alert">{error}</p> : null}
    </div>
  );
}

/** Chia sẻ link (Zalo, Messenger… qua menu chia sẻ của điện thoại; máy tính: sao chép link). */
export function ShareButton({ title }: { title: string }) {
  const [done, setDone] = useState(false);
  async function share() {
    const url = location.origin + location.pathname;
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setDone(true);
      setTimeout(() => setDone(false), 2500);
    } catch {
      /* người dùng huỷ chia sẻ */
    }
  }
  return <button className="btn btn-outline" style={{ width: "100%" }} onClick={share}>{done ? "✓ Đã sao chép link" : "Chia sẻ cơ hội này"}</button>;
}
