"use client";

import { useState } from "react";

import { Icon } from "@/components/admin/ui";
import { fmtDate, fromNow } from "@/lib/admin/format";
import { type AiBudget, type AiRun, CHANNELS, type DraftChannel } from "@/lib/member/crm";
import { errMsg, mapi } from "@/lib/member/api";

interface Props {
  leadId: number;
  initial: { budget: AiBudget; summary: AiRun | null; draft: AiRun | null };
  onRun: () => void; // tải lại lịch sử lead
}

function Result({ run, label }: { run: AiRun; label: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(run.result);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  }
  return (
    <div className="crm-ai-result">
      <div className="crm-ai-result-hd">
        <span className="muted">{label} · {run.member?.full_name ?? "—"} · {fromNow(run.created_at)}</span>
        <button className="adm-btn ghost sm" onClick={copy}><Icon name={copied ? "check" : "copy"} size={13} /> {copied ? "Đã chép" : "Chép"}</button>
      </div>
      <p className="crm-pre">{run.result}</p>
    </div>
  );
}

/** Trợ lý AI trên trang lead: tóm tắt công ty + soạn bản nháp lời mời. Chỉ là bản nháp — người dùng tự sửa, tự gửi. */
export function CrmAiCard({ leadId, initial, onRun }: Props) {
  const [budget, setBudget] = useState(initial.budget);
  const [summary, setSummary] = useState(initial.summary);
  const [draft, setDraft] = useState(initial.draft);
  const [channel, setChannel] = useState<DraftChannel>("email");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"" | "summary" | "draft">("");
  const [error, setError] = useState("");

  async function run(kind: "summary" | "draft") {
    setBusy(kind);
    setError("");
    try {
      const r = await mapi.post<{ run: AiRun; budget: AiBudget }>(`/crm/leads/${leadId}/ai/${kind}`, kind === "draft" ? { channel, note } : {});
      setBudget(r.budget);
      if (kind === "summary") setSummary(r.run);
      else setDraft(r.run);
      onRun();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy("");
    }
  }

  const off = !budget.enabled;
  const locked = off || budget.exhausted;
  return (
    <section className="adm-card crm-ai">
      <div className="hd">
        <h2><Icon name="spark" size={15} /> Trợ lý AI</h2>
        {!off ? (
          <span className="crm-ai-quota" title={`Hạn mức làm mới ngày ${fmtDate(budget.resets_at)}`}>
            <span className="bar" aria-hidden="true"><i style={{ width: `${budget.remaining_pct}%` }} /></span>
            Còn {budget.remaining_pct}% hạn mức tháng
          </span>
        ) : null}
      </div>
      <div className="bd">
        {off ? (
          <p className="muted" style={{ margin: 0 }}>Trợ lý AI chưa được bật cho hệ thống. Bạn vẫn dùng CRM bình thường.</p>
        ) : (
          <>
            {budget.exhausted ? <div className="adm-alert warn">Đã dùng hết hạn mức AI tháng này. Hạn mức làm mới ngày {fmtDate(budget.resets_at)}.</div> : null}
            {error ? <div className="adm-alert">{error}</div> : null}

            <div className="crm-ai-block">
              <div className="crm-ai-row">
                <div>
                  <b>Tóm tắt công ty</b>
                  <span className="muted">Họ là ai, cần gì, tín hiệu gần đây, gợi ý cách tiếp cận</span>
                </div>
                <button className="adm-btn sm" disabled={locked || !!busy} onClick={() => run("summary")}>
                  {busy === "summary" ? "Đang tóm tắt…" : summary ? "Tóm tắt lại" : "Tóm tắt"}
                </button>
              </div>
              {summary ? <Result run={summary} label="Tóm tắt" /> : null}
            </div>

            <div className="crm-ai-block">
              <div className="crm-ai-row">
                <div>
                  <b>Soạn tin mời</b>
                  <span className="muted">Bản nháp để bạn sửa rồi tự gửi bằng kênh của mình</span>
                </div>
              </div>
              <div className="crm-ai-draft-form">
                <select className="adm-input" value={channel} onChange={(e) => setChannel(e.target.value as DraftChannel)} aria-label="Kênh gửi">
                  {CHANNELS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                </select>
                <input className="adm-input" maxLength={1000} placeholder="Ý chính muốn nói (không bắt buộc)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Ý chính muốn nói" />
                <button className="adm-btn primary sm" disabled={locked || !!busy} onClick={() => run("draft")}>
                  {busy === "draft" ? "Đang soạn…" : "Soạn nháp"}
                </button>
              </div>
              {draft ? <Result run={draft} label="Bản nháp" /> : null}
            </div>
            <p className="crm-ai-foot muted">AI chỉ nhận thông tin doanh nghiệp, không nhận tên hay SĐT/email người liên hệ. Hãy đọc lại trước khi gửi.</p>
          </>
        )}
      </div>
    </section>
  );
}
