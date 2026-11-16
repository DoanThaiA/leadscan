"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { type AlertRow, type SearchMeta, useEnrichMeta, type WatchlistRow } from "@/lib/admin/enrich";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";

const KIND_CLASS: Record<string, string> = { nguoi_dai_dien: "warn", trang_thai: "s-rejected", no_thue: "s-rejected", dia_chi: "info", trung_thau: "s-active", bo_nhiem: "info", khac: "s-suspended" };

export default function AlertsPage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [kinds, setKinds] = useState<Record<string, string>>({});
  const [alerts, setAlerts] = useState<{ unread: number; items: AlertRow[] } | null>(null);
  const [lists, setLists] = useState<WatchlistRow[] | null>(null);
  const [open, setOpen] = useState<WatchlistRow | null>(null);
  const [editing, setEditing] = useState<WatchlistRow | "new" | null>(null);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get<{ unread: number; items: AlertRow[] }>(`/enrich/alerts${onlyUnread ? "?unread=true" : ""}`).then(setAlerts, (e) => setError(errMsg(e)));
    api.get<WatchlistRow[]>("/enrich/watchlists").then(setLists, () => {});
  }, [onlyUnread]);

  useEffect(() => {
    document.title = "Theo dõi & cảnh báo · Làm giàu theo MST";
    api.get<SearchMeta>("/enrich/search/meta").then((m) => setKinds(m.alert_kinds), () => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  async function markRead(body: { ids?: number[]; all?: boolean }) {
    await api.post("/enrich/alerts/read", body).catch(() => {});
    load();
  }

  async function openList(w: WatchlistRow) {
    try { setOpen(await api.get<WatchlistRow>(`/enrich/watchlists/${w.id}`)); } catch (e) { alert(errMsg(e)); }
  }

  async function removeItem(w: WatchlistRow, mst: string) {
    await api.del(`/enrich/watchlists/${w.id}/items/${mst}`).catch(() => {});
    openList(w);
    load();
  }

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Theo dõi & cảnh báo</h1>
          <p>Cảnh báo khi doanh nghiệp trong danh sách theo dõi đổi người đại diện, địa chỉ, tình trạng MST, có nợ thuế, trúng thầu hoặc bổ nhiệm. Thêm doanh nghiệp từ trang Hồ sơ doanh nghiệp (nút “Theo dõi kết quả”).</p>
        </div>
        <button className="adm-btn primary" onClick={() => setEditing("new")}><Icon name="plus" size={16} /> Danh sách mới</button>
      </div>
      <EnrichNav caps={meta.caps} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <div className="adm-grid side">
        <section className="adm-card">
          <div className="hd">
            <h2>Cảnh báo {alerts?.unread ? <span className="adm-badge warn" style={{ marginLeft: 6 }}>{fmtNum(alerts.unread)} chưa đọc</span> : null}</h2>
            <div className="adm-actions">
              <label style={{ fontSize: 13, display: "inline-flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={onlyUnread} onChange={(e) => setOnlyUnread(e.target.checked)} /> Chỉ chưa đọc</label>
              {alerts?.unread ? <button className="adm-btn sm" onClick={() => markRead({ all: true })}>Đánh dấu đã đọc hết</button> : null}
            </div>
          </div>
          {!alerts ? <Skeleton h={200} /> : !alerts.items.length ? <div className="adm-empty">Chưa có cảnh báo nào. Hệ thống quét thay đổi mới mỗi 10 phút.</div> : (
            <ul className="adm-timeline bd">
              {alerts.items.map((a) => (
                <li key={a.id} style={a.read ? { opacity: 0.6 } : undefined}>
                  <span className="dot"><Icon name="bell" /></span>
                  <div>
                    <div className="txt">
                      <span className={`adm-badge ${KIND_CLASS[a.kind] ?? ""}`} style={{ marginRight: 6 }}>{a.kind_name}</span>
                      <Link href={`/admin/lam-giau/${a.mst}`} className="name" onClick={() => !a.read && markRead({ ids: [a.id] })}>{a.ten || a.mst}</Link>
                    </div>
                    <div style={{ marginTop: 2, wordBreak: "break-word" }}>{a.summary}</div>
                    <div className="meta">{fmtDateTime(a.created_at)}{!a.read ? <> · <button className="adm-btn sm ghost" style={{ padding: "0 6px", height: 22 }} onClick={() => markRead({ ids: [a.id] })}>Đã đọc</button></> : null}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="adm-card">
          <div className="hd"><h2>Danh sách theo dõi</h2></div>
          {!lists ? <Skeleton h={120} /> : !lists.length ? <div className="adm-empty">Chưa có danh sách.</div> : (
            <div className="bd" style={{ display: "grid", gap: 10 }}>
              {lists.map((w) => (
                <div key={w.id} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 6 }}>
                    <button className="name" style={{ border: 0, background: "none", padding: 0, cursor: "pointer", textAlign: "left" }} onClick={() => openList(w)}>{w.name}</button>
                    <span className="muted" style={{ fontSize: 12.5 }}>{fmtNum(w.count)} DN</span>
                  </div>
                  <div className="sub">
                    {w.kinds.length ? w.kinds.map((k) => kinds[k] ?? k).join(", ") : "Mọi loại cảnh báo"}
                    {w.email_digest ? " · gửi email" : ""}{w.shared ? " · chia sẻ nhóm" : ""}{!w.mine && w.owner ? ` · của ${w.owner}` : ""}
                  </div>
                  {w.mine ? <div className="adm-actions" style={{ justifyContent: "flex-start", marginTop: 6 }}><button className="adm-btn sm" onClick={() => setEditing(w)}>Sửa</button></div> : null}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <Dialog open={open !== null} title={open ? `${open.name} — ${fmtNum(open.items?.length ?? 0)} doanh nghiệp` : ""} onClose={() => setOpen(null)} wide>
        {open ? (
          <>
            <div className="adm-table-wrap" style={{ maxHeight: 420, overflow: "auto" }}>
              <table className="adm-table">
                <thead><tr><th>Doanh nghiệp</th><th>Tình trạng</th><th>Theo dõi từ</th>{open.mine ? <th /> : null}</tr></thead>
                <tbody>
                  {(open.items ?? []).map((i) => (
                    <tr key={i.mst}>
                      <td><Link className="name" href={`/admin/lam-giau/${i.mst}`}>{i.ten || i.mst}</Link><div className="sub mono">{i.mst}{i.ma_ck ? ` · ${i.ma_ck}` : ""}</div></td>
                      <td>{i.trang_thai || "—"}</td>
                      <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(i.added_at)}</td>
                      {open.mine ? <td><button className="adm-btn sm ghost" onClick={() => removeItem(open, i.mst)} aria-label="Bỏ theo dõi"><Icon name="trash" size={14} /></button></td> : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="adm-actions" style={{ marginTop: 12 }}><button className="adm-btn primary" onClick={() => setOpen(null)}>Đóng</button></div>
          </>
        ) : null}
      </Dialog>

      <ListDialog value={editing} kinds={kinds} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
    </>
  );
}

function ListDialog({ value, kinds, onClose, onSaved }: { value: WatchlistRow | "new" | null; kinds: Record<string, string>; onClose: () => void; onSaved: () => void }) {
  const [msg, setMsg] = useState("");
  const w = value && value !== "new" ? value : null;
  useEffect(() => setMsg(""), [value]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = { name: f.get("name"), shared: f.get("shared") === "on", email_digest: f.get("email") === "on", kinds: f.getAll("kinds").map(String) };
    try {
      if (w) await api.put(`/enrich/watchlists/${w.id}`, body);
      else await api.post("/enrich/watchlists", body);
      onSaved();
    } catch (err) { setMsg(errMsg(err)); }
  }
  async function remove() {
    if (!w || !confirm(`Xoá danh sách “${w.name}”?`)) return;
    await api.del(`/enrich/watchlists/${w.id}`).catch(() => {});
    onSaved();
  }
  return (
    <Dialog open={value !== null} title={w ? `Sửa — ${w.name}` : "Danh sách theo dõi mới"} onClose={onClose} wide>
      {value !== null ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Tên danh sách" full htmlFor="wl-name"><input id="wl-name" className="adm-input" name="name" maxLength={200} defaultValue={w?.name ?? ""} autoFocus /></Field>
          <div className="adm-field full" role="group" aria-labelledby="wl-k">
            <label id="wl-k">Loại cảnh báo (bỏ trống = tất cả)</label>
            <div className="adm-checks">{Object.entries(kinds).map(([k, v]) => <label key={k}><input type="checkbox" name="kinds" value={k} defaultChecked={w?.kinds.includes(k)} /> {v}</label>)}</div>
          </div>
          <label className="full" style={{ display: "flex", gap: 8, fontSize: 13 }}><input type="checkbox" name="email" defaultChecked={w?.email_digest} /> Gửi email tổng hợp cảnh báo (mỗi giờ, khi có cảnh báo mới)</label>
          <label className="full" style={{ display: "flex", gap: 8, fontSize: 13 }}><input type="checkbox" name="shared" defaultChecked={w?.shared} /> Cho cả nhóm xem danh sách này</label>
          <div className="adm-actions full" style={{ justifyContent: "space-between" }}>
            {w ? <button type="button" className="adm-btn danger" onClick={remove}>Xoá danh sách</button> : <span />}
            <div className="adm-actions"><button type="button" className="adm-btn" onClick={onClose}>Huỷ</button><button type="submit" className="adm-btn primary">Lưu</button></div>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}
