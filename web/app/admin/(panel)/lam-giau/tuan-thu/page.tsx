"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { type AccessLogRow, type ExportLogRow, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDate, fmtDateTime, fmtNum } from "@/lib/admin/format";

type Tab = "subjects" | "optouts" | "retention" | "exports" | "access" | "dpia";

interface Subject { id: number; ho_ten: string; roles: { company_mst: string; chuc_danh: string }[] }
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

export default function CompliancePage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [tab, setTab] = useState<Tab>("subjects");
  const [flash, setFlash] = useState("");
  useEffect(() => { document.title = "Tuân thủ · Làm giàu theo MST"; }, []);
  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;
  const canManage = meta.caps.includes("compliance.manage");
  const tabs: [Tab, string][] = [
    ["subjects", "Yêu cầu của chủ thể dữ liệu"],
    ["optouts", "Danh sách từ chối"],
    ["retention", "Rà soát thời hạn lưu"],
    ["exports", "Nhật ký xuất"],
    ["access", "Nhật ký truy cập kho B"],
    ["dpia", "Báo cáo đánh giá tác động"],
  ];
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Tuân thủ bảo vệ dữ liệu cá nhân</h1>
          <p>Công cụ thực hiện yêu cầu theo Luật Bảo vệ dữ liệu cá nhân — diễn giải pháp lý (khi nào phải xoá, thời hạn trả lời…) cần pháp chế quyết định.</p>
        </div>
      </div>
      <EnrichNav caps={meta.caps} />
      {flash ? <div className="adm-alert ok" role="status" style={{ marginBottom: 16 }}>{flash}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs" role="tablist">
          {tabs.filter(([k]) => k !== "subjects" || canManage).map(([k, v]) => <button key={k} role="tab" className={tab === k ? "on" : undefined} onClick={() => { setTab(k); setFlash(""); }}>{v}</button>)}
        </div>
        <div className="bd">
          {tab === "subjects" && canManage ? <Subjects onFlash={setFlash} /> : null}
          {tab === "optouts" ? <OptOuts canManage={canManage} /> : null}
          {tab === "retention" ? <Retention /> : null}
          {tab === "exports" ? <Exports /> : null}
          {tab === "access" ? <Access /> : null}
          {tab === "dpia" ? <Dpia purposes={meta.purposes} /> : null}
        </div>
      </section>
    </>
  );
}

