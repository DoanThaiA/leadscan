"use client";

import Link from "next/link";
import { type DragEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Icon, ScoreChip, Skeleton } from "@/components/admin/ui";
import { CrmGate, CrmTabs } from "@/components/member/CrmGate";
import { fromNow } from "@/lib/admin/format";
import { type Board, fmtDue, type Lead, type StageKey } from "@/lib/member/crm";
import { errMsg, mapi, qs } from "@/lib/member/api";

const PAGE = 50; // số thẻ mỗi cột mỗi lần tải

function BoardView() {
  const [owner, setOwner] = useState<"all" | "me">("all");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const [dragId, setDragId] = useState<number | null>(null);
  const [over, setOver] = useState<StageKey | null>(null);
  const [perStage, setPerStage] = useState(PAGE);

  const load = useCallback(() => {
    mapi.get<Board>("/crm/board" + qs({ owner, q: query, per_stage: perStage })).then((d) => { setData(d); setError(""); }, (e) => setError(errMsg(e)));
  }, [owner, query, perStage]);

  useEffect(() => { document.title = "CRM · LeadScan B2B"; }, []);
  useEffect(load, [load]);
  useEffect(() => { const t = setTimeout(() => setQuery(q), 300); return () => clearTimeout(t); }, [q]);

  const byStage = useMemo(() => {
    const m = new Map<StageKey, Lead[]>();
    for (const l of data?.leads ?? []) m.set(l.stage, [...(m.get(l.stage) ?? []), l]);
    return m;
  }, [data]);

  async function move(id: number, stage: StageKey) {
    if (!data) return;
    const prev = data;
    const label = data.stages.find((s) => s.key === stage)?.label ?? stage;
    const from = data.leads.find((l) => l.id === id)?.stage;
    const counts = { ...data.counts };
    if (from && from !== stage) { counts[from] -= 1; counts[stage] += 1; }
    setData({ ...data, counts, leads: data.leads.map((l) => (l.id === id ? { ...l, stage, stage_label: label } : l)) }); // cập nhật ngay, lỗi thì trả lại
    try {
      await mapi.patch(`/crm/leads/${id}`, { stage });
    } catch (e) {
      setData(prev);
      setError(errMsg(e));
    }
  }

  function onDrop(e: DragEvent, stage: StageKey) {
    e.preventDefault();
    const id = Number(e.dataTransfer.getData("text/plain")) || dragId;
    setOver(null);
    setDragId(null);
    const lead = data?.leads.find((l) => l.id === id);
    if (lead && lead.stage !== stage) move(lead.id, stage);
  }

  const total = data?.total ?? 0;
  const overdue = data?.overdue ?? 0;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>CRM</h1>
          <p>Mỗi phiếu đã mua là một lead. Kéo thẻ sang cột khác để đổi giai đoạn.</p>
        </div>
        <div className="adm-actions" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <a className="adm-btn" href="/api/member/crm/export.xlsx" download title="Chỉ dữ liệu doanh nghiệp, không kèm thông tin người liên hệ">
            <Icon name="download" size={15} /> Xuất Excel
          </a>
          <Link className="adm-btn primary" href="/thanh-vien/phu-hop">Tìm thêm cơ hội</Link>
        </div>
      </div>
      <CrmTabs active="board" />

      <div className="crm-toolbar">
        <div className="crm-seg" role="group" aria-label="Lọc theo người phụ trách">
          <button className={owner === "all" ? "on" : undefined} aria-pressed={owner === "all"} onClick={() => setOwner("all")}>Tất cả</button>
          <button className={owner === "me" ? "on" : undefined} aria-pressed={owner === "me"} onClick={() => setOwner("me")}>Của tôi</button>
        </div>
        <label className="crm-search">
          <Icon name="search" size={15} />
          <input className="adm-input" placeholder="Tìm mã, tên cơ hội, bên có nhu cầu" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Tìm lead" />
        </label>
        {data ? (
          <span className="muted crm-sum">
            {total} lead{overdue ? <> · <b className="crm-red">{overdue} có việc quá hạn</b></> : null}
          </span>
        ) : null}
      </div>

      {error ? <div className="adm-alert" style={{ marginBottom: 12 }}>{error}</div> : null}

      {!data ? (
        <div className="crm-board">{[1, 2, 3, 4].map((i) => <div key={i} className="crm-col"><Skeleton h={120} /></div>)}</div>
      ) : !total && !query && owner === "all" ? (
        <section className="adm-card"><div className="adm-empty">Chưa có lead nào. Phiếu cơ hội bạn mua sẽ tự xuất hiện ở đây. <Link href="/thanh-vien/phu-hop" style={{ color: "var(--brand-600)" }}>Xem cơ hội phù hợp →</Link></div></section>
      ) : (
        <div className="crm-board">
          {data.stages.map((s) => {
            const items = byStage.get(s.key) ?? [];
            const count = data.counts[s.key] ?? items.length;
            return (
              <section
                key={s.key}
                className={`crm-col st-${s.key}${over === s.key ? " over" : ""}`}
                aria-label={`${s.label}: ${count} lead`}
                onDragOver={(e) => { e.preventDefault(); if (over !== s.key) setOver(s.key); }}
                onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null); }}
                onDrop={(e) => onDrop(e, s.key)}
              >
                <header><span className="dot" />{s.label}<b>{count}</b></header>
                <div className="crm-cards">
                  {items.map((l) => (
                    <article
                      key={l.id}
                      className={`crm-card${dragId === l.id ? " dragging" : ""}`}
                      draggable
                      onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(l.id)); e.dataTransfer.effectAllowed = "move"; setDragId(l.id); }}
                      onDragEnd={() => { setDragId(null); setOver(null); }}
                    >
                      <Link href={`/thanh-vien/crm/${l.id}`} className="crm-card-title">{l.title}</Link>
                      <div className="crm-card-sub">{l.buyer_name || "—"}</div>
                      <div className="crm-card-meta">
                        <ScoreChip score={l.score} />
                        <span className="mono">{l.code}</span>
                        {l.refunded ? <span className="crm-tag">Đã hoàn điểm</span> : null}
                      </div>
                      <div className="crm-card-foot">
                        <span title={l.owner ? `Phụ trách: ${l.owner.full_name}` : "Chưa giao"} className={l.owner ? undefined : "muted"}>
                          <Icon name="user" size={12} /> {l.owner?.full_name ?? "Chưa giao"}
                        </span>
                        {l.open_tasks ? (
                          <span className={l.overdue ? "crm-red" : undefined} title={l.next_due ? `Hạn gần nhất ${fmtDue(l.next_due)}` : undefined}>
                            <Icon name="check" size={12} /> {l.open_tasks} việc{l.next_due ? ` · ${fmtDue(l.next_due)}` : ""}
                          </span>
                        ) : <span className="muted">{fromNow(l.updated_at)}</span>}
                      </div>
                      <select
                        className="crm-move"
                        value={l.stage}
                        aria-label={`Chuyển giai đoạn cho ${l.code}`}
                        onChange={(e) => move(l.id, e.target.value as StageKey)}
                      >
                        {data.stages.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
                      </select>
                    </article>
                  ))}
                  {!items.length ? <div className="crm-col-empty">Thả thẻ vào đây</div> : null}
                  {!query && count > items.length ? (
                    <button className="adm-btn sm ghost crm-more" onClick={() => setPerStage(perStage + PAGE)}>
                      Hiện thêm · còn {count - items.length}
                    </button>
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}

export default function CrmPage() {
  return <CrmGate><BoardView /></CrmGate>;
}
