/** Kiểu dữ liệu & định dạng dùng chung cho cổng thành viên và admin (ví, đơn, cơ hội, phiếu). */

export interface Invoice {
  id: number;
  company_name: string;
  tax_code: string;
  address: string;
  buyer_name: string;
  receive_email: string;
  note: string;
  status: "pending" | "issued";
  invoice_number: string;
  email_sent_at: string | null;
  issued_at: string | null;
  created_at: string;
  /** "member" = khách gửi form · "auto" = hệ thống tự lấy thông tin doanh nghiệp khi thanh toán */
  source: "member" | "auto";
  /** Hoá đơn điện tử IAM: mẫu số + ký hiệu (vd 1C26TYY), trạng thái IAM, lỗi lần gọi gần nhất */
  einvoice_serial: string;
  einvoice_status: string;
  einvoice_error: string;
  einvoice_at: string | null;
}

export interface Order {
  id: number;
  code: string;
  kind: "membership" | "topup";
  amount: number;
  points: number;
  status: "pending" | "paid" | "expired" | "cancelled";
  provider: string;
  paid_amount: number | null;
  paid_at: string | null;
  expires_at: string;
  created_at: string;
  note: string;
  invoice: Invoice | null;
}

export interface PaymentInfo {
  provider: string;
  configured: boolean;
  bank_name: string;
  account_no: string;
  account_name: string;
  amount: number;
  transfer_content: string;
  qr_payload: string | null;
  // Chỉ có khi provider = "mcv" (cổng thanh toán MCV)
  payment_code?: string | null;
  mcv_status?: McvStatus | null;
  checkout_url?: string | null;
  expires_at?: string | null;
  test_mode?: boolean;
  can_simulate?: boolean;
  error?: string;
}

export type McvStatus = "pending" | "paid" | "expired" | "needs_attention" | "failed";

export interface Tx {
  id: number;
  kind: string;
  amount: number;
  balance_after: number;
  note: string;
  created_at: string;
  actor?: { id: number; full_name: string } | null;
}

export interface OppContact {
  id: number;
  full_name: string;
  title: string;
  phone: string;
  email: string;
  note: string;
}

/** Ảnh / tài liệu của phiếu cơ hội (lưu trên Cloudflare R2; link xem/tải ký sẵn, hết hạn sau ~15 phút) */
export interface Attachment {
  id: number;
  filename: string;
  content_type: string;
  size: number;
  kind: "image" | "file";
  width: number | null;
  height: number | null;
  caption: string;
  status: "pending" | "ready";
  url: string | null; // ảnh: xem trực tiếp
  thumb_url: string | null; // ảnh nhỏ
  download_url: string | null; // tải về
}

export interface AttachConfig {
  configured: boolean;
  max_files: number;
  image_max_mb: number;
  file_max_mb: number;
  image_exts: string[];
  file_exts: string[];
}

