/** Sự kiện: kiểu dữ liệu và nhãn dùng chung cho trang công khai /su-kien và trang quản trị. */

export const EVENT_STATUS: Record<string, string> = { draft: "Bản nháp", published: "Đang mở", closed: "Đã đóng" };
export const EVENT_STATUS_CLASS: Record<string, string> = { draft: "s-suspended", published: "s-active", closed: "s-rejected" };

export const ATTENDEE_TYPES: Record<string, string> = { member: "Thành viên CLB", guest: "Khách mời ngoài CLB" };

export const REG_STATUS: Record<string, string> = {
  new: "Chờ thanh toán",
  review: "Chờ đối soát",
  paid: "Đã thanh toán",
  cancelled: "Đã huỷ",
};
export const REG_STATUS_CLASS: Record<string, string> = {
  new: "s-new",
  review: "s-contacted",
  paid: "s-active",
  cancelled: "s-suspended",
};

export const OCR_STATUS: Record<string, string> = {
  none: "Chưa có ảnh",
  matched: "Khớp tự động",
  mismatch: "Không khớp",
  unreadable: "Không đọc được chữ",
  error: "Lỗi gọi OCR",
  off: "Chưa bật OCR",
};

/** Các mục nội dung theo thứ tự hiển thị (đánh số 01, 02… trên trang chi tiết) */
export const EVENT_SECTIONS = [
  ["intro", "Tổng quan chương trình"],
  ["agenda", "Chương trình chi tiết"],
  ["content", "Khung nội dung chia sẻ"],
  ["matching", "Kết nối giao thương"],
  ["notes", "Chuẩn bị & lưu ý"],
] as const;

export type EventSectionKey = (typeof EVENT_SECTIONS)[number][0];

/** Vé: total = null → không giới hạn chỗ. registered gồm cả vé bán ngoài form. */
export interface TicketStats {
  total: number | null;
  registered: number;
  remaining: number | null;
  sold_out: boolean;
}

export interface EventCard {
  slug: string;
  title: string;
  subtitle: string;
  summary: string;
  host: string;
  partner: string;
  starts_at: string | null; // giờ Việt Nam, không có hậu tố Z
  venue: string;
  address: string;
  deadline: string | null; // YYYY-MM-DD
  cover_image: string;
  fee_member: number;
  fee_guest: number;
  published_at: string | null;
  tickets?: TicketStats;
}

export interface EventPublic extends EventCard, Record<EventSectionKey, string> {
  status: string;
  ends_at: string | null;
  ticket_total: number | null;
  banner_image: string;
  fee_note: string;
  contact_name: string;
  contact_phone: string;
  updated_at: string;
  is_open: boolean;
  file_upload: boolean; // đã cấu hình Cloudflare R2 → cho đính kèm profile / nộp ảnh
  profile_max_mb: number;
  proof_max_mb: number;
  payment_ready: boolean; // đã có tài khoản nhận phí → vẽ được mã QR
  bank_name: string;
  account_name: string;
}

export interface EventAdmin extends Omit<EventPublic, "is_open" | "file_upload" | "profile_max_mb" | "proof_max_mb" | "payment_ready"> {
  id: number;
  site: string; // leadscan / c89 / epc
  bank_bin: string;
  account_no: string;
  notify_email: string;
  tickets_sold: number;
  tickets?: TicketStats & { web: number; offline: number };
  registrations: number;
  paid: number;
  created_at: string;
}

export interface EventAdminListItem {
  id: number;
  site: string;
  slug: string;
  status: string;
  title: string;
  partner: string;
  venue: string;
  starts_at: string | null;
  deadline: string | null;
  fee_member: number;
  fee_guest: number;
  registrations: number;
  paid: number;
  tickets?: TicketStats & { web: number; offline: number };
  updated_at: string;
}

export interface PaymentInfo {
  bank_bin: string;
  bank_name: string;
  account_no: string;
  account_name: string;
  amount: number;
  transfer_content: string;
  qr_payload: string;
  configured: boolean;
}

/** Trạng thái đơn đăng ký trả về cho khách sau khi gửi form / nộp ảnh */
export interface RegistrationState {
  code: string;
  status: string;
  amount: number;
  attendee_type: string;
  full_name: string;
  email: string;
  has_profile: boolean;
  has_proof: boolean;
  ocr_status: string;
  ocr_message: string;
  paid_at: string | null;
  payment: PaymentInfo;
}

