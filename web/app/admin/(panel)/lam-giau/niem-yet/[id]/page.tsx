"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg } from "@/lib/admin/api";
import { DOC_STATUS_CLASS, type DocDetail, type DocPerson, type DocsMeta, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDateTime } from "@/lib/admin/format";

const EMPTY: DocPerson = { ho_ten: "", chuc_danh: "", nhom: "bdh", tu_ngay: null, den_ngay: null };

export default function DocumentReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { meta, error: metaError } = useEnrichMeta();
  const [docsMeta, setDocsMeta] = useState<DocsMeta | null>(null);
  const [d, setD] = useState<DocDetail | null>(null);
  const [rows, setRows] = useState<DocPerson[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get<DocDetail>(`/enrich/documents/${id}`).then((x) => {
      setD(x);
      setRows((x.extracted.approved_people ?? x.extracted.people ?? []).map((p) => ({ ...p })));
    }, (e) => setError(errMsg(e)));
  }, [id]);

  useEffect(() => {
    api.get<DocsMeta>("/enrich/documents/meta").then(setDocsMeta, () => {});
    load();
  }, [load]);
  useEffect(() => { if (d) document.title = `Tài liệu #${d.id} · ${d.ma_ck ?? d.mst}`; }, [d]);

  function set(i: number, k: keyof DocPerson, v: string) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v || (k === "tu_ngay" || k === "den_ngay" ? null : "") } : r)));
  }

  async function act(action: "approve" | "reject") {
    if (action === "reject" && !confirm("Từ chối tài liệu này? Không có người nào được ghi vào kho.")) return;
    setBusy(true); setMsg("");
    try {
      await api.post(`/enrich/documents/${id}/review`, { action, people: rows.filter((r) => r.ho_ten.trim()) });
      router.push("/admin/lam-giau/niem-yet");
    } catch (e) { setMsg(e instanceof ApiError ? e.message : errMsg(e)); } finally { setBusy(false); }
  }

  async function reparse() {
    setBusy(true); setMsg("");
    try { await api.post(`/enrich/documents/${id}/reparse`); load(); } catch (e) { setMsg(errMsg(e)); } finally { setBusy(false); }
  }

  if (metaError || error) return <div className="adm-card adm-empty">{metaError || error}</div>;
  if (!meta || !docsMeta || !d) return <Skeleton h={400} />;
  const canManage = meta.caps.includes("docs.manage");
  const editable = canManage && (d.status === "needs_review" || d.status === "parsed");
  const ex = d.extracted;

  return (
    <>
      <EnrichNav caps={meta.caps} />
      <Link href="/admin/lam-giau/niem-yet" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Niêm yết & quản trị</Link>
      <div className="adm-head">
        <div style={{ minWidth: 0 }}>
          <h1><span className="mono">{d.ma_ck ?? ""}</span> {d.ten ?? d.mst}</h1>
          <p>
            {docsMeta.types[d.doc_type] ?? d.doc_type}{d.period ? ` · ${d.period}` : ""} · <span className={`adm-badge ${DOC_STATUS_CLASS[d.status] ?? ""}`}>{docsMeta.statuses[d.status] ?? d.status}</span>
            {d.method ? ` · ${meta.methods[d.method] ?? d.method}` : ""}
          </p>
          <p className="sub" style={{ wordBreak: "break-all", fontSize: 12.5 }}>
            Nguồn: {/^https?:/.test(d.source_url) ? <a href={d.source_url} target="_blank" rel="noopener noreferrer nofollow">{d.source_url}</a> : d.source_url}
            {d.reviewed_by ? ` · duyệt bởi ${d.reviewed_by} lúc ${fmtDateTime(d.reviewed_at)}` : ""}
          </p>
        </div>
        <div className="adm-actions">
          {d.file ? <a className="adm-btn" href={`/api/admin/enrich/documents/${d.id}/file`} target="_blank" rel="noopener"><Icon name="external" size={14} /> Xem bản gốc</a> : null}
          {canManage && d.file && editable ? <button className="adm-btn" onClick={reparse} disabled={busy}><Icon name="refresh" size={14} /> Bóc tách lại</button> : null}
        </div>
      </div>

      <p className="er-note" style={{ marginBottom: 12 }}><Icon name="lock" /><span>Dữ liệu cá nhân (kho B) — mỗi lần mở tài liệu hoặc bản gốc đều được ghi vào nhật ký truy cập. Bản gốc có thể chứa danh sách người nội bộ: chỉ xem khi cần đối chiếu.</span></p>
      {ex.notes?.length ? <div className="adm-alert warn" style={{ marginBottom: 12 }}>{ex.notes.map((n, i) => <div key={i}>{n}</div>)}</div> : null}
      {d.error ? <div className="adm-alert" style={{ marginBottom: 12 }}>{d.error}</div> : null}
      {msg ? <div className="adm-alert" style={{ marginBottom: 12 }}>{msg}</div> : null}

      <section className="adm-card">
        <div className="hd">
          <h2>Thành viên tìm được ({rows.length})</h2>
          <span className="muted" style={{ fontSize: 12.5 }}>{ex.has_board ? "HĐQT ✓" : "HĐQT ✗"} · {ex.has_exec ? "Ban điều hành ✓" : "Ban điều hành ✗"}</span>
        </div>
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead><tr><th>Họ tên</th><th>Chức danh</th><th>Nhóm</th><th>Bổ nhiệm</th><th>Miễn nhiệm</th><th>Trích từ tài liệu</th>{editable ? <th /> : null}</tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{editable ? <input className="adm-input" value={r.ho_ten} onChange={(e) => set(i, "ho_ten", e.target.value)} aria-label="Họ tên" /> : r.ho_ten}</td>
                  <td>{editable ? <input className="adm-input" value={r.chuc_danh} onChange={(e) => set(i, "chuc_danh", e.target.value)} aria-label="Chức danh" /> : r.chuc_danh}</td>
                  <td>
                    {editable ? (
                      <select className="adm-input" value={r.nhom} onChange={(e) => set(i, "nhom", e.target.value)} aria-label="Nhóm">
                        {Object.entries(docsMeta.groups).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                    ) : docsMeta.groups[r.nhom] ?? r.nhom}
                  </td>
                  <td>{editable ? <input className="adm-input" type="date" value={r.tu_ngay ?? ""} onChange={(e) => set(i, "tu_ngay", e.target.value)} aria-label="Ngày bổ nhiệm" /> : r.tu_ngay ?? "—"}</td>
                  <td>{editable ? <input className="adm-input" type="date" value={r.den_ngay ?? ""} onChange={(e) => set(i, "den_ngay", e.target.value)} aria-label="Ngày miễn nhiệm" /> : r.den_ngay ?? "—"}</td>
                  <td><div className="sub" style={{ maxWidth: 280, wordBreak: "break-word" }}>{r.nguon_trich || "—"}</div></td>
                  {editable ? <td><button className="adm-btn sm ghost" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))} aria-label="Bỏ dòng"><Icon name="trash" size={14} /></button></td> : null}
                </tr>
              ))}
              {!rows.length ? <tr><td colSpan={7} className="muted" style={{ textAlign: "center", padding: 20 }}>Chưa tìm được ai — đối chiếu bản gốc rồi thêm tay.</td></tr> : null}
            </tbody>
          </table>
        </div>
        {editable ? (
          <div className="bd adm-actions" style={{ justifyContent: "space-between" }}>
            <button className="adm-btn" onClick={() => setRows((rs) => [...rs, { ...EMPTY }])}><Icon name="plus" size={14} /> Thêm người</button>
            <div className="adm-actions">
              <button className="adm-btn danger" onClick={() => act("reject")} disabled={busy}>Từ chối</button>
              <button className="adm-btn primary" onClick={() => act("approve")} disabled={busy}>{busy ? "Đang ghi…" : "Duyệt & ghi vào kho"}</button>
            </div>
          </div>
        ) : null}
      </section>
      <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>Người bạn sửa hoặc thêm được ghi là quyết định của biên tập viên — các vòng thu thập sau không ghi đè.</p>
    </>
  );
}