function Subjects({ onFlash }: { onFlash: (m: string) => void }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Subject[] | null>(null);
  const [msg, setMsg] = useState("");
  const [report, setReport] = useState<Json | null>(null);
  const [erase, setErase] = useState<Subject | null>(null);

  async function find(e?: FormEvent) {
    e?.preventDefault();
    setMsg("");
    try { setRows(await api.get<Subject[]>(`/enrich/compliance/subjects?q=${encodeURIComponent(q)}`)); } catch (err) { setMsg(errMsg(err)); setRows(null); }
  }

  return (
    <>
      <form onSubmit={find} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input className="adm-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Họ tên, email hoặc MST cá nhân của người yêu cầu" aria-label="Tìm chủ thể dữ liệu" />
        <button className="adm-btn primary" type="submit"><Icon name="search" size={14} /> Tìm</button>
      </form>
      {msg ? <div className="adm-alert" style={{ marginBottom: 12 }}>{msg}</div> : null}
      {rows === null ? <p className="er-note"><Icon name="note" /><span>Tìm người yêu cầu → “Dữ liệu đang lưu” để trả lời yêu cầu truy cập (tải file JSON gửi cho họ), hoặc “Ẩn / Xoá” để thực hiện yêu cầu xoá. Mọi thao tác ghi nhật ký.</span></p> : !rows.length ? <div className="adm-empty">Không tìm thấy ai.</div> : (
        <table className="adm-table">
          <thead><tr><th>Người</th><th>Vai trò</th><th /></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><Link className="name" href={`/admin/lam-giau/nguoi/${r.id}`}>{r.ho_ten}</Link> <span className="muted mono">#{r.id}</span></td>
                <td>{r.roles.map((x, i) => <div key={i} className="sub">{x.chuc_danh} — <span className="mono">{x.company_mst}</span></div>)}</td>
                <td>
                  <div className="adm-actions">
                    <button className="adm-btn sm" onClick={async () => { try { setReport(await api.get(`/enrich/compliance/subjects/${r.id}/report`)); } catch (e) { setMsg(errMsg(e)); } }}>Dữ liệu đang lưu</button>
                    <button className="adm-btn sm danger" onClick={() => setErase(r)}>Ẩn / Xoá</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Dialog open={report !== null} title={report ? `Dữ liệu đang lưu về ${report.nguoi.ho_ten}` : ""} onClose={() => setReport(null)} wide>
        {report ? (
          <>
            <p style={{ fontSize: 13.5, marginBottom: 8 }}><b>{report.vai_tro.length}</b> vai trò · <b>{report.lien_he.length}</b> liên hệ · <b>{report.nguon_goc.length}</b> bằng chứng nguồn gốc · mục đích xử lý: {report.muc_dich_xu_ly.join(", ") || "—"}</p>
            <table className="adm-table" style={{ marginBottom: 10 }}>
              <thead><tr><th>Trường</th><th>Giá trị</th><th>Nguồn</th><th>Thu thập lúc</th></tr></thead>
              <tbody>{report.nguon_goc.map((e: Json, i: number) => <tr key={i}><td>{e.truong}</td><td>{e.gia_tri}{e.suy_luan ? " (suy luận)" : ""}</td><td>{e.nguon}<div className="sub" style={{ wordBreak: "break-all" }}>{e.duong_dan}</div></td><td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.thu_thap_luc)}</td></tr>)}</tbody>
            </table>
            <div className="adm-actions">
              <a className="adm-btn" href={`/api/admin/enrich/compliance/subjects/${report.nguoi.ma_ho_so}/report?download=true`}><Icon name="download" size={14} /> Tải file trả lời (JSON)</a>
              <button className="adm-btn primary" onClick={() => setReport(null)}>Đóng</button>
            </div>
          </>
        ) : null}
      </Dialog>
      <EraseDialog subject={erase} onClose={() => setErase(null)} onDone={(m) => { setErase(null); onFlash(m); find(); }} />
    </>
  );
}

function EraseDialog({ subject, onClose, onDone }: { subject: Subject | null; onClose: () => void; onDone: (m: string) => void }) {
  const [msg, setMsg] = useState("");
  useEffect(() => setMsg(""), [subject]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!subject) return;
    const f = new FormData(e.currentTarget);
    const mode = String(f.get("mode"));
    if (mode === "delete" && !confirm(`XOÁ dữ liệu của ${subject.ho_ten}? Không hoàn tác được.`)) return;
    try {
      const r = await api.post<Json>(`/enrich/compliance/subjects/${subject.id}/erase`, { mode, reason: f.get("reason") });
      onDone(mode === "delete" ? `Đã xoá dữ liệu của ${subject.ho_ten} (${r.roles} vai trò, ${r.contacts} liên hệ) và chặn thu thập lại.` : `Đã ẩn vĩnh viễn ${subject.ho_ten} khỏi mọi kết quả và bản xuất.`);
    } catch (err) { setMsg(errMsg(err)); }
  }
  return (
    <Dialog open={subject !== null} title={subject ? `Yêu cầu xoá — ${subject.ho_ten}` : ""} onClose={onClose}>
      {subject ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <div className="full" style={{ display: "grid", gap: 8, fontSize: 13.5 }}>
            <label style={{ display: "flex", gap: 8 }}><input type="radio" name="mode" value="hide" defaultChecked /> <span><b>Ẩn vĩnh viễn</b> — giữ dữ liệu nhưng không hiện trong kết quả, bản xuất; email / điện thoại vào danh sách từ chối.</span></label>
            <label style={{ display: "flex", gap: 8 }}><input type="radio" name="mode" value="delete" /> <span><b>Xoá</b> — xoá vai trò, liên hệ, bằng chứng; chặn thu thập lại (lưu khoá băm, không lưu tên). Bản gốc trang nguồn giữ tới hết thời hạn lưu bản gốc.</span></label>
          </div>
          <Field label="Lý do / số yêu cầu của chủ thể" full htmlFor="er-reason"><input id="er-reason" className="adm-input" name="reason" maxLength={2000} placeholder="VD: YC-2026-015, email ngày 18/11/2026" /></Field>
          <div className="adm-actions full"><button type="button" className="adm-btn" onClick={onClose}>Huỷ</button><button type="submit" className="adm-btn danger">Thực hiện</button></div>
        </form>
      ) : null}
    </Dialog>
  );
}

