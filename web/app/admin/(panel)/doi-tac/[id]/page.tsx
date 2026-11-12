"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { PartnerWalletCard } from "@/components/admin/PartnerWalletCard";
import { Dialog, Field, Icon, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime, fromNow } from "@/lib/admin/format";
import type { AdminPartnerDetail } from "@/lib/admin/partners";

const TIERS = { new: "Mới", silver: "Bạc", strategic: "Chiến lược" } as const;
const EV_ICON: Record<string, string> = { created: "plus", email_verified: "mail", phone_verified: "phone", status: "lock", tier: "target", note: "note", password: "key" };

export default function PartnerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAdmin();
  const isAdmin = user.role === "admin";
  const [p, setP] = useState<AdminPartnerDetail | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [dlg, setDlg] = useState<null | "verify" | "lock" | "unlock" | "tier">(null);
  const [reason, setReason] = useState("");
  const [tier, setTier] = useState("new");

  useEffect(() => {
    api.get<AdminPartnerDetail>(`/partners/${id}`).then(
      (d) => {
        setP(d);
        setNote(d.note);
        setTier(d.tier);
        document.title = `${d.full_name} · Đối tác · Quản trị LeadScan`;
      },
      (e) => setError(errMsg(e)),
    );
  }, [id]);

  async function run(fn: () => Promise<AdminPartnerDetail>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      const d = await fn();
      setP(d);
      setNote(d.note);
      setTier(d.tier);
      setDlg(null);
      setReason("");
      setMsg({ ok: true, text: ok });
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="adm-alert">{error}</div>;
  if (!p) return <div style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>;

  const patch = (body: object) => api.patch<AdminPartnerDetail>(`/partners/${p.id}`, body);

  return (
    <>
      <div className="adm-head">
        <div>
          <Link href="/admin/doi-tac" className="muted" style={{ fontSize: 13 }}>← Đối tác</Link>
          <h1 style={{ marginTop: 4 }}>{p.full_name}</h1>
          <p className="mono">{p.code} · {p.kind_label}{p.kind === "org" ? ` · ${p.org_name}` : ""}</p>
        </div>
        <div className="adm-actions">
          {!p.email_verified ? <button className="adm-btn primary" onClick={() => setDlg("verify")}><Icon name="mail" size={14} /> Kích hoạt tay</button> : null}
          {isAdmin ? <button className="adm-btn" onClick={() => setDlg("tier")}><Icon name="target" size={14} /> Đổi hạng</button> : null}
          {isAdmin ? (
            p.status === "active"
              ? <button className="adm-btn danger" onClick={() => setDlg("lock")}><Icon name="lock" size={14} /> Khoá tài khoản</button>
              : <button className="adm-btn" onClick={() => setDlg("unlock")}>Mở khoá</button>
          ) : null}
        </div>
      </div>

      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ marginBottom: 16 }} role="status">{msg.text}</div> : null}
      {p.flags.length ? (
        <div className="adm-alert" style={{ marginBottom: 16 }}>
          <b>⚠ Cờ gian lận cần xem xét:</b>
          <ul style={{ margin: "4px 0 0 18px" }}>{p.flags.map((f) => <li key={f.key}>{f.label} — {f.detail}</li>)}</ul>
          <Link href="/admin/doi-tac/gian-lan" style={{ textDecoration: "underline" }}>Xem xét / bỏ qua cờ</Link>
        </div>
      ) : null}

      <div className="adm-grid side">
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Thông tin đối tác</h2>
              <StatusBadge status={p.status === "locked" ? "suspended" : "active"} label={p.status_label} />
            </div>
            <div className="bd">
              <dl className="adm-kv">
                <dt>Email đăng nhập</dt>
                <dd>{p.email} {p.email_verified ? <StatusBadge status="active" label={`Đã xác thực ${fmtDateTime(p.email_verified_at)}`} /> : <StatusBadge status="contacted" label="Chưa xác thực" />}</dd>
                <dt>Điện thoại / Zalo</dt>
                <dd>{p.phone}</dd>
                {p.kind === "org" ? (<><dt>Tổ chức</dt><dd>{p.org_name}</dd><dt>MST tổ chức</dt><dd className="mono">{p.org_tax_code}</dd></>) : null}
                <dt>Hạng</dt><dd>{p.tier_label}</dd>
                <dt>Ngành tiếp xúc</dt><dd>{p.industries.length ? p.industries.join(", ") : "—"}</dd>
                <dt>Khu vực</dt><dd>{p.regions.length ? p.regions.join(", ") : "—"}</dd>
                <dt>Điều khoản</dt><dd>Phiên bản {p.terms_version || "—"} · đồng ý {fmtDateTime(p.terms_accepted_at)}</dd>
                <dt>Đăng ký</dt><dd>{fmtDateTime(p.created_at)} · IP <span className="mono">{p.signup_ip || "—"}</span></dd>
                <dt>Đăng nhập gần nhất</dt><dd>{p.last_login_at ? fmtDateTime(p.last_login_at) : "—"}</dd>
              </dl>
            </div>
          </section>
          <PartnerWalletCard p={p} isAdmin={isAdmin} onChanged={(d, text) => { setP(d); setMsg({ ok: true, text }); }} />
          <section className="adm-card">
            <div className="hd"><h2>Cơ hội đã gửi</h2>
              <Link href={`/admin/xac-minh-doi-tac?status=all&partner_id=${p.id}`} style={{ color: "var(--brand-600)", fontSize: 13, fontWeight: 600 }}>Xem danh sách →</Link>
            </div>
            <div className="bd">
              <p>{p.submissions.total} cơ hội · đạt xác minh {p.submissions.ok}{p.submissions.pass_rate !== null ? ` (tỷ lệ đạt ${p.submissions.pass_rate}%)` : ""}</p>
            </div>
          </section>
          <section className="adm-card">
            <div className="hd"><h2>Ghi chú nội bộ</h2></div>
            <div className="bd" style={{ display: "grid", gap: 10 }}>
              <textarea className="adm-input" rows={4} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Nguồn đối tác, mức độ tin cậy, thoả thuận riêng…" />
              <div className="adm-actions">
                <button className="adm-btn" disabled={busy || note === p.note} onClick={() => run(() => patch({ note }), "Đã lưu ghi chú.")}>Lưu ghi chú</button>
              </div>
            </div>
          </section>
        </div>

        <section className="adm-card">
          <div className="hd"><h2>Nhật ký</h2>
            <Link href={`/admin/doi-tac/nhat-ky?partner_id=${p.id}`} style={{ color: "var(--brand-600)", fontSize: 13, fontWeight: 600 }}>Toàn bộ nhật ký →</Link>
          </div>
          <div className="bd">
            <ul className="adm-timeline">
              {p.events.map((e) => (
                <li key={e.id} className={`k-${e.kind === "created" ? "created" : e.kind === "note" ? "note" : "status"}`}>
                  <span className="dot"><Icon name={EV_ICON[e.kind] ?? "note"} /></span>
                  <div>
                    <div className="txt">{e.content}</div>
                    <div className="meta" title={fmtDateTime(e.created_at)}>{e.actor ?? "Đối tác / hệ thống"} · {fromNow(e.created_at)}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <Dialog open={dlg === "verify"} title="Kích hoạt tài khoản (xác nhận email)" onClose={() => setDlg(null)}
        footer={<><button className="adm-btn" onClick={() => setDlg(null)}>Huỷ</button>
          <button className="adm-btn primary" disabled={busy} onClick={() => run(() => api.post<AdminPartnerDetail>(`/partners/${p.id}/verify-email`, { note: reason }), "Đã kích hoạt — đối tác vào được cổng.")}>Xác nhận</button></>}>
        <p style={{ marginBottom: 12 }}>Dùng khi đối tác báo không nhận được mã OTP qua email. Chỉ kích hoạt khi đã liên hệ (số <b>{p.phone}</b>) và xác nhận <b>{p.full_name}</b> đúng là chủ email <b>{p.email}</b>.</p>
        <Field label="Ghi chú (không bắt buộc)" htmlFor="v-note"><input id="v-note" className="adm-input" value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)} placeholder="vd. Không nhận được email — đã gọi xác nhận 12/11" /></Field>
      </Dialog>

      <Dialog open={dlg === "lock" || dlg === "unlock"} title={dlg === "lock" ? "Khoá tài khoản đối tác" : "Mở khoá tài khoản"} onClose={() => setDlg(null)}
        footer={<><button className="adm-btn" onClick={() => setDlg(null)}>Huỷ</button>
          <button className={dlg === "lock" ? "adm-btn danger" : "adm-btn primary"} disabled={busy || (dlg === "lock" && !reason.trim())}
            onClick={() => run(() => patch({ status: dlg === "lock" ? "locked" : "active", reason }), dlg === "lock" ? "Đã khoá tài khoản và đăng xuất mọi phiên." : "Đã mở khoá tài khoản.")}>
            {dlg === "lock" ? "Khoá" : "Mở khoá"}</button></>}>
        {dlg === "lock" ? <p style={{ marginBottom: 12 }}>Đối tác bị đăng xuất ngay và không đăng nhập lại được cho tới khi mở khoá.</p> : null}
        <Field label={dlg === "lock" ? "Lý do (bắt buộc, ghi vào nhật ký)" : "Lý do (không bắt buộc)"} htmlFor="l-reason">
          <input id="l-reason" className="adm-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} />
        </Field>
      </Dialog>

      <Dialog open={dlg === "tier"} title="Đổi hạng đối tác" onClose={() => setDlg(null)}
        footer={<><button className="adm-btn" onClick={() => setDlg(null)}>Huỷ</button>
          <button className="adm-btn primary" disabled={busy || tier === p.tier} onClick={() => run(() => patch({ tier, reason }), "Đã đổi hạng.")}>Lưu</button></>}>
        <div style={{ display: "grid", gap: 12 }}>
          <Field label="Hạng" htmlFor="t-tier">
            <select id="t-tier" className="adm-input" value={tier} onChange={(e) => setTier(e.target.value)}>
              {Object.entries(TIERS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <Field label="Lý do" htmlFor="t-reason"><input id="t-reason" className="adm-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="vd. Đạt ≥ 10 cơ hội đạt và ≥ 3 cơ hội bán được trong 90 ngày" /></Field>
          <p className="muted" style={{ fontSize: 12.5 }}>Hạn mức ly cafe/tháng và tỷ lệ hoa hồng theo hạng áp dụng khi có ví hoa hồng (Mốc 3).</p>
        </div>
      </Dialog>
    </>
  );
}
