"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Field, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";

interface SettingField {
  key: string;
  label: string;
  type: "int" | "choice";
  min: number | null;
  max: number | null;
  default: number | string;
  choices: Record<string, string> | null;
}

interface SettingsView {
  values: Record<string, number | string>;
  fields: SettingField[];
  logs: { key: string; old: string; new: string; reason: string; actor: string | null; created_at: string }[];
}

const GROUPS: [string, string[]][] = [
  ["Ly cafe & cách cộng", ["cafe_amount", "reward_mode"]],
  ["Tỷ lệ hoa hồng", ["rate_new", "rate_silver", "rate_strategic", "rate_large", "rate_max"]],
  ["Hạn mức ly cafe / tháng", ["cafe_quota_new", "cafe_quota_silver", "cafe_quota_strategic"]],
  ["Thời gian", ["hold_days", "share_months"]],
];

/** Tham số thưởng đối tác (brief mục 5, 9 — "tham số cấu hình được, không phải sửa code"). Chỉ quản trị viên sửa. */
export default function PartnerSettingsPage() {
  const { user } = useAdmin();
  const isAdmin = user.role === "admin";
  const [data, setData] = useState<SettingsView | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  function load(d: SettingsView) {
    setData(d);
    setVals(Object.fromEntries(Object.entries(d.values).map(([k, v]) => [k, String(v)])));
  }

  useEffect(() => {
    document.title = "Cấu hình thưởng đối tác · Quản trị LeadScan";
    api.get<SettingsView>("/partner-settings").then(load, (e) => setMsg({ ok: false, text: errMsg(e) }));
  }, []);

  if (!data) return msg ? <div className="adm-alert">{msg.text}</div> : <div style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>;

  const byKey = Object.fromEntries(data.fields.map((f) => [f.key, f]));
  const changed = Object.fromEntries(Object.entries(vals).filter(([k, v]) => v !== String(data.values[k])).map(([k, v]) => [k, byKey[k]?.type === "int" ? Number(v) : v]));
  const nChanged = Object.keys(changed).length;

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      load(await api.put<SettingsView>("/partner-settings", { values: changed, reason }));
      setReason("");
      setMsg({ ok: true, text: "Đã lưu cấu hình. Áp dụng cho các khoản ghi từ bây giờ; khoản đã ghi giữ nguyên." });
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <Link href="/admin/doi-tac" className="muted" style={{ fontSize: 13 }}>← Đối tác</Link>
          <h1 style={{ marginTop: 4 }}>Cấu hình thưởng đối tác</h1>
          <p>Giá trị ly cafe, tỷ lệ hoa hồng, hạn mức, thời gian giữ — trang /doi-tac và cổng đối tác hiển thị theo cấu hình này</p>
        </div>
      </div>
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ marginBottom: 16 }}>{msg.text}</div> : null}
      {!isAdmin ? <div className="adm-alert warn" style={{ marginBottom: 16 }}>Chỉ quản trị viên được sửa cấu hình.</div> : null}

      <div className="adm-grid side">
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {GROUPS.map(([title, keys]) => (
            <section key={title} className="adm-card">
              <div className="hd"><h2>{title}</h2></div>
              <div className="bd" style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" }}>
                {keys.map((k) => {
                  const f = byKey[k];
                  if (!f) return null;
                  const dirty = vals[k] !== String(data.values[k]);
                  return (
                    <Field key={k} label={`${f.label}${dirty ? " •" : ""}`} htmlFor={`st-${k}`}>
                      {f.type === "choice" ? (
                        <select id={`st-${k}`} className="adm-input" value={vals[k]} disabled={!isAdmin} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}>
                          {Object.entries(f.choices ?? {}).map(([c, label]) => <option key={c} value={c}>{label}</option>)}
                        </select>
                      ) : (
                        <input id={`st-${k}`} className="adm-input" type="number" min={f.min ?? undefined} max={f.max ?? undefined} value={vals[k]} disabled={!isAdmin}
                          onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
                      )}
                      <span className="muted" style={{ fontSize: 12 }}>Mặc định brief: {f.choices ? f.choices[String(f.default)] : String(f.default)}</span>
                    </Field>
                  );
                })}
              </div>
            </section>
          ))}
        </div>

        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {isAdmin ? (
            <section className="adm-card">
              <div className="hd"><h2>Lưu thay đổi</h2></div>
              <div className="bd" style={{ display: "grid", gap: 12 }}>
                <p className="muted" style={{ fontSize: 13 }}>{nChanged ? `${nChanged} tham số thay đổi.` : "Chưa thay đổi gì."} Mỗi lần lưu được ghi lịch sử (ai, khi nào, vì sao).</p>
                <Field label="Lý do (bắt buộc)" htmlFor="st-reason"><input id="st-reason" className="adm-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="vd. Chốt mục 12 brief ngày…" /></Field>
                <button className="adm-btn primary" disabled={busy || !nChanged || reason.trim().length < 3} onClick={save}>{busy ? "Đang lưu…" : "Lưu cấu hình"}</button>
              </div>
            </section>
          ) : null}
          <section className="adm-card">
            <div className="hd"><h2>Lịch sử thay đổi</h2></div>
            <div className="bd">
              {!data.logs.length ? <p className="muted">Chưa thay đổi lần nào — đang dùng mức mặc định theo brief.</p> : (
                <ul className="adm-timeline">
                  {data.logs.map((l, i) => (
                    <li key={i} className="k-status">
                      <span className="dot">•</span>
                      <div>
                        <div className="txt">{byKey[l.key]?.label ?? l.key}: {l.old} → <b>{l.new}</b></div>
                        <div className="meta">{l.reason} · {l.actor ?? "—"} · {fmtDateTime(l.created_at)}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
