"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg } from "@/lib/admin/api";
import { fileToBase64, MAX_FILE_MB, type OfficialImport, type OfficialReport, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDate, fmtDateTime, fmtNum } from "@/lib/admin/format";

const HELP: Record<string, { src: string; cols: string }> = {
  dkkd_mua: {
    src: "Số hợp đồng / văn bản mua dữ liệu từ Cổng thông tin quốc gia về đăng ký doanh nghiệp",
    cols: "Mã số doanh nghiệp, Tên doanh nghiệp (bắt buộc) · Địa chỉ trụ sở, Tình trạng hoạt động, Ngành nghề kinh doanh chính, Ngày thành lập, Vốn điều lệ, Người đại diện theo pháp luật",
  },
  no_thue: {
    src: "Đường dẫn trang cơ quan thuế công khai danh sách nợ thuế",
    cols: "Mã số thuế, Tổng số tiền thuế nợ (bắt buộc) · Tên người nộp thuế, Cơ quan thuế quản lý, Nợ đến ngày",
  },
  dau_thau: {
    src: "Đường dẫn thông báo kết quả trên Hệ thống mạng đấu thầu quốc gia",
    cols: "Mã số thuế nhà thầu, Tên gói thầu (bắt buộc) · Số TBMT, Bên mời thầu, Giá trúng thầu, Ngày phê duyệt",
  },
};

export default function OfficialImportPage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [data, setData] = useState<{ kinds: Record<string, string>; items: OfficialImport[] } | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState<OfficialImport | null>(null);
  const [open, setOpen] = useState<OfficialImport | null>(null);

  const load = useCallback(() => {
    api.get<{ kinds: Record<string, string>; items: OfficialImport[] }>("/enrich/imports").then(setData, (e) => setError(errMsg(e)));
  }, []);
  useEffect(() => {
    document.title = "Nhập nguồn chính thức · Làm giàu theo MST";
    load();
  }, [load]);

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Nhập nguồn chính thức</h1>
          <p>Dữ liệu mua từ Cổng ĐKKD, danh sách nợ thuế, kết quả đấu thầu. Chỉ ghi cho MST đã có trong hệ thống; cột dữ liệu cá nhân nhạy cảm (CCCD, ngày sinh, địa chỉ cá nhân…) luôn bị bỏ qua.</p>
        </div>
      </div>
      <EnrichNav caps={meta.caps} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {done ? (
        <div className="adm-alert ok" role="status" style={{ marginBottom: 16 }}>
          Đã nhập “{done.file_name}”: {fmtNum(done.report.matched)} dòng khớp MST · {fmtNum(done.report.evidence ?? 0)} bằng chứng mới · {fmtNum(done.report.people ?? 0)} người · {fmtNum(done.report.signals ?? 0)} tín hiệu
          {done.report.duplicates ? ` · ${fmtNum(done.report.duplicates)} giá trị đã có (bỏ qua)` : ""}.
        </div>
      ) : null}

      {data ? <ImportForm kinds={data.kinds} onDone={(i) => { setDone(i); load(); }} /> : <Skeleton h={300} />}

      <section className="adm-card">
        <div className="hd"><h2>Lịch sử nhập</h2></div>
        {!data ? <Skeleton h={120} /> : !data.items.length ? <div className="adm-empty">Chưa nhập file nào.</div> : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>File</th><th>Loại</th><th style={{ textAlign: "right" }}>Khớp MST</th><th style={{ textAlign: "right" }}>Bằng chứng mới</th><th>Người nhập</th><th>Thời điểm</th><th /></tr></thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id}>
                    <td><div className="name">{i.file_name}</div><div className="sub" style={{ maxWidth: 340, wordBreak: "break-word" }}>{i.source_url}{i.data_date ? ` · dữ liệu tới ${fmtDate(i.data_date)}` : ""}</div></td>
                    <td><span className="adm-tag">{i.kind_name}</span></td>
                    <td style={{ textAlign: "right" }}>{fmtNum(i.report.matched)}<div className="sub">{fmtNum(i.report.not_in_system)} ngoài DS</div></td>
                    <td style={{ textAlign: "right" }}>{fmtNum((i.report.evidence ?? 0) + (i.report.signals ?? 0))}</td>
                    <td>{i.created_by ?? "—"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(i.created_at)}</td>
                    <td><button className="adm-btn sm" onClick={() => setOpen(i)}>Biên bản</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Dialog open={open !== null} title={open ? `Biên bản — ${open.file_name}` : ""} onClose={() => setOpen(null)} wide>
        {open ? (
          <>
            <ReportView r={open.report} />
            <div className="adm-actions" style={{ marginTop: 14 }}><button className="adm-btn primary" onClick={() => setOpen(null)}>Đóng</button></div>
          </>
        ) : null}
      </Dialog>
    </>
  );
}

