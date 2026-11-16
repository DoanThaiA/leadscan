"use client";

import { useEffect, useState } from "react";

import { EnrichNav } from "@/components/admin/EnrichNav";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { type MarketReport, pct, useEnrichMeta } from "@/lib/admin/enrich";
import { fmtNum } from "@/lib/admin/format";

function Bars({ title, rows, total }: { title: string; rows: { key: string; count: number }[]; total: number }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <section className="adm-card">
      <div className="hd"><h2>{title}</h2></div>
      <div className="bd" style={{ display: "grid", gap: 6 }}>
        {!rows.length ? <p className="muted">Chưa có dữ liệu.</p> : rows.map((r) => (
          <div key={r.key} style={{ display: "grid", gridTemplateColumns: "minmax(110px, 38%) 1fr auto", gap: 8, alignItems: "center", fontSize: 13 }}>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={r.key}>{r.key}</span>
            <span style={{ height: 10, borderRadius: 999, background: "var(--line-2)", overflow: "hidden" }}><i style={{ display: "block", height: "100%", width: `${(r.count / max) * 100}%`, background: "var(--brand)" }} /></span>
            <span style={{ fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>{fmtNum(r.count)} <span className="muted">· {pct(r.count, total)}</span></span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function MarketReportPage() {
  const { meta, error: metaError } = useEnrichMeta();
  const [r, setR] = useState<MarketReport | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    document.title = "Báo cáo thị trường · Làm giàu theo MST";
    api.get<MarketReport>("/enrich/reports/market").then(setR, (e) => setError(errMsg(e)));
  }, []);
  if (metaError || error) return <div className="adm-card adm-empty">{metaError || error}</div>;
  if (!meta || !r) return <Skeleton h={400} />;
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Báo cáo tổng hợp thị trường</h1>
          <p>Phân bổ doanh nghiệp theo tỉnh, ngành, quy mô vốn, tình trạng và độ phủ dữ liệu. Chỉ số liệu tổng hợp — không chứa dữ liệu cá nhân.</p>
        </div>
        <a className="adm-btn" href="/api/admin/enrich/reports/market.csv"><Icon name="download" size={14} /> Tải CSV</a>
      </div>
      <EnrichNav caps={meta.caps} />
      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        <div className="adm-card adm-stat"><small>Tổng doanh nghiệp</small><b>{fmtNum(r.total)}</b></div>
        {meta.required_fields.slice(0, 2).map((f) => (
          <div key={f} className="adm-card adm-stat"><small>Có {meta.fields[f]?.toLowerCase()}</small><b>{pct(r.coverage[f] ?? 0, r.total)}</b><span>{fmtNum(r.coverage[f] ?? 0)} DN</span></div>
        ))}
        <div className="adm-card adm-stat"><small>Có người ra quyết định</small><b>{pct(r.decision_maker, r.total)}</b><span>{fmtNum(r.decision_maker)} DN</span></div>
      </div>
      <div className="er-two" style={{ marginBottom: 16 }}>
        <Bars title="Theo tỉnh/thành" rows={r.by_tinh} total={r.total} />
        <Bars title="Theo ngành chính" rows={r.by_nganh} total={r.total} />
      </div>
      <div className="er-two">
        <Bars title="Theo quy mô vốn điều lệ" rows={r.by_von} total={r.total} />
        <Bars title="Theo tình trạng hoạt động" rows={r.by_trang_thai} total={r.total} />
      </div>
    </>
  );
}
