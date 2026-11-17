"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, ApiError, errMsg } from "@/lib/admin/api";
import { type Batch, fileToBase64, type ImportReport, MAX_FILE_MB, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";

export default function EnrichBatchesPage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [batches, setBatches] = useState<Batch[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<Batch | null>(null);
  const [created, setCreated] = useState<Batch | null>(null);

  const load = useCallback(() => {
    api.get<Batch[]>("/enrich/batches").then(setBatches, (e) => setError(errMsg(e)));
  }, []);
  useEffect(() => {
    document.title = "Lô MST · Làm giàu theo MST";
    load();
  }, [load]);

  if (metaError) return <div className="adm-card adm-empty">{metaError}</div>;
  if (!meta) return <Skeleton h={400} />;
  const canImport = meta.caps.includes("batch.import");

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Lô mã số thuế</h1>
          <p>Mỗi lô ghi rõ danh sách lấy từ đâu và được phép dùng cho mục đích nào. Mọi hồ sơ truy ngược được về lô và dòng trong file gốc.</p>
        </div>
      </div>
      <EnrichNav caps={meta.caps} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      {created ? (
        <div className="adm-alert ok" style={{ marginBottom: 16 }} role="status">
          Đã nhập lô #{created.id} “{created.name}”: {fmtNum(created.mst_count)} MST ({fmtNum(created.new_count)} mới).{" "}
          <Link href={`/admin/lam-giau?lo=${created.id}`} style={{ fontWeight: 600 }}>Xem hồ sơ trong lô →</Link>
        </div>
      ) : null}

      {canImport ? <ImportForm purposes={meta.purposes} onCreated={(b) => { setCreated(b); load(); }} /> : null}

      <section className="adm-card">
        <div className="hd"><h2>Các lô đã nhập</h2></div>
        {!batches ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={32} />)}</div>
        ) : !batches.length ? (
          <div className="adm-empty">Chưa có lô nào.</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Lô</th><th>Mục đích được phép</th><th style={{ textAlign: "right" }}>MST</th><th>Người nhập</th><th>Thời điểm</th><th /></tr></thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <Link className="name" href={`/admin/lam-giau?lo=${b.id}`}>#{b.id} · {b.name}</Link>
                      <div className="sub">{b.list_source} · <span className="mono">{b.file_name}</span></div>
                    </td>
                    <td><div className="er-tags">{b.purposes.map((k) => <span key={k} className="adm-tag">{meta.purposes[k] ?? k}</span>)}</div></td>
                    <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                      {fmtNum(b.mst_count)}<div className="sub">{fmtNum(b.new_count)} mới</div>
                    </td>
                    <td>{b.created_by ?? "—"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(b.created_at)}</td>
                    <td><button className="adm-btn sm" onClick={() => setOpen(b)}>Biên bản</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Dialog open={open !== null} title={open ? `Biên bản nhập lô #${open.id}` : ""} onClose={() => setOpen(null)} wide>
        {open ? (
          <>
            <ReportView r={open.report} />
            {open.note ? <p style={{ marginTop: 12 }}><b>Ghi chú:</b> {open.note}</p> : null}
            <div className="adm-actions" style={{ marginTop: 14 }}><button className="adm-btn primary" onClick={() => setOpen(null)}>Đóng</button></div>
          </>
        ) : null}
      </Dialog>
    </>
  );
}

