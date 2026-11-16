"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg, qs } from "@/lib/admin/api";
import { type Candidate, type CandidateSide, fileToBase64, MAX_FILE_MB, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtNum } from "@/lib/admin/format";

interface PersonRow {
  id: number;
  ho_ten: string;
  nam_sinh?: number | null;
  mst_ca_nhan?: string | null;
}

type Tab = "search" | "candidates";

function Side({ s }: { s: CandidateSide }) {
  return (
    <div>
      <Link className="name" href={`/admin/lam-giau/nguoi/${s.id}`}>{s.ho_ten}</Link> <span className="muted mono">#{s.id}</span>
      {s.nam_sinh ? <span className="muted"> · sinh {s.nam_sinh}</span> : null}
      {s.mst_ca_nhan ? <span className="muted mono"> · MST CN {s.mst_ca_nhan}</span> : null}
      {s.roles.map((r, i) => (
        <div key={i} className="sub">{r.chuc_danh} — {r.company_ten ?? r.company_mst}{r.den_ngay ? " (đã thôi)" : ""}</div>
      ))}
    </div>
  );
}

export default function PeoplePage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [tab, setTab] = useState<Tab>("candidates");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [list, setList] = useState<{ total: number; items: PersonRow[] } | null>(null);
  const [cands, setCands] = useState<Candidate[] | null>(null);
  const [dialog, setDialog] = useState<"" | "import">("");
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadCands = useCallback(() => {
    api.get<Candidate[]>("/enrich/merge-candidates").then(setCands, (e) => setError(errMsg(e)));
  }, []);

  useEffect(() => {
    document.title = "Người & quan hệ · Làm giàu theo MST";
    loadCands();
  }, [loadCands]);
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => {
    if (tab !== "search") return;
    setList(null);
    api.get<{ total: number; items: PersonRow[] }>("/enrich/persons" + qs({ q, page_size: 50 })).then(setList, (e) => setError(errMsg(e)));
  }, [q, tab]);

  async function decide(c: Candidate, action: "merge" | "reject", keep: "a" | "b" = "a") {
    if (action === "merge" && !confirm(`Gộp “${(keep === "a" ? c.b : c.a).ho_ten}” #${(keep === "a" ? c.b : c.a).id} vào #${(keep === "a" ? c.a : c.b).id}? Có thể hoàn tác ở hồ sơ người.`)) return;
    try {
      await api.post(`/enrich/merge-candidates/${c.id}`, { action, keep });
      setFlash(action === "merge" ? "Đã gộp hai hồ sơ." : "Đã đánh dấu là hai người khác nhau.");
      loadCands();
    } catch (e) { alert(errMsg(e)); }
  }

  async function inferEmails() {
    if (!confirm("Suy luận email cho người ra quyết định ở mọi doanh nghiệp có tên miền? Chỉ chạy với tên miền đã có email thật và có bản ghi MX.")) return;
    setBusy(true);
    try {
      const r = await api.post<{ companies: number; created: number; skipped: Record<string, number> }>("/enrich/emails/infer", {});
      const why = Object.entries(r.skipped).map(([k, v]) => `${v}: ${k}`).join("; ");
      setFlash(`Đã xét ${fmtNum(r.companies)} doanh nghiệp, tạo ${fmtNum(r.created)} email suy luận (gắn cờ suy luận, đã xác minh MX).${why ? ` Bỏ qua — ${why}.` : ""}`);
    } catch (e) { setError(errMsg(e)); } finally { setBusy(false); }
  }

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;
  const canManage = meta.caps.includes("people.manage");

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Người & quan hệ</h1>
          <p>Hồ sơ người ra quyết định (kho B). Hai hồ sơ cùng tên chỉ tự gộp khi MST cá nhân chứng minh là một người; còn lại nằm ở “Nghi trùng” chờ biên tập viên quyết.</p>
        </div>
        {canManage ? (
          <div className="adm-actions">
            <button className="adm-btn" onClick={inferEmails} disabled={busy}><Icon name="mail" size={16} /> {busy ? "Đang suy luận…" : "Suy luận email"}</button>
            <button className="adm-btn primary" onClick={() => setDialog("import")}><Icon name="plus" size={16} /> Nhập MST cá nhân</button>
          </div>
        ) : null}
      </div>
      <EnrichNav caps={meta.caps} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {flash ? <div className="adm-alert ok" role="status" style={{ marginBottom: 16 }}>{flash}</div> : null}
      <p className="er-note" style={{ marginBottom: 12 }}><Icon name="lock" /><span>Dữ liệu cá nhân — mỗi lần tìm kiếm, mở hồ sơ hay xuất đều được ghi vào nhật ký truy cập.</span></p>

      <section className="adm-card">
        <div className="adm-tabs" role="tablist">
          <button role="tab" className={tab === "candidates" ? "on" : undefined} onClick={() => setTab("candidates")}>Nghi trùng<span>{fmtNum(cands?.length ?? 0)}</span></button>
          <button role="tab" className={tab === "search" ? "on" : undefined} onClick={() => setTab("search")}>Tìm người</button>
        </div>
        {tab === "candidates" ? (
          !cands ? <Skeleton h={160} /> : !cands.length ? <div className="adm-empty">Không có cặp nghi trùng nào.</div> : (
            <div className="adm-table-wrap">
              <table className="adm-table">
                <thead><tr><th>Hồ sơ A</th><th>Hồ sơ B</th><th>Điểm khớp</th>{canManage ? <th /> : null}</tr></thead>
                <tbody>
                  {cands.map((c) => (
                    <tr key={c.id}>
                      <td><Side s={c.a} /></td>
                      <td><Side s={c.b} /></td>
                      <td style={{ whiteSpace: "nowrap" }}>{c.score.toFixed(2)}<div className="sub">{c.reasons.join(" · ")}</div></td>
                      {canManage ? (
                        <td>
                          <div className="adm-actions" style={{ flexDirection: "column", alignItems: "stretch" }}>
                            <button className="adm-btn sm" onClick={() => decide(c, "merge", "a")}>Gộp vào A</button>
                            <button className="adm-btn sm" onClick={() => decide(c, "merge", "b")}>Gộp vào B</button>
                            <button className="adm-btn sm ghost" onClick={() => decide(c, "reject")}>Hai người khác nhau</button>
                          </div>
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <>
            <div className="adm-toolbar">
              <div className="adm-search"><Icon name="search" /><input className="adm-input" type="search" placeholder="Tìm theo họ tên (không dấu) hoặc MST cá nhân…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm người" /></div>
            </div>
            {!list ? <Skeleton h={160} /> : !list.items.length ? <div className="adm-empty">Không tìm thấy ai.</div> : (
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead><tr><th>Họ tên</th>{list.items.some((p) => "nam_sinh" in p) ? <th>Năm sinh</th> : null}{list.items.some((p) => "mst_ca_nhan" in p) ? <th>MST cá nhân</th> : null}</tr></thead>
                  <tbody>
                    {list.items.map((p) => (
                      <tr key={p.id}>
                        <td><Link className="name" href={`/admin/lam-giau/nguoi/${p.id}`}>{p.ho_ten}</Link></td>
                        {"nam_sinh" in p ? <td>{p.nam_sinh ?? "—"}</td> : null}
                        {"mst_ca_nhan" in p ? <td className="mono">{p.mst_ca_nhan ?? "—"}</td> : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="adm-pager"><span>{fmtNum(list.total)} người</span></div>
              </div>
            )}
          </>
        )}
      </section>

      {canManage ? <ImportDialog open={dialog === "import"} onClose={() => setDialog("")} onDone={(m) => { setDialog(""); setFlash(m); loadCands(); }} /> : null}
    </>
  );
}

function ImportDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (msg: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setMsg(""); setFile(null); } }, [open]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (!file) return setMsg("Chọn file CSV hoặc Excel.");
    if (file.size > MAX_FILE_MB * 1024 * 1024) return setMsg(`File quá lớn (tối đa ${MAX_FILE_MB} MB).`);
    setBusy(true); setMsg("");
    try {
      const r = await api.post<{ rows: number; by_mst: number; by_company_name: number; created: number; auto_merged: number; skipped: { row: number; reason: string }[] }>("/enrich/persons/import-mst", {
        file_name: file.name, file_b64: await fileToBase64(file), source_note: f.get("source_note"), confirmed: f.get("confirmed") === "on",
      });
      onDone(`Đã nhập ${fmtNum(r.rows)} dòng: ${fmtNum(r.by_mst)} khớp theo MST cá nhân, ${fmtNum(r.by_company_name)} khớp theo tên + doanh nghiệp, ${fmtNum(r.created)} hồ sơ mới, ${fmtNum(r.auto_merged)} hồ sơ tự gộp nhờ MST cá nhân${r.skipped.length ? `, bỏ qua ${r.skipped.length} dòng (dòng ${r.skipped.slice(0, 5).map((s) => `${s.row}: ${s.reason}`).join("; ")})` : ""}.`);
    } catch (err) { setMsg(err instanceof ApiError ? err.message : errMsg(err)); } finally { setBusy(false); }
  }

  return (
    <Dialog open={open} title="Nhập MST cá nhân nội bộ" onClose={onClose} wide>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <p className="full" style={{ fontSize: 13.5 }}>Cột bắt buộc: <b>MST cá nhân</b>, <b>Họ và tên</b>, <b>MST doanh nghiệp</b> (tuỳ chọn: Chức danh). MST cá nhân chỉ dùng để khớp người, không bao giờ có trong bản xuất.</p>
          <Field label="Nguồn của danh sách" full htmlFor="i-src"><input id="i-src" className="adm-input" name="source_note" maxLength={500} placeholder="VD: hồ sơ khách hàng đã ký hợp đồng, phòng kinh doanh cung cấp 11/2026" /></Field>
          <Field label={`File (.csv, .xlsx ≤ ${MAX_FILE_MB} MB)`} full htmlFor="i-file"><input id="i-file" className="adm-input" type="file" accept=".csv,.xlsx,.xlsm,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <label className="full" style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13.5 }}>
            <input type="checkbox" name="confirmed" style={{ marginTop: 3 }} />
            <span>Tôi xác nhận đây là dữ liệu doanh nghiệp đang nắm giữ hợp pháp, <b>không mua từ bên thứ ba</b> (Luật Bảo vệ dữ liệu cá nhân cấm mua bán dữ liệu cá nhân).</span>
          </label>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang nhập…" : "Nhập"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}
