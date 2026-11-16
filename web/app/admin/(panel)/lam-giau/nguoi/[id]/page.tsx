"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { type GraphData, type PersonProfile, useEnrichMeta, VERIFY_STATUS } from "@/lib/admin/enrich";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";

/** Đồ thị quan hệ dạng vòng: người đang xem ở giữa, doanh nghiệp vòng trong, người cùng doanh nghiệp vòng ngoài. */
function Graph({ g, onPick }: { g: GraphData; onPick: (n: GraphData["nodes"][number]) => void }) {
  const W = 760, H = 460, cx = W / 2, cy = H / 2;
  const layout = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    const center = g.nodes.find((n) => n.center);
    const companies = g.nodes.filter((n) => n.type === "company");
    const others = g.nodes.filter((n) => n.type === "person" && !n.center);
    if (center) pos[center.id] = { x: cx, y: cy };
    companies.forEach((c, i) => {
      const a = (2 * Math.PI * i) / Math.max(companies.length, 1) - Math.PI / 2;
      pos[c.id] = { x: cx + Math.cos(a) * 130, y: cy + Math.sin(a) * 110 };
    });
    // người khác: xếp quanh doanh nghiệp đầu tiên họ nối tới
    const byCompany: Record<string, string[]> = {};
    for (const o of others) {
      const e = g.edges.find((x) => x.from === o.id);
      if (e) (byCompany[e.to] ??= []).push(o.id);
    }
    for (const [cid, ids] of Object.entries(byCompany)) {
      const base = Math.atan2(pos[cid].y - cy, pos[cid].x - cx);
      ids.forEach((id, k) => {
        const spread = Math.min(0.9, 0.28 * (ids.length - 1));
        const a = base + (ids.length > 1 ? -spread / 2 + (spread * k) / (ids.length - 1) : 0);
        pos[id] = { x: cx + Math.cos(a) * 290, y: cy + Math.sin(a) * 195 };
      });
    }
    return pos;
  }, [g, cx, cy]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Đồ thị quan hệ người và doanh nghiệp" style={{ width: "100%", height: "auto", display: "block" }}>
      {g.edges.map((e, i) => {
        const a = layout[e.from], b = layout[e.to];
        if (!a || !b) return null;
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--line)" strokeWidth={1.5} strokeDasharray={e.active ? undefined : "4 4"}><title>{e.label}{e.active ? "" : " (đã thôi)"}</title></line>;
      })}
      {g.nodes.map((n) => {
        const p = layout[n.id];
        if (!p) return null;
        const company = n.type === "company";
        const label = n.label.length > 26 ? n.label.slice(0, 25) + "…" : n.label;
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} style={{ cursor: n.center ? "default" : "pointer" }} onClick={() => !n.center && onPick(n)}>
            {company ? <rect x={-9} y={-9} width={18} height={18} rx={3} fill="var(--brand-50)" stroke="var(--brand)" /> : <circle r={n.center ? 12 : 8} fill={n.center ? "var(--brand)" : "#fff"} stroke="var(--brand)" strokeWidth={1.5} />}
            <text y={n.center ? 28 : 22} textAnchor="middle" fontSize={n.center ? 13 : 11.5} fontWeight={n.center ? 700 : 500} fill="var(--ink)">{label}</text>
            <title>{n.label}</title>
          </g>
        );
      })}
    </svg>
  );
}

