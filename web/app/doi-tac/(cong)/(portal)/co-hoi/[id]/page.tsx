"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Skeleton, StatusBadge } from "@/components/admin/ui";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";
import { errMsg, papi } from "@/lib/partner/api";
import { vnd } from "@/lib/partner/content";
import { SUB_BADGE, SUB_FLOW, SUB_MEANING, type Submission } from "@/lib/partner/submissions";

const FLOW_LABEL = { submitted: "Đã gửi", verifying: "Đang xác minh", verified: "Đạt xác minh", published: "Đã xuất bản" } as const;

function Flow({ s }: { s: Submission }) {
  const stopped = s.status === "rejected" || s.status === "duplicate" || s.status === "supplement";
  const idx = stopped ? 2 : SUB_FLOW.indexOf(s.status);
  return (
    <ol className="ptn-flow" aria-label="Tiến trình">
      {SUB_FLOW.map((st, i) => {
        let cls = i < idx ? "done" : i === idx ? "now" : "";
        let label: string = FLOW_LABEL[st as keyof typeof FLOW_LABEL];
        if (stopped && i === 2) {
          cls = s.status === "supplement" ? "done" : "stop";
          label = s.status_label;
        }
        if (s.status === "published" && i === idx) cls = "done";
        return <li key={st} className={cls}>{label}</li>;
      })}
    </ol>
  );
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const fresh = sp.get("moi") === "1";
  const edited = sp.get("da-sua") === "1";
  const [s, setS] = useState<Submission | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () => papi.get<Submission>(`/submissions/${id}`).then((d) => { setS(d); document.title = `${d.code} · Đối tác LeadScan`; }, (e) => setError(errMsg(e)));
    load();
    window.addEventListener("focus", load); // quay lại tab → cập nhật trạng thái mới nhất
    return () => window.removeEventListener("focus", load);
  }, [id]);

  if (error) return <div className="adm-alert">{error}</div>;
  if (!s) return <div style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>;

  const row = (k: string, v: React.ReactNode) => (v ? <><dt>{k}</dt><dd>{v}</dd></> : null);

  return (
    <>
      <div className="adm-head">
        <div>
          <Link href="/doi-tac/co-hoi" className="muted" style={{ fontSize: 13 }}>← Cơ hội của tôi</Link>
          <h1 style={{ marginTop: 4 }}>{s.title || s.company_name}</h1>
          <p className="mono">{s.code} · gửi {fmtDateTime(s.created_at)}</p>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {s.editable ? <Link className="adm-btn" href={`/doi-tac/gui-co-hoi?sua=${s.id}`}>Sửa cơ hội</Link> : null}
          <StatusBadge status={SUB_BADGE[s.status]} label={s.status_label} />
        </div>
      </div>

      {fresh ? <div className="adm-alert ok" style={{ marginBottom: 16 }}>Đã gửi cơ hội. LeadScan sẽ xác minh trong khoảng 2 ngày làm việc và báo kết quả qua email. Cần chỉnh lại? Bấm “Sửa cơ hội” trước khi LeadScan bắt đầu xác minh.</div> : null}
      {edited ? <div className="adm-alert ok" style={{ marginBottom: 16 }}>Đã lưu thay đổi.</div> : null}

      <div className="adm-grid side">
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Trạng thái</h2></div>
            <Flow s={s} />
            <div className="ptn-result">
              <p>{SUB_MEANING[s.status]}</p>
              {s.reject_label ? <p><b>Lý do:</b> {s.reject_label}</p> : null}
              {s.partner_note ? <div className="adm-alert warn" style={{ whiteSpace: "pre-wrap" }}><b>LeadScan:</b> {s.partner_note}</div> : null}
              {s.score !== null ? <p className="muted" style={{ fontSize: 13 }}>Điểm chất lượng: <b style={{ color: "var(--ink)" }}>{s.score}</b>/100 (ngưỡng đạt 60)</p> : null}
              {s.status === "submitted" || s.status === "verifying" ? <p className="muted" style={{ fontSize: 13 }}>Hạn xác minh dự kiến: {fmtDate(s.sla_due_at)}</p> : null}
              {s.status === "published" ? (
                <div className="ptn-reward" style={{ border: "1px solid var(--line)", borderRadius: 8, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
                  <div><small>Đã bán</small><b>{s.sold_count} lượt</b><span>mở bán {fmtDate(s.published_at)}</span></div>
                  <div><small>Đã ghi vào ví</small><b>{vnd(s.earned)}</b><span><Link href="/doi-tac/vi" style={{ color: "var(--brand-600)" }}>Xem ví</Link></span></div>
                  <div><small>Chia sẻ doanh thu</small><b>{s.share_expired ? "Hết hạn" : `đến ${fmtDate(s.share_until)}`}</b><span>{s.share_expired ? "Dừng ghi hoa hồng" : "mọi lượt bán, mọi vòng enrich"}</span></div>
                </div>
              ) : s.earned ? <p className="muted" style={{ fontSize: 13 }}>Đã ghi vào ví: <b style={{ color: "var(--ink)" }}>{vnd(s.earned)}</b></p> : null}
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Thông tin đã gửi</h2></div>
            <div className="bd">
              <dl className="adm-kv">
                {row("Tiêu đề", s.title)}
                {row("Doanh nghiệp", s.company_name)}
                {row("Mã số thuế", s.tax_code && <span className="mono">{s.tax_code}</span>)}
                {row("Khu vực", s.province)}
                {row("Ngành hàng", s.industry)}
                {row("Loại cơ hội", s.kind_label)}
                {row("Nhu cầu", <span style={{ whiteSpace: "pre-wrap" }}>{s.need}</span>)}
                {row("Quy mô", s.scale)}
                {row("Thời điểm cần", s.timing)}
                {row("Nguồn biết tin", s.source_label)}
                {row("Link nguồn", s.source_url && <a href={s.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand-600)" }}>{s.source_url}</a>)}
                {row("Mức độ chắc chắn", s.certainty_label)}
                {row("Tài liệu, link", s.evidence && <span style={{ whiteSpace: "pre-wrap" }}>{s.evidence}</span>)}
                {row("Ảnh", s.images?.length ? (
                  <div className="ptn-images">{s.images.map((im) => (
                    <a key={im.id} href={im.url ?? "#"} target="_blank" rel="noopener noreferrer" title={im.filename}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={im.thumb_url ?? im.url ?? ""} alt={im.filename} />
                    </a>))}</div>) : null)}
                {row("Người liên hệ", [s.contact_name, s.contact_title, s.contact_phone, s.contact_email].filter(Boolean).join(" · "))}
              </dl>
            </div>
          </section>
        </div>

        <section className="adm-card">
          <div className="hd"><h2>Lịch sử</h2></div>
          <div className="bd">
            <ul className="adm-timeline">
              {[...(s.events ?? [])].reverse().map((e, i) => (
                <li key={i} className="k-status">
                  <span className="dot">•</span>
                  <div><div className="txt">{e.content}</div><div className="meta">{fmtDateTime(e.created_at)}</div></div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </>
  );
}

export default function SubmissionDetailPage() {
  return (
    <Suspense>
      <Detail />
    </Suspense>
  );
}
