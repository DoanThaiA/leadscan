"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { fmtDate } from "@/lib/admin/format";
import { errMsg, papi, qs } from "@/lib/partner/api";

interface Need {
  code: string;
  created_at: string | null;
  fresh: boolean;
  industries: string[];
  regions: string[];
  sizes: string[];
  sources: string[];
  products: string[];
  places: string[];
  text: string;
  match_count: number;
}

interface NeedPage {
  total: number;
  page: number;
  page_size: number;
  items: Need[];
  stats: { total: number; unmet: number; new_7d: number; industries: [string, number][] };
  industries: string[];
  regions: string[];
}

const PAGE = 20;

/** Mô tả khách viết dạng "Mục: nội dung" mỗi dòng (mẫu AI viết lại) → hiện mục in đậm; văn bản tự do giữ nguyên. */
function NeedText({ text }: { text: string }) {
  const lines = text.split("\n").filter((l) => l.trim());
  return (
    <div className="ptn-need-text">
      {lines.map((l, i) => {
        const m = /^([^:]{2,40}):\s*(.+)$/.exec(l.trim());
        return m ? <p key={i}><b>{m[1]}:</b> {m[2]}</p> : <p key={i}>{l}</p>;
      })}
    </div>
  );
}

function NeedCard({ n }: { n: Need }) {
  const [open, setOpen] = useState(false);
  const long = n.text.length > 280;
  const where = [...new Set([...n.places, ...n.regions])];
  const findHref = "/doi-tac/gui-co-hoi" + qs({ nhu_cau: n.code, nganh: n.industries.length === 1 ? n.industries[0] : undefined });
  return (
    <article className="ptn-need">
      <header>
        <span className="mono muted">{n.code}</span>
        {n.fresh ? <span className="adm-badge s-new">Mới</span> : null}
        {n.match_count === 0 ? (
          <span className="adm-badge s-gold" title="Chưa có phiếu cơ hội nào đang bán khớp với nhu cầu này">Chưa có cơ hội phù hợp</span>
        ) : (
          <span className="adm-badge s-suspended" title="Số phiếu cơ hội đang bán đã khớp">{n.match_count} cơ hội đã khớp</span>
        )}
        <span className="muted" style={{ marginLeft: "auto", fontSize: 12.5 }}>gửi {fmtDate(n.created_at)}</span>
      </header>
      {n.products.length ? <h3>{n.products.join(", ")}</h3> : null}
      <div className={open || !long ? undefined : "ptn-need-clamp"}><NeedText text={n.text} /></div>
      {long ? (
        <button type="button" className="ptn-linkbtn" onClick={() => setOpen((o) => !o)}>{open ? "Thu gọn" : "Xem đầy đủ"}</button>
      ) : null}
      <div className="tags">
        {n.industries.map((x) => <span key={x} className="adm-tag"><Icon name="factory" size={12} /> {x}</span>)}
        {where.map((x) => <span key={x} className="adm-tag"><Icon name="map" size={12} /> {x}</span>)}
        {n.sizes.map((x) => <span key={x} className="adm-tag"><Icon name="users" size={12} /> {x}</span>)}
        {n.sources.map((x) => <span key={x} className="adm-tag"><Icon name="target" size={12} /> {x}</span>)}
      </div>
      <footer>
        <span className="muted" style={{ fontSize: 12.5 }}>Tìm được doanh nghiệp đang cần mua đúng như trên? Gửi cơ hội để LeadScan xác minh.</span>
        <Link className="adm-btn sm primary" href={findHref}><Icon name="plus" size={14} /> Gửi cơ hội phù hợp</Link>
      </footer>
    </article>
  );
}

