"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { type CompanyProfile, type Evidence, type EnrichMeta, fmtValue, type Person, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";

type Tab = "info" | "people" | "signals" | "changes" | "evidence";

function SourceLink({ url }: { url: string }) {
  if (!url) return null;
  return /^https?:\/\//.test(url) ? (
    <a href={url} target="_blank" rel="noopener noreferrer nofollow">{url.length > 60 ? url.slice(0, 57) + "…" : url}</a>
  ) : (
    <span className="mono">{url}</span>
  );
}

export default function EnrichCompanyPage() {
  const { mst } = useParams<{ mst: string }>();
  const { meta } = useEnrichMeta();
  const [p, setP] = useState<CompanyProfile | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("info");

  useEffect(() => {
    api.get<CompanyProfile>(`/enrich/companies/${mst}`).then(setP, (e) => setError(errMsg(e)));
  }, [mst]);
  useEffect(() => {
    if (p) document.title = `${p.ten || p.mst} · Làm giàu theo MST`;
  }, [p]);

  if (error) return <div className="adm-card adm-empty">{error}</div>;
  if (!p || !meta) return <Skeleton h={400} />;

  const tabs: [Tab, string, number | null][] = [
    ["info", "Thông tin pháp lý", null],
    ["people", "Người liên quan", null],
    ["signals", "Tín hiệu", p.signals.length],
    ["changes", "Lịch sử thay đổi", p.changes.length],
    ["evidence", "Nguồn gốc", null],
  ];

  return (
    <>
      <EnrichNav caps={meta.caps} />
      <div className="adm-head">
        <div style={{ minWidth: 0 }}>
          <h1>{p.ten || <span className="muted">Chưa có tên doanh nghiệp</span>}</h1>
          <p><span className="mono">MST {p.mst}</span>{p.loai_hinh ? ` · ${p.loai_hinh}` : ""} · vào hệ thống {fmtDate(p.created_at)}</p>
          <div className="er-tags" style={{ marginTop: 8 }} aria-label="Mục đích sử dụng được phép">
            {p.purposes.length ? p.purposes.map((k) => <span key={k} className="adm-badge info">{meta.purposes[k] ?? k}</span>) : <span className="adm-badge s-rejected">Chưa gắn mục đích sử dụng</span>}
          </div>
        </div>
      </div>

      <section className="adm-card">
        <div className="adm-tabs" role="tablist">
          {tabs.map(([k, label, n]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : undefined} onClick={() => setTab(k)}>
              {label}{n ? <span>{n}</span> : null}
            </button>
          ))}
        </div>
        <div className="bd">
          {tab === "info" ? <InfoTab p={p} meta={meta} /> : null}
          {tab === "people" ? <PeopleTab p={p} /> : null}
          {tab === "signals" ? <SignalsTab p={p} /> : null}
          {tab === "changes" ? <ChangesTab p={p} /> : null}
          {tab === "evidence" ? <EvidenceTab mst={p.mst} meta={meta} /> : null}
        </div>
      </section>
    </>
  );
}

