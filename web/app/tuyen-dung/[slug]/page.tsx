import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import ApplyBar from "@/components/careers/ApplyBar";
import ApplyForm from "@/components/careers/ApplyForm";
import { DeadlineTag, JobCardItem } from "@/components/careers/JobCardItem";
import { RichText } from "@/components/careers/RichText";
import { daysLeft, fmtDay, JOB_SECTIONS, JOB_TYPES, type JobPublic } from "@/lib/careers";
import { fetchJob, fetchJobs } from "@/lib/careers-server";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

const getJob = cache(fetchJob); // generateMetadata và trang dùng chung 1 lần gọi API

const SCHEMA_TYPE: Record<string, string> = {
  full_time: "FULL_TIME",
  part_time: "PART_TIME",
  intern: "INTERN",
  contract: "CONTRACTOR",
  remote: "FULL_TIME",
};

/** Bỏ ký hiệu định dạng (##, -, **) để đưa vào mô tả SEO / JSON-LD */
const plain = (s: string) => s.replace(/^#{2,3}\s+|^[-•*+]\s+|\*\*/gm, "").trim();

const shortHash = (s: string) => {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const job = await getJob((await params).slug);
  if (!job) return { title: "Không tìm thấy vị trí – LeadScan B2B" };
  const title = `Tuyển dụng ${job.title} – LeadScan B2B`;
  const description = (job.summary || job.subtitle || plain(job.description)).slice(0, 200);
  // Ảnh preview khi gửi link: luôn là JPG 1200×630 (xem og.jpg/route.ts). ?v đổi theo ảnh bìa để Zalo/Facebook lấy ảnh mới.
  const image = `/tuyen-dung/${job.slug}/og.jpg?v=${shortHash(job.cover_image ?? "")}`;
  return {
    title,
    description,
    alternates: { canonical: `/tuyen-dung/${job.slug}` },
    robots: job.is_open ? undefined : { index: false },
    openGraph: {
      type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: `/tuyen-dung/${job.slug}`, title, description,
      images: [{ url: image, width: 1200, height: 630, type: "image/jpeg", alt: `Tuyển dụng ${job.title}` }],
    },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

function jobPostingLd(job: JobPublic) {
  const site = process.env.NEXT_PUBLIC_SITE_URL ?? "https://leadscan.net";
  const html = JOB_SECTIONS.filter(([k]) => job[k])
    .map(([k, label]) => `<h3>${label}</h3><p>${escapeHtml(plain(job[k])).replace(/\n+/g, "<br>")}</p>`)
    .join("");
  return {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description: html || escapeHtml(job.summary),
    datePosted: job.published_at,
    ...(job.cover_image ? { image: new URL(job.cover_image, site).toString() } : {}),
    ...(job.deadline ? { validThrough: `${job.deadline}T23:59:59+07:00` } : {}),
    employmentType: SCHEMA_TYPE[job.employment_type] ?? "FULL_TIME",
    hiringOrganization: { "@type": "Organization", name: "LeadScan B2B", sameAs: site, logo: `${site}/brand/leadscan-logo-1200.png` },
    ...(job.employment_type === "remote" ? { jobLocationType: "TELECOMMUTE", applicantLocationRequirements: { "@type": "Country", name: "VN" } } : {}),
    jobLocation: { "@type": "Place", address: { "@type": "PostalAddress", streetAddress: job.location || "Việt Nam", addressCountry: "VN" } },
    ...(job.quantity ? { totalJobOpenings: job.quantity } : {}),
    directApply: true,
  };
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export default async function JobDetailPage({ params }: Props) {
  const { slug } = await params;
  const job = await getJob(slug);
  if (!job) notFound();
  const others = ((await fetchJobs()) ?? []).filter((j) => j.slug !== job.slug).slice(0, 3);
  const sections = JOB_SECTIONS.filter(([k]) => job[k]);
  const left = daysLeft(job.deadline);

  const info: [string, string, string][] = (
    [
      ["i-wallet", "Thu nhập", job.salary || "Thoả thuận"],
      ["i-layers", "Phòng ban", job.department],
      ["i-map", "Địa điểm", job.location],
      ["i-brief", "Hình thức", JOB_TYPES[job.employment_type] ?? job.employment_type],
      ["i-calc", "Thời gian làm việc", job.work_time],
      ["i-user", "Báo cáo trực tiếp", job.reports_to],
      ["i-users", "Số lượng", job.quantity ? `${job.quantity} người` : ""],
      ["i-clipboard", "Hạn nộp hồ sơ", job.deadline ? `${fmtDay(job.deadline)}${left !== null && left >= 0 && job.is_open ? ` (còn ${left} ngày)` : ""}` : ""],
    ] as [string, string, string][]
  ).filter(([, , v]) => v);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jobPostingLd(job)).replace(/</g, "\\u003c") }} />

      <section className="cr-dhero">
        <div className="container">
          <nav className="cr-crumb" aria-label="Breadcrumb">
            <a href="/">Trang chủ</a><span aria-hidden="true">/</span><a href="/tuyen-dung">Tuyển dụng</a><span aria-hidden="true">/</span><span aria-current="page">{job.title}</span>
          </nav>
          <div className="cr-dhero-tags">
            <span className="pill"><i className="cr-dot" aria-hidden="true" />LeadScan tuyển dụng</span>
            {job.department ? <span className="pill-tag">{job.department}</span> : null}
            {job.is_open ? <DeadlineTag deadline={job.deadline} /> : null}
          </div>
          <h1 className="h-display">{job.title}</h1>
          {job.subtitle ? <p className="cr-sub">{job.subtitle}</p> : null}
          <p className="cr-salary"><svg className="icon"><use href="#i-wallet" /></svg><span>Thu nhập: <b>{job.salary || "Thoả thuận"}</b></span></p>
          {job.is_open ? (
            <div className="cr-cta">
              <a href="#ung-tuyen" className="btn btn-primary">Ứng tuyển ngay <svg className="icon"><use href="#i-arrow" /></svg></a>
              <a href="#mo-ta" className="btn btn-outline">Xem mô tả công việc</a>
            </div>
          ) : (
            <div className="cr-closed" role="status"><svg className="icon"><use href="#i-info" /></svg>Vị trí này đã ngừng nhận hồ sơ. <a href="/tuyen-dung#vi-tri">Xem các vị trí đang tuyển →</a></div>
          )}
        </div>
      </section>

      {job.cover_image ? (
        <div className="container cr-cover">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={job.cover_image} alt={`Tuyển dụng ${job.title} – LeadScan`} fetchPriority="high" />
        </div>
      ) : null}

      <section className="cr-body" id="mo-ta">
        <div className="container cr-detail">
          <article className="cr-article">
            {sections.length ? (
              sections.map(([k, label], i) => (
                <section key={k} className="cr-sec">
                  <div className="cr-num" aria-hidden="true">{String(i + 1).padStart(2, "0")}</div>
                  <div className="cr-sec-bd">
                    <h2>{label}</h2>
                    <RichText text={job[k]} />
                  </div>
                </section>
              ))
            ) : (
              <p className="cr-sub">{job.summary || "Thông tin chi tiết đang được cập nhật."}</p>
            )}
          </article>

          <aside className="cr-aside">
            <div className="cr-info">
              <h3>Thông tin chung</h3>
              <dl>
                {info.map(([ic, label, value]) => (
                  <div key={label}>
                    <dt><svg className="icon"><use href={`#${ic}`} /></svg>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              {job.is_open ? <a href="#ung-tuyen" className="btn btn-primary">Ứng tuyển ngay</a> : null}
            </div>
          </aside>
        </div>
      </section>

      {job.is_open ? (
        <section className="section cr-apply" id="ung-tuyen">
          <div className="container reg-grid">
            <div className="reg-side">
              <span className="pill-tag">Ứng tuyển</span>
              <h2 className="h-display" style={{ marginTop: 16 }}>Sẵn sàng gia nhập? <b>Gửi hồ sơ ngay</b></h2>
              <p>Hồ sơ của bạn được chuyển thẳng tới bộ phận tuyển dụng LeadScan qua email.</p>
              <ol className="reg-next">
                <li><b>Gửi hồ sơ</b>Điền form bên cạnh kèm {job.cv_upload !== false ? "link hoặc file CV" : "link CV"}.</li>
                <li><b>Nhận email xác nhận</b>LeadScan gửi xác nhận đã nhận hồ sơ tới email của bạn.</li>
                <li><b>Phản hồi trong 3–5 ngày</b>Nếu phù hợp, chúng tôi liên hệ hẹn lịch phỏng vấn.</li>
              </ol>
              <div className="reg-trust">
                <span><svg className="icon"><use href="#i-shield" /></svg>Thông tin chỉ dùng cho mục đích tuyển dụng</span>
                <span><svg className="icon"><use href="#i-check" /></svg>Không thu bất kỳ khoản phí nào của ứng viên</span>
              </div>
            </div>
            <div className="form-card">
              <ApplyForm slug={job.slug} title={job.title} allowFile={job.cv_upload !== false} maxMb={job.cv_max_mb ?? 5} />
            </div>
          </div>
        </section>
      ) : null}

      {others.length ? (
        <section className="section cr-others">
          <div className="container">
            <div className="cr-head">
              <div>
                <span className="pill-tag">Cơ hội khác</span>
                <h2 className="h-display h2">Vị trí <b>khác đang tuyển</b></h2>
              </div>
              <a href="/tuyen-dung#vi-tri" className="link-arrow">Xem tất cả <svg className="icon" style={{ width: 16, height: 16 }}><use href="#i-arrow" /></svg></a>
            </div>
            <div className="cr-grid">
              {others.map((j) => <JobCardItem key={j.slug} job={j} />)}
            </div>
          </div>
        </section>
      ) : null}

      {job.is_open ? <ApplyBar salary={job.salary} /> : null}
    </>
  );
}