function OptOuts({ canManage }: { canManage: boolean }) {
  const [d, setD] = useState<{ kinds: Record<string, string>; items: { id: number; kind: string; value: string; day: string; reason: string }[] } | null>(null);
  const [msg, setMsg] = useState("");
  const load = useCallback(() => { api.get<typeof d>("/enrich/compliance/optouts").then(setD, (e) => setMsg(errMsg(e))); }, []);
  useEffect(() => { load(); }, [load]);
  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setMsg("");
    try { await api.post("/enrich/compliance/optouts", { kind: f.get("kind"), value: f.get("value"), reason: f.get("reason") }); (e.target as HTMLFormElement).reset(); load(); } catch (err) { setMsg(errMsg(err)); }
  }
  return (
    <>
      <p className="er-note" style={{ marginBottom: 12 }}><Icon name="note" /><span>Email, điện thoại hoặc người trong danh sách bị ẩn khỏi mọi kết quả và bản xuất ngay khi thêm, và không bị ghi lại khi thu thập.</span></p>
      {canManage ? (
        <form onSubmit={add} style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          <select className="adm-input" name="kind" style={{ width: 170 }} aria-label="Loại">{Object.entries(d?.kinds ?? { email: "Email", phone: "Điện thoại", person: "Người" }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <input className="adm-input" name="value" style={{ width: 240 }} placeholder="Giá trị" aria-label="Giá trị" />
          <input className="adm-input" name="reason" style={{ flex: 1, minWidth: 200 }} placeholder="Lý do / nguồn yêu cầu" aria-label="Lý do" />
          <button className="adm-btn primary" type="submit">Thêm</button>
        </form>
      ) : null}
      {msg ? <div className="adm-alert" style={{ marginBottom: 12 }}>{msg}</div> : null}
      {!d ? <Skeleton h={120} /> : !d.items.length ? <div className="adm-empty">Danh sách trống.</div> : (
        <table className="adm-table">
          <thead><tr><th>Loại</th><th>Giá trị</th><th>Ngày</th><th>Lý do</th></tr></thead>
          <tbody>{d.items.map((o) => <tr key={o.id}><td>{d.kinds[o.kind] ?? o.kind}</td><td className="mono">{o.kind === "person" ? <Link href={`/admin/lam-giau/nguoi/${o.value}`}>#{o.value}</Link> : o.value}</td><td>{fmtDate(o.day)}</td><td>{o.reason}</td></tr>)}</tbody>
        </table>
      )}
    </>
  );
}

function Retention() {
  const [d, setD] = useState<{ months: number; items: { id: number; ho_ten: string; created_at: string; last_used_at: string | null }[] } | null>(null);
  useEffect(() => { api.get<typeof d>("/enrich/compliance/retention").then(setD, () => {}); }, []);
  if (!d) return <Skeleton h={120} />;
  return (
    <>
      <p className="er-note" style={{ marginBottom: 12 }}><Icon name="note" /><span>Hồ sơ người không được xem hay xuất trong {d.months} tháng — rà soát rồi xoá ở tab “Yêu cầu của chủ thể dữ liệu” nếu không còn mục đích xử lý.</span></p>
      {!d.items.length ? <div className="adm-empty">Không có hồ sơ quá hạn.</div> : (
        <table className="adm-table">
          <thead><tr><th>Người</th><th>Tạo lúc</th><th>Dùng lần cuối</th></tr></thead>
          <tbody>{d.items.map((p) => <tr key={p.id}><td><Link className="name" href={`/admin/lam-giau/nguoi/${p.id}`}>{p.ho_ten}</Link></td><td>{fmtDate(p.created_at)}</td><td>{p.last_used_at ? fmtDate(p.last_used_at) : "Chưa từng"}</td></tr>)}</tbody>
        </table>
      )}
    </>
  );
}

function Exports() {
  const [rows, setRows] = useState<ExportLogRow[] | null>(null);
  useEffect(() => { api.get<ExportLogRow[]>("/enrich/compliance/exports").then(setRows, () => {}); }, []);
  if (!rows) return <Skeleton h={120} />;
  if (!rows.length) return <div className="adm-empty">Chưa có lần xuất nào.</div>;
  return (
    <div className="adm-table-wrap">
      <table className="adm-table">
        <thead><tr><th>#</th><th>Người xuất</th><th>Mục đích</th><th style={{ textAlign: "right" }}>Dòng</th><th>Cột</th><th>Trạng thái</th><th>Hạn file</th><th>Lúc</th></tr></thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.id}>
              <td className="mono">{e.id}</td>
              <td>{e.user}</td>
              <td>{e.purpose}</td>
              <td style={{ textAlign: "right" }}>{fmtNum(e.row_count)}{e.blocked_count ? <div className="sub">{fmtNum(e.blocked_count)} bị chặn</div> : null}{e.optout_count ? <div className="sub">{fmtNum(e.optout_count)} từ chối</div> : null}</td>
              <td><div className="sub" style={{ maxWidth: 260 }}>{e.columns.join(", ")}</div>{e.includes_kho_b ? <span className="adm-badge warn">Có dữ liệu cá nhân</span> : null}{e.include_inferred ? <span className="adm-badge plain role" style={{ marginLeft: 4 }}>Kèm suy luận</span> : null}</td>
              <td>{e.status === "ok" ? <span className="adm-badge s-active">Đã xuất</span> : <span className="adm-badge s-rejected">Bị chặn</span>}</td>
              <td>{e.expires_on ? fmtDate(e.expires_on) : "—"}</td>
              <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ACTIONS: Record<string, string> = { read: "Xem", list: "Tìm / liệt kê", export: "Xuất", edit: "Sửa", write: "Ghi (thu thập)", delete: "Xoá" };

function Access() {
  const [action, setAction] = useState("");
  const [rows, setRows] = useState<AccessLogRow[] | null>(null);
  useEffect(() => { setRows(null); api.get<AccessLogRow[]>(`/enrich/compliance/access-logs${action ? `?action=${action}` : ""}`).then(setRows, () => {}); }, [action]);
  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <select className="adm-input" style={{ width: "auto" }} value={action} onChange={(e) => setAction(e.target.value)} aria-label="Lọc hành động">
          <option value="">Mọi hành động</option>
          {Object.entries(ACTIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <span className="er-note"><Icon name="lock" /><span>Nhật ký chỉ ghi thêm — cơ sở dữ liệu chặn sửa / xoá. 200 dòng gần nhất.</span></span>
      </div>
      {!rows ? <Skeleton h={160} /> : !rows.length ? <div className="adm-empty">Chưa có.</div> : (
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead><tr><th>Lúc</th><th>Người dùng</th><th>Hành động</th><th>Đối tượng</th><th style={{ textAlign: "right" }}>Dòng</th><th>IP</th></tr></thead>
            <tbody>{rows.map((a) => <tr key={a.id}><td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(a.at)}</td><td>{a.user}</td><td>{ACTIONS[a.action] ?? a.action}</td><td className="mono" style={{ wordBreak: "break-all" }}>{a.target}</td><td style={{ textAlign: "right" }}>{a.row_count}</td><td className="mono">{a.ip || "—"}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Dpia({ purposes }: { purposes: Record<string, string> }) {
  const [d, setD] = useState<Json | null>(null);
  useEffect(() => { api.get("/enrich/compliance/dpia").then(setD, () => {}); }, []);
  if (!d) return <Skeleton h={200} />;
  const n = d.loai_du_lieu.so_luong;
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="adm-actions" style={{ justifyContent: "space-between" }}>
        <span className="muted" style={{ fontSize: 13 }}>Lập lúc {fmtDateTime(d.lap_luc)} — đầu vào cho hồ sơ đánh giá tác động xử lý dữ liệu cá nhân (pháp chế hoàn thiện).</span>
        <a className="adm-btn" href="/api/admin/enrich/compliance/dpia?download=true"><Icon name="download" size={14} /> Tải JSON</a>
      </div>
      <div className="er-two">
        <div>
          <h3 style={{ fontSize: 14, marginBottom: 6 }}>Loại dữ liệu cá nhân</h3>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>{d.loai_du_lieu.kho_b_truong.map((x: string) => <li key={x}>{x}</li>)}</ul>
          <p className="sub" style={{ marginTop: 6 }}>Không thu thập: {d.loai_du_lieu.khong_thu_thap.join(", ")}.</p>
          <p style={{ fontSize: 13.5, marginTop: 6 }}>{fmtNum(n.nguoi)} người · {fmtNum(n.co_mst_ca_nhan)} có MST cá nhân · {fmtNum(n.email_thu_thap)} email thu thập · {fmtNum(n.email_suy_luan)} email suy luận · {fmtNum(n.tu_choi)} mục từ chối</p>
        </div>
        <div>
          <h3 style={{ fontSize: 14, marginBottom: 6 }}>Thời hạn & bảo vệ</h3>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>
            <li>Dữ liệu cá nhân không dùng quá {d.thoi_han.du_lieu_ca_nhan_khong_dung_thang} tháng → rà soát xoá</li>
            <li>Bản gốc giữ {d.thoi_han.ban_goc_ngay} ngày; file xuất có hạn {d.thoi_han.han_file_xuat_ngay} ngày</li>
            <li>Nhật ký truy cập: {d.thoi_han.nhat_ky_truy_cap}</li>
            <li>MST cá nhân + bản gốc mã hoá khi lưu{d.bao_ve.khoa_rieng_da_dat ? "" : " — ⚠ chưa đặt khoá riêng (LEADSCAN_ENRICH_DATA_KEY)"}</li>
            <li>Mô hình ngôn ngữ bên ngoài: {d.bao_ve.mo_hinh_ngon_ngu_ngoai ? "ĐANG BẬT" : "tắt"}</li>
          </ul>
        </div>
      </div>
      <div>
        <h3 style={{ fontSize: 14, marginBottom: 6 }}>Nguồn và cơ sở pháp lý</h3>
        <table className="adm-table"><thead><tr><th>Nguồn</th><th>Bật</th><th>Cơ sở pháp lý</th><th style={{ textAlign: "right" }}>Bằng chứng về người</th></tr></thead>
          <tbody>{d.nguon.map((s: Json) => <tr key={s.ma}><td>{s.ten}</td><td>{s.dang_bat ? "✓" : "—"}</td><td style={{ fontSize: 12.5 }}>{s.co_so_phap_ly || <span style={{ color: "var(--danger)" }}>Chưa khai</span>}</td><td style={{ textAlign: "right" }}>{fmtNum(s.so_bang_chung_nguoi)}</td></tr>)}</tbody></table>
      </div>
      <div className="er-two">
        <div>
          <h3 style={{ fontSize: 14, marginBottom: 6 }}>Mục đích (số lô)</h3>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>{d.muc_dich.map((m: Json) => <li key={m.ma}>{purposes[m.ma] ?? m.ten}: {m.so_lo} lô</li>)}</ul>
        </div>
        <div>
          <h3 style={{ fontSize: 14, marginBottom: 6 }}>Ai được truy cập</h3>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>{d.nguoi_duoc_cap_quyen.map((u: Json, i: number) => <li key={i}>{u.ho_ten} — {u.vai_tro}</li>)}</ul>
        </div>
      </div>
      <div>
        <h3 style={{ fontSize: 14, marginBottom: 6 }}>Truy cập kho B 12 tháng qua</h3>
        <table className="adm-table"><thead><tr><th>Người dùng</th><th>Vai trò</th><th>Hành động</th><th style={{ textAlign: "right" }}>Số lần</th><th style={{ textAlign: "right" }}>Số dòng</th></tr></thead>
          <tbody>{d.truy_cap_12_thang.map((a: Json, i: number) => <tr key={i}><td>{a.nguoi_dung}</td><td>{a.vai_tro}</td><td>{ACTIONS[a.hanh_dong] ?? a.hanh_dong}</td><td style={{ textAlign: "right" }}>{fmtNum(a.so_lan)}</td><td style={{ textAlign: "right" }}>{fmtNum(a.so_dong)}</td></tr>)}</tbody></table>
      </div>
    </div>
  );
}
