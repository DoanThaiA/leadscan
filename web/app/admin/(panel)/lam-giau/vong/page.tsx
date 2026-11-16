"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg } from "@/lib/admin/api";
import { type Batch, fmtDuration, type Ops, type Run, type RunConnector, type Source, SOURCE_KIND, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";

function Bar({ c }: { c: Pick<RunConnector, "total" | "done" | "not_found" | "manual" | "failed"> }) {
  const w = (n: number) => `${c.total ? (n / c.total) * 100 : 0}%`;
  return (
    <span className="er-bar" aria-hidden>
      <i className="done" style={{ width: w(c.done) }} />
      <i className="nf" style={{ width: w(c.not_found) }} />
      <i className="manual" style={{ width: w(c.manual) }} />
      <i className="failed" style={{ width: w(c.failed) }} />
    </span>
  );
}

function Legend({ c }: { c: Omit<RunConnector, "connector" | "name" | "kind" | "enabled" | "paused_reason" | "eta_seconds"> }) {
  return (
    <div className="er-legend">
      <span className="done">Xong {fmtNum(c.done)}</span>
      <span className="nf">Nguồn không có {fmtNum(c.not_found)}</span>
      <span className="manual">Chờ thủ công {fmtNum(c.manual)}</span>
      <span className="failed">Lỗi {fmtNum(c.failed)}</span>
      <span className="left">Còn lại {fmtNum(c.remaining)}</span>
    </div>
  );
}

export default function EnrichRunsPage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [data, setData] = useState<{ ops: Ops; runs: Run[] } | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [detail, setDetail] = useState<Run | null>(null);

  const load = useCallback(() => {
    api.get<{ ops: Ops; runs: Run[] }>("/enrich/runs").then(setData, (e) => setError(errMsg(e)));
  }, []);

  useEffect(() => {
    document.title = "Vòng thu thập · Làm giàu theo MST";
    load();
    const t = setInterval(load, 10_000); // tiến trình tự cập nhật
    return () => clearInterval(t);
  }, [load]);

  async function setStatus(r: Run, status: string) {
    if (status === "cancelled" && !confirm(`Huỷ vòng “${r.name}”? Các việc chưa chạy sẽ bị bỏ qua.`)) return;
    try {
      await api.post(`/enrich/runs/${r.id}/status`, { status });
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  async function openDetail(r: Run) {
    try {
      setDetail(await api.get<Run>(`/enrich/runs/${r.id}`));
    } catch (e) {
      alert(errMsg(e));
    }
  }

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;
  const canManage = meta.caps.includes("run.manage");

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Vòng thu thập</h1>
          <p>Mỗi vòng chạy danh sách MST qua các nguồn đã chọn. Tiến độ lưu theo từng MST — dừng rồi chạy lại không mất phần đã xong và không tải trùng.</p>
        </div>
        {canManage ? <button className="adm-btn primary" onClick={() => setCreating(true)}><Icon name="plus" size={16} /> Tạo vòng mới</button> : null}
      </div>
      <EnrichNav caps={meta.caps} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {data && !data.ops.running_now ? (
        <div className="adm-alert warn" style={{ marginBottom: 16 }}>
          {data.ops.blocked_reason} — nguồn tự động đang chờ. <Link href="/admin/lam-giau/nguon" style={{ fontWeight: 600 }}>Nguồn & cấu hình →</Link>
        </div>
      ) : null}

      {!data ? (
        <Skeleton h={240} />
      ) : !data.runs.length ? (
        <section className="adm-card adm-empty">Chưa có vòng thu thập nào.{canManage ? " Bấm “Tạo vòng mới” để bắt đầu." : ""}</section>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          {data.runs.map((r) => (
            <section className="adm-card" key={r.id}>
              <div className="hd">
                <div>
                  <h2 style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    #{r.id} · {r.name}
                    <span className={`adm-badge ${r.status === "running" ? "s-new" : r.status === "done" ? "s-active" : "s-suspended"}`}>{meta.run_statuses[r.status] ?? r.status}</span>
                  </h2>
                  <div className="sub muted" style={{ fontSize: 12.5, marginTop: 2 }}>
                    {r.batch ? <>Lô #{r.batch.id} · {r.batch.name}</> : "Toàn bộ MST"} · {fmtNum(r.totals.total)} việc · {r.created_by ?? "—"} · {fmtDateTime(r.created_at)}
                    {r.status === "running" && r.eta_seconds ? ` · còn khoảng ${fmtDuration(r.eta_seconds)}` : ""}
                  </div>
                </div>
                <div className="adm-actions">
                  <button className="adm-btn sm" onClick={() => openDetail(r)}>Lỗi gần đây</button>
                  {canManage && r.status === "running" ? <button className="adm-btn sm" onClick={() => setStatus(r, "paused")}>Tạm dừng</button> : null}
                  {canManage && r.status === "paused" ? <button className="adm-btn sm primary" onClick={() => setStatus(r, "running")}>Chạy tiếp</button> : null}
                  {canManage && (r.status === "running" || r.status === "paused") ? <button className="adm-btn sm danger" onClick={() => setStatus(r, "cancelled")}>Huỷ</button> : null}
                </div>
              </div>
              <div className="bd" style={{ display: "grid", gap: 14 }}>
                {r.connectors.map((c) => (
                  <div key={c.connector}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                      <span>
                        <b>{c.name}</b> <span className="adm-badge plain role">{SOURCE_KIND[c.kind] ?? c.kind}</span>
                        {!c.enabled ? <span className="adm-badge s-rejected" style={{ marginLeft: 6 }} title={c.paused_reason}>Nguồn đang tắt</span> : null}
                      </span>
                      <span className="muted" style={{ fontSize: 12.5 }}>
                        {fmtNum(c.total - c.remaining - c.manual)}/{fmtNum(c.total)}
                        {c.kind === "http" && c.remaining ? ` · còn ~${fmtDuration(c.eta_seconds)}` : ""}
                        {c.kind === "manual" && c.manual ? <> · <Link href={`/admin/lam-giau/thu-cong?nguon=${c.connector}`}>xử lý thủ công →</Link></> : ""}
                      </span>
                    </div>
                    <Bar c={c} />
                    <Legend c={c} />
                    {c.paused_reason ? <div className="sub" style={{ color: "var(--danger)", marginTop: 4 }}>{c.paused_reason}</div> : null}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {canManage ? <CreateRunDialog open={creating} onClose={() => setCreating(false)} onCreated={() => { setCreating(false); load(); }} /> : null}

      <Dialog open={detail !== null} title={detail ? `Lỗi gần đây — vòng #${detail.id}` : ""} onClose={() => setDetail(null)} wide>
        {detail ? (
          <>
            {!detail.errors?.length ? <div className="adm-empty" style={{ padding: 20 }}>Không có lỗi.</div> : (
              <div className="adm-table-wrap" style={{ maxHeight: 420, overflow: "auto" }}>
                <table className="adm-table">
                  <thead><tr><th>MST</th><th>Nguồn</th><th>Trạng thái</th><th>Lần thử</th><th>Lỗi</th><th>Lúc</th></tr></thead>
                  <tbody>
                    {detail.errors.map((e, i) => (
                      <tr key={i}>
                        <td><Link className="mono" href={`/admin/lam-giau/${e.mst}`}>{e.mst}</Link></td>
                        <td className="mono">{e.connector}</td>
                        <td>{meta.job_statuses[e.status] ?? e.status}</td>
                        <td>{e.attempts}</td>
                        <td style={{ maxWidth: 360, wordBreak: "break-word" }}>{e.error}</td>
                        <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="adm-actions" style={{ marginTop: 14 }}><button className="adm-btn primary" onClick={() => setDetail(null)}>Đóng</button></div>
          </>
        ) : null}
      </Dialog>
    </>
  );
}

function CreateRunDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMsg("");
    api.get<Source[]>("/enrich/sources").then((s) => setSources(s.filter((x) => x.kind === "http" || x.kind === "manual")), () => {});
    api.get<Batch[]>("/enrich/batches").then(setBatches, () => {});
  }, [open]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const connectors = f.getAll("connectors").map(String);
    if (!connectors.length) return setMsg("Chọn ít nhất một nguồn.");
    setBusy(true);
    setMsg("");
    try {
      await api.post("/enrich/runs", { name: f.get("name"), connectors, batch_id: f.get("batch_id") ? Number(f.get("batch_id")) : null });
      onCreated();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} title="Tạo vòng thu thập" onClose={onClose} wide>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Tên vòng" htmlFor="r-name"><input id="r-name" className="adm-input" name="name" maxLength={200} defaultValue={`Vòng ${new Date().toLocaleDateString("vi-VN")}`} /></Field>
          <Field label="Phạm vi" htmlFor="r-batch">
            <select id="r-batch" className="adm-input" name="batch_id" defaultValue="">
              <option value="">Toàn bộ MST trong hệ thống</option>
              {batches.map((b) => <option key={b.id} value={b.id}>Lô #{b.id} · {b.name} ({fmtNum(b.mst_count)} MST)</option>)}
            </select>
          </Field>
          <div className="adm-field full" role="group" aria-labelledby="r-src">
            <label id="r-src">Nguồn</label>
            <div className="adm-checks">
              {sources.map((s) => (
                <label key={s.code} title={s.enabled ? "" : s.paused_reason || "Nguồn đang tắt"} style={s.enabled ? undefined : { opacity: 0.5 }}>
                  <input type="checkbox" name="connectors" value={s.code} disabled={!s.enabled} /> {s.name}
                </label>
              ))}
            </div>
          </div>
          <p className="muted full" style={{ fontSize: 12.5 }}>
            Nguồn tra cứu thủ công đưa MST vào hàng đợi thủ công cho nhân viên. MST đang có việc chưa xong ở cùng nguồn sẽ không bị tạo trùng.
            Dữ liệu mua ĐKKD, nợ thuế, đấu thầu nhập ở trang “Nhập nguồn chính thức”.
          </p>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang tạo…" : "Bắt đầu"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}
