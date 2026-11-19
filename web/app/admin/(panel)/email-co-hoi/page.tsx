"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Dialog, Icon, Skeleton, StatusBadge } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum, fromNow } from "@/lib/admin/format";

type Opp = { id: number; code: string; status: string; title: string };
type Row = {
  id: number;
  from_email: string;
  from_name: string;
  subject: string;
  received_at: string | null;
  created_at: string;
  status: string;
  reason: string;
  error: string;
  industry: string | null;
  confidence: number | null;
  title: string | null;
  opportunity: Opp | null;
  purged: boolean;
  attachment_count: number;
};
type Detail = Row & {
  to: string;
  body_text: string;
  attachment_names: string[];
  ai_json: Record<string, unknown> | null;
  ai_model: string;
  ai_cost_usd: number;
  processed_at: string | null;
  blocked: boolean;
  thread: Row[];
};
type Meta = {
  statuses: Record<string, string>;
  counts: Record<string, number>;
  industries: string[];
  webhook_enabled: boolean;
  ai_enabled: boolean;
  ai_model: string;
  ai_month_cost_usd: number;
  ai_budget_usd: number;
  min_confidence: number;
  keep_days: number;
  last_received_at: string | null;
};

const TABS: [string, string][] = [
  ["drafted", "Đã tạo nháp"],
  ["review", "Cần xem lại"],
  ["merged", "Gộp vào phiếu có sẵn"],
  ["rejected", "Không phải cơ hội"],
  ["skipped", "Bỏ qua"],
  ["error", "Lỗi"],
  ["pending", "Chờ xử lý"],
  ["all", "Tất cả"],
];
const BADGE: Record<string, string> = {
  drafted: "active", review: "contacted", merged: "new", rejected: "rejected", skipped: "suspended", error: "rejected", new: "new", processing: "new",
};
const AI_LABELS: [string, string][] = [
  ["title", "Tiêu đề"], ["summary", "Tóm tắt"], ["industry", "Ngành"], ["province", "Tỉnh / thành"], ["region", "Khu vực"],
  ["scale", "Quy mô"], ["estimated_value", "Giá trị ước tính"], ["deadline", "Hạn"], ["buyer_name", "Bên có nhu cầu"],
  ["buyer_tax_id", "MST"], ["buyer_website", "Website"], ["buyer_address", "Địa chỉ"],
];
const PAGE = 20;

