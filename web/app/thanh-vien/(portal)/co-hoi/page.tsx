"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { OppCard } from "@/components/member/OppCard";
import type { Opp } from "@/lib/commerce";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface ListResp {
  total: number;
  page: number;
  page_size: number;
  items: Opp[];
  facets: { industries: string[]; regions: string[]; sources: string[] };
}

const PAGE_SIZE = 12;

function Catalog() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const f = {
    q: sp.get("q") ?? "",
    industry: sp.get("industry") ?? "",
    region: sp.get("region") ?? "",
    source: sp.get("source") ?? "",
    min_score: sp.get("min_score") ?? "",
    only: sp.get("only") ?? "",
    sort: sp.get("sort") ?? "new",
    page: Math.max(1, Number(sp.get("page")) || 1),
  };
  const [search, setSearch] = useState(f.q);
  const [data, setData] = useState<ListResp | null>(null);
  const [error, setError] = useState("");

  function setF(next: Partial<typeof f>) {
    const m = { ...f, page: undefined as number | undefined, ...next };
    router.replace(pathname + qs({ ...m, sort: m.sort === "new" ? "" : m.sort, page: m.page && m.page > 1 ? m.page : undefined }), { scroll: false });
  }

  useEffect(() => {
    if (search === f.q) return;
    const t = setTimeout(() => setF({ q: search.trim() }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const key = sp.toString();
  useEffect(() => {
    document.title = "Tất cả cơ hội · LeadScan B2B";
    setData(null);
    mapi.get<ListResp>("/opportunities" + qs({ ...f, page_size: PAGE_SIZE })).then(setData, (e) => setError(errMsg(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Tất cả cơ hội</h1>
          <p>Cơ hội phù hợp với bạn, tổng hợp từ mọi phiếu tìm cơ hội (đã loại trùng). Điểm và giá phiếu tính riêng cho doanh nghiệp bạn — mua phiếu để mở khoá bên có nhu cầu và đầu mối.</p>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card" style={{ marginBottom: 16 }}>
        <div className="adm-tabs" role="tablist" aria-label="Lọc nhanh">
          {[["", "Tất cả"], ["available", "Còn lượt mua"], ["purchased", "Đã mua"]].map(([k, label]) => (
            <button key={k} role="tab" aria-selected={f.only === k} className={f.only === k ? "on" : undefined} onClick={() => setF({ only: k })}>{label}</button>
          ))}
        </div>
        <div className="adm-filters">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo nhu cầu, mã, tỉnh/thành…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm cơ hội" />
          </div>
          <select className="adm-input" value={f.industry} onChange={(e) => setF({ industry: e.target.value })} aria-label="Ngành">
            <option value="">Mọi ngành</option>
            {data?.facets.industries.map((x) => <option key={x}>{x}</option>)}
          </select>
          <select className="adm-input" value={f.region} onChange={(e) => setF({ region: e.target.value })} aria-label="Khu vực">
            <option value="">Mọi khu vực</option>
            {data?.facets.regions.map((x) => <option key={x}>{x}</option>)}
          </select>
          <select className="adm-input" value={f.min_score} onChange={(e) => setF({ min_score: e.target.value })} aria-label="Điểm tối thiểu">
            <option value="">Mọi mức điểm</option>
            <option value="70">Từ 70 điểm</option>
            <option value="80">Từ 80 điểm</option>
            <option value="90">Từ 90 điểm</option>
          </select>
          <select className="adm-input" value={f.sort} onChange={(e) => setF({ sort: e.target.value })} aria-label="Sắp xếp">
            <option value="new">Mới nhất</option>
            <option value="score">Điểm cao nhất</option>
            <option value="price_asc">Giá thấp → cao</option>
            <option value="price_desc">Giá cao → thấp</option>
          </select>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", padding: "0 14px 14px" }}>
          <button className={!f.source ? "adm-btn sm primary" : "adm-btn sm"} onClick={() => setF({ source: "" })}>Mọi nguồn</button>
          {data?.facets.sources.map((s) => (
            <button key={s} className={f.source === s ? "adm-btn sm primary" : "adm-btn sm"} onClick={() => setF({ source: s })}>{s}</button>
          ))}
        </div>
      </section>

      {!data ? (
        <div className="adm-opps">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={200} />)}</div>
      ) : data.items.length ? (
        <>
          <p className="muted" style={{ marginBottom: 10 }}>{data.total.toLocaleString("vi-VN")} cơ hội</p>
          <div className="adm-opps">{data.items.map((o) => <OppCard key={o.id} o={o} />)}</div>
          {pages > 1 ? (
            <div className="adm-pager" style={{ border: 0, padding: "16px 0" }}>
              <span>Trang {f.page}/{pages}</span>
              <div>
                <button className="adm-btn sm" disabled={f.page <= 1} onClick={() => setF({ page: f.page - 1 })}>← Trước</button>
                <button className="adm-btn sm" disabled={f.page >= pages} onClick={() => setF({ page: f.page + 1 })}>Sau →</button>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <div className="adm-card adm-empty">
          {f.q || f.industry || f.region || f.source || f.min_score || f.only ? (
            "Không có cơ hội phù hợp bộ lọc."
          ) : (
            <>
              Bạn chưa có cơ hội nào. Hãy gửi phiếu tìm cơ hội để hệ thống tìm, chấm điểm và thêm cơ hội phù hợp vào đây.
              <p style={{ marginTop: 12 }}><Link className="adm-btn primary" href="/thanh-vien/phu-hop"><Icon name="scan" size={16} /> Tìm cơ hội phù hợp</Link></p>
            </>
          )}
        </div>
      )}
    </>
  );
}

export default function CatalogPage() {
  return (
    <Suspense>
      <Catalog />
    </Suspense>
  );
}
