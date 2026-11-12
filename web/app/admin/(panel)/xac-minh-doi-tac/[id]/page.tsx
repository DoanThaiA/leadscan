"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Fragment, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { CreditTable } from "@/components/admin/PartnerWalletCard";
import { Dialog, Field, Icon, ScoreChip, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDate, fmtDateTime, fromNow } from "@/lib/admin/format";
import type { AdminSubmissionDetail, DupHint, SubmissionMeta } from "@/lib/admin/partners";
import { vnd } from "@/lib/partner/content";
import { SUB_BADGE } from "@/lib/partner/submissions";

const DECISIONS: [string, string][] = [
  ["verified", "Đạt xác minh"],
  ["duplicate", "Trùng"],
  ["supplement", "Đóng góp bổ sung"],
  ["rejected", "Không đạt"],
];
const OPEN = ["submitted", "verifying"];

const REL_CLASS: Record<string, string> = { same: "adm-alert", similar: "adm-alert warn", different: "adm-alert ok" };

function Dups({ title, items }: { title: string; items: DupHint[] }) {
  if (!items.length) return null;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <b style={{ fontSize: 13 }}>{title}</b>
      {items.map((h) => {
        // cơ hội cũ (trước khi so theo nhu cầu) chưa có relation → dùng same_group như trước
        const rel = h.relation ?? (h.same_group ? "same" : "different");
        return (
          <div key={`${h.type}-${h.id}`} className={REL_CLASS[rel]} style={{ display: "grid", gap: 2 }}>
            <span>
              <b>{h.relation_label ?? (rel === "same" ? "Nghi trùng" : "Liên quan")}{h.similarity !== undefined ? ` · giống ${h.similarity}%` : ""}</b>
              {" — "}
              <Link href={h.type === "opportunity" ? `/admin/co-hoi/${h.id}` : `/admin/xac-minh-doi-tac/${h.id}`} className="mono" style={{ fontWeight: 600, textDecoration: "underline" }}>{h.code}</Link>
              {" · "}{h.type === "opportunity" ? "phiếu cơ hội" : "cơ hội đối tác khác"} · {h.match === "tax" ? "cùng MST" : h.match === "name" ? "cùng tên doanh nghiệp" : "khác doanh nghiệp, cùng tỉnh + ngành"} · {fromNow(h.created_at)}
            </span>
            <span style={{ fontSize: 12.5, opacity: 0.85 }}>{h.title}</span>
            {h.basis?.length ? <span style={{ fontSize: 12, opacity: 0.8 }}>Căn cứ: {h.basis.join(" · ")}</span> : null}
          </div>
        );
      })}
    </div>
  );
}

