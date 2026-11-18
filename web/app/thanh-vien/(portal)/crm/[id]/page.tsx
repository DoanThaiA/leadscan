"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { Icon, ScoreChip, Skeleton } from "@/components/admin/ui";
import { CrmAiCard } from "@/components/member/CrmAiCard";
import { CrmGate } from "@/components/member/CrmGate";
import { fmtDate, fmtDateTime, fromNow } from "@/lib/admin/format";
import { fmtPts } from "@/lib/commerce";
import { fmtDue, type LeadDetail, type Note, type StageKey, type Task } from "@/lib/member/crm";
import { errMsg, mapi } from "@/lib/member/api";

const EVENT_ICON: Record<string, string> = { created: "plus", stage: "layers", assign: "user", note: "note", task: "check", task_done: "check", ai: "spark" };

function LeadView({ id }: { id: string }) {
  const [d, setD] = useState<LeadDetail | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [noteMsg, setNoteMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState({ title: "", due_date: "", assignee_id: "" });

  const load = useCallback(() => {
    mapi.get<LeadDetail>(`/crm/leads/${id}`).then((x) => { setD(x); document.title = `${x.lead.code} · CRM · LeadScan B2B`; }, (e) => setError(errMsg(e)));
  }, [id]);
  useEffect(load, [load]);

  async function patch(body: Record<string, unknown>) {
    setError("");
    try {
      await mapi.patch(`/crm/leads/${id}`, body);
      load();
    } catch (e) {
      setError(errMsg(e));
    }
  }

  async function addNote(e: FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;
    setBusy(true);
    setNoteMsg("");
    try {
      const r = await mapi.post<{ note: Note; warning: string }>(`/crm/leads/${id}/notes`, { content: note });
      setNote("");
      setNoteMsg(r.warning);
      load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function delNote(n: Note) {
    if (!confirm("Xoá ghi chú này?")) return;
    await mapi.del(`/crm/notes/${n.id}`).then(load, (e) => setError(errMsg(e)));
  }

  async function addTask(e: FormEvent) {
    e.preventDefault();
    if (!task.title.trim()) return;
    setBusy(true);
    try {
      await mapi.post<Task>(`/crm/leads/${id}/tasks`, {
        title: task.title,
        due_date: task.due_date || null,
        assignee_id: task.assignee_id ? Number(task.assignee_id) : null,
      });
      setTask({ title: "", due_date: "", assignee_id: "" });
      load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(t: Task) {
    await mapi.patch(`/crm/tasks/${t.id}`, { done: !t.done }).then(load, (e) => setError(errMsg(e)));
  }

  async function delTask(t: Task) {
    if (!confirm(`Xoá việc "${t.title}"?`)) return;
    await mapi.del(`/crm/tasks/${t.id}`).then(load, (e) => setError(errMsg(e)));
  }

  if (!d) {
    return error ? (
      <><Link className="crm-back" href="/thanh-vien/crm"><Icon name="back" size={15} /> Về bảng CRM</Link><div className="adm-alert">{error}</div></>
    ) : <div style={{ display: "grid", gap: 12 }}><Skeleton h={60} /><Skeleton h={240} /></div>;
  }

  const { lead, opportunity: o } = d;
  return (
    <>
      <Link className="crm-back" href="/thanh-vien/crm"><Icon name="back" size={15} /> Về bảng CRM</Link>
      <div className="adm-head">
        <div style={{ minWidth: 0 }}>
          <h1>{o.title}</h1>
          <p><span className="mono">{o.code}</span> · {o.buyer_name || "—"} · {[o.industry, o.province].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="crm-head-ctl">
          <label>
            <small>Giai đoạn</small>
            <select className={`adm-input crm-stage st-${lead.stage}`} value={lead.stage} onChange={(e) => patch({ stage: e.target.value as StageKey })}>
              {d.stages.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </label>
          <label>
            <small>Phụ trách</small>
            <select
              className="adm-input"
              value={lead.owner?.id ?? ""}
              onChange={(e) => patch(e.target.value ? { owner_id: Number(e.target.value) } : { unassign: true })}
            >
              <option value="">Chưa giao</option>
              {d.members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
            </select>
          </label>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 12 }}>{error}</div> : null}

      <div className="crm-detail">
        <div className="crm-main">
          <section className="adm-card">
            <div className="hd"><h2>Thông tin cơ hội</h2><Link className="adm-btn sm ghost" href={`/thanh-vien/co-hoi/${lead.opportunity_id}`}>Xem phiếu <Icon name="external" size={13} /></Link></div>
            <div className="bd crm-info">
              {o.summary ? <p>{o.summary}</p> : null}
              <dl>
                <div><dt>Điểm phù hợp</dt><dd><ScoreChip score={lead.score} /></dd></div>
                {o.scale ? <div><dt>Quy mô</dt><dd>{o.scale}</dd></div> : null}
                {o.estimated_value ? <div><dt>Giá trị ước tính</dt><dd>{o.estimated_value}</dd></div> : null}
                {o.deadline ? <div><dt>Hạn chót</dt><dd>{fmtDate(o.deadline)}</dd></div> : null}
                <div><dt>Giá phiếu</dt><dd>{fmtPts(lead.price)}{lead.refunded ? <span className="crm-tag" style={{ marginLeft: 6 }}>Đã hoàn điểm</span> : null}</dd></div>
              </dl>
              {o.detail ? <p className="crm-pre">{o.detail}</p> : null}
              {o.contacts?.length ? (
                <div className="crm-contacts">
                  <h3>Đầu mối (từ phiếu đã mua)</h3>
                  {o.contacts.map((c, i) => (
                    <div key={i} className="crm-contact">
                      <b>{c.full_name}</b>{c.title ? <span className="muted"> · {c.title}</span> : null}
                      <div>
                        {c.phone ? <a href={`tel:${c.phone}`}><Icon name="phone" size={12} /> {c.phone}</a> : null}
                        {c.email ? <a href={`mailto:${c.email}`}><Icon name="mail" size={12} /> {c.email}</a> : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </section>

          <CrmAiCard key={lead.id} leadId={lead.id} initial={d.ai} onRun={load} />

          <section className="adm-card">
            <div className="hd"><h2>Ghi chú</h2><span className="muted">{d.notes.length}</span></div>
            <div className="bd">
              <form onSubmit={addNote} className="crm-note-form">
                <textarea className="adm-input" rows={3} maxLength={5000} placeholder="Kết quả cuộc gọi, nhu cầu khách, bước tiếp theo…" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Ghi chú mới" />
                <div className="crm-note-foot">
                  <span className="muted">SĐT / email không thuộc đầu mối của phiếu sẽ được tự ẩn.</span>
                  <button className="adm-btn primary sm" disabled={busy || !note.trim()}>Lưu ghi chú</button>
                </div>
              </form>
              {noteMsg ? <div className="adm-alert warn" style={{ marginTop: 10 }}>{noteMsg}</div> : null}
              <ul className="crm-notes">
                {d.notes.map((n) => (
                  <li key={n.id}>
                    <div className="crm-note-hd">
                      <b>{n.author?.full_name ?? "—"}</b>
                      <span className="muted" title={fmtDateTime(n.created_at)}>{fromNow(n.created_at)}</span>
                      <button className="adm-btn ghost sm" aria-label="Xoá ghi chú" onClick={() => delNote(n)}><Icon name="trash" size={13} /></button>
                    </div>
                    <p className="crm-pre">{n.content}</p>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </div>

        <aside className="crm-side">
          <section className="adm-card">
            <div className="hd"><h2>Việc cần làm</h2><span className="muted">{d.tasks.filter((t) => !t.done).length} chưa xong</span></div>
            <div className="bd">
              <form onSubmit={addTask} className="crm-task-form">
                <input className="adm-input" placeholder="VD: Gọi lại báo giá" maxLength={200} value={task.title} onChange={(e) => setTask({ ...task, title: e.target.value })} aria-label="Tên việc" />
                <div className="row">
                  <input className="adm-input" type="date" value={task.due_date} onChange={(e) => setTask({ ...task, due_date: e.target.value })} aria-label="Hạn" />
                  <select className="adm-input" value={task.assignee_id} onChange={(e) => setTask({ ...task, assignee_id: e.target.value })} aria-label="Người làm">
                    <option value="">Tôi</option>
                    {d.members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
                  </select>
                </div>
                <button className="adm-btn sm" disabled={busy || !task.title.trim()}><Icon name="plus" size={14} /> Thêm việc</button>
              </form>
              <ul className="crm-tasks">
                {d.tasks.map((t) => (
                  <li key={t.id} className={t.done ? "done" : undefined}>
                    <input type="checkbox" checked={t.done} onChange={() => toggle(t)} aria-label={`Đánh dấu xong: ${t.title}`} />
                    <div>
                      <span className="t">{t.title}</span>
                      <span className="m">
                        {t.due_date ? <span className={t.overdue ? "crm-red" : undefined}>Hạn {fmtDue(t.due_date)}{t.overdue ? " · quá hạn" : ""}</span> : <span>Không hạn</span>}
                        {t.assignee ? <> · {t.assignee.full_name}</> : null}
                      </span>
                    </div>
                    <button className="adm-btn ghost sm" aria-label={`Xoá việc ${t.title}`} onClick={() => delTask(t)}><Icon name="trash" size={13} /></button>
                  </li>
                ))}
                {!d.tasks.length ? <li className="muted crm-none">Chưa có việc nào.</li> : null}
              </ul>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Lịch sử</h2></div>
            <ol className="crm-events">
              {d.events.map((e) => (
                <li key={e.id}>
                  <span className="ic"><Icon name={EVENT_ICON[e.kind] ?? "note"} size={12} /></span>
                  <div>
                    <span>{e.content}</span>
                    <small className="muted">{e.actor?.full_name ?? "Hệ thống"} · <span title={fmtDateTime(e.created_at)}>{fromNow(e.created_at)}</span></small>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </>
  );
}

export default function LeadPage() {
  const { id } = useParams<{ id: string }>();
  return <CrmGate><LeadView id={id} /></CrmGate>;
}
