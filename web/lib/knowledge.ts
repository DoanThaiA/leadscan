/** Kho doanh nghiệp (knowledge_companies) — danh sách đầu vào để AI quét. */

export const AI_STATUS: Record<string, string> = {
  pending: "Chờ quét",
  done: "Đã quét",
  error: "Lỗi",
  skip: "Bỏ qua",
};

export const AI_STATUS_CLASS: Record<string, string> = {
  pending: "s-new",
  done: "s-active",
  error: "s-rejected",
  skip: "s-suspended",
};

export const KNOWLEDGE_SOURCE: Record<string, string> = {
  manual: "Nhập tay",
  profit500: "PROFIT500",
};

export interface KnowledgeListItem {
  id: number;
  name: string;
  tax_code: string | null;
  industry: string;
  province: string;
  rank: number | null;
  rank_year: number | null;
  source: string;
  ai_status: string;
  updated_at: string;
}

export interface KnowledgeCompany extends KnowledgeListItem {
  name_en: string;
  stock_code: string;
  address: string;
  phone: string;
  fax: string;
  email: string;
  website: string;
  founded_year: number | null;
  ceo_name: string;
  description: string;
  logo_url: string;
  rank_label: string;
  rank_list: string;
  source_id: string | null;
  source_url: string;
  extra: Record<string, string>;
  crawled_at: string | null;
  ai_scanned_at: string | null;
  ai_note: string;
  note: string;
  created_at: string;
}