export const fmtBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / 1024 / 1024).toFixed(n < 10 * 1024 * 1024 ? 1 : 0).replace(".", ",")} MB`;

export interface Opp {
  id: number;
  code: string;
  title: string;
  summary: string;
  industry: string;
  province: string;
  region: string;
  source_type: string;
  scale: string;
  estimated_value: string;
  deadline: string | null;
  score: number;
  score_fit: number;
  score_urgency: number;
  score_trust: number;
  enrich_round: number;
  price: number;
  max_buyers: number;
  sold_count: number;
  published_at: string | null;
  contact_count: number;
  purchased: boolean;
  saved?: boolean; // đã thêm vào kho của thành viên
  saved_at?: string;
  sold_out: boolean;
  is_new?: boolean; // cơ hội mới khớp phiếu tìm, khách chưa xem
  reasons?: string[]; // vì sao cơ hội phù hợp với doanh nghiệp (điểm & giá là của riêng doanh nghiệp)
  match_count?: number; // chỉ ở admin: số doanh nghiệp được cơ hội khớp
  // chỉ có sau khi mua (hoặc ở admin)
  buyer_name?: string;
  detail?: string;
  source_url?: string;
  contacts?: OppContact[];
  attachments?: Attachment[]; // chỉ ở admin (phiếu đầy đủ)
  status?: "draft" | "published" | "closed";
  created_at?: string;
  updated_at?: string;
}

/** Tiêu chí "Cơ hội phù hợp" của thành viên */
export interface Criteria {
  industries: string[];
  regions: string[];
  sizes: string[];
  sources: string[];
  min_score: number;
}

/** Yêu cầu "Enrich tìm kiếm cơ hội" thành viên gửi cho LeadScan */
export interface SearchReq {
  id: number;
  criteria: Partial<Criteria>;
  note: string;
  status: "open" | "rejected"; // open = tìm kiếm liên tục
  reply: string;
  created_at: string;
  resolved_at: string | null;
  match_count?: number; // số cơ hội phù hợp với phiếu
  new_count?: number; // cơ hội mới phù hợp chưa xem
  match_status?: "pending" | "running" | "done" | "error"; // so khớp chạy nền
  matched_at?: string | null;
}

/** Phiếu còn đang được hệ thống so khớp (chạy nền) */
export const isMatching = (r: SearchReq) => r.match_status === "pending" || r.match_status === "running";

/** Phiếu tìm cơ hội tìm kiếm liên tục: cơ hội mới mở bán khớp phiếu sẽ tự thêm vào và báo cho khách */
export const SEARCH_STATUS: Record<SearchReq["status"], string> = { open: "Tìm kiếm liên tục", rejected: "Từ chối" };
export const SEARCH_STATUS_CLASS: Record<SearchReq["status"], string> = { open: "sr-live", rejected: "s-suspended" };

/** Thông báo trong cổng thành viên: cơ hội mới phù hợp với phiếu tìm cơ hội */
export interface MemberNotice {
  id: number;
  kind: "match";
  created_at: string;
  read: boolean;
  score: number;
  request: { id: number; note: string } | null;
  opportunity: { id: number; code: string; title: string; industry: string; province: string };
}

/** Tóm tắt tiêu chí thành danh sách nhãn ngắn để hiển thị */
export function criteriaTags(c: Partial<Criteria>): string[] {
  return [
    ...(c.industries ?? []),
    ...(c.regions ?? []),
    ...(c.sizes ?? []),
    ...(c.sources ?? []),
    ...(c.min_score ? [`≥ ${c.min_score} điểm`] : []),
  ];
}

export interface EnrichReq {
  id: number;
  note: string;
  status: "open" | "done" | "rejected";
  reply: string;
  created_at: string;
  resolved_at: string | null;
}

export const ORDER_STATUS: Record<Order["status"], string> = {
  pending: "Chờ thanh toán",
  paid: "Đã thanh toán",
  expired: "Hết hạn",
  cancelled: "Đã huỷ",
};
export const ORDER_STATUS_CLASS: Record<Order["status"], string> = {
  pending: "s-contacted",
  paid: "s-active",
  expired: "s-suspended",
  cancelled: "s-suspended",
};
export const ORDER_KIND: Record<Order["kind"], string> = { membership: "Phí thành viên", topup: "Nạp điểm" };
export const TX_KIND: Record<string, string> = {
  membership: "Phí thành viên",
  topup: "Nạp điểm",
  purchase: "Mua phiếu",
  refund: "Hoàn điểm",
  adjust: "Điều chỉnh",
};
export const ENRICH_STATUS: Record<EnrichReq["status"], string> = { open: "Đang xử lý", done: "Đã xong", rejected: "Từ chối" };
export const OPP_STATUS: Record<string, string> = { draft: "Nháp", published: "Đang bán", closed: "Đã đóng" };

export const fmtVnd = (n: number | null | undefined) => `${(n ?? 0).toLocaleString("vi-VN")}đ`;
export const fmtPts = (n: number | null | undefined) => `${(n ?? 0).toLocaleString("vi-VN")} điểm`;

/** Hạng theo điểm chất lượng — dùng cho nhãn màu */
export function scoreClass(score: number) {
  if (score >= 85) return "sc-hi";
  if (score >= 70) return "sc-md";
  return "sc-lo";
}
