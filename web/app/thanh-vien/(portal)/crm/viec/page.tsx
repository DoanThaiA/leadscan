"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { CrmGate, CrmTabs } from "@/components/member/CrmGate";
import { fmtDateTime } from "@/lib/admin/format";
import { fmtDue, type Task, todayIso } from "@/lib/member/crm";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface TaskList { items: Task[]; counts: { overdue: number; today: number } }

function TasksView() {
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const [status, setStatus] = useState<"open" | "done">("open");
  const [data, setData] = useState<TaskList | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    mapi.get<TaskList>("/crm/tasks" + qs({ scope, status })).then(setData, (e) => setError(errMsg(e)));
  }, [scope, status]);
  useEffect(() => { document.title = "Việc cần làm · CRM · LeadScan B2B"; }, []);
  useEffect(load, [load]);

  async function toggle(t: Task) {
    await mapi.patch(`/crm/tasks/${t.id}`, { done: !t.done }).then(load, (e) => setError(errMsg(e)));
  }

  const today = todayIso();
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>CRM</h1>
          <p>Việc cần làm trên các lead, sắp theo hạn</p>
        </div>
      </div>
      <CrmTabs active="tasks" />

      <div className="crm-toolbar">
        <div className="crm-seg" role="group" aria-label="Phạm vi">
          <button className={scope === "mine" ? "on" : undefined} aria-pressed={scope === "mine"} onClick={() => setScope("mine")}>Của tôi</button>
          <button className={scope === "all" ? "on" : undefined} aria-pressed={scope === "all"} onClick={() => setScope("all")}>Cả nhóm</button>
        </div>
        <div className="crm-seg" role="group" aria-label="Trạng thái">
          <button className={status === "open" ? "on" : undefined} aria-pressed={status === "open"} onClick={() => setStatus("open")}>Chưa xong</button>
          <button className={status === "done" ? "on" : undefined} aria-pressed={status === "done"} onClick={() => setStatus("done")}>Đã xong</button>
        </div>
        {data && status === "open" ? (
          <span className="muted crm-sum">
            {data.counts.overdue ? <b className="crm-red">{data.counts.overdue} quá hạn</b> : "Không có việc quá hạn"}
            {data.counts.today ? <> · {data.counts.today} hạn hôm nay</> : null}
          </span>
        ) : null}
      </div>

      {error ? <div className="adm-alert" style={{ marginBottom: 12 }}>{error}</div> : null}
      <section className="adm-card">
        {!data ? (
          <div className="bd" style={{ display: "grid", gap: 10 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !data.items.length ? (
          <div className="adm-empty">{status === "open" ? "Không còn việc nào. Thêm việc trong trang chi tiết của từng lead." : "Chưa có việc nào hoàn thành."}</div>
        ) : (
          <ul className="crm-tasks crm-tasks-page">
            {data.items.map((t) => (
              <li key={t.id} className={t.done ? "done" : undefined}>
                <input type="checkbox" checked={t.done} onChange={() => toggle(t)} aria-label={`Đánh dấu xong: ${t.title}`} />
                <div>
                  <span className="t">{t.title}</span>
                  <span className="m">
                    {t.lead ? <Link href={`/thanh-vien/crm/${t.lead.id}`}>{t.lead.code} · {t.lead.title}</Link> : null}
                    {t.assignee && scope === "all" ? <> · {t.assignee.full_name}</> : null}
                  </span>
                </div>
                <span className={`crm-due${t.overdue ? " crm-red" : t.due_date === today ? " today" : ""}`}>
                  {t.done ? `Xong ${fmtDateTime(t.done_at)}` : t.due_date ? (t.due_date === today ? "Hôm nay" : fmtDue(t.due_date)) : "Không hạn"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}><Icon name="bell" size={12} /> Mỗi sáng 8:00 bạn nhận email nhắc việc quá hạn và đến hạn; sáng thứ Hai có thêm báo cáo tuần.</p>
    </>
  );
}

export default function CrmTasksPage() {
  return <CrmGate><TasksView /></CrmGate>;
}