function InfoTab({ p, meta }: { p: CompanyProfile; meta: EnrichMeta }) {
  return (
    <>
      <dl className="er-fields">
        {p.fields.map((f) => (
          <div key={f.key}>
            <dt>{f.label}</dt>
            <dd>
              <div className="v" style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                <span>{fmtValue(f.key, f.value)}</span>
                <span className={`er-score ${f.score >= 85 ? "hi" : f.score >= 60 ? "mid" : "lo"}`} title="Điểm tin cậy: độ tin cậy nguồn + số nguồn đồng thuận, giảm khi dữ liệu cũ">{f.score}</span>
                {f.stale ? <span className="adm-badge warn" title={`Quá ${f.recrawl_days} ngày chưa thu thập lại`}>Dữ liệu cũ</span> : null}
              </div>
              <div className="er-src">
                <span>{f.source.name}{f.source.trust !== null ? ` (tin cậy ${f.source.trust})` : ""}</span>
                <span>{fmtDateTime(f.fetched_at)}</span>
                <SourceLink url={f.source_url} />
                <span>{f.evidence_count} bằng chứng{f.evidence_count > 1 ? ` · ${f.agree} đồng thuận` : ""}</span>
                {f.conflict ? <span className="adm-badge warn" title="Các nguồn đưa ra giá trị khác nhau — xem tab Nguồn gốc">Xung đột</span> : null}
                {f.is_inferred ? <span className="adm-badge plain role">Suy luận</span> : null}
                <span className="muted">{meta.methods[f.method] ?? f.method}</span>
              </div>
            </dd>
          </div>
        ))}
      </dl>
      {p.contacts?.length ? (
        <>
          <h3 style={{ margin: "22px 0 8px", fontSize: 14 }}>Liên hệ chung của doanh nghiệp</h3>
          <dl className="er-fields">
            {(["phone", "email"] as const).map((kind) => {
              const items = p.contacts!.filter((c) => c.kind === kind);
              if (!items.length) return null;
              return (
                <div key={kind}>
                  <dt>{kind === "phone" ? "Điện thoại" : "Email"}</dt>
                  <dd>
                    {items.map((c) => (
                      <div key={c.value} className="v" style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                        <span className="mono">{c.value}</span>
                        <span className="muted" style={{ fontSize: 12 }}>{c.source_name}</span>
                      </div>
                    ))}
                  </dd>
                </div>
              );
            })}
          </dl>
        </>
      ) : null}
      {p.missing_fields.length ? (
        <p className="er-note" style={{ marginTop: 12 }}>
          <Icon name="note" />
          <span>Chưa có bằng chứng nên không hiển thị: {p.missing_fields.join(", ")}.</span>
        </p>
      ) : null}

      <h3 style={{ margin: "22px 0 8px", fontSize: 14 }}>Lô nhập</h3>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr><th>Lô</th><th>Dòng</th><th>Mục đích được phép</th><th>Ngày nhập</th></tr></thead>
          <tbody>
            {p.batches.map((b) => (
              <tr key={b.id}>
                <td><Link className="name" href={`/admin/lam-giau?lo=${b.id}`}>#{b.id} · {b.name}</Link></td>
                <td>{b.row_no}</td>
                <td><div className="er-tags">{b.purposes.map((k) => <span key={k} className="adm-tag">{meta.purposes[k] ?? k}</span>)}</div></td>
                <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(b.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function PeopleTab({ p }: { p: CompanyProfile }) {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (p.can.people) api.get<Person[]>(`/enrich/companies/${p.mst}/people`).then(setPeople, (e) => setError(errMsg(e)));
  }, [p.mst, p.can.people]);

  if (!p.can.people) return <div className="adm-empty"><Icon name="lock" /> Vai trò của bạn không được xem dữ liệu cá nhân (kho B).</div>;
  if (error) return <div className="adm-alert">{error}</div>;
  if (!people) return <Skeleton h={120} />;

  const showMst = people.some((x) => "mst_ca_nhan" in x);
  const showYear = people.some((x) => "nam_sinh" in x);
  return (
    <>
      <p className="er-note" style={{ marginBottom: 12 }}><Icon name="lock" /><span>Dữ liệu cá nhân (kho B) — mỗi lần mở tab này được ghi vào nhật ký truy cập.</span></p>
      {!people.length ? (
        <div className="adm-empty">Chưa có người nào. Người ra quyết định được thu thập từ giai đoạn 3 (doanh nghiệp niêm yết) và 4 (website, MST cá nhân).</div>
      ) : (
        <div className="adm-table-wrap">
          <table className="adm-table">
            <thead>
              <tr>
                <th>Họ tên</th><th>Chức danh</th><th>Liên hệ công việc</th>
                {showYear ? <th>Năm sinh</th> : null}
                {showMst ? <th>MST cá nhân</th> : null}
              </tr>
            </thead>
            <tbody>
              {people.map((x, i) => (
                <tr key={x.id ?? i}>
                  <td>
                    <div className="name">{x.id ? <Link href={`/admin/lam-giau/nguoi/${x.id}`}>{x.ho_ten}</Link> : x.ho_ten}</div>
                    {x.la_nguoi_quyet_dinh ? <span className="adm-badge s-active">Người ra quyết định</span> : null}
                  </td>
                  <td>{x.chuc_danh}{x.den_ngay ? <div className="sub">Đến {fmtDate(x.den_ngay)}</div> : null}</td>
                  <td>
                    {x.lien_he?.length ? x.lien_he.map((c) => (
                      <div key={c.value} className="sub">{c.value}{c.is_inferred ? <span className="adm-badge plain role" style={{ marginLeft: 6 }}>Suy luận</span> : null}</div>
                    )) : <span className="muted">—</span>}
                  </td>
                  {showYear ? <td>{x.nam_sinh ?? "—"}</td> : null}
                  {showMst ? <td className="mono">{x.mst_ca_nhan ?? "—"}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function SignalsTab({ p }: { p: CompanyProfile }) {
  if (!p.signals.length) return <div className="adm-empty">Chưa có tín hiệu. Nợ thuế, trúng thầu, bổ nhiệm, thay đổi đăng ký sẽ xuất hiện khi có connector ở giai đoạn 2.</div>;
  return (
    <ul className="adm-timeline">
      {p.signals.map((s, i) => (
        <li key={i}>
          <span className="dot"><Icon name="bell" /></span>
          <div>
            <div className="txt"><b>{s.label}</b>{signalText(s.payload)}</div>
            <div className="meta">{s.day ? `${fmtDate(s.day)} · ` : ""}{s.source_name} · <SourceLink url={s.source_url} /></div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function signalText(p: Record<string, unknown>): string {
  const money = (v: unknown) => (typeof v === "number" ? `${v.toLocaleString("vi-VN")} đ` : "");
  const parts = [
    p.goi_thau ? `gói “${p.goi_thau}”` : "",
    p.ben_moi_thau ? `bên mời thầu ${p.ben_moi_thau}` : "",
    money(p.gia_trung_thau),
    money(p.so_tien),
    p.co_quan ? String(p.co_quan) : "",
  ].filter(Boolean);
  return parts.length ? " — " + parts.join(" · ") : "";
}

function ChangesTab({ p }: { p: CompanyProfile }) {
  if (!p.changes.length) return <div className="adm-empty">Chưa ghi nhận thay đổi nào.</div>;
  return (
    <div className="adm-table-wrap">
      <table className="adm-table">
        <thead><tr><th>Trường</th><th>Giá trị cũ</th><th>Giá trị mới</th><th>Nguồn</th><th>Phát hiện lúc</th></tr></thead>
        <tbody>
          {p.changes.map((c, i) => (
            <tr key={i}>
              <td>{c.label}</td>
              <td className="muted" style={{ textDecoration: "line-through" }}>{c.old_value ?? "—"}</td>
              <td>{c.new_value ?? "—"}</td>
              <td>{c.source_code}</td>
              <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(c.detected_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EvidenceTab({ mst, meta }: { mst: string; meta: EnrichMeta }) {
  const [rows, setRows] = useState<Evidence[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get<Evidence[]>(`/enrich/companies/${mst}/evidence`).then(setRows, (e) => setError(errMsg(e)));
  }, [mst]);
  if (error) return <div className="adm-alert">{error}</div>;
  if (!rows) return <Skeleton h={160} />;
  return (
    <>
      <p className="er-note" style={{ marginBottom: 12 }}><Icon name="note" /><span>Mỗi dòng là một lần một nguồn nói một điều. Giá trị cũ không bị xoá — hệ thống chỉ chọn giá trị hiển thị theo độ tin cậy nguồn.</span></p>
      <div className="adm-table-wrap">
        <table className="adm-table er-ev">
          <thead><tr><th>Trường</th><th>Giá trị</th><th>Nguồn</th><th>Đường dẫn</th><th>Trích đoạn</th><th>Thời điểm</th></tr></thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className={e.in_use ? undefined : "off"}>
                <td style={{ whiteSpace: "nowrap" }}>
                  {e.label}
                  <div style={{ marginTop: 4 }}>
                    {e.in_use ? <span className="adm-badge s-active">Đang dùng</span> : <span className="adm-badge s-suspended">Không dùng</span>}
                  </div>
                </td>
                <td className="v">{e.value}{e.is_inferred ? <span className="adm-badge plain role" style={{ marginLeft: 6 }}>Suy luận</span> : null}</td>
                <td>
                  {e.source_name}
                  <div className="sub">{meta.methods[e.method] ?? e.method}{e.trust !== null ? ` · tin cậy ${e.trust}` : ""}</div>
                  {e.batch ? <div className="sub"><Link href={`/admin/lam-giau?lo=${e.batch.id}`}>Lô #{e.batch.id} · {e.batch.name}</Link></div> : null}
                </td>
                <td><SourceLink url={e.source_url} /></td>
                <td><div className="excerpt">{e.excerpt || "—"}</div></td>
                <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.fetched_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
