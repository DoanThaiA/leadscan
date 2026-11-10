/** Tuyển dụng: kiểu dữ liệu và nhãn dùng chung cho trang công khai /tuyen-dung và trang quản trị. */

export const JOB_TYPES: Record<string, string> = {
  full_time: "Toàn thời gian",
  part_time: "Bán thời gian",
  intern: "Thực tập",
  contract: "Hợp đồng / Freelance",
  remote: "Làm việc từ xa",
};

export const JOB_STATUS: Record<string, string> = { draft: "Bản nháp", published: "Đang tuyển", closed: "Đã đóng" };
export const JOB_STATUS_CLASS: Record<string, string> = { draft: "s-suspended", published: "s-active", closed: "s-rejected" };

export const APP_STATUS: Record<string, string> = {
  new: "Mới nhận",
  reviewing: "Đang xem xét",
  interview: "Hẹn phỏng vấn",
  hired: "Đã tuyển",
  rejected: "Chưa phù hợp",
};
export const APP_STATUS_CLASS: Record<string, string> = {
  new: "s-new",
  reviewing: "s-contacted",
  interview: "s-contacted",
  hired: "s-active",
  rejected: "s-suspended",
};

/** Các mục nội dung theo thứ tự hiển thị (đánh số 01, 02… trên trang chi tiết) */
export const JOB_SECTIONS = [
  ["objective", "Mục tiêu công việc"],
  ["description", "Mô tả công việc"],
  ["requirements", "Yêu cầu ứng viên"],
  ["benefits", "Quyền lợi"],
  ["how_to_apply", "Cách thức ứng tuyển"],
] as const;

export type JobSectionKey = (typeof JOB_SECTIONS)[number][0];

export interface JobCard {
  slug: string;
  title: string;
  department: string;
  location: string;
  employment_type: string;
  salary: string;
  quantity: number | null;
  deadline: string | null; // YYYY-MM-DD
  summary: string;
  published_at: string | null;
}

export interface JobPublic extends JobCard, Record<JobSectionKey, string> {
  status: string;
  subtitle: string;
  work_time: string;
  reports_to: string;
  updated_at: string;
  is_open: boolean;
  cv_upload?: boolean; // đã cấu hình Cloudflare R2 → cho tải file CV
  cv_max_mb?: number;
}

export interface JobAdmin extends Omit<JobPublic, "is_open" | "cv_upload" | "cv_max_mb"> {
  id: number;
  apply_email: string;
  applications: number;
  created_at: string;
}

export interface JobAdminListItem {
  id: number;
  slug: string;
  status: string;
  title: string;
  department: string;
  location: string;
  employment_type: string;
  salary: string;
  deadline: string | null;
  applications: number;
  applications_new: number;
  updated_at: string;
}

export interface JobApplication {
  id: number;
  job_id: number | null;
  job_slug: string | null;
  job_title: string;
  status: string;
  full_name: string;
  phone: string;
  email: string;
  cv_url: string;
  portfolio_url: string;
  intro: string;
  cv_filename: string;
  cv_size: number;
  note: string;
  email_sent_at: string | null;
  created_at: string;
}

export interface JobsMeta {
  recruit_email: string;
  mail_ready: boolean;
  cv_max_mb: number;
  storage_ready: boolean;
}

/** "2026-12-31" → "31/12/2026" */
export function fmtDay(d: string | null | undefined): string {
  if (!d) return "";
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y}`;
}

/** Số ngày còn lại tới hạn nộp (theo giờ Việt Nam); null nếu không có hạn */
export function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
  return Math.round((Date.parse(deadline) - Date.parse(today)) / 86400000);
}

export const fmtSize = (n: number) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
