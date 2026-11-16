"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg, qs } from "@/lib/admin/api";
import { fmtValue, type ManualTask, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtNum } from "@/lib/admin/format";

interface Queue {
  connector: string;
  name: string;
  count: number;
}

function ManualInner() {
  const params = useSearchParams();
  const { meta, error: metaError } = useEnrichMeta();
  const [queues, setQueues] = useState<Queue[] | null>(null);
  const [connector, setConnector] = useState(params.get("nguon") ?? "");
  const [task, setTask] = useState<ManualTask | null | undefined>(undefined);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [doneCount, setDoneCount] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);

  const loadQueues = useCallback(() => {
    api.get<{ queues: Queue[] }>("/enrich/manual").then((d) => setQueues(d.queues), () => {});
  }, []);

  const next = useCallback(
    async (after = 0) => {
      setMsg("");
      setTask(undefined);
      try {
        const d = await api.get<{ task: ManualTask | null }>("/enrich/manual/next" + qs({ connector, after }));
        setTask(d.task);
        formRef.current?.reset();
      } catch (e) {
        setMsg(errMsg(e));
        setTask(null);
      }
      loadQueues();
    },
    [connector, loadQueues],
  );

  useEffect(() => {
    document.title = "Hàng đợi thủ công · Làm giàu theo MST";
    next();
  }, [next]);

  async function send(action: "save" | "not_found" | "skip", e?: FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    if (!task) return;
    const values: Record<string, string> = {};
    let source_url = "";
    if (action === "save" && formRef.current) {
      const f = new FormData(formRef.current);
      for (const fld of task.fields) values[fld.key] = String(f.get(fld.key) ?? "").trim();
      source_url = String(f.get("source_url") ?? "").trim();
    }
    setBusy(true);
    setMsg("");
    try {
      await api.post(`/enrich/manual/${task.job_id}`, { action, values, source_url });
      if (action !== "skip") setDoneCount((n) => n + 1);
      await next(action === "skip" ? task.job_id : 0);
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Hàng đợi thủ công</h1>
          <p>Nguồn có captcha không được tự động vượt — nhân viên tra cứu từng MST trên trang nguồn rồi chép thông tin vào đây. Mỗi giá trị lưu kèm đường dẫn và thời điểm tra.</p>
        </div>
      </div>
      <EnrichNav caps={meta.caps} />

      <div className="adm-toolbar" style={{ padding: 0, marginBottom: 12 }}>
        <select className="adm-input" style={{ width: "auto" }} value={connector} onChange={(e) => setConnector(e.target.value)} aria-label="Chọn hàng đợi">
          <option value="">Mọi nguồn ({fmtNum((queues ?? []).reduce((a, q) => a + q.count, 0))})</option>
          {(queues ?? []).map((q) => <option key={q.connector} value={q.connector}>{q.name} ({fmtNum(q.count)})</option>)}
        </select>
        {doneCount ? <span className="adm-badge s-active">Đã xử lý {doneCount} MST trong phiên này</span> : null}
      </div>

      {msg ? <div className="adm-alert" style={{ marginBottom: 12 }}>{msg}</div> : null}

      {task === undefined ? (
        <Skeleton h={320} />
      ) : task === null ? (
        <section className="adm-card adm-empty">
          <Icon name="check" /> Hàng đợi trống. MST được đưa vào đây khi tạo <Link href="/admin/lam-giau/vong" style={{ color: "var(--brand-600)" }}>vòng thu thập</Link> với nguồn tra cứu thủ công, hoặc khi nguồn tự động gặp captcha.
        </section>
      ) : (
        <div className="er-task">
          <section className="adm-card">
            <div className="hd">
              <div>
                <div className="muted" style={{ fontSize: 12.5 }}>{task.connector_name} · còn {fmtNum(task.remaining)} MST{task.run ? ` · vòng #${task.run.id}` : ""}</div>
                <div className="er-mst">{task.mst}</div>
              </div>
              <div className="adm-actions">
                <button type="button" className="adm-btn sm" onClick={() => navigator.clipboard?.writeText(task.mst)}><Icon name="copy" size={14} /> Chép MST</button>
                {task.lookup_url ? <a className="adm-btn sm primary" href={task.lookup_url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={14} /> Mở trang tra cứu</a> : null}
              </div>
            </div>
            <div className="bd">
              {task.hint ? <p className="er-note" style={{ marginBottom: 14 }}><Icon name="note" /><span>{task.hint}</span></p> : null}
              <form ref={formRef} className="adm-form" onSubmit={(e) => send("save", e)} key={task.job_id}>
                {task.fields.map((f, i) => (
                  <div key={f.key} className={f.kind === "textarea" ? "adm-field full" : "adm-field"}>
                    <label htmlFor={`m-${f.key}`}>{f.label}</label>
                    {f.kind === "textarea" ? (
                      <textarea id={`m-${f.key}`} className="adm-input" name={f.key} rows={2} autoFocus={i === 0} />
                    ) : f.kind === "select" ? (
                      <select id={`m-${f.key}`} className="adm-input" name={f.key} defaultValue="">
                        <option value="">— chưa xác định —</option>
                        {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input id={`m-${f.key}`} className="adm-input" name={f.key} type={f.kind === "date" ? "date" : "text"} autoFocus={i === 0} autoComplete="off" />
                    )}
                  </div>
                ))}
                <div className="adm-field full">
                  <label htmlFor="m-url">Đường dẫn trang đã tra (để trống = trang tra cứu của nguồn)</label>
                  <input id="m-url" className="adm-input" name="source_url" placeholder={task.lookup_url} autoComplete="off" />
                </div>
                <div className="adm-actions full" style={{ justifyContent: "space-between" }}>
                  <div className="adm-actions">
                    <button type="button" className="adm-btn" disabled={busy} onClick={() => send("skip")}>Bỏ qua (để sau)</button>
                    <button type="button" className="adm-btn" disabled={busy} onClick={() => send("not_found")}>Nguồn không có MST này</button>
                  </div>
                  <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Lưu & MST tiếp theo"} <span className="er-kbd">Enter</span></button>
                </div>
              </form>
            </div>
          </section>
          <aside className="adm-card">
            <div className="hd"><h2>Đang có trong hồ sơ</h2></div>
            <div className="bd">
              {Object.keys(task.current).length ? (
                <dl className="adm-dl">
                  {Object.entries(task.current).map(([k, v]) => (
                    <div key={k}><dt className="muted">{meta.fields[k] ?? k}</dt><dd style={{ margin: 0, wordBreak: "break-word" }}>{fmtValue(k, v)}</dd></div>
                  ))}
                </dl>
              ) : <p className="muted">Hồ sơ chưa có thông tin nào ngoài MST.</p>}
              <p style={{ marginTop: 12 }}><Link href={`/admin/lam-giau/${task.mst}`} target="_blank" style={{ color: "var(--brand-600)" }}>Mở hồ sơ đầy đủ →</Link></p>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

export default function ManualQueuePage() {
  return (
    <Suspense fallback={<Skeleton h={400} />}>
      <ManualInner />
    </Suspense>
  );
}