export default function PartnerSubmissionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, meta: adminMeta } = useAdmin();
  const [s, setS] = useState<AdminSubmissionDetail | null>(null);
  const [m, setM] = useState<SubmissionMeta | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [decision, setDecision] = useState("");
  const [reason, setReason] = useState("");
  const [score, setScore] = useState("");
  const [large, setLarge] = useState(false);
  const [pnote, setPnote] = useState("");
  const [inote, setInote] = useState("");
  const [fraudOpen, setFraudOpen] = useState(false);
  const [fraudReason, setFraudReason] = useState("");
  const [fraudLock, setFraudLock] = useState(true);

  function load(d: AdminSubmissionDetail) {
    setS(d);
    setScore(String(d.final_score ?? d.auto_score));
    setLarge(d.is_large);
    setPnote(d.partner_note);
    setInote(d.internal_note);
    setDecision(OPEN.includes(d.status) || d.status === "published" ? "" : d.status);
    setReason(d.reject_reason);
    document.title = `${d.code} · Xác minh cơ hội đối tác`;
  }

  useEffect(() => {
    api.get<AdminSubmissionDetail>(`/partner-submissions/${id}`).then(load, (e) => setError(errMsg(e)));
    api.get<SubmissionMeta>("/partner-submissions/meta").then(setM, () => {});
  }, [id]);

  async function run(fn: () => Promise<AdminSubmissionDetail>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      load(await fn());
      setMsg({ ok: true, text: ok });
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  async function createOpp() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post<{ opportunity_id: number }>(`/partner-submissions/${id}/create-opportunity`);
      router.push(`/admin/co-hoi/${r.opportunity_id}`);
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
      setBusy(false);
    }
  }

  if (error) return <div className="adm-alert">{error}</div>;
  if (!s || !m) return <div style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>;

  const open = OPEN.includes(s.status);
  const canDecide = s.status !== "published" && !s.opportunity && (open || user.role === "admin");
  const scoreN = Number(score);
  const row = (k: string, v: React.ReactNode) => (v ? <><dt>{k}</dt><dd>{v}</dd></> : null);
  const otherHints = s.dup_live.filter((h) => !s.dup_hints.some((x) => x.type === h.type && x.id === h.id));

  return (
    <>
      <div className="adm-head">
        <div>
          <Link href="/admin/xac-minh-doi-tac" className="muted" style={{ fontSize: 13 }}>← Xác minh cơ hội đối tác</Link>
          <h1 style={{ marginTop: 4 }}>{s.title || s.company_name}</h1>
          <p className="mono">{s.code} · gửi {fmtDateTime(s.created_at)}{open ? ` · hạn ${fmtDate(s.sla_due_at)}` : ""}</p>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {s.overdue ? <StatusBadge status="rejected" label="Quá hạn SLA" /> : null}
          <StatusBadge status={SUB_BADGE[s.status]} label={s.status_label} />
        </div>
      </div>
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ marginBottom: 16 }} role="status">{msg.text}</div> : null}

      <div className="adm-grid side">
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Cơ hội đối tác gửi</h2></div>
            <div className="bd">
              <dl className="adm-kv">
                {row("Tiêu đề (→ tiêu đề phiếu)", s.title)}
                {row("Doanh nghiệp", <b>{s.company_name}</b>)}
                {row("Mã số thuế", s.tax_code ? <span className="mono">{s.tax_code}</span> : <span className="muted">Không có</span>)}
                {row("Tra MST (trình duyệt)", s.tax_lookup && <>{s.tax_lookup.name} · <span style={{ color: s.tax_lookup.active ? "var(--ok)" : "var(--danger)" }}>{s.tax_lookup.status}</span> <span className="muted">(gợi ý, cần kiểm chứng)</span></>)}
                {row("Khu vực · ngành", `${s.province} · ${s.industry}`)}
                {row("Loại cơ hội", s.kind_label)}
                {row("Nhu cầu", <span style={{ whiteSpace: "pre-wrap" }}>{s.need}</span>)}
                {row("Quy mô", s.scale)}
                {row("Thời điểm cần", s.timing)}
                {row("Nguồn", s.source_label)}
                {row("Link nguồn", s.source_url && <a href={s.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand-600)", wordBreak: "break-all" }}>{s.source_url}</a>)}
                {row("Mức độ chắc chắn", s.certainty_label)}
                {row("Tài liệu, link", s.evidence && <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{s.evidence}</span>)}
                {row("Người liên hệ", (s.contact_name || s.contact_phone || s.contact_email) && (
                  <>{[s.contact_name, s.contact_title, s.contact_phone, s.contact_email].filter(Boolean).join(" · ")}
                    <div style={{ fontSize: 12.5, color: s.contact_consent ? "var(--ok)" : "var(--danger)" }}>{s.contact_consent ? "✓ Đối tác xác nhận người này đồng ý được giới thiệu" : "Chưa có xác nhận đồng ý"}</div></>
                ))}
                {row("Ảnh", s.images?.length ? (
                  <div className="adm-sub-images">{s.images.map((im) => (
                    <a key={im.id} href={im.url ?? "#"} target="_blank" rel="noopener noreferrer" title={im.filename}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={im.thumb_url ?? im.url ?? ""} alt={im.filename} />
                    </a>))}</div>) : null)}
                {row("Kết nối trực tiếp", s.can_connect === "yes" ? "Đối tác kết nối được" : s.can_connect === "no" ? "Không" : "")}
              </dl>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Kiểm tra trùng ({m.dup_days} ngày)</h2></div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              {!s.dup_hints.length && !otherHints.length ? <p className="muted">Không thấy cơ hội nào cùng doanh nghiệp (theo MST hoặc tên), hay nhu cầu giống trong cùng tỉnh + ngành.</p> : null}
              <Dups title="Lúc đối tác gửi" items={s.dup_hints} />
              <Dups title="Phát sinh sau khi gửi" items={otherHints} />
              <p className="muted" style={{ fontSize: 12.5 }}>Kết luận theo độ giống của mô tả nhu cầu (ngữ nghĩa + từ khoá + sản phẩm): ≥ 70% trùng, 45–70% gần giống, dưới 45% là nhu cầu khác — cùng doanh nghiệp nhưng nhu cầu khác KHÔNG tính trùng. Ai gửi trước được ghi nhận. Cơ hội đã có nhưng đối tác bổ sung thông tin mới có giá trị (người ra quyết định, ngân sách, thời điểm) → chọn <b>Đóng góp bổ sung</b>.</p>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Điểm chất lượng tự động</h2><ScoreChip score={s.auto_score} /></div>
            <div className="bd">
              <dl className="adm-kv">
                {s.score_detail.map((p) => (<Fragment key={p.label}><dt style={{ color: "var(--ink-2)" }}>{p.label}</dt><dd style={{ color: p.points < 0 ? "var(--danger)" : "var(--ok)", fontWeight: 600 }}>{p.points > 0 ? "+" : ""}{p.points}</dd></Fragment>))}
              </dl>
              <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>Điểm theo quy tắc (độ đủ thông tin, độ chắc chắn, nguồn, bằng chứng, nghi trùng) — chỉ là gợi ý; người duyệt chốt điểm cuối. Ngưỡng Đạt: {m.min_score}.</p>
            </div>
          </section>
        </div>

        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Xác minh</h2></div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              {open ? (
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <span className="muted">Người xác minh: <b style={{ color: "var(--ink)" }}>{s.assigned_to?.full_name ?? "Chưa giao"}</b></span>
                  {s.assigned_to?.id !== user.id ? <button className="adm-btn sm" disabled={busy} onClick={() => run(() => api.post(`/partner-submissions/${id}/assign`, {}), "Đã nhận xác minh.")}>Tôi nhận</button> : null}
                  <select className="adm-input" style={{ width: 170, height: 30 }} value="" disabled={busy} aria-label="Giao cho"
                    onChange={(e) => e.target.value && run(() => api.post(`/partner-submissions/${id}/assign`, { user_id: Number(e.target.value) }), "Đã giao việc.")}>
                    <option value="">Giao cho…</option>
                    {adminMeta.staff.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                  </select>
                </div>
              ) : (
                <p className="muted">Quyết định bởi <b style={{ color: "var(--ink)" }}>{s.decided_by ?? "—"}</b> · {fmtDateTime(s.decided_at)} · điểm {s.final_score ?? "—"}{s.is_large ? " · cơ hội lớn" : ""}</p>
              )}

              {canDecide ? (
                <>
                  {!open ? <div className="adm-alert warn">Đổi quyết định đã đưa ra (chỉ quản trị viên) — đối tác sẽ nhận email mới.</div> : null}
                  <div role="group" aria-label="Quyết định" style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {DECISIONS.map(([k, label]) => (
                      <button key={k} type="button" className={decision === k ? "adm-btn primary sm" : "adm-btn sm"} aria-pressed={decision === k} onClick={() => setDecision(k)}>{label}</button>
                    ))}
                  </div>
                  {decision === "rejected" ? (
                    <Field label="Lý do không đạt *" htmlFor="d-reason">
                      <select id="d-reason" className="adm-input" value={reason} onChange={(e) => setReason(e.target.value)}>
                        <option value="">Chọn lý do…</option>
                        {Object.entries(m.reject_reasons).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                    </Field>
                  ) : null}
                  <Field label={`Điểm chất lượng chốt (ngưỡng ${m.min_score})`} htmlFor="d-score">
                    <input id="d-score" className="adm-input" type="number" min={0} max={100} value={score} onChange={(e) => setScore(e.target.value)} />
                  </Field>
                  {decision === "verified" ? (
                    <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13.5 }}>
                      <input type="checkbox" checked={large} onChange={(e) => setLarge(e.target.checked)} /> Cơ hội lớn (gói thầu, dự án đầu tư lớn — tỷ lệ hoa hồng riêng)
                    </label>
                  ) : null}
                  <Field label="Ghi chú gửi đối tác (đối tác thấy, kèm email)" htmlFor="d-pnote">
                    <textarea id="d-pnote" className="adm-input" rows={3} value={pnote} onChange={(e) => setPnote(e.target.value)} placeholder={decision === "rejected" ? "Gợi ý đối tác bổ sung gì để lần sau đạt…" : "Cảm ơn bạn…"} />
                  </Field>
                  <Field label="Ghi chú nội bộ" htmlFor="d-inote">
                    <textarea id="d-inote" className="adm-input" rows={2} value={inote} onChange={(e) => setInote(e.target.value)} placeholder="Đã gọi xác nhận với…, nguồn kiểm chứng…" />
                  </Field>
                  {decision === "verified" && scoreN < m.min_score ? <div className="adm-alert">Điểm {scoreN} dưới ngưỡng {m.min_score} — chưa thể Đạt xác minh.</div> : null}
                  <div className="adm-actions">
                    <button className="adm-btn primary" disabled={busy || !decision || (decision === "rejected" && !reason) || (decision === "verified" && scoreN < m.min_score)}
                      onClick={() => run(() => api.post(`/partner-submissions/${id}/decide`, { decision, reason, partner_note: pnote, internal_note: inote, final_score: scoreN, is_large: large }), "Đã lưu kết quả xác minh — đối tác nhận email.")}>
                      Lưu kết quả
                    </button>
                  </div>
                </>
              ) : !open ? (
                <>
                  {s.reject_label ? <p><b>Lý do:</b> {s.reject_label}</p> : null}
                  {s.partner_note ? <p style={{ whiteSpace: "pre-wrap" }}><b>Gửi đối tác:</b> {s.partner_note}</p> : null}
                  <Field label="Ghi chú nội bộ" htmlFor="n-inote">
                    <textarea id="n-inote" className="adm-input" rows={2} value={inote} onChange={(e) => setInote(e.target.value)} />
                  </Field>
                  <div className="adm-actions"><button className="adm-btn sm" disabled={busy || inote === s.internal_note} onClick={() => run(() => api.patch(`/partner-submissions/${id}`, { internal_note: inote }), "Đã lưu ghi chú.")}>Lưu ghi chú</button></div>
                </>
              ) : null}
            </div>
          </section>

          {s.status === "verified" || s.opportunity ? (
            <section className="adm-card">
              <div className="hd"><h2>Phiếu cơ hội</h2></div>
              <div className="bd" style={{ display: "grid", gap: 10 }}>
                {s.opportunity ? (
                  <>
                    <p><Link href={`/admin/co-hoi/${s.opportunity.id}`} className="mono" style={{ fontWeight: 600, color: "var(--brand-600)" }}>{s.opportunity.code}</Link> · {s.opportunity.status === "published" ? "Đang bán" : s.opportunity.status === "draft" ? "Nháp" : "Đã đóng"}</p>
                    <p className="muted" style={{ fontSize: 13 }}>{s.opportunity.title}</p>
                    {s.opportunity.status === "draft" ? <p className="muted" style={{ fontSize: 12.5 }}>Hoàn thiện tiêu đề, tóm tắt, giá, khu vực rồi chuyển trạng thái “Đang bán” — cơ hội đối tác tự chuyển “Đã xuất bản”.</p> : null}
                  </>
                ) : (
                  <>
                    <p className="muted" style={{ fontSize: 13 }}>Tạo phiếu NHÁP điền sẵn từ cơ hội này, gắn mã đối tác nguồn {s.partner.code}. Bạn hoàn thiện rồi mở bán ở trang phiếu.</p>
                    <button className="adm-btn primary" disabled={busy} onClick={createOpp}><Icon name="plus" size={14} /> Tạo phiếu nháp</button>
                  </>
                )}
              </div>
            </section>
          ) : null}

          <section className="adm-card">
            <div className="hd">
              <h2>Ví — cơ hội này</h2>
              <span className="muted" style={{ fontSize: 13 }}>{s.sold_count} lượt bán · đã ghi {vnd(s.earned)}{s.share_until ? ` · chia sẻ đến ${fmtDate(s.share_until)}` : ""}</span>
            </div>
            <CreditTable items={s.credits} showSub={false} />
            {user.role === "admin" && s.reject_reason !== "fraud" ? (
              <div className="bd" style={{ borderTop: "1px solid var(--line)" }}>
                <button className="adm-btn danger sm" onClick={() => setFraudOpen(true)}><Icon name="flag" size={14} /> Đánh dấu gian lận</button>
              </div>
            ) : null}
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Đối tác</h2><Link href={`/admin/doi-tac/${s.partner.id}`} style={{ color: "var(--brand-600)", fontSize: 13, fontWeight: 600 }}>Hồ sơ →</Link></div>
            <div className="bd">
              <dl className="adm-kv">
                <dt>Đối tác</dt><dd>{s.partner.full_name} <span className="mono muted">{s.partner.code}</span></dd>
                {s.partner.org_name ? <><dt>Tổ chức</dt><dd>{s.partner.org_name}</dd></> : null}
                <dt>Điện thoại</dt><dd>{s.partner.phone}</dd>
                <dt>Đã gửi</dt><dd>{s.partner_stats.total} cơ hội · đạt {s.partner_stats.ok}{s.partner_stats.pass_rate !== null ? ` (${s.partner_stats.pass_rate}%)` : ""}</dd>
              </dl>
              <Link href={`/admin/xac-minh-doi-tac?status=all&partner_id=${s.partner.id}`} className="adm-btn sm" style={{ marginTop: 10 }}>Các cơ hội khác của đối tác</Link>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Nhật ký</h2></div>
            <div className="bd">
              <ul className="adm-timeline">
                {s.events.map((e, i) => (
                  <li key={i} className={e.kind === "sub_created" ? "k-created" : "k-status"}>
                    <span className="dot"><Icon name={e.kind === "sub_decided" ? "check" : e.kind === "sub_opp" || e.kind === "sub_published" ? "ticket" : "note"} /></span>
                    <div><div className="txt">{e.content}</div><div className="meta" title={fmtDateTime(e.created_at)}>{e.actor ?? "Đối tác / hệ thống"} · {fromNow(e.created_at)}</div></div>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </div>
      </div>
      <Dialog open={fraudOpen} title="Đánh dấu gian lận" onClose={() => setFraudOpen(false)}
        footer={<><button className="adm-btn" onClick={() => setFraudOpen(false)}>Huỷ</button>
          <button className="adm-btn danger" disabled={busy || fraudReason.trim().length < 5}
            onClick={() => run(() => api.post(`/partner-submissions/${id}/fraud`, { reason: fraudReason, lock_partner: fraudLock }), "Đã đánh dấu gian lận, thu hồi thưởng.").then(() => setFraudOpen(false))}>Xác nhận gian lận</button></>}>
        <div style={{ display: "grid", gap: 12 }}>
          <p>Huỷ mọi khoản Chờ duyệt và thu hồi khoản Khả dụng của cơ hội này (<b>kể cả ly cafe</b>), chuyển “Không đạt — Gian lận”.</p>
          {s.opportunity?.status === "published" ? <div className="adm-alert warn">Phiếu {s.opportunity.code} vẫn đang bán — đóng phiếu ở trang Cơ hội & phiếu nếu cần.</div> : null}
          <Field label="Lý do (bắt buộc, ghi nhật ký)" htmlFor="fr-reason"><input id="fr-reason" className="adm-input" value={fraudReason} maxLength={300} onChange={(e) => setFraudReason(e.target.value)} /></Field>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13.5 }}><input type="checkbox" checked={fraudLock} onChange={(e) => setFraudLock(e.target.checked)} /> Khoá tài khoản đối tác {s.partner.code}</label>
        </div>
      </Dialog>
    </>
  );
}
