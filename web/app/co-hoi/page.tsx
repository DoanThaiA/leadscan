import type { Metadata } from "next";

import PublicOppCard from "@/components/public-opp/OppCard";
import { fetchPublicOpps } from "@/lib/public-opps";

export const dynamic = "force-dynamic";

const TITLE = "Cơ hội kinh doanh B2B đang mở bán – LeadScan";
const DESC = "Nhu cầu mua hàng, dự án, nhà máy mới đã được LeadScan kiểm duyệt và chấm điểm. Xem tóm tắt miễn phí, mua phiếu để mở khoá bên có nhu cầu và đầu mối liên hệ.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESC,
  alternates: { canonical: "/co-hoi" },
  openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: "/co-hoi", title: TITLE, description: DESC,
    images: [{ url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "LeadScan B2B" }] },
};

type Props = { searchParams: Promise<Record<string, string | undefined>> };

const STEPS: [string, string, string][] = [
  ["search", "Xem trước miễn phí", "Ngành, khu vực, quy mô, hạn chót, độ tin cậy nguồn — đủ để biết cơ hội có đáng theo hay không."],
  ["user", "Đăng ký thành viên", "Khoảng 1 phút. Phí 89.000đ/năm được cộng đủ thành điểm trong ví để mua phiếu."],
  ["ticket", "Mua phiếu, mở khoá đầu mối", "Tên bên có nhu cầu, mô tả chi tiết, người liên hệ, tài liệu kèm — chủ động liên hệ trước đối thủ."],
];

export default async function PublicOppsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const q = sp.q ?? "", industry = sp.nganh ?? "", region = sp.khu_vuc ?? "";
  const page = Math.max(1, Number(sp.trang) || 1);
  const data = await fetchPublicOpps({ q, industry, region, page: String(page) });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const href = (o: Record<string, string>) =>
    `/co-hoi?${new URLSearchParams(Object.entries({ q, nganh: industry, khu_vuc: region, ...o }).filter(([, v]) => v))}`;
  const filtered = Boolean(q || industry || region);

  return (
    <>
      <section className="pub-hero">
        <div className="container">
          <span className="pub-live"><i />{data ? `${data.stats.open} cơ hội đang mở bán` : "Cơ hội đang mở bán"}</span>
          <h1 className="h-display">Khách hàng đang cần mua — <b>bạn có muốn là người liên hệ đầu tiên?</b></h1>
          <p className="pub-hero-sub">Nhu cầu mua hàng, dự án, nhà máy mới đã được LeadScan kiểm duyệt và chấm điểm. Xem tóm tắt miễn phí, mua phiếu để mở khoá bên có nhu cầu và đầu mối liên hệ.</p>

          <form className="pub-filter" action="/co-hoi" method="get">
            <label className="pub-q">
              <svg className="icon"><use href="#i-search" /></svg>
              <input name="q" defaultValue={q} placeholder="Tìm theo mặt hàng, dịch vụ, mã CH-…" aria-label="Tìm cơ hội" />
            </label>
            <select name="nganh" defaultValue={industry} aria-label="Ngành hàng">
              <option value="">Mọi ngành</option>
              {data?.industries.map((x) => <option key={x}>{x}</option>)}
            </select>
            <select name="khu_vuc" defaultValue={region} aria-label="Khu vực">
              <option value="">Mọi khu vực</option>
              {data?.regions.map((x) => <option key={x}>{x}</option>)}
            </select>
            <button className="btn btn-primary" type="submit">Tìm cơ hội</button>
          </form>

          {data ? (
            <ul className="pub-stats">
              <li><b>{data.stats.open}</b><span>cơ hội đang mở</span></li>
              <li><b>{data.stats.new_7d}</b><span>mới trong 7 ngày</span></li>
              <li><b>{data.stats.industries}</b><span>ngành hàng</span></li>
              <li><b>0đ</b><span>để xem trước</span></li>
            </ul>
          ) : null}
        </div>
      </section>

      <section className="pub-list">
        <div className="container">
          {data && data.chips.length > 1 ? (
            <nav className="pub-chips" aria-label="Lọc nhanh theo ngành">
              <a className={!industry ? "on" : undefined} href={href({ nganh: "", trang: "" })}>Tất cả</a>
              {data.chips.map(([name, n]) => (
                <a key={name} className={industry === name ? "on" : undefined} href={href({ nganh: name, trang: "" })}>{name}<span>{n}</span></a>
              ))}
            </nav>
          ) : null}

          {!data ? (
            <p className="pub-empty">Không tải được danh sách cơ hội. Vui lòng thử lại sau ít phút.</p>
          ) : !data.items.length ? (
            <div className="pub-empty">
              <b>Chưa có cơ hội phù hợp bộ lọc.</b>
              <span>Thành viên có thể gửi yêu cầu tìm cơ hội — LeadScan quét và báo khi có cơ hội khớp.</span>
              {filtered ? <a className="btn btn-outline btn-sm" href="/co-hoi">Xem tất cả cơ hội</a> : null}
            </div>
          ) : (
            <>
              <p className="pub-count">
                {filtered ? <>Tìm thấy <b>{data.total}</b> cơ hội</> : <><b>{data.total}</b> cơ hội đang mở bán · mới nhất trước</>}
              </p>
              <div className="pub-grid">{data.items.map((o) => <PublicOppCard key={o.id} o={o} />)}</div>
              {pages > 1 ? (
                <nav className="pub-pager" aria-label="Phân trang">
                  {page > 1 ? <a className="btn btn-outline btn-sm" href={href({ trang: page - 1 > 1 ? String(page - 1) : "" })}>← Trước</a> : <span />}
                  <span>Trang {page}/{pages}</span>
                  {page < pages ? <a className="btn btn-outline btn-sm" href={href({ trang: String(page + 1) })}>Sau →</a> : <span />}
                </nav>
              ) : null}
            </>
          )}

          <div className="pub-how">
            <h2 className="h-display">Từ xem trước tới <b>chốt khách hàng</b> trong 3 bước</h2>
            <ol>
              {STEPS.map(([icon, t, d], i) => (
                <li key={t}>
                  <span className="pub-how-ic"><svg className="icon"><use href={`#i-${icon}`} /></svg></span>
                  <small>Bước {i + 1}</small>
                  <b>{t}</b>
                  <p>{d}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="cta pub-band">
        <div className="cta-dots" />
        <div className="container cta-grid">
          <h2>Không thấy đúng cơ hội? <b>Để LeadScan <em>tìm cho bạn</em>.</b></h2>
          <p>Thành viên gửi yêu cầu tìm cơ hội theo ngành, khu vực, quy mô. AI quét đa nguồn, so khớp và chấm điểm phù hợp riêng cho doanh nghiệp bạn.</p>
          <div className="cta-actions">
            <a className="btn btn-primary" href="/#dang-ky">Đăng ký thành viên</a>
            <a className="btn btn-ghost" href="/thanh-vien/dang-nhap">Đã là thành viên? Đăng nhập</a>
          </div>
        </div>
      </section>
    </>
  );
}