export default function PersonPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { meta, error: metaError } = useEnrichMeta();
  const [p, setP] = useState<PersonProfile | null>(null);
  const [g, setG] = useState<GraphData | null>(null);
  const [split, setSplit] = useState<number[]>([]);
  const [mergeWith, setMergeWith] = useState("");
  const [purpose, setPurpose] = useState("tham_dinh_kyc");
  const [inferred, setInferred] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setSplit([]);
    api.get<PersonProfile>(`/enrich/persons/${id}`).then((x) => {
      if (x.merged_into_id) router.replace(`/admin/lam-giau/nguoi/${x.merged_into_id}`);
      else setP(x);
    }, (e) => setError(errMsg(e)));
    api.get<GraphData>(`/enrich/persons/${id}/graph`).then(setG, () => {});
  }, [id, router]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (p?.ho_ten) document.title = `${p.ho_ten} · Người & quan hệ`; }, [p]);

  async function run(fn: () => Promise<unknown>, ok: string) {
    setMsg("");
    try { await fn(); setMsg(ok); load(); } catch (e) { setMsg(errMsg(e)); }
  }

  if (metaError || error) return <div className="adm-card adm-empty">{metaError || error}</div>;
  if (!meta || !p) return <Skeleton h={400} />;
  const canManage = meta.caps.includes("people.manage");
  const canList = meta.caps.includes("b.list");
  const roles = p.roles ?? [];
  const current = roles.filter((r) => !r.den_ngay);
  const past = roles.filter((r) => r.den_ngay);

  return (
    <>
      <EnrichNav caps={meta.caps} />
      {canList ? <Link href="/admin/lam-giau/nguoi" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Người & quan hệ</Link> : null}
      <div className="adm-head">
        <div>
          <h1>{p.ho_ten}</h1>
          <p>
            <span className="mono">#{p.id}</span>
            {"nam_sinh" in p && p.nam_sinh ? ` · sinh năm ${p.nam_sinh}` : ""}
            {"mst_ca_nhan" in p && p.mst_ca_nhan ? <> · MST cá nhân <span className="mono">{p.mst_ca_nhan}</span> (chỉ đối soát nội bộ)</> : ""}
            {" · "}{current.length} vai trò đang giữ ở {new Set(current.map((r) => r.company_mst)).size} doanh nghiệp
          </p>
        </div>
        {canList ? (
          <div className="adm-actions" style={{ alignItems: "center" }}>
            <select className="adm-input" style={{ width: "auto", height: 34 }} value={purpose} onChange={(e) => setPurpose(e.target.value)} aria-label="Mục đích xuất">
              {Object.entries(meta.purposes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <label style={{ fontSize: 12.5, display: "inline-flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={inferred} onChange={(e) => setInferred(e.target.checked)} /> kèm email suy luận</label>
            <a className="adm-btn" href={`/api/admin/enrich/persons/${p.id}/related.csv?purpose=${purpose}${inferred ? "&include_inferred=true" : ""}`}><Icon name="download" size={14} /> Xuất bên liên quan</a>
          </div>
        ) : null}
      </div>
      <p className="er-note" style={{ marginBottom: 12 }}><Icon name="lock" /><span>Dữ liệu cá nhân (kho B) — mở hồ sơ, xem đồ thị và xuất đều được ghi nhật ký. Bản xuất không bao giờ có MST cá nhân.</span></p>
      {msg ? <div className="adm-alert" style={{ marginBottom: 12 }}>{msg}</div> : null}

      <div className="adm-grid side" style={{ marginBottom: 16 }}>
        <section className="adm-card">
          <div className="hd"><h2>Đồ thị quan hệ</h2><span className="muted" style={{ fontSize: 12 }}>■ doanh nghiệp · ● người · nét đứt: đã thôi</span></div>
          <div className="bd">{g ? <Graph g={g} onPick={(n) => router.push(n.type === "company" ? `/admin/lam-giau/${n.mst}` : `/admin/lam-giau/nguoi/${n.person_id}`)} /> : <Skeleton h={300} />}</div>
        </section>
        <section className="adm-card">
          <div className="hd"><h2>Liên hệ công việc</h2></div>
          <div className="bd">
            {!p.lien_he?.length ? <p className="muted">Chưa có.</p> : p.lien_he.map((c) => (
              <div key={c.value} style={{ marginBottom: 8 }}>
                <span className="mono">{c.value}</span>{c.is_inferred ? <span className="adm-badge warn" style={{ marginLeft: 6 }}>Suy luận</span> : null}
                <div className="sub">{VERIFY_STATUS[c.verify_status] ?? c.verify_status}{c.source_code ? ` · ${c.source_code}` : ""}</div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="adm-card" style={{ marginBottom: 16 }}>
        <div className="hd">
          <h2>Vai trò</h2>
          {canManage && split.length ? (
            <button className="adm-btn sm" onClick={() => confirm(`Tách ${split.length} vai trò đã chọn sang một hồ sơ mới cùng tên (khi hai người trùng tên bị gộp nhầm)?`) && run(() => api.post(`/enrich/persons/${p.id}/split`, { role_ids: split }), "Đã tách — có thể hoàn tác ở lịch sử bên dưới.")}>Tách {split.length} vai trò đã chọn</button>
          ) : null}
        </div>
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead><tr>{canManage ? <th /> : null}<th>Doanh nghiệp</th><th>Chức danh</th><th>Thời gian</th><th>Nguồn</th></tr></thead>
            <tbody>
              {[...current, ...past].map((r) => (
                <tr key={r.id} style={r.den_ngay ? { opacity: 0.65 } : undefined}>
                  {canManage ? <td><input type="checkbox" aria-label="Chọn để tách" checked={split.includes(r.id)} onChange={(e) => setSplit((s) => (e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id)))} /></td> : null}
                  <td><Link className="name" href={`/admin/lam-giau/${r.company_mst}`}>{r.ma_ck ? <span className="mono">{r.ma_ck} · </span> : null}{r.company_ten ?? r.company_mst}</Link><div className="sub mono">{r.company_mst}</div></td>
                  <td>{r.chuc_danh}{r.la_nguoi_quyet_dinh ? <span className="adm-badge s-active" style={{ marginLeft: 6 }}>Ra quyết định</span> : null}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{r.tu_ngay ? fmtDate(r.tu_ngay) : "?"} → {r.den_ngay ? fmtDate(r.den_ngay) : "nay"}</td>
                  <td className="mono">{r.source_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {p.bang_chung?.length ? (
        <section className="adm-card" style={{ marginBottom: 16 }}>
          <div className="hd"><h2>Nguồn gốc</h2></div>
          <div className="adm-table-wrap">
            <table className="adm-table er-ev">
              <thead><tr><th>Trường</th><th>Giá trị</th><th>Nguồn</th><th>Trích đoạn</th><th>Thời điểm</th></tr></thead>
              <tbody>
                {p.bang_chung.map((e, i) => (
                  <tr key={i}>
                    <td>{e.field}{e.is_inferred ? <div><span className="adm-badge warn">Suy luận</span></div> : null}</td>
                    <td className="v">{e.value}</td>
                    <td>{e.source_code}<div className="sub">{meta.methods[e.method] ?? e.method}</div>{/^https?:/.test(e.source_url) ? <div className="sub"><a href={e.source_url} target="_blank" rel="noopener noreferrer nofollow">{e.source_url.slice(0, 50)}</a></div> : <div className="sub mono">{e.source_url}</div>}</td>
                    <td><div className="excerpt">{e.excerpt || "—"}</div></td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.fetched_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {canList ? (
        <div className="adm-grid side">
          <section className="adm-card">
            <div className="hd"><h2>Lịch sử gộp / tách</h2></div>
            <div className="bd">
              {!p.ops?.length ? <p className="muted">Chưa có thao tác nào.</p> : (
                <ul className="adm-timeline">
                  {p.ops.map((o) => (
                    <li key={o.id}>
                      <span className="dot"><Icon name={o.op === "merge" ? "layers" : "users"} /></span>
                      <div>
                        <div className="txt">{o.op === "merge" ? `Gộp hồ sơ #${o.other_person_id} vào #${o.person_id}` : `Tách vai trò từ #${o.person_id} sang #${o.other_person_id}`}{o.note ? ` — ${o.note}` : ""}</div>
                        <div className="meta">{fmtDateTime(o.created_at)}{o.undone_at ? ` · đã hoàn tác ${fmtDateTime(o.undone_at)}` : ""}</div>
                        {canManage && !o.undone_at ? <button className="adm-btn sm" style={{ marginTop: 4 }} onClick={() => run(() => api.post(`/enrich/entity-ops/${o.id}/undo`), "Đã hoàn tác.")}>Hoàn tác</button> : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
          <section className="adm-card">
            <div className="hd"><h2>Nghi trùng & gộp</h2></div>
            <div className="bd">
              {p.candidates?.length ? p.candidates.map((c) => {
                const other = c.a.id === p.id ? c.b : c.a;
                return (
                  <div key={c.id} style={{ marginBottom: 10 }}>
                    <Link href={`/admin/lam-giau/nguoi/${other.id}`} className="name">{other.ho_ten} #{other.id}</Link> <span className="muted">· điểm {c.score.toFixed(2)}</span>
                    {other.roles.map((r, i) => <div key={i} className="sub">{r.chuc_danh} — {r.company_ten ?? r.company_mst}</div>)}
                  </div>
                );
              }) : <p className="muted">Không có hồ sơ nghi trùng.</p>}
              {canManage ? (
                <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                  <input className="adm-input" value={mergeWith} onChange={(e) => setMergeWith(e.target.value.replace(/\D/g, ""))} placeholder="Mã hồ sơ cần gộp vào đây" aria-label="Mã hồ sơ cần gộp" />
                  <button className="adm-btn" disabled={!mergeWith} onClick={() => confirm(`Gộp hồ sơ #${mergeWith} vào #${p.id}?`) && run(() => api.post("/enrich/persons/merge", { keep_id: p.id, drop_id: Number(mergeWith) }), "Đã gộp — có thể hoàn tác.")}>Gộp</button>
                </div>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