function ReportView({ r }: { r: ImportReport }) {
  const tiles: [string, number, string?][] = [
    ["Dòng có dữ liệu", r.total_rows],
    ["MST hợp lệ", r.valid],
    ["Mới vào hệ thống", r.new],
    ["Đã có sẵn", r.existing],
    ["Trùng trong file", r.duplicate_in_file, r.duplicate_in_file ? "warn" : undefined],
    ["Sai định dạng", r.invalid, r.invalid ? "bad" : undefined],
  ];
  return (
    <>
      <div className="er-report">
        {tiles.map(([label, n, cls]) => (
          <div key={label} className={cls}><small>{label}</small><b>{fmtNum(n)}</b></div>
        ))}
      </div>
      {r.zero_padded ? (
        <div className="adm-alert warn" style={{ marginBottom: 12 }}>{fmtNum(r.zero_padded)} MST chỉ có 9 hoặc 12 chữ số (Excel làm rơi số 0 đầu) — đã tự bù số 0.</div>
      ) : null}
      {!r.has_name_column ? <p className="er-note" style={{ marginBottom: 12 }}><Icon name="note" /><span>File không có cột tên doanh nghiệp — hồ sơ chỉ có MST cho tới khi connector thu thập (giai đoạn 2).</span></p> : null}
      {r.columns ? (
        <div style={{ marginBottom: 12 }}>
          <b style={{ fontSize: 13 }}>Cột được nhập vào hồ sơ</b>
          {r.columns.length ? (
            <div className="adm-table-wrap" style={{ marginTop: 6 }}>
              <table className="adm-table">
                <thead><tr><th>Cột trong file</th><th>Ghi vào</th><th style={{ textAlign: "right" }}>Dòng có giá trị</th></tr></thead>
                <tbody>
                  {r.columns.map((c) => (
                    <tr key={c.header}><td>{c.header}</td><td>{c.label}</td><td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmtNum(c.filled)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="er-note" style={{ marginTop: 6 }}><Icon name="note" /><span>Ngoài MST và tên, không cột nào khớp trường hồ sơ.</span></p>
          )}
          <p className="er-note" style={{ marginTop: 6 }}>
            <Icon name="note" />
            <span>Dữ liệu từ lô có độ tin cậy 0,5 — khi có dữ liệu ĐKKD / nguồn chính thức, giá trị đó được ưu tiên hiển thị; giá trị từ lô vẫn giữ làm bằng chứng.</span>
          </p>
          {r.ignored_columns?.length ? <p className="er-note" style={{ marginTop: 6 }}><Icon name="note" /><span>Không nhận ra (chỉ lưu trong trích đoạn bằng chứng): {r.ignored_columns.join(", ")}.</span></p> : null}
          {r.sensitive_columns?.length ? <div className="adm-alert warn" style={{ marginTop: 6 }}>Bỏ qua cột dữ liệu cá nhân nhạy cảm: {r.sensitive_columns.join(", ")}.</div> : null}
        </div>
      ) : null}
      {r.phones && (r.phones.ok || r.phones.bad) ? (
        <details style={{ marginBottom: 10 }} open={false}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            Điện thoại: {fmtNum(r.phones.ok)} số nhận được{r.phones.bad ? ` · ${fmtNum(r.phones.bad)} dòng có số không đọc được` : ""}
          </summary>
          {r.phones.bad_rows.length ? (
            <>
              <p className="er-note" style={{ marginTop: 8 }}><Icon name="note" /><span>Số dạng “8.40948E+11” là Excel đã đổi sang dạng khoa học và làm mất chữ số — sửa ô thành dạng Văn bản (Text) trong file gốc rồi nhập lại. Số thiếu mã vùng cũng không nhận.</span></p>
              <div className="adm-table-wrap" style={{ maxHeight: 220, overflow: "auto", marginTop: 8 }}>
                <table className="adm-table">
                  <thead><tr><th>Dòng</th><th>Giá trị trong ô</th><th>Phần không đọc được</th></tr></thead>
                  <tbody>{r.phones.bad_rows.map((x) => <tr key={x.row}><td>{x.row}</td><td className="mono">{x.value}</td><td className="mono">{x.unreadable.join(" · ")}</td></tr>)}</tbody>
                </table>
              </div>
            </>
          ) : null}
        </details>
      ) : null}
      {r.invalid_rows.length ? (
        <details open={r.invalid_rows.length <= 10} style={{ marginBottom: 10 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Dòng sai định dạng ({fmtNum(r.invalid)}{r.invalid > r.invalid_rows.length ? `, hiện ${r.invalid_rows.length} dòng đầu` : ""})</summary>
          <div className="adm-table-wrap" style={{ maxHeight: 260, overflow: "auto", marginTop: 8 }}>
            <table className="adm-table">
              <thead><tr><th>Dòng</th><th>Giá trị</th><th>Lý do</th></tr></thead>
              <tbody>{r.invalid_rows.map((x) => <tr key={x.row}><td>{x.row}</td><td className="mono">{x.value || "(trống)"}</td><td>{x.reason}</td></tr>)}</tbody>
            </table>
          </div>
        </details>
      ) : null}
      {r.duplicate_rows.length ? (
        <details style={{ marginBottom: 10 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Dòng trùng trong file ({fmtNum(r.duplicate_in_file)}) — chỉ lấy lần xuất hiện đầu</summary>
          <div className="adm-table-wrap" style={{ maxHeight: 220, overflow: "auto", marginTop: 8 }}>
            <table className="adm-table">
              <thead><tr><th>Dòng</th><th>MST</th><th>Trùng với dòng</th></tr></thead>
              <tbody>{r.duplicate_rows.map((x) => <tr key={x.row}><td>{x.row}</td><td className="mono">{x.mst}</td><td>{x.first_row}</td></tr>)}</tbody>
            </table>
          </div>
        </details>
      ) : null}
    </>
  );
}

function ImportForm({ purposes, onCreated }: { purposes: Record<string, string>; onCreated: (b: Batch) => void }) {
  const formRef = useRef<HTMLFormElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState<"" | "check" | "import">("");

  async function payloadFile() {
    if (!file) throw new ApiError(422, "Chọn file CSV hoặc Excel.", { file: "Chọn file CSV hoặc Excel." });
    if (file.size > MAX_FILE_MB * 1024 * 1024) throw new ApiError(422, `File quá lớn (tối đa ${MAX_FILE_MB} MB).`, { file: `Tối đa ${MAX_FILE_MB} MB.` });
    return { file_name: file.name, file_b64: await fileToBase64(file) };
  }

  function fail(e: unknown) {
    if (e instanceof ApiError) {
      setMsg(e.message);
      setErrors(e.fields);
    } else setMsg(errMsg(e));
  }

  async function check() {
    setBusy("check");
    setMsg("");
    setErrors({});
    setReport(null);
    try {
      setReport(await api.post<ImportReport>("/enrich/batches/preview", await payloadFile()));
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const chosen = fd.getAll("purposes").map(String);
    const local: Record<string, string> = {};
    if (!String(fd.get("name") ?? "").trim()) local.name = "Đặt tên cho lô.";
    if (!String(fd.get("list_source") ?? "").trim()) local.list_source = "Ghi rõ danh sách lấy từ đâu.";
    if (!chosen.length) local.purposes = "Chọn ít nhất một mục đích sử dụng được phép.";
    if (Object.keys(local).length) {
      setErrors(local);
      setMsg("");
      return;
    }
    setBusy("import");
    setMsg("");
    setErrors({});
    try {
      const b = await api.post<Batch>("/enrich/batches", {
        name: fd.get("name"),
        list_source: fd.get("list_source"),
        note: fd.get("note") ?? "",
        purposes: chosen,
        ...(await payloadFile()),
      });
      formRef.current?.reset();
      setFile(null);
      setReport(null);
      onCreated(b);
    } catch (err) {
      fail(err);
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="adm-card" style={{ marginBottom: 16 }}>
      <div className="hd"><h2>Nhập lô mới</h2></div>
      <div className="bd">
        <form ref={formRef} className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Tên lô" error={errors.name} htmlFor="b-name">
            <input id="b-name" className="adm-input" name="name" maxLength={200} placeholder="VD: Khách hàng hiện hữu 11/2026" aria-invalid={!!errors.name} />
          </Field>
          <Field label="Nguồn danh sách" error={errors.list_source} htmlFor="b-src">
            <input id="b-src" className="adm-input" name="list_source" maxLength={300} placeholder="VD: CRM nội bộ, hội chợ VIETBUILD 2026" aria-invalid={!!errors.list_source} />
          </Field>
          <div className="adm-field full" role="group" aria-labelledby="b-purposes">
            <label id="b-purposes">Mục đích sử dụng được phép</label>
            <div className="adm-checks">
              {Object.entries(purposes).map(([k, v]) => (
                <label key={k}><input type="checkbox" name="purposes" value={k} /> {v}</label>
              ))}
            </div>
            {errors.purposes ? <span className="adm-err">{errors.purposes}</span> : null}
          </div>
          <Field label="Ghi chú (tuỳ chọn)" full htmlFor="b-note">
            <textarea id="b-note" className="adm-input" name="note" rows={2} maxLength={5000} />
          </Field>
          <Field label={`File CSV hoặc Excel (.xlsx, ≤ ${MAX_FILE_MB} MB, sheet đầu tiên) — cột “MST” bắt buộc; tên, địa chỉ, điện thoại, email, website, ngành nghề, nhóm sản phẩm, mã HS… nhận theo tiêu đề cột`} error={errors.file} full htmlFor="b-file">
            <input
              id="b-file"
              className="adm-input"
              type="file"
              accept=".csv,.xlsx,.xlsm,.txt"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); setMsg(""); }}
              aria-invalid={!!errors.file}
            />
          </Field>
          {report ? (
            <div className="full">
              <ReportView r={report} />
              {report.sample?.length ? (
                <p className="er-note"><Icon name="check" /><span>Ví dụ: {report.sample.slice(0, 3).map((s) => `${s.mst}${s.name ? ` (${s.name})` : ""}`).join(", ")}…</span></p>
              ) : null}
            </div>
          ) : null}
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={check} disabled={!file || busy !== ""}>{busy === "check" ? "Đang kiểm tra…" : "Kiểm tra file"}</button>
            <button type="submit" className="adm-btn primary" disabled={!report || !report.valid || busy !== ""}>
              {busy === "import" ? "Đang nhập…" : report ? `Nhập ${fmtNum(report.valid)} MST` : "Nhập lô"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
