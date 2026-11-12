/** Cơ hội đối tác gửi — kiểu dữ liệu & nhãn dùng chung cho cổng đối tác và trang quản trị. */

export type SubStatus = "submitted" | "verifying" | "duplicate" | "rejected" | "verified" | "supplement" | "published";

export interface Submission {
  id: number;
  code: string;
  status: SubStatus;
  status_label: string;
  company_name: string;
  tax_code: string;
  province: string;
  industry: string;
  kind: string;
  kind_label: string;
  need: string;
  scale: string;
  timing: string;
  source_type: string;
  source_label: string;
  source_url: string;
  certainty: string;
  certainty_label: string;
  evidence: string;
  contact_name: string;
  contact_title: string;
  contact_phone: string;
  contact_email: string;
  can_connect: string;
  reject_reason: string;
  reject_label: string;
  partner_note: string;
  score: number | null;
  sla_due_at: string | null;
  decided_at: string | null;
  published_at: string | null;
  created_at: string;
  sold_count: number;
  earned: number;
  share_until: string | null;
  share_expired: boolean;
  events?: { kind: string; content: string; created_at: string; actor?: string | null }[];
}

export interface SubPage {
  total: number;
  page: number;
  page_size: number;
  items: Submission[];
  counts: Partial<Record<SubStatus, number>>;
}

export interface SubOptions {
  industries: string[];
  regions: string[];
  kinds: Record<string, string>;
  sources: Record<string, string>;
  certainty: Record<string, string>;
  statuses: Record<SubStatus, string>;
}

/** Màu nhãn trạng thái — dùng lại class adm-badge s-* có sẵn trong admin.css */
export const SUB_BADGE: Record<SubStatus, string> = {
  submitted: "new",
  verifying: "contacted",
  verified: "active",
  supplement: "active",
  published: "active",
  duplicate: "suspended",
  rejected: "rejected",
};

/** Ý nghĩa từng trạng thái cho đối tác (brief mục 4) */
export const SUB_MEANING: Record<SubStatus, string> = {
  submitted: "Chờ LeadScan tiếp nhận.",
  verifying: "Đang kiểm tra trùng, xác minh và chấm điểm (khoảng 2 ngày làm việc).",
  duplicate: "Cơ hội đã có trong CSDL hoặc đối tác khác gửi trước — không được thưởng.",
  rejected: "Chưa đạt: thông tin sai, không xác minh được hoặc điểm chất lượng dưới 60.",
  verified: "Đạt xác minh — thông tin đúng, mới, điểm ≥ 60. LeadScan đang hoàn thiện phiếu để mở bán.",
  supplement: "Cơ hội đã có, nhưng thông tin bạn bổ sung có giá trị — được ghi nhận Đóng góp bổ sung.",
  published: "Phiếu đang bán trên LeadScan. Mỗi lượt bán được chia hoa hồng.",
};

export const SUB_FLOW: SubStatus[] = ["submitted", "verifying", "verified", "published"];
