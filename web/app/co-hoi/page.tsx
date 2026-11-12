import type { Metadata } from "next";

import PublicOppCard from "@/components/public-opp/OppCard";
import { fetchPublicOpps } from "@/lib/public-opps";

export const dynamic = "force-dynamic";

const TITLE = "Cơ hội kinh doanh B2B đang mở bán – LeadScan";
const DESC = "Nhu cầu mua hàng, dự án, nhà máy mới đã được LeadScan xác minh và chấm điểm. Xem tóm tắt miễn phí, mua phiếu để mở khoá bên có nhu cầu và đầu mối liên hệ.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESC,
  alternates: { canonical: "/co-hoi" },
  openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: "/co-hoi", title: TITLE, description: DESC,
    images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }] },
};

type Props = { searchParams: Promise<Record<string, string | undefined>> };

export default async function PublicOppsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const q = sp.q ?? "", industry = sp.nganh ?? "", region = sp.khu_vuc ?? "";
  const page = Math.max(1, Number(sp.trang) || 1);
  const data = await fetchPublicOpps({ q, industry, region, page: String(page) });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const link = (p: number) => `/co-hoi?${new URLSearchParams(Object.entries({ q, nganh: industry, khu_vuc: region, trang: p > 1 ? String(p) : "" }).filter(([, v]) => v))}`;

  return (
    <section className="section pub-list">
      <div className="container">
        <div className="section-head" style={{ textAlign: "left", marginLeft: 0 }}>
          <span className="pill-tag">Cơ hội đang mở bán</span>
          <h1 className="h-display h2" style={{ marginTop: 14 }}>Cơ hội kinh doanh B2B <b>đã xác minh</b></h1>
          <p>Xem tóm tắt miễn phí. Tên bên có nhu cầu, chi tiết và đầu mối liên hệ mở khoá khi thành viên mua phiếu.</p>
        </div>

        <form className="pub-filter" action="/co-hoi" method="get">
          <input name="q" defaultValue={q} placeholder="Tìm theo mặt hàng, dịch vụ, mã CH-…" aria-label="Tìm cơ hội" />
          <select name="nganh" defaultValue={industry} aria-label="Ngành hàng">
            <option value="">Mọi ngành</option>
            {data?.industries.map((x) => <option key={x}>{x}</option>)}
          </select>
          <select name="khu_vuc" defaultValue={region} aria-label="Khu vực">
            <option value="">Mọi khu vực</option>
            {data?.regions.map((x) => <option key={x}>{x}</option>)}
          </select>
          <button className="btn btn-primary" type="submit">Lọc</button>
        </form>

        {!data ? (
          <p className="pub-empty">Không tải được danh sách cơ hội. Vui lòng thử lại sau ít phút.</p>
        ) : !data.items.length ? (
          <p className="pub-empty">Chưa có cơ hội phù hợp bộ lọc.</p>
        ) : (
          <>
            <p className="pub-count">{data.total} cơ hội</p>
            <div className="pub-grid">{data.items.map((o) => <PublicOppCard key={o.id} o={o} />)}</div>
            {pages > 1 ? (
              <nav className="pub-pager" aria-label="Phân trang">
                {page > 1 ? <a className="btn btn-outline btn-sm" href={link(page - 1)}>← Trước</a> : <span />}
                <span>Trang {page}/{pages}</span>
                {page < pages ? <a className="btn btn-outline btn-sm" href={link(page + 1)}>Sau →</a> : <span />}
              </nav>
            ) : null}
          </>
        )}

        <div className="pub-cta">
          <div><b>Muốn LeadScan tìm đúng cơ hội cho doanh nghiệp bạn?</b><span>Thành viên gửi yêu cầu tìm cơ hội, AI so khớp và chấm điểm riêng cho từng doanh nghiệp.</span></div>
          <a className="btn btn-primary" href="/#dang-ky">Đăng ký thành viên</a>
        </div>
      </div>
    </section>
  );
}
