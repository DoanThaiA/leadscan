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
}

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
  sold_out: boolean;
  // chỉ có sau khi mua (hoặc ở admin)
  buyer_name?: string;
  detail?: string;
  source_url?: string;
  contacts?: OppContact[];
  status?: "draft" | "published" | "closed";
  created_at?: string;
  updated_at?: string;
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