export interface EventRegistration {
  id: number;
  site: string;
  event_id: number | null;
  event_slug: string | null;
  event_title: string;
  code: string;
  status: string;
  full_name: string;
  phone: string;
  email: string;
  company: string;
  position: string;
  attendee_type: string;
  needs: string;
  amount: number;
  profile_filename: string;
  profile_size: number;
  proof_filename: string;
  proof_size: number;
  proof_at: string | null;
  ocr_status: string;
  ocr_text: string;
  ocr_amount: number | null;
  ocr_checks: Record<string, boolean> | null;
  ocr_message: string;
  ocr_at: string | null;
  paid_at: string | null;
  checked_in: boolean;
  note: string;
  email_sent_at: string | null;
  created_at: string;
}

export interface EventsMeta {
  /** trang đang quản lý; null = nhân viên LeadScan xem tổng hợp mọi trang */
  scope: string | null;
  sites: Record<string, { name: string; url: string }>;
  event_email: string;
  mail_ready: boolean;
  storage_ready: boolean;
  ocr_ready: boolean;
  profile_max_mb: number;
  proof_max_mb: number;
  default_bank: { bank_bin: string; bank_name: string; account_no: string; account_name: string };
}

/** Còn ít chỗ → nhấn mạnh để khách đăng ký sớm: ≤ 10 chỗ hoặc ≤ 15% tổng */
export function ticketsLow(t: TicketStats | undefined): boolean {
  if (!t || t.total === null || t.remaining === null || t.sold_out) return false;
  return t.remaining <= 10 || t.remaining <= t.total * 0.15;
}

/** Phần trăm đã đăng ký (0–100) để vẽ thanh tiến độ */
export const ticketsPct = (t: TicketStats) => (t.total ? Math.min(100, Math.round((t.registered / t.total) * 100)) : 0);

/** Nhãn trang (cột "Trang" ở admin LeadScan): màu theo logo từng đơn vị */
export const SITE_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  leadscan: { label: "LeadScan", color: "#004B87", bg: "#EEF4FA" },
  c89: { label: "CEO 1989", color: "#0E873D", bg: "#EAF8EF" },
  epc: { label: "EPC", color: "#C9520C", bg: "#FEF1E8" },
};

/** Link công khai của sự kiện: ở cổng dùng đường dẫn tương đối, ở admin tổng hợp dùng tên miền của trang đăng */
export function eventPublicUrl(meta: EventsMeta | null, site: string, slug: string): string {
  const base = meta && meta.scope === null ? (meta.sites[site]?.url ?? "") : "";
  return `${base}/su-kien/${slug}`;
}

export const fmtVnd = (n: number) => `${(n || 0).toLocaleString("vi-VN")}đ`;

/** "2026-12-31" → "31/12/2026" */
export function fmtDay(d: string | null | undefined): string {
  if (!d) return "";
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y}`;
}

const WEEKDAYS = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];

/** "2026-12-02T14:00:00" → { day: "Thứ Tư, 02/12/2026", time: "14:00" } — giờ lưu sẵn theo giờ Việt Nam */
export function parseLocal(iso: string | null | undefined): { day: string; time: string; date: string } | null {
  if (!iso) return null;
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
  if (!m) return null;
  const [, y, mo, d, hh, mm] = m;
  const wd = WEEKDAYS[new Date(Date.UTC(+y, +mo - 1, +d)).getUTCDay()];
  return { day: `${wd}, ${d}/${mo}/${y}`, time: hh ? `${hh}:${mm}` : "", date: `${d}/${mo}/${y}` };
}

/** Khoảng thời gian: "Thứ Tư, 02/12/2026 · 14:00 – 20:30" */
export function fmtRange(start: string | null, end: string | null): string {
  const s = parseLocal(start);
  if (!s) return "";
  const e = parseLocal(end);
  const sameDay = e && end?.slice(0, 10) === start?.slice(0, 10);
  if (!e) return s.time ? `${s.day} · ${s.time}` : s.day;
  if (sameDay) return `${s.day} · ${s.time} – ${e.time}`;
  return `${s.day} ${s.time} – ${e.day} ${e.time}`;
}

/** Số ngày còn lại tới hạn đăng ký (theo giờ Việt Nam); null nếu không có hạn */
export function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
  return Math.round((Date.parse(deadline) - Date.parse(today)) / 86400000);
}

export const fmtSize = (n: number) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