function ReportView({ r }: { r: OfficialReport }) {
  const tiles: [string, number, string?][] = [
    ["Dòng có dữ liệu", r.total_rows],
    ["Khớp MST trong hệ thống", r.matched],
    ["MST ngoài danh sách (bỏ qua)", r.not_in_system, r.not_in_system ? "warn" : undefined],
    ["Sai định dạng MST", r.invalid, r.invalid ? "bad" : undefined],
  ];
  if (r.evidence !== undefined) tiles.push(["Bằng chứng mới", r.evidence ?? 0], ["Người (kho B)", r.people ?? 0], ["Tín hiệu", r.signals ?? 0], ["Trùng (bỏ qua)", r.duplicates ?? 0]);
  return (
    <>
      <div className="er-report">
        {tiles.map(([label, n, cls]) => <div key={label} className={cls}><small>{label}</small><b>{fmtNum(n)}</b></div>)}
      </div>
      <p style={{ fontSize: 13, marginBottom: 6 }}><b>Cột nhận diện:</b> {Object.entries(r.columns).map(([k, v]) => `${v} → ${k}`).join(" · ") || "—"}</p>
      {r.sensitive_columns.length ? (
        <div className="adm-alert warn" style={{ marginBottom: 8 }}>Đã bỏ qua cột dữ liệu cá nhân nhạy cảm: {r.sensitive_columns.join(", ")} — hệ thống không lưu các trường này.</div>
      ) : null}
      {r.ignored_columns.length ? <p className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>Cột không dùng: {r.ignored_columns.join(", ")}</p> : null}
      {r.not_in_system_sample.length ? <p className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>Ví dụ MST ngoài danh sách: <span className="mono">{r.not_in_system_sample.slice(0, 10).join(", ")}</span></p> : null}
      {r.invalid_rows.length ? (
        <details>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Dòng sai định dạng ({fmtNum(r.invalid)})</summary>
          <table className="adm-table" style={{ marginTop: 8 }}>
            <thead><tr><th>Dòng</th><th>Giá trị</th><th>Lý do</th></tr></thead>
            <tbody>{r.invalid_rows.map((x) => <tr key={x.row}><td>{x.row}</td><td className="mono">{x.value || "(trống)"}</td><td>{x.reason}</td></tr>)}</tbody>
          </table>
        </details>
      ) : null}
    </>
  );
}

function ImportForm({ kinds, onDone }: { kinds: Record<string, string>; onDone: (i: OfficialImport) => void }) {
  const formRef = useRef<HTMLFormElement>(null);
  const [kind, setKind] = useState("dkkd_mua");
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<OfficialReport | null>(null);
  const [msg, setMsg] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"" | "check" | "import">("");

  async function filePayload() {
    if (!file) throw new ApiError(422, "Chọn file CSV hoặc Excel.", { file: "Chọn file." });
    if (file.size > MAX_FILE_MB * 1024 * 1024) throw new ApiError(422, `File quá lớn (tối đa ${MAX_FILE_MB} MB).`);
    return { kind, file_name: file.name, file_b64: await fileToBase64(file) };
  }

  function fail(e: unknown) {
    if (e instanceof ApiError) { setMsg(e.message); setErrors(e.fields); } else setMsg(errMsg(e));
  }

  async function check() {
    setBusy("check"); setMsg(""); setErrors({}); setReport(null);
    try { setReport(await api.post<OfficialReport>("/enrich/imports/preview", await filePayload())); } catch (e) { fail(e); } finally { setBusy(""); }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (!String(f.get("source_url") ?? "").trim()) { setErrors({ source_url: "Bắt buộc — để mọi giá trị truy được về nguồn." }); return; }
    setBusy("import"); setMsg(""); setErrors({});
    try {
      const imp = await api.post<OfficialImport>("/enrich/imports", {
        ...(await filePayload()),
        source_url: f.get("source_url"),
        data_date: f.get("data_date") || null,
        note: f.get("note") ?? "",
      });
      formRef.current?.reset(); setFile(null); setReport(null);
      onDone(imp);
    } catch (err) { fail(err); } finally { setBusy(""); }
  }

  const help = HELP[kind];
  return (
    <section className="adm-card" style={{ marginBottom: 16 }}>
      <div className="hd"><h2>Nhập file mới</h2></div>
      <div className="bd">
        <div className="adm-tabs" style={{ padding: 0, marginBottom: 14 }}>
          {Object.entries(kinds).map(([k, v]) => (
            <button key={k} type="button" className={kind === k ? "on" : undefined} onClick={() => { setKind(k); setReport(null); setMsg(""); }}>{v}</button>
          ))}
        </div>
        <p className="er-note" style={{ marginBottom: 12 }}><Icon name="note" /><span>Cột nhận diện: {help.cols}. Dòng tiêu đề có thể nằm dưới vài dòng tên bảng.</span></p>
        <form ref={formRef} className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Nguồn công bố / chứng từ mua" error={errors.source_url} full htmlFor="o-src">
            <input id="o-src" className="adm-input" name="source_url" maxLength={1000} placeholder={help.src} aria-invalid={!!errors.source_url} />
          </Field>
          <Field label="Dữ liệu tính đến ngày" htmlFor="o-date"><input id="o-date" className="adm-input" name="data_date" type="date" /></Field>
          <Field label={`File (.csv, .xlsx ≤ ${MAX_FILE_MB} MB)`} error={errors.file} htmlFor="o-file">
            <input id="o-file" className="adm-input" type="file" accept=".csv,.xlsx,.xlsm,.txt" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); setMsg(""); }} />
          </Field>
          <Field label="Ghi chú (tuỳ chọn)" full htmlFor="o-note"><textarea id="o-note" className="adm-input" name="note" rows={2} maxLength={5000} /></Field>
          {report ? <div className="full"><ReportView r={report} /></div> : null}
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={check} disabled={!file || busy !== ""}>{busy === "check" ? "Đang kiểm tra…" : "Kiểm tra file"}</button>
            <button type="submit" className="adm-btn primary" disabled={!report || !report.matched || busy !== ""}>
              {busy === "import" ? "Đang nhập…" : report ? `Nhập ${fmtNum(report.matched)} dòng khớp MST` : "Nhập"}
            </button>
          </div>
          {report && !report.matched ? <p className="muted full" style={{ fontSize: 12.5 }}>Không dòng nào khớp MST trong hệ thống — <Link href="/admin/lam-giau/nhap-lo">nhập lô MST</Link> trước.</p> : null}
        </form>
      </div>
    </section>
  );
}
