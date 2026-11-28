"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { ATTENDEE_TYPES, REG_STATUS, REG_STATUS_CLASS, fmtVnd, type EventRegistration } from "@/lib/events";

/**
 * Check-in tại sự kiện. Khách đưa mã QR trong email xác nhận; lễ tân quét bằng camera điện thoại
 * → mở trang này với ?ma=SK…, xem đúng người rồi bấm "Xác nhận đã đến". Gõ tay mã đăng ký cũng được.
 */
export default function CheckInPage() {
  const [code, setCode] = useState("");
  const [input, setInput] = useState("");
  const [r, setR] = useState<EventRegistration | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<"" | "now" | "already">("");
  const inputRef = useRef<HTMLInputElement>(null);

  const lookup = useCallback(async (c: string) => {
    const v = c.trim().toUpperCase();
    if (!v) return;
    setCode(v);
    setLoading(true);
    setError("");
    setDone("");
    setR(null);
    history.replaceState(null, "", `?ma=${encodeURIComponent(v)}`);
    try {
      const out = await api.get<EventRegistration>(`/event-registrations/by-code/${encodeURIComponent(v)}`);
      setR(out);
      if (out.checked_in) setDone("already");
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = "Check-in sự kiện · Quản trị LeadScan";
    const ma = new URLSearchParams(location.search).get("ma");
    if (ma) lookup(ma);
    else inputRef.current?.focus();
  }, [lookup]);

  async function confirmArrival() {
    if (!r) return;
    setBusy(true);
    setError("");
    try {
      const out = await api.post<EventRegistration & { already: boolean }>(`/event-registrations/${r.id}/check-in`);
      setR(out);
      setDone(out.already ? "already" : "now");
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  function next() {
    setR(null);
    setCode("");
    setInput("");
    setDone("");
    setError("");
    history.replaceState(null, "", location.pathname);
    inputRef.current?.focus();
  }

  const unpaid = r && r.status !== "paid" && r.status !== "cancelled";
  const cancelled = r?.status === "cancelled";

  return (
    <div style={{ maxWidth: 560 }}>
      <Link href="/admin/su-kien/dang-ky" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Đăng ký sự kiện</Link>
      <div className="adm-head">
        <div>
          <h1>Check-in sự kiện</h1>
          <p>Quét mã QR trong email xác nhận của khách bằng camera điện thoại, hoặc gõ mã đăng ký (SK…) vào ô bên dưới.</p>
        </div>
      </div>

      <form
        className="adm-card"
        style={{ padding: 16, display: "flex", gap: 8, marginBottom: 16 }}
        onSubmit={(e) => { e.preventDefault(); lookup(input); }}
      >
        <input
          ref={inputRef}
          className="adm-input mono"
          placeholder="Mã đăng ký, vd. SK7KQ4MX"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          aria-label="Mã đăng ký"
          autoCapitalize="characters"
          autoComplete="off"
          style={{ flex: 1, fontSize: 17, letterSpacing: ".06em" }}
        />
        <button className="adm-btn primary" disabled={!input.trim() || loading}><Icon name="search" size={14} /> Tra cứu</button>
      </form>

      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}{code ? ` (mã ${code})` : ""}</div> : null}

      {loading ? (
        <section className="adm-card" style={{ padding: 20, display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={28} />)}</section>
      ) : r ? (
        <section className="adm-card" style={{ padding: 20 }}>
          {done === "now" ? (
            <div className="adm-alert ok" style={{ fontSize: 16, fontWeight: 600 }}>✓ Đã check-in {r.full_name} lúc {fmtDateTime(r.checked_in_at)}</div>
          ) : done === "already" ? (
            <div className="adm-alert ok">Khách này đã check-in trước đó lúc {fmtDateTime(r.checked_in_at)}.</div>
          ) : cancelled ? (
            <div className="adm-alert">Đăng ký này đã bị huỷ — không check-in được.</div>
          ) : unpaid ? (
            <div className="adm-alert">Đăng ký chưa ghi nhận thanh toán ({REG_STATUS[r.status] ?? r.status}). Kiểm tra với khách trước khi cho vào.</div>
          ) : null}

          <div style={{ fontSize: 22, fontWeight: 700, margin: "4px 0 2px" }}>{r.full_name}</div>
          <div className="muted" style={{ marginBottom: 14 }}>{[r.position, r.company].filter(Boolean).join(" — ") || "—"}</div>
          <dl className="adm-dl">
            <div><dt>Sự kiện</dt><dd>{r.event_title}</dd></div>
            <div><dt>Mã đăng ký</dt><dd className="mono">{r.code}</dd></div>
            <div><dt>Hình thức</dt><dd>{ATTENDEE_TYPES[r.attendee_type] ?? r.attendee_type} · {fmtVnd(r.amount)}</dd></div>
            <div><dt>Trạng thái</dt><dd><span className={`adm-badge ${REG_STATUS_CLASS[r.status] ?? ""}`}>{REG_STATUS[r.status] ?? r.status}</span></dd></div>
            <div><dt>Điện thoại</dt><dd><a href={`tel:${r.phone}`}>{r.phone}</a></dd></div>
          </dl>

          <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
            {!r.checked_in && !cancelled ? (
              <button className="adm-btn primary" style={{ flex: 1, justifyContent: "center", padding: "14px 18px", fontSize: 16 }} onClick={confirmArrival} disabled={busy}>
                {busy ? "Đang xác nhận…" : "Xác nhận đã đến"}
              </button>
            ) : null}
            <button className="adm-btn" style={{ justifyContent: "center", padding: "14px 18px" }} onClick={next}>Khách tiếp theo</button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
