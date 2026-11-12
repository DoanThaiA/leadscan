"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Dialog, Field, Icon, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime, fromNow } from "@/lib/admin/format";
import type { FraudFlag } from "@/lib/admin/partners";

type View = "open" | "reviewed" | "all";
type Dlg = { kind: "review" | "reopen"; flag: FraudFlag } | { kind: "lock"; partner: FraudFlag["partners"][number] } | null;

const TYPES: Record<string, string> = {
  same_device: "Cùng IP + trình duyệt",
  same_ip: "Cùng IP",
  shared_bank: "Chung tài khoản ngân hàng",
  related_buyer: "Người mua có liên quan",
  fraud_marked: "Đã đánh dấu gian lận",
  high_reject: "Tỷ lệ không đạt cao",
};

/** Cờ gian lận (brief mục 9 & 10): chỉ là dấu hiệu để xem xét — quản trị viên khoá tài khoản hoặc bỏ qua cờ (ghi lý do vào nhật ký). */
export default function PartnerFraudPage() {
  const { user } = useAdmin();
  const isAdmin = user.role === "admin";
  const [items, setItems] = useState<FraudFlag[] | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [view, setView] = useState<View>("open");
  const [type, setType] = useState("");
  const [severity, setSeverity] = useState("");
  const [hideLocked, setHideLocked] = useState(false);
  const [dlg, setDlg] = useState<Dlg>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get<{ items: FraudFlag[] }>("/partner-reports/fraud").then((r) => { setItems(r.items); setError(""); }, (e) => setError(errMsg(e)));
  }, []);

  useEffect(() => {
    document.title = "Cờ gian lận đối tác · Quản trị LeadScan";
    load();
  }, [load]);

  const counts = useMemo(() => {
    const c = { open: 0, reviewed: 0, all: items?.length ?? 0, high: 0 };
    for (const f of items ?? []) {
      c[f.status] += 1;
      if (f.status === "open" && f.severity === "high") c.high += 1;
    }
    return c;
  }, [items]);

  const shown = useMemo(() => (items ?? []).filter((f) =>
    (view === "all" || f.status === view)
    && (!type || f.type === type)
    && (!severity || f.severity === severity)
    && (!hideLocked || f.partners.some((p) => p.status !== "locked"))), [items, view, type, severity, hideLocked]);

  function open(d: Dlg) {
    setDlg(d);
    setNote("");
    setMsg(null);
  }

  async function submit() {
    if (!dlg) return;
    setBusy(true);
    try {
      if (dlg.kind === "lock") {
        await api.patch(`/partners/${dlg.partner.id}`, { status: "locked", reason: note.trim() });
        setMsg({ ok: true, text: `Đã khoá ${dlg.partner.code} và đăng xuất mọi phiên.` });
      } else {
        await api.post(`/partner-reports/fraud/${dlg.kind}`, { key: dlg.flag.key, note: note.trim() });
        setMsg({ ok: true, text: dlg.kind === "review" ? "Đã bỏ qua cờ — ghi vào nhật ký các đối tác liên quan. Cờ tự hiện lại khi có dấu hiệu mới." : "Đã mở lại cờ để xem xét." });
      }
      setDlg(null);
      load();
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
      setDlg(null);
    } finally {
      setBusy(false);
    }
  }

  const tabs: [View, string, number][] = [["open", "Cần xem xét", counts.open], ["reviewed", "Đã bỏ qua", counts.reviewed], ["all", "Tất cả", counts.all]];
  const needNote = dlg?.kind === "review" || dlg?.kind === "lock";

  return (
    <>
      <div className="adm-head">
        <div>
          <Link href="/admin/doi-tac" className="muted" style={{ fontSize: 13 }}>← Đối tác</Link>
          <h1 style={{ marginTop: 4 }}>Cờ gian lận</h1>
          <p>Nhiều tài khoản cùng IP / trình duyệt / tài khoản ngân hàng, tỷ lệ không đạt cao, người mua có liên quan, đã bị đánh dấu gian lận</p>
        </div>
        <div className="adm-actions">
          <Link className="adm-btn" href="/admin/doi-tac/nhat-ky?kind=fraud"><Icon name="note" size={14} /> Lịch sử xử lý cờ</Link>
          <button className="adm-btn" onClick={() => { setItems(null); load(); }}><Icon name="refresh" size={14} /> Tải lại</button>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ marginBottom: 16 }} role="status">{msg.text}</div> : null}
      <div className="adm-alert warn" style={{ marginBottom: 16 }}>
        Cờ chỉ là dấu hiệu, có thể trùng hợp (vd. nhiều người cùng mạng văn phòng). Kiểm tra trước khi khoá tài khoản hoặc đánh dấu gian lận cơ hội
        (ở trang <Link href="/admin/xac-minh-doi-tac" style={{ textDecoration: "underline" }}>xác minh cơ hội</Link> — thu hồi thưởng).
        Hệ thống chưa thu dấu vân tay thiết bị — “cùng thiết bị” được suy ra từ cùng IP và trình duyệt lúc đăng ký.
      </div>

      {items ? (
        <div className="adm-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", marginBottom: 16 }}>
          <section className="adm-card adm-stat"><small>Cần xem xét</small><b>{counts.open}</b><span>cờ chưa xử lý</span></section>
          <section className="adm-card adm-stat"><small>Mức cao</small><b style={{ color: counts.high ? "var(--danger)" : undefined }}>{counts.high}</b><span>trong số cần xem xét</span></section>
          <section className="adm-card adm-stat"><small>Đã bỏ qua</small><b>{counts.reviewed}</b><span>hiện lại khi có dấu hiệu mới</span></section>
        </div>
      ) : null}

      <section className="adm-card">
        <div className="adm-tabs" role="tablist" aria-label="Trạng thái cờ">
          {tabs.map(([k, label, n]) => (
            <button key={k} role="tab" aria-selected={view === k} className={view === k ? "on" : undefined} onClick={() => setView(k)}>
              {label}{items ? <span>{n}</span> : null}
            </button>
          ))}
        </div>
        <div className="adm-toolbar">
          <select className="adm-input" style={{ width: 230 }} value={type} onChange={(e) => setType(e.target.value)} aria-label="Loại dấu hiệu">
            <option value="">Mọi loại dấu hiệu</option>
            {Object.entries(TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className="adm-input" style={{ width: 160 }} value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label="Mức độ">
            <option value="">Mọi mức độ</option>
            <option value="high">Cao</option>
            <option value="medium">Trung bình</option>
          </select>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <input type="checkbox" checked={hideLocked} onChange={(e) => setHideLocked(e.target.checked)} /> Ẩn cờ mà mọi đối tác đã bị khoá
          </label>
        </div>
        {!items ? <div className="bd" style={{ display: "grid", gap: 12 }}>{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} h={22} />)}</div>
          : !shown.length ? <div className="adm-empty">{view === "open" && !type && !severity ? "Không có cờ nào cần xem xét." : "Không có cờ phù hợp bộ lọc."}</div> : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Mức</th><th>Dấu hiệu</th><th>Đối tác</th><th>Xử lý</th></tr></thead>
              <tbody>
                {shown.map((f) => (
                  <tr key={f.key}>
                    <td><StatusBadge status={f.severity === "high" ? "rejected" : "contacted"} label={f.severity === "high" ? "⚠ Cao" : "Trung bình"} /></td>
                    <td>
                      <b>{f.label}</b>
                      <div className="sub">{f.detail}</div>
                      {f.review ? (
                        <div className="sub" style={{ marginTop: 4 }}>
                          {f.status === "reviewed" ? "✓ Đã bỏ qua" : "↺ Đã bỏ qua trước đây — có dấu hiệu mới"} · {f.review.actor ?? "—"} · <span title={fmtDateTime(f.review.created_at)}>{fromNow(f.review.created_at)}</span>
                          <div>Lý do: {f.review.note}</div>
                          {f.status === "open" && f.review.detail !== f.detail ? <div>Lúc bỏ qua: {f.review.detail}</div> : null}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      {f.partners.map((p) => (
                        <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                          <Link href={`/admin/doi-tac/${p.id}`} className="mono" style={{ color: "var(--brand-600)" }}>{p.code}</Link> · {p.full_name}
                          {p.status === "locked" ? <StatusBadge status="suspended" label="Đã khoá" />
                            : isAdmin ? <button className="adm-btn sm danger" onClick={() => open({ kind: "lock", partner: p })} aria-label={`Khoá ${p.code}`}><Icon name="lock" size={12} /> Khoá</button> : null}
                        </div>
                      ))}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {!isAdmin ? <span className="muted" style={{ fontSize: 12.5 }}>Chỉ quản trị viên</span>
                        : f.status === "open"
                          ? <button className="adm-btn sm" onClick={() => open({ kind: "review", flag: f })}><Icon name="check" size={12} /> Bỏ qua cờ</button>
                          : <button className="adm-btn sm" onClick={() => open({ kind: "reopen", flag: f })}>Mở lại</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Dialog open={dlg !== null} onClose={() => setDlg(null)}
        title={dlg?.kind === "lock" ? `Khoá tài khoản ${dlg.partner.code}` : dlg?.kind === "review" ? "Bỏ qua cờ gian lận" : "Mở lại cờ"}
        footer={<>
          <button className="adm-btn" onClick={() => setDlg(null)}>Huỷ</button>
          <button className={dlg?.kind === "lock" ? "adm-btn danger" : "adm-btn primary"} disabled={busy || (needNote && !note.trim())} onClick={submit}>
            {dlg?.kind === "lock" ? "Khoá" : dlg?.kind === "review" ? "Bỏ qua cờ" : "Mở lại"}
          </button>
        </>}>
        {dlg?.kind === "lock" ? (
          <p style={{ marginBottom: 12 }}><b>{dlg.partner.full_name}</b> bị đăng xuất ngay và không đăng nhập lại được cho tới khi mở khoá. Thưởng đã ghi không tự thu hồi — đánh dấu gian lận từng cơ hội ở trang xác minh nếu cần.</p>
        ) : dlg ? (
          <div style={{ marginBottom: 12 }}>
            <p><b>{dlg.flag.label}</b></p>
            <p className="muted" style={{ fontSize: 13 }}>{dlg.flag.detail} — {dlg.flag.partners.map((p) => p.code).join(", ")}</p>
            {dlg.kind === "review" ? <p style={{ marginTop: 8 }}>Chỉ bỏ qua khi đã kiểm tra và kết luận không phải gian lận. Cờ tự hiện lại nếu có dấu hiệu mới.</p> : null}
          </div>
        ) : null}
        <Field label={needNote ? "Lý do (bắt buộc, ghi vào nhật ký)" : "Lý do (không bắt buộc)"} htmlFor="f-note">
          <input id="f-note" className="adm-input" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)}
            placeholder={dlg?.kind === "review" ? "vd. Hai đối tác là vợ chồng, dùng chung wifi nhà — đã gọi xác nhận" : ""} />
        </Field>
      </Dialog>
    </>
  );
}
