import type { Metadata } from "next";

import JobBoard from "@/components/careers/JobBoard";
import { fetchJobs } from "@/lib/careers-server";

export const dynamic = "force-dynamic"; // luôn lấy danh sách mới nhất từ API

const DESC =
  "Gia nhập LeadScan B2B – nền tảng dùng AI tìm, làm giàu và chấm điểm cơ hội kinh doanh cho doanh nghiệp. Xem các vị trí đang tuyển và ứng tuyển trực tuyến.";

const OG_IMAGE = { url: "/brand/leadscan-og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: "Tuyển dụng LeadScan B2B" };

export const metadata: Metadata = {
  title: "Tuyển dụng – LeadScan B2B",
  description: DESC,
  alternates: { canonical: "/tuyen-dung" },
  openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: "/tuyen-dung", title: "Tuyển dụng – LeadScan B2B", description: DESC, images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", images: [OG_IMAGE.url] },
};

const WHY = [
  ["i-bot", "Làm sản phẩm AI thực chiến", "Trực tiếp xây và vận hành nền tảng dùng AI để tìm, làm giàu và chấm điểm cơ hội kinh doanh cho doanh nghiệp Việt."],
  ["i-users", "Đội ngũ tinh gọn", "Ý tưởng tốt được thử ngay. Bạn thấy rõ tác động của mình lên sản phẩm và khách hàng mỗi tuần."],
  ["i-book", "Học nhanh, lớn nhanh", "Tiếp xúc dữ liệu thị trường B2B đa ngành, được đào tạo và trang bị công cụ để phát triển chuyên môn."],
  ["i-shield", "Minh bạch & ghi nhận", "Mục tiêu rõ ràng, đánh giá theo kết quả; thu nhập và thưởng tương xứng với đóng góp."],
] as const;

const STEPS = [
  ["Gửi hồ sơ", "Điền form ứng tuyển ngay trên trang vị trí, kèm link hoặc file CV. Chỉ mất khoảng 2 phút."],
  ["Sàng lọc", "Bộ phận tuyển dụng xem hồ sơ và phản hồi trong 3–5 ngày làm việc nếu bạn phù hợp."],
  ["Phỏng vấn", "Trao đổi chuyên môn với quản lý trực tiếp, online hoặc tại văn phòng."],
  ["Nhận việc", "Nhận thư mời làm việc và cùng thống nhất ngày bắt đầu."],
] as const;

export default async function CareersPage() {
  const jobs = await fetchJobs();
  const n = jobs?.length ?? 0;
  const depts = [...new Set((jobs ?? []).map((j) => j.department).filter(Boolean))].slice(0, 4);

  return (
    <>
      <section className="cr-hero">
        <div className="container cr-hero-grid">
          <div>
            <span className="pill"><i className="cr-dot" aria-hidden="true" />Gia nhập LeadScan</span>
            <h1 className="h-display">Cùng LeadScan <b>đưa đúng cơ hội tới đúng doanh nghiệp</b></h1>
            <p className="cr-lead">
              Chúng tôi tìm những đồng đội chủ động, ham học và thích làm việc với dữ liệu – cùng xây nền tảng giúp doanh nghiệp B2B tìm khách hàng nhanh hơn bằng AI.
            </p>
            <div className="cr-cta">
              <a href="#vi-tri" className="btn btn-primary">Xem vị trí đang tuyển <svg className="icon"><use href="#i-arrow" /></svg></a>
              <a href="#vi-sao" className="btn btn-outline">Vì sao chọn LeadScan</a>
            </div>
          </div>

          <div className="cr-art" aria-hidden="true">
            <div className="card cr-art-main">
              <small>Đang tuyển</small>
              <strong>{n > 0 ? `${n} vị trí` : "Sắp mở"}</strong>
              <div className="chips">
                {(depts.length ? depts : ["Kinh doanh", "Công nghệ", "Dữ liệu & AI"]).map((d) => <span key={d} className="chip on">{d}</span>)}
              </div>
            </div>
            <div className="card cr-art-row">
              <span className="cr-art-ic"><svg className="icon"><use href="#i-spark" /></svg></span>
              <div><b>Sản phẩm AI cho doanh nghiệp</b><small>Scan · Enrich · Scoring cơ hội B2B</small></div>
            </div>
            <div className="card cr-art-row">
              <span className="cr-art-ic green"><svg className="icon"><use href="#i-check" /></svg></span>
              <div><b>Phản hồi trong 3–5 ngày</b><small>Quy trình tuyển dụng 4 bước, rõ ràng</small></div>
            </div>
          </div>
        </div>
      </section>

      <section className="section cr-jobs" id="vi-tri">
        <div className="container">
          <div className="cr-head">
            <div>
              <span className="pill-tag">Vị trí đang tuyển</span>
              <h2 className="h-display h2">{n > 0 ? <><b>{n} vị trí</b> đang mở</> : <>Vị trí <b>đang tuyển</b></>}</h2>
            </div>
            <p>Bấm vào từng vị trí để xem mô tả công việc, quyền lợi và gửi hồ sơ trực tuyến.</p>
          </div>

          {jobs === null ? (
            <div className="cr-empty">
              <svg className="icon"><use href="#i-info" /></svg>
              <h3>Chưa tải được danh sách vị trí</h3>
              <p>Vui lòng tải lại trang sau ít phút.</p>
            </div>
          ) : n === 0 ? (
            <div className="cr-empty">
              <svg className="icon"><use href="#i-brief" /></svg>
              <h3>Hiện LeadScan chưa mở vị trí mới</h3>
              <p>Các vị trí mới sẽ được cập nhật tại đây – bạn quay lại sau nhé.</p>
            </div>
          ) : (
            <JobBoard jobs={jobs} />
          )}
        </div>
      </section>

      <section className="section audience" id="vi-sao">
        <div className="container">
          <div className="section-head">
            <span className="pill-tag">Làm việc tại LeadScan</span>
            <h2 className="h-display h2">Vì sao chọn <b>LeadScan</b></h2>
          </div>
          <div className="aud-grid">
            {WHY.map(([ic, t, d]) => (
              <div className="aud" key={t}>
                <div className="ic"><svg className="icon"><use href={`#${ic}`} /></svg></div>
                <h3>{t}</h3>
                <p>{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-head">
            <span className="pill-tag">Quy trình</span>
            <h2 className="h-display h2">Tuyển dụng <b>4 bước, rõ ràng</b></h2>
          </div>
          <ol className="cr-steps">
            {STEPS.map(([t, d], i) => (
              <li key={t}>
                <span className="cr-step-n">{String(i + 1).padStart(2, "0")}</span>
                <h3>{t}</h3>
                <p>{d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="cta">
        <div className="cta-dots" />
        <div className="container cta-grid">
          <h2>Chưa thấy vị trí phù hợp? <b>Hãy tìm hiểu LeadScan trước.</b></h2>
          <p>Xem cách LeadScan dùng AI để giúp doanh nghiệp tìm cơ hội kinh doanh – và quay lại khi có vị trí dành cho bạn.</p>
          <div className="cta-actions">
            <a href="/" className="btn btn-primary">Tìm hiểu LeadScan <svg className="icon"><use href="#i-arrow" /></svg></a>
            {n > 0 ? <a href="#vi-tri" className="btn btn-ghost">Xem lại vị trí đang tuyển</a> : null}
          </div>
        </div>
      </section>
    </>
  );
}
