"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg, qs } from "@/lib/admin/api";
import { DOC_STATUS_CLASS, type DocRow, type DocsMeta, fileToBase64, type ListedRow, MAX_FILE_MB, pct, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";

type Tab = "companies" | "documents";

export default function ListedPage() {
  const router = useRouter();
  const { meta, error: metaError } = useEnrichMeta();
  const [docsMeta, setDocsMeta] = useState<DocsMeta | null>(null);
  const [tab, setTab] = useState<Tab>("companies");
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [q, setQ] = useState("");
  const [listed, setListed] = useState<{ total_listed: number; full_board: number; count: number; items: ListedRow[] } | null>(null);
  const [docStatus, setDocStatus] = useState("");
  const [docs, setDocs] = useState<{ total: number; counts: Record<string, number>; items: DocRow[] } | null>(null);
  const [dialog, setDialog] = useState<"" | "upload" | "urls">("");
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  const loadListed = useCallback(() => {
    api.get<typeof listed>("/enrich/listed" + qs({ q, only_missing: onlyMissing ? "true" : "" })).then(setListed, (e) => setError(errMsg(e)));
  }, [q, onlyMissing]);
  const loadDocs = useCallback(() => {
    api.get<typeof docs>("/enrich/documents" + qs({ status: docStatus })).then(setDocs, (e) => setError(errMsg(e)));
  }, [docStatus]);

  useEffect(() => {
    document.title = "Niêm yết & quản trị · Làm giàu theo MST";
    api.get<DocsMeta>("/enrich/documents/meta").then(setDocsMeta, () => {});
  }, []);
  useEffect(() => { loadListed(); }, [loadListed]);
  useEffect(() => { loadDocs(); }, [loadDocs]);

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta || !docsMeta) return <Skeleton h={400} />;
  const canManage = meta.caps.includes("docs.manage");
  const canOpen = meta.caps.includes("b.evidence");
  const reviewCount = docs?.counts.needs_review ?? 0;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Doanh nghiệp niêm yết & quản trị</h1>
          <p>Bóc tách thành viên HĐQT, Ban kiểm soát, Ban điều hành từ báo cáo tình hình quản trị / báo cáo thường niên. Phần danh sách người nội bộ, người có liên quan luôn bị cắt trước khi đọc.</p>
        </div>
        {canManage ? (
          <div className="adm-actions">
            <button className="adm-btn" onClick={() => setDialog("urls")}><Icon name="external" size={16} /> Khai đường dẫn</button>
            <button className="adm-btn primary" onClick={() => setDialog("upload")}><Icon name="plus" size={16} /> Tải tài liệu lên</button>
          </div>
        ) : null}
      </div>
      <EnrichNav caps={meta.caps} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {flash ? <div className="adm-alert ok" role="status" style={{ marginBottom: 16 }}>{flash}</div> : null}

      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        <div className="adm-card adm-stat"><small>Doanh nghiệp niêm yết</small><b>{fmtNum(listed?.total_listed ?? 0)}</b><span>có mã CK trong danh sách</span></div>
        <div className="adm-card adm-stat">
          <small>Đủ HĐQT + Ban điều hành</small>
          <b>{pct(listed?.full_board ?? 0, listed?.total_listed ?? 0)}</b>
          <span>Mục tiêu ≥ 90% · {fmtNum(listed?.full_board ?? 0)} DN</span>
          <span className="er-target" aria-hidden><i style={{ width: `${listed?.total_listed ? (listed.full_board / listed.total_listed) * 100 : 0}%` }} /><u style={{ left: "90%" }} /></span>
        </div>
        <div className="adm-card adm-stat"><small>Tài liệu</small><b>{fmtNum(Object.values(docs?.counts ?? {}).reduce((a, b) => a + b, 0))}</b><span>{fmtNum(docs?.counts.parsed ?? 0)} tự ghi · {fmtNum(docs?.counts.approved ?? 0)} đã duyệt</span></div>
        <button className="adm-card adm-stat" style={{ textAlign: "left", cursor: "pointer", border: reviewCount ? "1px solid #f3dca8" : undefined }} onClick={() => { setTab("documents"); setDocStatus("needs_review"); }}>
          <small>Chờ duyệt</small><b>{fmtNum(reviewCount)}</b><span>thiếu nhóm, mô hình ngôn ngữ, PDF ảnh</span>
        </button>
      </div>

      <section className="adm-card">
        <div className="adm-tabs" role="tablist">
          <button role="tab" className={tab === "companies" ? "on" : undefined} onClick={() => setTab("companies")}>Doanh nghiệp<span>{fmtNum(listed?.total_listed ?? 0)}</span></button>
          <button role="tab" className={tab === "documents" ? "on" : undefined} onClick={() => setTab("documents")}>Tài liệu<span>{fmtNum(docs?.total ?? 0)}</span></button>
        </div>

        {tab === "companies" ? (
          <>
            <div className="adm-toolbar">
              <div className="adm-search"><Icon name="search" /><input className="adm-input" type="search" placeholder="Tìm theo tên, mã CK, MST…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Tìm doanh nghiệp niêm yết" /></div>
              <label style={{ display: "inline-flex", gap: 6, alignItems: "center", fontSize: 13 }}><input type="checkbox" checked={onlyMissing} onChange={(e) => setOnlyMissing(e.target.checked)} /> Chỉ DN còn thiếu</label>
            </div>
            {!listed ? <Skeleton h={160} /> : !listed.items.length ? (
              <div className="adm-empty">{listed.total_listed ? "Không có doanh nghiệp nào khớp." : <>Chưa có doanh nghiệp niêm yết. Nhập “Danh sách niêm yết” ở trang <Link href="/admin/lam-giau/nhap-nguon" style={{ color: "var(--brand-600)" }}>Nhập nguồn chính thức</Link> để gắn mã CK cho MST.</>}</div>
            ) : (
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead><tr><th>Mã CK</th><th>Doanh nghiệp</th><th style={{ textAlign: "right" }}>HĐQT</th><th style={{ textAlign: "right" }}>Ban điều hành</th><th>Tình trạng</th><th style={{ textAlign: "right" }}>Tài liệu</th><th>Tài liệu gần nhất</th></tr></thead>
                  <tbody>
                    {listed.items.map((r) => (
                      <tr key={r.mst} className="link" onClick={() => router.push(`/admin/lam-giau/${r.mst}`)}>
                        <td><b className="mono">{r.ma_ck}</b></td>
                        <td><Link className="name" href={`/admin/lam-giau/${r.mst}`} onClick={(e) => e.stopPropagation()}>{r.ten || r.mst}</Link><div className="sub mono">{r.mst}</div></td>
                        <td style={{ textAlign: "right" }}>{r.board || <span className="muted">0</span>}</td>
                        <td style={{ textAlign: "right" }}>{r.exec || <span className="muted">0</span>}</td>
                        <td>{r.full ? <span className="adm-badge s-active">Đủ</span> : <span className="adm-badge warn">Thiếu {!r.board ? "HĐQT" : ""}{!r.board && !r.exec ? " + " : ""}{!r.exec ? "BĐH" : ""}</span>}{r.needs_review ? <div className="sub">{r.needs_review} tài liệu chờ duyệt</div> : null}</td>
                        <td style={{ textAlign: "right" }}>{r.documents}</td>
                        <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(r.last_document_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="adm-toolbar">
              <select className="adm-input" style={{ width: "auto" }} value={docStatus} onChange={(e) => setDocStatus(e.target.value)} aria-label="Lọc theo trạng thái">
                <option value="">Mọi trạng thái</option>
                {Object.entries(docsMeta.statuses).map(([k, v]) => <option key={k} value={k}>{v} ({fmtNum(docs?.counts[k] ?? 0)})</option>)}
              </select>
            </div>
            {!docs ? <Skeleton h={160} /> : !docs.items.length ? <div className="adm-empty">Chưa có tài liệu nào{docStatus ? " ở trạng thái này" : ""}.</div> : (
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead><tr><th>Doanh nghiệp</th><th>Tài liệu</th><th>Trạng thái</th><th style={{ textAlign: "right" }}>Người tìm được</th><th>Cách bóc tách</th><th>Thời điểm</th></tr></thead>
                  <tbody>
                    {docs.items.map((d) => (
                      <tr key={d.id} className={canOpen ? "link" : undefined} onClick={canOpen ? () => router.push(`/admin/lam-giau/niem-yet/${d.id}`) : undefined}>
                        <td><b className="mono">{d.ma_ck ?? "—"}</b> {d.ten ?? d.mst}</td>
                        <td>
                          {docsMeta.types[d.doc_type] ?? d.doc_type}{d.period ? ` · ${d.period}` : ""}
                          <div className="sub" style={{ maxWidth: 320, wordBreak: "break-all" }}>{d.source_url}</div>
                        </td>
                        <td>
                          <span className={`adm-badge ${DOC_STATUS_CLASS[d.status] ?? ""}`}>{docsMeta.statuses[d.status] ?? d.status}</span>
                          {d.error ? <div className="sub" style={{ color: "var(--danger)", maxWidth: 240 }}>{d.error}</div> : null}
                        </td>
                        <td style={{ textAlign: "right" }}>{d.people_count}<div className="sub">{d.has_board ? "HĐQT ✓" : "HĐQT ✗"} · {d.has_exec ? "BĐH ✓" : "BĐH ✗"}</div></td>
                        <td>{meta.methods[d.method] ?? (d.method || "—")}</td>
                        <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(d.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      {canManage ? (
        <>
          <UploadDialog open={dialog === "upload"} types={docsMeta.types} onClose={() => setDialog("")} onDone={(id, status) => {
            setDialog("");
            setFlash(status === "parsed" ? "Đã bóc tách và ghi vào kho (đủ HĐQT + Ban điều hành)." : "Đã tải lên — tài liệu cần duyệt trước khi ghi vào kho.");
            loadListed(); loadDocs();
            if (status !== "parsed" && canOpen) router.push(`/admin/lam-giau/niem-yet/${id}`);
          }} />
          <UrlsDialog open={dialog === "urls"} types={docsMeta.types} onClose={() => setDialog("")} onDone={(msg) => { setDialog(""); setFlash(msg); setTab("documents"); setDocStatus(""); loadDocs(); }} />
        </>
      ) : null}
    </>
  );
}

function UploadDialog({ open, types, onClose, onDone }: { open: boolean; types: Record<string, string>; onClose: () => void; onDone: (id: number, status: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setMsg(""); setFile(null); } }, [open]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (!file) return setMsg("Chọn file tài liệu.");
    if (file.size > MAX_FILE_MB * 1024 * 1024) return setMsg(`File quá lớn (tối đa ${MAX_FILE_MB} MB).`);
    setBusy(true); setMsg("");
    try {
      const r = await api.post<{ id: number; status: string }>("/enrich/documents/upload", {
        ref: f.get("ref"), doc_type: f.get("doc_type"), period: f.get("period"), source_url: f.get("source_url"),
        file_name: file.name, file_b64: await fileToBase64(file),
      });
      onDone(r.id, r.status);
    } catch (err) { setMsg(err instanceof ApiError ? err.message : errMsg(err)); } finally { setBusy(false); }
  }

  return (
    <Dialog open={open} title="Tải tài liệu công bố thông tin" onClose={onClose} wide>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Mã CK hoặc MST" htmlFor="u-ref"><input id="u-ref" className="adm-input" name="ref" maxLength={20} placeholder="VD: VNM hoặc 0300588569" autoFocus /></Field>
          <Field label="Loại tài liệu" htmlFor="u-type">
            <select id="u-type" className="adm-input" name="doc_type" defaultValue="bao_cao_quan_tri">{Object.entries(types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </Field>
          <Field label="Kỳ báo cáo (tuỳ chọn)" htmlFor="u-period"><input id="u-period" className="adm-input" name="period" maxLength={40} placeholder="VD: 6 tháng đầu năm 2026" /></Field>
          <Field label="Đường dẫn công bố gốc (nên ghi)" htmlFor="u-src"><input id="u-src" className="adm-input" name="source_url" maxLength={1000} placeholder="https://…" /></Field>
          <Field label={`File (.pdf, .html, .txt ≤ ${MAX_FILE_MB} MB)`} full htmlFor="u-file">
            <input id="u-file" className="adm-input" type="file" accept=".pdf,.html,.htm,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Field>
          <p className="muted full" style={{ fontSize: 12.5 }}>Hệ thống đọc bảng thành viên trước, rồi tới các dòng “Ông/Bà … – chức danh”. Đủ cả HĐQT và Ban điều hành thì ghi luôn; thiếu thì chuyển sang hàng chờ duyệt.</p>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang bóc tách…" : "Tải lên & bóc tách"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}

function UrlsDialog({ open, types, onClose, onDone }: { open: boolean; types: Record<string, string>; onClose: () => void; onDone: (msg: string) => void }) {
  const [msg, setMsg] = useState("");
  const [skipped, setSkipped] = useState<{ line: number; value: string; reason: string }[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setMsg(""); setSkipped([]); } }, [open]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setMsg(""); setSkipped([]);
    try {
      const r = await api.post<{ created: number; skipped: { line: number; value: string; reason: string }[] }>("/enrich/documents/urls", { text: f.get("text"), doc_type: f.get("doc_type") });
      if (r.skipped.length && !r.created) { setSkipped(r.skipped); setMsg("Không dòng nào hợp lệ."); return; }
      onDone(`Đã xếp ${fmtNum(r.created)} tài liệu vào hàng chờ tải${r.skipped.length ? `, bỏ qua ${r.skipped.length} dòng` : ""}. Hệ thống tải lần lượt, tôn trọng giới hạn tốc độ và robots.txt.`);
    } catch (err) { setMsg(err instanceof ApiError ? err.message : errMsg(err)); } finally { setBusy(false); }
  }

  return (
    <Dialog open={open} title="Khai đường dẫn tài liệu" onClose={onClose} wide>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Loại tài liệu" htmlFor="l-type">
            <select id="l-type" className="adm-input" name="doc_type" defaultValue="bao_cao_quan_tri">{Object.entries(types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </Field>
          <Field label="Mỗi dòng: mã CK hoặc MST, đường dẫn, kỳ (tuỳ chọn) — cách nhau bằng dấu phẩy" full htmlFor="l-text">
            <textarea id="l-text" className="adm-input mono" name="text" rows={8} placeholder={"VNM, https://www.vinamilk.com.vn/.../bao-cao-quan-tri-6t-2026.pdf, 6T/2026\nFPT, https://fpt.com/.../BCQT_2026.pdf"} />
          </Field>
          {skipped.length ? (
            <div className="full adm-table-wrap" style={{ maxHeight: 180, overflow: "auto" }}>
              <table className="adm-table"><thead><tr><th>Dòng</th><th>Giá trị</th><th>Lý do</th></tr></thead>
                <tbody>{skipped.map((s) => <tr key={s.line}><td>{s.line}</td><td className="mono">{s.value}</td><td>{s.reason}</td></tr>)}</tbody></table>
            </div>
          ) : null}
          <p className="muted full" style={{ fontSize: 12.5 }}>Chỉ tải đúng các đường dẫn khai ở đây (không tự dò cả trang công bố thông tin). Đường dẫn bị robots.txt chặn sẽ báo lỗi, không tải.</p>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang xếp hàng…" : "Xếp vào hàng chờ tải"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}
