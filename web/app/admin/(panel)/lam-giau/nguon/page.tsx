"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg } from "@/lib/admin/api";
import { type Ops, type Source, SOURCE_KIND, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";

interface DomainRow {
  domain: string;
  requests: number;
  min_gap_s: number | null;
}

export default function EnrichSourcesPage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [list, setList] = useState<Source[] | null>(null);
  const [ops, setOps] = useState<Ops | null>(null);
  const [domains, setDomains] = useState<{ min_interval_s: number; domains: DomainRow[] } | null>(null);
  const [editing, setEditing] = useState<Source | null>(null);
  const [error, setError] = useState("");

  const canManage = !!meta?.caps.includes("source.manage");
  const canRead = !!meta?.caps.includes("run.read");

  const load = useCallback(() => {
    api.get<Source[]>("/enrich/sources").then(setList, (e) => setError(errMsg(e)));
  }, []);

  useEffect(() => {
    document.title = "Nguồn & cấu hình · Làm giàu theo MST";
    load();
  }, [load]);

  useEffect(() => {
    if (!canRead) return;
    api.get<Ops>("/enrich/ops").then(setOps, () => {});
    api.get<{ min_interval_s: number; domains: DomainRow[] }>("/enrich/ops/domains").then(setDomains, () => {});
  }, [canRead]);

  async function saveOps(body: Record<string, unknown>) {
    try {
      setOps(await api.put<Ops>("/enrich/ops", body));
    } catch (e) {
      alert(errMsg(e));
    }
  }

  async function toggle(s: Source) {
    try {
      await api.patch(`/enrich/sources/${s.code}`, { enabled: !s.enabled });
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Nguồn & cấu hình</h1>
          <p>Mỗi nguồn là một connector độc lập: bật/tắt, độ tin cậy, tốc độ, số lần thử lại — đổi ở đây không cần triển khai lại.</p>
        </div>
      </div>
      <EnrichNav caps={meta.caps} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      {ops ? (
        <div className={ops.paused.on ? "er-stop off" : "er-stop"}>
          <div>
            <b>{ops.paused.on ? "Đang DỪNG KHẨN CẤP — không gửi request nào ra ngoài" : ops.running_now ? "Thu thập tự động đang được phép chạy" : ops.blocked_reason}</b>
            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
              {ops.paused.on && ops.paused.reason ? `Lý do: ${ops.paused.reason}. ` : ""}
              Khung giờ: {ops.window.enabled ? `${ops.window.start}h – ${ops.window.end}h (giờ Việt Nam)` : "cả ngày"} · tối đa {ops.max_running.per_connector} việc song song mỗi nguồn
            </div>
          </div>
          {canManage ? (
            <div className="adm-actions">
              {ops.paused.on ? (
                <button className="adm-btn primary" onClick={() => saveOps({ paused: false })}>Chạy lại</button>
              ) : (
                <button
                  className="adm-btn danger"
                  onClick={() => {
                    const reason = prompt("Lý do dừng khẩn cấp (không bắt buộc):", "");
                    if (reason !== null) saveOps({ paused: true, pause_reason: reason });
                  }}
                >
                  Dừng khẩn cấp
                </button>
              )}
              <WindowButton ops={ops} onSave={saveOps} />
            </div>
          ) : null}
        </div>
      ) : null}

      {canRead ? <RecrawlCard canManage={canManage} canRun={!!meta.caps.includes("run.manage")} /> : null}

      <section className="adm-card" style={{ marginBottom: 16 }}>
        <div className="hd"><h2>Nguồn dữ liệu</h2></div>
        {!list ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Nguồn</th><th>Kiểu</th><th>Tin cậy</th><th>Tốc độ / thử lại</th><th>Tái thu thập</th><th>1 giờ qua</th><th>Trạng thái</th>{canManage ? <th /> : null}</tr></thead>
              <tbody>
                {list.map((s) => (
                  <tr key={s.code}>
                    <td>
                      <div className="name">{s.name}</div>
                      <div className="sub"><span className="mono">{s.code}</span>{s.domain ? ` · ${s.domain}` : ""}</div>
                      {s.legal_basis ? <div className="sub" style={{ maxWidth: 420 }} title={s.legal_basis}>Cơ sở pháp lý: {s.legal_basis.length > 90 ? s.legal_basis.slice(0, 88) + "…" : s.legal_basis}</div> : <div className="sub" style={{ color: "var(--danger)" }}>Chưa khai cơ sở pháp lý — không được bật</div>}
                    </td>
                    <td><span className="adm-badge plain role">{SOURCE_KIND[s.kind] ?? s.kind}</span></td>
                    <td style={{ fontVariantNumeric: "tabular-nums" }}>{s.trust}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{s.kind === "http" ? <>≥ {s.min_interval_s}s/request<div className="sub">timeout {s.timeout_s}s · thử lại {s.max_retries} lần</div></> : <span className="muted">—</span>}</td>
                    <td>{s.kind === "internal" ? "—" : `${s.recrawl_days} ngày`}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{s.requests_last_hour ? <>{fmtNum(s.requests_last_hour)} req<div className="sub">{s.errors_last_hour} lỗi</div></> : <span className="muted">—</span>}</td>
                    <td>
                      {s.enabled ? <span className="adm-badge s-active">Đang bật</span> : <span className="adm-badge s-suspended">Tắt</span>}
                      {s.paused_reason ? <div className="sub" style={{ color: "var(--danger)", maxWidth: 240 }}>{s.paused_reason}<br />{fmtDateTime(s.paused_at)}</div> : null}
                    </td>
                    {canManage ? (
                      <td>
                        <div className="adm-actions">
                          {s.kind !== "internal" ? <button className="adm-btn sm" onClick={() => toggle(s)}>{s.enabled ? "Tắt" : "Bật"}</button> : null}
                          <button className="adm-btn sm" onClick={() => setEditing(s)}>Sửa</button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {domains ? (
        <section className="adm-card">
          <div className="hd"><h2>Tốc độ theo tên miền — 24 giờ qua</h2></div>
          <div className="bd">
            <p className="er-note" style={{ marginBottom: 10 }}><Icon name="check" /><span>Mỗi request ra ngoài đều ghi nhật ký. Khoảng cách nhỏ nhất giữa 2 request liên tiếp tới cùng tên miền phải ≥ {domains.min_interval_s} giây.</span></p>
            {!domains.domains.length ? <div className="adm-empty" style={{ padding: 20 }}>Chưa có request tự động nào.</div> : (
              <table className="adm-table">
                <thead><tr><th>Tên miền</th><th style={{ textAlign: "right" }}>Số request</th><th style={{ textAlign: "right" }}>Khoảng cách nhỏ nhất</th><th /></tr></thead>
                <tbody>
                  {domains.domains.map((d) => {
                    const ok = d.min_gap_s === null || d.min_gap_s >= domains.min_interval_s;
                    return (
                      <tr key={d.domain}>
                        <td className="mono">{d.domain}</td>
                        <td style={{ textAlign: "right" }}>{fmtNum(d.requests)}</td>
                        <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{d.min_gap_s === null ? "—" : `${d.min_gap_s.toFixed(2)} s`}</td>
                        <td>{ok ? <span className="adm-badge s-active">Đạt</span> : <span className="adm-badge s-rejected">Vượt ngưỡng</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>
      ) : null}

      <EditSourceDialog source={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
    </>
  );
}

function WindowButton({ ops, onSave }: { ops: Ops; onSave: (b: Record<string, unknown>) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="adm-btn" onClick={() => setOpen(true)}>Khung giờ chạy</button>
      <Dialog open={open} title="Khung giờ chạy tự động" onClose={() => setOpen(false)}>
        {open ? (
          <form
            className="adm-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              onSave({
                window_enabled: f.get("enabled") === "on",
                window_start: Number(f.get("start")),
                window_end: Number(f.get("end")),
                per_connector: Number(f.get("per")),
              });
              setOpen(false);
            }}
          >
            <label className="full" style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" name="enabled" defaultChecked={ops.window.enabled} /> Chỉ chạy trong khung giờ (ví dụ chạy đêm)
            </label>
            <Field label="Từ giờ (0–23)" htmlFor="w-s"><input id="w-s" className="adm-input" name="start" type="number" min={0} max={23} defaultValue={ops.window.start} /></Field>
            <Field label="Đến giờ (0–23)" htmlFor="w-e"><input id="w-e" className="adm-input" name="end" type="number" min={0} max={23} defaultValue={ops.window.end} /></Field>
            <Field label="Việc song song tối đa mỗi nguồn" htmlFor="w-p"><input id="w-p" className="adm-input" name="per" type="number" min={1} max={20} defaultValue={ops.max_running.per_connector} /></Field>
            <p className="muted full" style={{ fontSize: 12.5 }}>Giờ Việt Nam. Từ 22 đến 6 nghĩa là chạy qua đêm. Giới hạn ≥ 2 giây/request mỗi tên miền luôn áp dụng dù chạy bao nhiêu việc song song.</p>
            <div className="adm-actions full">
              <button type="button" className="adm-btn" onClick={() => setOpen(false)}>Huỷ</button>
              <button type="submit" className="adm-btn primary">Lưu</button>
            </div>
          </form>
        ) : null}
      </Dialog>
    </>
  );
}

function EditSourceDialog({ source, onClose, onSaved }: { source: Source | null; onClose: () => void; onSaved: () => void }) {
  const [msg, setMsg] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => { setMsg(""); setErrors({}); }, [source]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!source) return;
    const f = new FormData(e.currentTarget);
    const body: Record<string, unknown> = { trust: Number(f.get("trust")), legal_basis: String(f.get("legal_basis") ?? ""), recrawl_days: Number(f.get("recrawl_days")) };
    if (source.kind === "http") {
      body.min_interval_s = Number(f.get("min_interval_s"));
      body.timeout_s = Number(f.get("timeout_s"));
      body.max_retries = Number(f.get("max_retries"));
    }
    try {
      await api.patch(`/enrich/sources/${source.code}`, body);
      onSaved();
    } catch (err) {
      if (err instanceof ApiError) { setMsg(err.message); setErrors(err.fields); } else setMsg(errMsg(err));
    }
  }

  return (
    <Dialog open={source !== null} title={source ? `Cấu hình — ${source.name}` : ""} onClose={onClose} wide>
      {source ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Độ tin cậy (0–1)" error={errors.trust} htmlFor="s-t"><input id="s-t" className="adm-input" name="trust" type="number" step="0.05" min={0} max={1} defaultValue={source.trust} /></Field>
          <Field label="Tái thu thập sau (ngày)" error={errors.recrawl_days} htmlFor="s-r"><input id="s-r" className="adm-input" name="recrawl_days" type="number" min={1} defaultValue={source.recrawl_days} /></Field>
          {source.kind === "http" ? (
            <>
              <Field label="Giãn cách mỗi request (giây, ≥ 2)" error={errors.min_interval_s} htmlFor="s-i"><input id="s-i" className="adm-input" name="min_interval_s" type="number" step="0.5" min={2} defaultValue={source.min_interval_s} /></Field>
              <Field label="Timeout (giây)" error={errors.timeout_s} htmlFor="s-to"><input id="s-to" className="adm-input" name="timeout_s" type="number" min={1} defaultValue={source.timeout_s} /></Field>
              <Field label="Số lần thử lại" error={errors.max_retries} htmlFor="s-m"><input id="s-m" className="adm-input" name="max_retries" type="number" min={0} max={10} defaultValue={source.max_retries} /></Field>
            </>
          ) : null}
          <Field label="Cơ sở pháp lý của nguồn (bắt buộc để bật — cần pháp chế duyệt)" error={errors.legal_basis} full htmlFor="s-l">
            <textarea id="s-l" className="adm-input" name="legal_basis" rows={4} defaultValue={source.legal_basis} />
          </Field>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button type="submit" className="adm-btn primary">Lưu</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}

interface Schedule {
  recrawl: { enabled: boolean; daily_limit: number };
  file_reminders: { source: string; name: string; last_import: string | null; every_days: number }[];
}

/** A12: lịch tái thu thập tự động mỗi ngày + nhắc nhập lại các nguồn dạng file. */
function RecrawlCard({ canManage, canRun }: { canManage: boolean; canRun: boolean }) {
  const [d, setD] = useState<Schedule | null>(null);
  const [msg, setMsg] = useState("");
  const load = useCallback(() => { api.get<Schedule>("/enrich/ops/schedule").then(setD, () => {}); }, []);
  useEffect(() => { load(); }, [load]);
  async function save(body: Record<string, unknown>) {
    try { await api.put("/enrich/ops/schedule", body); load(); } catch (e) { setMsg(errMsg(e)); }
  }
  async function runNow() {
    try {
      const r = await api.post<{ runs: { connector: string; jobs: number }[] }>("/enrich/ops/recrawl-now");
      setMsg(r.runs.length ? `Đã tạo ${r.runs.length} vòng: ${r.runs.map((x) => `${x.connector} (${fmtNum(x.jobs)} MST)`).join(", ")}.` : "Không có MST nào đến hạn tái thu thập.");
    } catch (e) { setMsg(errMsg(e)); }
  }
  if (!d) return null;
  return (
    <section className="adm-card" style={{ marginBottom: 16 }}>
      <div className="hd">
        <h2>Lịch tái thu thập tự động</h2>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {canManage ? (
            <>
              <label style={{ fontSize: 13, display: "inline-flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={d.recrawl.enabled} onChange={(e) => save({ enabled: e.target.checked })} /> Bật</label>
              <label style={{ fontSize: 13, display: "inline-flex", gap: 6, alignItems: "center" }}>Tối đa
                <input className="adm-input" type="number" min={1} style={{ width: 90, height: 30 }} defaultValue={d.recrawl.daily_limit} onBlur={(e) => Number(e.target.value) !== d.recrawl.daily_limit && save({ daily_limit: Number(e.target.value) })} aria-label="Số MST tối đa mỗi nguồn mỗi ngày" /> MST/nguồn/ngày</label>
            </>
          ) : <span className="muted" style={{ fontSize: 13 }}>{d.recrawl.enabled ? `Đang bật · tối đa ${fmtNum(d.recrawl.daily_limit)} MST/nguồn/ngày` : "Đang tắt"}</span>}
          {canRun ? <button className="adm-btn sm" onClick={runNow}>Chạy ngay</button> : null}
        </div>
      </div>
      <div className="bd">
        <p className="er-note" style={{ marginBottom: 8 }}><Icon name="refresh" /><span>Mỗi ngày, MST đã quá “Tái thu thập sau (ngày)” của từng nguồn tự động / tra cứu thủ công đang bật được đưa vào một vòng mới (cột “Tái thu thập” bên dưới). Thay đổi phát hiện được sinh cảnh báo cho danh sách theo dõi.</span></p>
        {msg ? <div className="adm-alert ok" style={{ marginBottom: 8 }}>{msg}</div> : null}
        {d.file_reminders.length ? (
          <div className="adm-alert warn">
            Nguồn dạng file đến hạn nhập lại: {d.file_reminders.map((r) => `${r.name} (${r.last_import ? "lần cuối " + fmtDateTime(r.last_import) : "chưa nhập lần nào"}, chu kỳ ${r.every_days} ngày)`).join(" · ")}.
          </div>
        ) : null}
      </div>
    </section>
  );
}