function NeedsList() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const industry = params.get("nganh") ?? "";
  const region = params.get("khu_vuc") ?? "";
  const unmet = params.get("chua_co") === "1";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [data, setData] = useState<NeedPage | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState(q);

  useEffect(() => {
    document.title = "Nhu cầu đang tìm · Đối tác LeadScan";
    setData(null);
    setError("");
    papi
      .get<NeedPage>("/needs" + qs({ q, industry, region, unmet: unmet ? "true" : undefined, sort: unmet ? "unmet" : undefined, page, page_size: PAGE }))
      .then(setData, (e) => setError(errMsg(e)));
  }, [q, industry, region, unmet, page]);
  useEffect(() => setText(q), [q]);

  const cur = { q: q || undefined, nganh: industry || undefined, khu_vuc: region || undefined, chua_co: unmet ? "1" : undefined };
  const go = (next: Record<string, string | number | undefined>) => router.replace(pathname + qs({ ...cur, page: undefined, ...next }), { scroll: false });
  const search = (e: FormEvent) => { e.preventDefault(); go({ q: text.trim() || undefined }); };
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  const st = data?.stats;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Nhu cầu đang tìm</h1>
          <p>Thành viên LeadScan đang cần tìm khách hàng / cơ hội như dưới đây. Bạn biết doanh nghiệp nào đang có nhu cầu mua phù hợp — gửi cơ hội để được thưởng.</p>
        </div>
        <Link className="adm-btn primary" href="/doi-tac/gui-co-hoi">+ Gửi cơ hội</Link>
      </div>

      <div className="adm-grid ptn-cols-3" style={{ marginBottom: 16 }}>
        <section className="adm-card adm-stat"><small>Nhu cầu đang tìm</small><b>{st?.total ?? "—"}</b><span>của thành viên còn hạn</span></section>
        <section className="adm-card adm-stat"><small>Chưa có cơ hội phù hợp</small><b>{st?.unmet ?? "—"}</b><span>nên ưu tiên đi tìm</span></section>
        <section className="adm-card adm-stat"><small>Mới trong 7 ngày</small><b>{st?.new_7d ?? "—"}</b><span>nhu cầu vừa gửi</span></section>
      </div>

      {st?.industries.length ? (
        <div className="ptn-need-chips" aria-label="Ngành có nhiều nhu cầu">
          <span className="muted">Ngành nhiều nhu cầu:</span>
          {st.industries.map(([k, v]) => {
            const on = industry === k;
            const usable = data?.industries.includes(k);
            return usable ? (
              <button key={k} type="button" className={on ? "on" : undefined} onClick={() => go({ nganh: on ? undefined : k })}>{k} <b>{v}</b></button>
            ) : <span key={k} className="off">{k} <b>{v}</b></span>;
          })}
        </div>
      ) : null}

      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        <form className="adm-toolbar" onSubmit={search} role="search">
          <div className="adm-search">
            <Icon name="search" size={16} />
            <input className="adm-input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Tìm theo sản phẩm, khách hàng cần tìm… (vd: bao bì, linh kiện)" aria-label="Tìm nhu cầu" />
          </div>
          <select className="adm-input" style={{ width: "auto" }} value={industry} onChange={(e) => go({ nganh: e.target.value || undefined })} aria-label="Ngành hàng">
            <option value="">Mọi ngành</option>
            {data?.industries.map((x) => <option key={x}>{x}</option>)}
          </select>
          <select className="adm-input" style={{ width: "auto" }} value={region} onChange={(e) => go({ khu_vuc: e.target.value || undefined })} aria-label="Khu vực">
            <option value="">Mọi khu vực</option>
            {data?.regions.map((x) => <option key={x}>{x}</option>)}
          </select>
          <label className="ptn-switch-inline">
            <input type="checkbox" checked={unmet} onChange={(e) => go({ chua_co: e.target.checked ? "1" : undefined })} /> Chỉ nhu cầu chưa có cơ hội
          </label>
        </form>

        {!data ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} h={60} />)}</div>
        ) : !data.items.length ? (
          <div className="adm-empty">
            {q || industry || region || unmet ? "Không có nhu cầu nào khớp bộ lọc." : "Hiện chưa có nhu cầu nào đang tìm. Quay lại sau nhé."}
          </div>
        ) : (
          <div className="ptn-needs">{data.items.map((n) => <NeedCard key={n.code} n={n} />)}</div>
        )}

        {data && pages > 1 ? (
          <div className="adm-pager">
            <span>{data.total} nhu cầu · trang {page}/{pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="adm-btn sm" disabled={page <= 1} onClick={() => go({ page: page - 1 > 1 ? page - 1 : undefined })}>← Trước</button>
              <button className="adm-btn sm" disabled={page >= pages} onClick={() => go({ page: page + 1 })}>Sau →</button>
            </div>
          </div>
        ) : null}
      </section>

      <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
        Nhu cầu hiển thị ẩn danh: LeadScan không cho biết thành viên nào gửi, đã che tên doanh nghiệp, số điện thoại, email, đường link và mã số thuế trong mô tả.
        Bạn không cần liên hệ thành viên — chỉ cần gửi cơ hội (doanh nghiệp có nhu cầu mua) như bình thường, LeadScan xác minh và kết nối.
      </p>
    </>
  );
}

export default function PartnerNeedsPage() {
  return (
    <Suspense fallback={<div className="adm-empty">Đang tải…</div>}>
      <NeedsList />
    </Suspense>
  );
}
