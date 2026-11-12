import { createApi } from "@/lib/api";

export { ApiError, errFields, errMsg, qs } from "@/lib/api";

/** API cổng đối tác (/api/partner/*); hết phiên → chuyển tới trang đăng nhập đối tác */
export const papi = createApi("/api/partner", "/doi-tac/dang-nhap");

export interface PartnerMe {
  id: number;
  code: string;
  email: string;
  full_name: string;
  phone: string;
  phone_verified: boolean;
  phone_verified_at: string | null;
  kind: "personal" | "org";
  kind_label: string;
  org_name: string;
  org_tax_code: string;
  industries: string[];
  regions: string[];
  tier: string;
  tier_label: string;
  created_at: string;
  otp_resend_after?: number;
}

export interface OtpSent {
  sent: boolean;
  phone?: string;
  resend_after?: number;
  ttl_minutes?: number;
}

export interface WalletSummary {
  pending: number;
  available: number;
  withdrawing: number;
  paid: number;
  total: number;
  month: number;
  cafe_quota: number;
  cafe_used: number;
  cafe_left: number;
  rate: number;
}

export interface Credit {
  id: number;
  kind: string;
  kind_label: string;
  amount: number;
  state: "pending" | "available" | "void";
  state_label: string;
  note: string;
  submission: { id: number; code: string; company_name: string } | null;
  available_at: string | null;
  created_at: string;
  // chỉ có ở trang quản trị
  calc?: Record<string, number | string> | null;
  purchase_id?: number | null;
  actor?: string | null;
}

/** Mức thưởng đang áp dụng (GET /api/partner/reward-config) */
export interface RewardConfig {
  cafe: number;
  mode: "max" | "sum";
  rate: number;
  rate_silver: number;
  rate_large: number;
  rate_max: number;
  hold_days: number;
  months: number;
  quota_new: number;
  quota_silver: number;
  min_withdraw: number;
  payout_days: string;
  tax_threshold: number;
  tax_rate: number;
}

export interface PayoutProfile {
  legal_name: string;
  id_masked: string;
  tax_code: string;
  bank_bin: string;
  bank_name: string;
  account_masked: string;
  account_holder: string;
  name_match: boolean;
  updated_at: string;
  shared_with?: string[]; // chỉ trang quản trị
}

export interface Withdrawal {
  id: number;
  code: string;
  status: "requested" | "approved" | "paid" | "rejected" | "cancelled";
  status_label: string;
  amount: number;
  tax_withheld: number;
  net_amount: number;
  bank_name: string;
  account_masked: string;
  holder: string;
  invoice_no: string;
  tax_cert_no: string;
  reject_reason: string;
  batch: { code: string; pay_date: string } | null;
  created_at: string;
  approved_at: string | null;
  paid_at: string | null;
}

export interface WithdrawRules {
  min: number;
  max: number;
  tax_threshold: number;
  tax_rate: number;
  withholds_tax: boolean;
  needs_invoice: boolean;
  next_pay_date: string;
  pay_days: number[];
  month_count: number;
  month_max: number;
  can_request: boolean;
  reason: string;
}
