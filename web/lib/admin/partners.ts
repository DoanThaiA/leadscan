import type { Credit, PartnerMe, PayoutProfile, Withdrawal, WalletSummary } from "@/lib/partner/api";
import type { PartnerImage, Submission } from "@/lib/partner/submissions";

export interface AdminPartner extends PartnerMe {
  status: "active" | "locked";
  status_label: string;
  last_login_at: string | null;
  flags?: string[];
}

/** Cờ gian lận (/partner-reports/fraud) — chỉ là dấu hiệu, quản trị viên xem xét rồi khoá hoặc bỏ qua. */
export interface FraudFlag {
  key: string;
  type: string;
  severity: "high" | "medium";
  label: string;
  detail: string;
  status: "open" | "reviewed";
  review: { note: string; detail: string; actor: string | null; created_at: string } | null;
  partners: { id: number; code: string; full_name: string; status: string }[];
}

export interface AdminPartnerDetail extends Omit<AdminPartner, "flags"> {
  note: string;
  terms_version: string;
  terms_accepted_at: string | null;
  signup_ip: string;
  submissions: { total: number; ok: number; pass_rate: number | null; by_status: Record<string, number> };
  custom_rate: number | null;
  custom_cafe_quota: number | null;
  wallet: WalletSummary;
  payout_profile: PayoutProfile | null;
  flags: FraudFlag[];
  events: { id: number; kind: string; content: string; actor: string | null; created_at: string }[];
}

export interface PartnerPage {
  total: number;
  page: number;
  page_size: number;
  items: AdminPartner[];
  counts: { all: number; unverified: number };
}


export interface DupHint {
  type: "opportunity" | "submission";
  id: number;
  code: string;
  title: string;
  match: "tax" | "name";
  same_group: boolean;
  created_at: string;
  partner_id?: number;
  status?: string;
  similarity?: number; // độ giống nhu cầu 0–100 (cơ hội gửi trước khi có so theo nhu cầu: không có)
  relation?: "same" | "similar" | "different";
  relation_label?: string;
  basis?: string[];
}

export interface AdminSubmission extends Submission {
  partner: { id: number; code: string; full_name: string; phone: string; tier: string; kind: string; org_name: string };
  auto_score: number;
  final_score: number | null;
  dup_count: number;
  dup_strong: boolean;
  dup_same?: number; // số cơ hội trùng nhu cầu (cùng doanh nghiệp)
  dup_similar?: number; // gần giống / trùng mô tả khác tên doanh nghiệp
  is_large: boolean;
  assigned_to: { id: number; full_name: string } | null;
  overdue: boolean;
  decided_by: string | null;
}

export interface AdminSubmissionDetail extends AdminSubmission {
  contact_consent: boolean;
  tax_lookup: { name: string; status: string; active: boolean } | null;
  score_detail: { label: string; points: number }[];
  internal_note: string;
  dup_hints: DupHint[];
  dup_live: DupHint[];
  opportunity: { id: number; code: string; status: string; title: string } | null;
  partner_stats: { total: number; ok: number; pass_rate: number | null; by_status: Record<string, number> };
  events: { kind: string; content: string; actor: string | null; created_at: string }[];
  credits: Credit[];
  images: PartnerImage[];
}

export interface SubmissionQueue {
  total: number;
  page: number;
  page_size: number;
  items: AdminSubmission[];
  counts: Record<string, number>;
  queue: number;
  overdue: number;
}

export interface SubmissionMeta {
  statuses: Record<string, string>;
  kinds: Record<string, string>;
  sources: Record<string, string>;
  certainty: Record<string, string>;
  reject_reasons: Record<string, string>;
  min_score: number;
  dup_days: number;
}

export interface AdminWithdrawal extends Withdrawal {
  partner: { id: number; code: string; full_name: string; kind: string; status: string };
  legal_name: string;
  tax_code: string;
  bank_ref: string;
  note: string;
  name_match: boolean;
  shared_with: string[];
  profile_changed: boolean;
  needs_invoice: boolean;
}

export interface PayoutBatch {
  id: number;
  code: string;
  pay_date: string;
  status: "draft" | "exported" | "paid";
  status_label: string;
  count: number;
  gross: number;
  tax: number;
  net: number;
  exported_at: string | null;
  paid_at: string | null;
  created_at: string;
  items?: AdminWithdrawal[];
}
