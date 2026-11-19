"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Dialog, Icon, ScoreChip, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fromNow } from "@/lib/admin/format";

type Recipient = {
  id: number;
  full_name: string;
  email: string;
  company: { id: number; code: string; name: string; industry: string; province: string };
  score: number | null;
  purchased: boolean;
  last_email: { status: string; at: string | null } | null;
};
type RecipResp = { can_send: boolean; blocked_reason: string; matched_companies: number; items: Recipient[] };
type Sent = {
  id: number;
  email: string;
  recipient_name: string;
  status: string;
  status_label: string;
  error: string;
  created_at: string;
  sent_at: string | null;
  company: { id: number; name: string } | null;
  sent_by: string | null;
};
type Preview = { subject: string; to: string; html: string };

const BADGE: Record<string, string> = { sent: "active", queued: "new", failed: "rejected" };
const MAX = 100;

/** Trang phiếu cơ hội (admin): chọn khách hàng → xem trước → gửi phiếu qua email (mỗi người 1 email riêng). */
export default function OppMailCard({ oppId }: { oppId: number }) {
  const [scope, setScope] = useState<"matched" | "all">("matched");
  const [q, setQ] = useState("");
  const [data, setData] = useState<RecipResp | null>(null);
  const [selected, setSelected] = useState<Map<number, Recipient>>(new Map());
  const [note, setNote] = useState("");
  const [history, setHistory] = useState<Sent[] | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  const base = `/opportunities/${oppId}/mail`;
  const loadList = useCallback(() => {
    setData(null);
    api.get<RecipResp>(`${base}/recipients` + qs({ scope, q: q.trim() || undefined })).then((r) => {
      setData(r);
      if (scope === "matched" && !q && !r.items.length && r.matched_companies === 0) setScope("all"); // chưa doanh nghiệp nào phù hợp → hiện tất cả
    }, (e) => setError(errMsg(e)));
  }, [base, scope, q]);
  const loadHistory = useCallback(() => {
    api.get<{ items: Sent[] }>(`${base}/history`).then((r) => setHistory(r.items), (e) => setError(errMsg(e)));
  }, [base]);

  useEffect(() => {
    const t = setTimeout(loadList, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [loadList, q]);
  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  function toggle(r: Recipient) {
    setSelected((m) => {
      const n = new Map(m);
      if (n.has(r.id)) n.delete(r.id);
      else if (n.size < MAX) n.set(r.id, r);
      return n;
    });
  }
  const pickable = (data?.items ?? []).filter((r) => !r.purchased);
  const allPicked = pickable.length > 0 && pickable.every((r) => selected.has(r.id));
  function toggleAll() {
    setSelected((m) => {
      const n = new Map(m);
      if (allPicked) pickable.forEach((r) => n.delete(r.id));
      else for (const r of pickable) if (n.size < MAX) n.set(r.id, r);
      return n;
    });
  }

  async function openPreview() {
    const first = selected.values().next().value as Recipient | undefined;
    if (!first) return;
    setPreview(null);
    setPreviewOpen(true);
    try {
      setPreview(await api.get<Preview>(`${base}/preview` + qs({ member_id: first.id, note: note.trim() || undefined })));
    } catch (e) {
      setPreviewOpen(false);
      alert(errMsg(e));
    }
  }

  async function send() {
    const n = selected.size;
    if (!n || !confirm(`Gửi phiếu cơ hội này qua email cho ${n} người đã chọn? Mỗi người nhận 1 email riêng.`)) return;
    setBusy(true);
    try {
      const r = await api.post<{ queued: number; skipped: { email: string; reason: string }[] }>(`${base}/send`, { member_ids: [...selected.keys()], note: note.trim() });
      setSelected(new Map());
      setPreviewOpen(false);
      setFlash(`Đang gửi ${r.queued} email` + (r.skipped.length ? ` · bỏ qua ${r.skipped.length} (đã mua phiếu)` : ""));
      setTimeout(() => setFlash(""), 5000);
      setTimeout(() => { loadHistory(); loadList(); }, 1500);
    } catch (e) {
      alert(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function retry(s: Sent) {
    try {
      await api.post(`${base}/history/${s.id}/retry`);
      setTimeout(loadHistory, 1500);
    } catch (e) {
      alert(errMsg(e));
    }
  }

  const blocked = data && !data.can_send;
  return (
    <section className="adm-card" style={{ marginTop: 16 }}>
      <div className="hd" style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <h2><Icon name="mail" size={16} /> Gửi cơ hội cho khách hàng qua email</h2>
        {flash ? <span className="adm-badge s-active" role="status">{flash}</span> : null}
      </div>
      <div className="bd" style={{ display: "grid", gap: 12 }}>
        <p className="muted" style={{ fontSize: 13 }}>
          Email chỉ có phần xem trước (tiêu đề, tóm tắt, ngành, khu vực, quy mô, hạn, giá phiếu theo điểm phù hợp của từng doanh nghiệp) và nút mở cơ hội trong cổng thành viên.
          Tên bên có nhu cầu, chi tiết và đầu mối chỉ mở khi khách mua phiếu.
        </p>
        {error ? <div className="adm-alert">{error}</div> : null}
        {blocked ? <div className="adm-alert">{data.blocked_reason}</div> : null}

        <div className="adm-tabs" role="tablist" style={{ margin: 0 }}>
          <button role="tab" aria-selected={scope === "matched"} className={scope === "matched" ? "on" : undefined} onClick={() => setScope("matched")}>
            Doanh nghiệp phù hợp{data ? <span>{data.matched_companies}</span> : null}
          </button>
          <button role="tab" aria-selected={scope === "all"} className={scope === "all" ? "on" : undefined} onClick={() => setScope("all")}>Tất cả khách hàng</button>
        </div>
        <div className="adm-search">
          <Icon name="search" />
          <input className="adm-input" type="search" placeholder="Tìm doanh nghiệp, mã LS-, MST, email, người liên hệ, ngành…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Tìm khách hàng" />
        </div>

        {!data ? (
          <Skeleton h={120} />
        ) : !data.items.length ? (
          <div className="adm-empty">{scope === "matched" ? "Chưa có doanh nghiệp nào được chấm là phù hợp với phiếu này — chọn tab “Tất cả khách hàng”." : "Không tìm thấy khách hàng."}</div>
        ) : (
          <div className="adm-table-wrap" style={{ maxHeight: 380, overflow: "auto" }}>
            <table className="adm-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" checked={allPicked} onChange={toggleAll} aria-label="Chọn tất cả trong danh sách" disabled={!pickable.length} /></th>
                  <th>Khách hàng</th><th>Phù hợp</th><th>Email phiếu này</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id} className={r.purchased ? undefined : "link"} onClick={() => !r.purchased && toggle(r)} style={r.purchased ? { opacity: 0.6 } : undefined}>
                    <td><input type="checkbox" checked={selected.has(r.id)} disabled={r.purchased} onChange={() => toggle(r)} onClick={(e) => e.stopPropagation()} aria-label={`Chọn ${r.email}`} /></td>
                    <td>
                      <Link className="name" href={`/admin/khach-hang/${r.company.id}`} onClick={(e) => e.stopPropagation()}>{r.company.name}</Link>
                      <div className="sub">{r.full_name} · {r.email}</div>
                      <div className="sub"><span className="mono">{r.company.code}</span>{r.company.industry ? ` · ${r.company.industry}` : ""}{r.company.province ? ` · ${r.company.province}` : ""}</div>
                    </td>
                    <td>{r.score !== null ? <ScoreChip score={r.score} /> : <span className="muted">—</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {r.purchased ? <StatusBadge status="gold" label="Đã mua phiếu" />
                        : r.last_email ? <span title={fmtDateTime(r.last_email.at)}><StatusBadge status={BADGE[r.last_email.status] ?? "new"} label={r.last_email.status === "sent" ? "Đã gửi" : r.last_email.status === "failed" ? "Gửi lỗi" : "Đang gửi"} /> <span className="muted" style={{ fontSize: 12 }}>{r.last_email.at ? fromNow(r.last_email.at) : ""}</span></span>
                        : <span className="muted">Chưa gửi</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {selected.size ? (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <span className="muted" style={{ fontSize: 13 }}>Đã chọn {selected.size}{selected.size >= MAX ? ` (tối đa ${MAX})` : ""}:</span>
            {[...selected.values()].slice(0, 12).map((r) => (
              <button key={r.id} className="adm-tag" onClick={() => toggle(r)} title="Bỏ chọn" style={{ cursor: "pointer" }}>{r.company.name} ✕</button>
            ))}
            {selected.size > 12 ? <span className="muted">… và {selected.size - 12} người khác</span> : null}
            <button className="adm-btn sm ghost" onClick={() => setSelected(new Map())}>Bỏ chọn hết</button>
          </div>
        ) : null}

        <textarea
          className="adm-input" style={{ minHeight: 80, height: "auto", padding: "8px 10px" }} maxLength={1000}
          placeholder="Lời nhắn hiện ở đầu email (không bắt buộc), ví dụ: Cơ hội này khớp năng lực sản xuất hộp giấy của anh chị, hạn báo giá cuối tháng."
          value={note} onChange={(e) => setNote(e.target.value)} aria-label="Lời nhắn trong email"
        />
        <div className="adm-actions">
          <button className="adm-btn" disabled={!selected.size} onClick={openPreview}><Icon name="external" size={14} /> Xem trước email</button>
          <button className="adm-btn primary" disabled={!selected.size || busy || !!blocked} onClick={send}><Icon name="mail" size={14} /> Gửi cho {selected.size || 0} người</button>
        </div>

        <div>
          <h3 style={{ fontSize: 14, margin: "8px 0" }}>Đã gửi{history ? ` (${history.length})` : ""}</h3>
          {!history ? <Skeleton h={40} /> : !history.length ? <p className="muted">Chưa gửi phiếu này cho ai.</p> : (
            <div className="adm-table-wrap" style={{ maxHeight: 300, overflow: "auto" }}>
              <table className="adm-table">
                <thead><tr><th>Người nhận</th><th>Trạng thái</th><th>Lúc</th><th>Người gửi</th><th></th></tr></thead>
                <tbody>
                  {history.map((s) => (
                    <tr key={s.id}>
                      <td>
                        {s.company ? <Link className="name" href={`/admin/khach-hang/${s.company.id}`}>{s.company.name}</Link> : null}
                        <div className="sub">{s.recipient_name} · {s.email}</div>
                      </td>
                      <td><StatusBadge status={BADGE[s.status] ?? "new"} label={s.status_label} />{s.error ? <div className="sub" style={{ color: "var(--danger)" }}>{s.error}</div> : null}</td>
                      <td style={{ whiteSpace: "nowrap" }}><span title={fmtDateTime(s.sent_at ?? s.created_at)}>{fromNow(s.sent_at ?? s.created_at)}</span></td>
                      <td>{s.sent_by ?? "—"}</td>
                      <td>{s.status === "failed" ? <button className="adm-btn sm" onClick={() => retry(s)}><Icon name="refresh" size={13} /> Gửi lại</button> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <Dialog
        open={previewOpen}
        wide
        title="Xem trước email"
        onClose={() => setPreviewOpen(false)}
        footer={(
          <>
            <button className="adm-btn sm ghost" onClick={() => setPreviewOpen(false)}>Đóng</button>
            <button className="adm-btn sm primary" disabled={busy || !!blocked} onClick={send}>Gửi cho {selected.size} người</button>
          </>
        )}
      >
        {!preview ? <Skeleton h={300} /> : (
          <div style={{ display: "grid", gap: 8 }}>
            <dl className="adm-dl">
              <div><dt>Tới</dt><dd>{preview.to}{selected.size > 1 ? ` (mẫu của người đầu tiên — mỗi người nhận email riêng với tên và giá phiếu của họ)` : ""}</dd></div>
              <div><dt>Tiêu đề</dt><dd>{preview.subject}</dd></div>
            </dl>
            <iframe title="Xem trước email" srcDoc={preview.html} sandbox="" style={{ width: "100%", height: 560, border: "1px solid var(--line, #e6e9ec)", borderRadius: 8, background: "#f3f5f7" }} />
          </div>
        )}
      </Dialog>
    </section>
  );
}