export default function InboundEmailsPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [status, setStatus] = useState("drafted");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: Row[]; total: number } | null>(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get<Meta>("/inbound-emails/meta").then(setMeta, (e) => setError(errMsg(e)));
    api.get<{ items: Row[]; total: number }>("/inbound-emails" + qs({ status, q: q.trim() || undefined, page, page_size: PAGE }))
      .then(setData, (e) => setError(errMsg(e)));
  }, [status, q, page]);

  useEffect(() => {
    document.title = "Cơ hội từ email · Quản trị LeadScan";
  }, []);
  useEffect(() => {
    setData(null);
    const t = setTimeout(load, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, q]);
  useEffect(() => {
    setDetail(null);
    if (openId) api.get<Detail>(`/inbound-emails/${openId}`).then(setDetail, (e) => alert(errMsg(e)));
  }, [openId]);

  async function act(path: string, body?: unknown) {
    if (!detail) return;
    setBusy(true);
    try {
      const r = await api.post<{ opportunity?: { id: number; code: string } }>(`/inbound-emails/${detail.id}/${path}`, body ?? {});
      if (r.opportunity) {
        window.location.href = `/admin/co-hoi/${r.opportunity.id}`;
        return;
      }
      setOpenId(null);
      load();
    } catch (e) {
      alert(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  const count = (k: string) => {
    if (!meta || k === "all") return null;
    if (k === "pending") return (meta.counts.new ?? 0) + (meta.counts.processing ?? 0);
    return meta.counts[k] ?? 0;
  };

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Cơ hội từ email</h1>
          <p>Thư khách gửi vào Gmail được Apps Script chuyển sang 5 phút một lần. AI đọc thư, giữ cơ hội thuộc lĩnh vực {meta?.industries.join(", ") || "…"} và tạo <b>phiếu nháp</b>. Kiểm tra phiếu, đặt giá, rồi mở bán ở trang Cơ hội.</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {meta && (!meta.webhook_enabled || !meta.ai_enabled) ? (
        <div className="adm-alert" style={{ marginBottom: 16 }}>
          {!meta.webhook_enabled ? "Webhook Gmail đang tắt (chưa đặt LEADSCAN_GMAIL_WEBHOOK_SECRET). " : ""}
          {!meta.ai_enabled ? "AI đọc thư đang tắt: thư qua lọc sơ bộ vào tab “Cần xem lại” để tạo phiếu bằng tay." : ""}
          {" "}Hướng dẫn: deploy/gmail-appscript/README.md
        </div>
      ) : null}
      {meta ? (
        <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          Thư mới nhất nhận lúc {meta.last_received_at ? fromNow(meta.last_received_at) : "—"} · AI {meta.ai_model}: {meta.ai_month_cost_usd.toFixed(2)} / {meta.ai_budget_usd} USD tháng này · tự tạo nháp khi AI chắc chắn ≥ {Math.round(meta.min_confidence * 100)}% · thư bị loại xoá nội dung sau {meta.keep_days} ngày
        </p>
      ) : null}

      <section className="adm-card">
        <div className="adm-tabs" role="tablist">
          {TABS.map(([k, label]) => {
            const n = count(k);
            return (
              <button key={k} role="tab" aria-selected={status === k} className={status === k ? "on" : undefined} onClick={() => { setStatus(k); setPage(1); }}>
                {label}{n !== null ? <span>{fmtNum(n)}</span> : null}
              </button>
            );
          })}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tiêu đề thư, người gửi…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Tìm thư" />
          </div>
        </div>

        {!data ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} h={22} />)}</div>
        ) : !data.items.length ? (
          <div className="adm-empty">Không có thư nào.</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Thư</th><th>Người gửi</th><th>AI</th><th>Trạng thái</th><th>Phiếu</th><th>Nhận</th></tr></thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id} className="link" onClick={() => setOpenId(r.id)}>
                    <td style={{ maxWidth: 380 }}>
                      <div className="name">{r.subject || "(không tiêu đề)"}</div>
                      {r.title ? <div className="sub">{r.title}</div> : null}
                      {r.reason || r.error ? <div className="sub" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={r.error || r.reason}>{r.error || r.reason}</div> : null}
                    </td>
                    <td><div>{r.from_name || r.from_email}</div><div className="sub">{r.from_email}</div></td>
                    <td>{r.industry ? <><div>{r.industry}</div><div className="sub">{r.confidence !== null ? `${Math.round(r.confidence * 100)}%` : ""}</div></> : <span className="muted">—</span>}</td>
                    <td><StatusBadge status={BADGE[r.status] ?? "new"} label={meta?.statuses[r.status] ?? r.status} /></td>
                    <td>{r.opportunity ? <Link href={`/admin/co-hoi/${r.opportunity.id}`} onClick={(e) => e.stopPropagation()} className="mono">{r.opportunity.code}</Link> : <span className="muted">—</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }}><span title={fmtDateTime(r.received_at ?? r.created_at)}>{fromNow(r.received_at ?? r.created_at)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > 0 ? (
          <div className="adm-pager">
            <span>{fmtNum((page - 1) * PAGE + 1)}–{fmtNum(Math.min(page * PAGE, data.total))} / {fmtNum(data.total)} thư</span>
            <div>
              <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
              <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
            </div>
          </div>
        ) : null}
      </section>

      <Dialog
        open={openId !== null}
        wide
        title={detail ? detail.subject || "(không tiêu đề)" : "Đang tải…"}
        onClose={() => setOpenId(null)}
        footer={detail ? (
          <>
            <button className="adm-btn sm ghost" onClick={() => setOpenId(null)}>Đóng</button>
            {!detail.blocked ? <button className="adm-btn sm ghost danger" disabled={busy} onClick={() => confirm(`Chặn ${detail.from_email}? Thư sau của người này sẽ bị bỏ qua.`) && act("block", { scope: "email" })}>Chặn người gửi</button> : null}
            {!detail.opportunity && !["new", "processing"].includes(detail.status) && !detail.purged ? (
              <>
                {meta?.ai_enabled ? <button className="adm-btn sm" disabled={busy} onClick={() => act("reprocess")}><Icon name="refresh" size={13} /> Xử lý lại bằng AI</button> : null}
                {detail.status !== "rejected" ? <button className="adm-btn sm ghost danger" disabled={busy} onClick={() => act("reject", { reason: prompt("Lý do loại (không bắt buộc):") ?? "" })}>Loại</button> : null}
                <button className="adm-btn sm primary" disabled={busy} onClick={() => act("draft")}>Tạo phiếu nháp</button>
              </>
            ) : null}
            {detail.opportunity ? <Link className="adm-btn sm primary" href={`/admin/co-hoi/${detail.opportunity.id}`}>Mở phiếu {detail.opportunity.code}</Link> : null}
          </>
        ) : null}
      >
        {!detail ? <Skeleton h={160} /> : (
          <div style={{ display: "grid", gap: 14 }}>
            <dl className="adm-dl">
              <div><dt>Người gửi</dt><dd>{detail.from_name ? `${detail.from_name} · ` : ""}{detail.from_email}{detail.blocked ? " (đã chặn)" : ""}</dd></div>
              <div><dt>Gửi tới</dt><dd>{detail.to || "—"}</dd></div>
              <div><dt>Nhận lúc</dt><dd>{fmtDateTime(detail.received_at ?? detail.created_at)}</dd></div>
              <div><dt>Trạng thái</dt><dd><StatusBadge status={BADGE[detail.status] ?? "new"} label={meta?.statuses[detail.status] ?? detail.status} /> {detail.error || detail.reason}</dd></div>
              {detail.ai_model ? <div><dt>AI</dt><dd>{detail.ai_model} · {detail.ai_cost_usd.toFixed(4)} USD</dd></div> : null}
              {detail.attachment_names.length ? <div><dt>Tệp đính kèm</dt><dd>{detail.attachment_names.join(", ")} <span className="muted">(chỉ có tên tệp, mở Gmail để tải)</span></dd></div> : null}
            </dl>

            {detail.ai_json ? (
              <div>
                <h3 style={{ fontSize: 14, marginBottom: 6 }}>AI trích xuất {typeof detail.ai_json.confidence === "number" ? `· chắc chắn ${Math.round((detail.ai_json.confidence as number) * 100)}%` : ""}</h3>
                <dl className="adm-dl">
                  {AI_LABELS.filter(([k]) => detail.ai_json?.[k]).map(([k, label]) => <div key={k}><dt>{label}</dt><dd>{String(detail.ai_json?.[k])}</dd></div>)}
                </dl>
                {detail.ai_json.detail ? <p style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{String(detail.ai_json.detail)}</p> : null}
                {Array.isArray(detail.ai_json.contacts) && detail.ai_json.contacts.length ? (
                  <p className="muted" style={{ marginTop: 8 }}>
                    Đầu mối: {(detail.ai_json.contacts as Record<string, string>[]).map((c) => [c.full_name, c.title, c.email, c.phone].filter(Boolean).join(" · ")).join(" | ")}
                  </p>
                ) : null}
              </div>
            ) : null}

            <div>
              <h3 style={{ fontSize: 14, marginBottom: 6 }}><Icon name="mail" size={14} /> Thư gốc</h3>
              {detail.purged ? <p className="muted">Nội dung đã xoá theo thời hạn lưu.</p> : (
                <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 13, maxHeight: 360, overflow: "auto", background: "var(--bg-soft, #f6f7f9)", padding: 12, borderRadius: 8 }}>{detail.body_text}</pre>
              )}
            </div>

            {detail.thread.length ? (
              <div>
                <h3 style={{ fontSize: 14, marginBottom: 6 }}>Thư khác cùng luồng</h3>
                <ul style={{ display: "grid", gap: 4, paddingLeft: 18 }}>
                  {detail.thread.map((t) => (
                    <li key={t.id}><button className="adm-btn sm ghost" onClick={() => setOpenId(t.id)}>{t.subject || "(không tiêu đề)"}</button> <span className="muted">{meta?.statuses[t.status]} · {fromNow(t.received_at ?? t.created_at)}</span></li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
      </Dialog>
    </>
  );
}
