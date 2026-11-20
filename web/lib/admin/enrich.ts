/** Phân hệ làm giàu dữ liệu doanh nghiệp theo MST — /api/admin/enrich/* */

import { useEffect, useState } from "react";

import { api } from "@/lib/admin/api";

export interface EnrichMeta {
  roles: Record<string, string>;
  purposes: Record<string, string>;
  fields: Record<string, string>;
  required_fields: string[];
  methods: Record<string, string>;
  job_statuses: Record<string, string>;
  run_statuses: Record<string, string>;
  signal_kinds: Record<string, string>;
  my_role: string | null;
  caps: string[];
}

export interface EnrichStats {
  total: number;
  by_field: Record<string, number>;
  full_profile: number;
  with_decision_maker: number;
  batches: number;
  listed: number;
  listed_full_board: number;
}

export interface CompanyListItem {
  mst: string;
  ten: string | null;
  tinh: string | null;
  trang_thai: string | null;
  nganh_nghe: string[] | null;
  missing: string[];
  updated_at: string;
}

export interface ProfileField {
  key: string;
  label: string;
  value: unknown;
  /** null khi trường chưa có bằng chứng */
  source: { code: string; name: string; trust: number | null } | null;
  source_url: string | null;
  method: string | null;
  is_inferred: boolean;
  fetched_at: string | null;
  evidence_count: number;
  agree: number;
  conflict: boolean;
  /** B08: điểm tin cậy 0–100; null khi chưa có bằng chứng */
  score: number | null;
  /** B13: quá hạn tái thu thập */
  stale: boolean;
  recrawl_days: number;
}

export interface Signal {
  kind: string;
  label: string;
  payload: Record<string, unknown>;
  day: string | null;
  source_code: string;
  source_name: string;
  source_url: string;
  detected_at: string;
}

export interface CompanyProfile {
  mst: string;
  ten: string | null;
  loai_hinh: string | null;
  fields: ProfileField[];
  missing_fields: string[];
  purposes: string[];
  batches: { id: number; name: string; purposes: string[]; created_at: string; row_no: number }[];
  changes: { field: string; label: string; old_value: string | null; new_value: string | null; source_code: string; detected_at: string }[];
  signals: Signal[];
  /** điện thoại / email chung của doanh nghiệp */
  contacts?: { kind: "phone" | "fax" | "email"; value: string; source_code: string; source_name: string }[];
  can: { people: boolean; evidence: boolean; add_people?: boolean };
  created_at: string;
}

// ------------------------------------------------------------------ giai đoạn 2: nguồn, vòng thu thập, thủ công, nhập file

export interface Source {
  code: string;
  name: string;
  kind: "http" | "manual" | "file" | "document" | "internal";
  domain: string;
  trust: number;
  enabled: boolean;
  legal_basis: string;
  min_interval_s: number;
  timeout_s: number;
  max_retries: number;
  recrawl_days: number;
  paused_reason: string;
  paused_at: string | null;
  errors_last_hour: number;
  requests_last_hour: number;
  updated_at: string;
}

export const SOURCE_KIND: Record<string, string> = {
  http: "Tự động",
  manual: "Tra cứu thủ công",
  file: "Nhập file",
  document: "Tài liệu công bố",
  internal: "Nội bộ",
};

export interface Ops {
  paused: { on: boolean; reason: string };
  window: { enabled: boolean; start: number; end: number };
  max_running: { per_connector: number };
  running_now: boolean;
  blocked_reason: string;
}

export interface RunConnector {
  connector: string;
  name: string;
  kind: string;
  enabled: boolean;
  paused_reason: string;
  total: number;
  done: number;
  not_found: number;
  failed: number;
  manual: number;
  skipped: number;
  remaining: number;
  eta_seconds: number;
}

export interface Run {
  id: number;
  name: string;
  connectors: RunConnector[];
  batch: { id: number; name: string } | null;
  status: string;
  totals: Record<"total" | "done" | "not_found" | "failed" | "manual" | "skipped" | "remaining", number>;
  eta_seconds: number;
  created_by: string | null;
  created_at: string;
  finished_at: string | null;
  errors?: { mst: string; connector: string; status: string; attempts: number; error: string; at: string | null }[];
}

export interface ManualTask {
  job_id: number;
  mst: string;
  connector: string;
  connector_name: string;
  lookup_url: string;
  hint: string;
  fields: { key: string; label: string; kind: "text" | "textarea" | "date" | "select"; options: string[] }[];
  current: Record<string, unknown>;
  remaining: number;
  run: { id: number; name: string } | null;
}

export interface OfficialReport {
  kind: string;
  total_rows: number;
  valid: number;
  matched: number;
  not_in_system: number;
  not_in_system_sample: string[];
  invalid: number;
  invalid_rows: { row: number; value: string; reason: string }[];
  columns: Record<string, string>;
  ignored_columns: string[];
  sensitive_columns: string[];
  sample?: Record<string, string | number>[];
  evidence?: number;
  duplicates?: number;
  people?: number;
  signals?: number;
  changes?: number;
}

export interface OfficialImport {
  id: number;
  kind: string;
  kind_name: string;
  file_name: string;
  source_url: string;
  data_date: string | null;
  note: string;
  report: OfficialReport;
  created_by: string | null;
  created_at: string;
}

/** 3725 → "1 giờ 2 phút" */
export function fmtDuration(seconds: number): string {
  if (!seconds || seconds < 60) return seconds ? "dưới 1 phút" : "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return [d ? `${d} ngày` : "", h ? `${h} giờ` : "", !d && m ? `${m} phút` : ""].filter(Boolean).join(" ");
}

export interface Evidence {
  id: number;
  field: string;
  label: string;
  value: string;
  source_code: string;
  source_name: string;
  trust: number | null;
  source_url: string;
  excerpt: string;
  method: string;
  is_inferred: boolean;
  batch: { id: number; name: string } | null;
  fetched_at: string;
  in_use: boolean;
  conflict: boolean;
}

/** Người liên quan — các trường vắng mặt là do vai trò không được xem. */
export interface Person {
  id?: number;
  ho_ten?: string;
  chuc_danh?: string;
  chuc_danh_chuan?: string;
  la_nguoi_quyet_dinh?: boolean;
  tu_ngay?: string | null;
  den_ngay?: string | null;
  lien_he?: { kind: string; value: string; is_inferred: boolean; verify_status: string }[];
  nam_sinh?: number | null;
  mst_ca_nhan?: string | null;
  bang_chung?: { field: string; value: string; source_url: string; fetched_at: string; method: string }[];
}

export interface ImportReport {
  total_rows: number;
  valid: number;
  duplicate_in_file: number;
  invalid: number;
  zero_padded: number;
  has_header: boolean;
  has_name_column: boolean;
  invalid_rows: { row: number; value: string; reason: string }[];
  duplicate_rows: { row: number; mst: string; first_row: number }[];
  existing: number;
  new: number;
  sample?: { row: number; mst: string; name: string; extra?: Record<string, string> }[];
  /** cột phụ nhận được theo tiêu đề (địa chỉ, điện thoại, nhóm sản phẩm, mã HS…) — lô cũ không có */
  columns?: { header: string; field: string; label: string; filled: number }[];
  ignored_columns?: string[];
  sensitive_columns?: string[];
  /** lô PROFIT500: số doanh nghiệp không có MST (không vào được phân hệ) */
  no_tax_code?: number;
  phones?: { ok: number; bad: number; bad_rows: { row: number; value: string; unreadable: string[] }[] };
}

export interface Batch {
  id: number;
  name: string;
  list_source: string;
  purposes: string[];
  note: string;
  file_name: string;
  mst_count: number;
  new_count: number;
  report: ImportReport;
  created_by: string | null;
  created_at: string;
}

export const MAX_FILE_MB = 10;

/** Đọc file thành base64 (không kèm tiền tố data:) để gửi trong JSON. */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(new Error("Không đọc được file."));
    r.readAsDataURL(file);
  });
}

export function useEnrichMeta(): { meta: EnrichMeta | null; error: string } {
  const [meta, setMeta] = useState<EnrichMeta | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get<EnrichMeta>("/enrich/meta").then(setMeta, (e) => setError(e instanceof Error ? e.message : "Không tải được."));
  }, []);
  return { meta, error };
}

export const pct = (n: number, total: number) => (total ? `${Math.round((n / total) * 1000) / 10}%` : "—");

/** Giá trị trường hồ sơ → chữ hiển thị. */
export function fmtValue(key: string, v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.join(" · ");
  if (typeof v === "boolean") return v ? "Có" : "Không";
  if (key === "von" && typeof v === "number") return `${v.toLocaleString("vi-VN")} đ`;
  if (key === "ngay_thanh_lap" && typeof v === "string") return new Date(v).toLocaleDateString("vi-VN");
  return String(v);
}

// ------------------------------------------------------------------ giai đoạn 3: doanh nghiệp niêm yết, tài liệu công bố

export interface ListedRow {
  mst: string;
  ten: string | null;
  ma_ck: string | null;
  board: number;
  exec: number;
  full: boolean;
  documents: number;
  needs_review: number;
  last_document_at: string | null;
}

export interface DocsMeta {
  types: Record<string, string>;
  statuses: Record<string, string>;
  groups: Record<string, string>;
}

export interface DocRow {
  id: number;
  mst: string;
  ten: string | null;
  ma_ck: string | null;
  doc_type: string;
  period: string;
  source_url: string;
  status: string;
  method: string;
  people_count: number;
  has_board: boolean;
  has_exec: boolean;
  error: string;
  created_by: string | null;
  created_at: string;
  parsed_at: string | null;
}

export interface DocPerson {
  ho_ten: string;
  chuc_danh: string;
  nhom: string;
  tu_ngay: string | null;
  den_ngay: string | null;
  confidence?: number;
  nguon_trich?: string;
}

export interface DocDetail extends DocRow {
  extracted: {
    people?: DocPerson[];
    approved_people?: DocPerson[];
    notes?: string[];
    cut_at?: string;
    has_board?: boolean;
    has_exec?: boolean;
    text_chars?: number;
  };
  reviewed_by: string | null;
  reviewed_at: string | null;
  file: { content_type: string; size: number; content_hash: string } | null;
}

export const DOC_STATUS_CLASS: Record<string, string> = {
  pending: "s-new",
  fetched: "s-new",
  parsed: "s-active",
  approved: "s-active",
  needs_review: "warn",
  rejected: "s-suspended",
  failed: "s-rejected",
};

// ------------------------------------------------------------------ giai đoạn 4: người, đồ thị quan hệ, nghi trùng

export interface PersonContact {
  id?: number;
  kind: string;
  value: string;
  is_inferred: boolean;
  verify_status: string;
  source_code?: string;
}

export interface PersonRoleRow {
  id: number;
  company_mst: string;
  company_ten: string | null;
  ma_ck: string | null;
  chuc_danh: string;
  chuc_danh_chuan: string;
  la_nguoi_quyet_dinh: boolean;
  tu_ngay: string | null;
  den_ngay: string | null;
  source_code: string;
}

export interface CandidateSide {
  id: number;
  ho_ten: string;
  nam_sinh?: number | null;
  mst_ca_nhan?: string | null;
  roles: { chuc_danh: string; company_mst: string; company_ten: string | null; den_ngay: string | null }[];
}

export interface Candidate {
  id: number;
  score: number;
  reasons: string[];
  status: string;
  a: CandidateSide;
  b: CandidateSide;
}

export interface EntityOpRow {
  id: number;
  op: "merge" | "split";
  person_id: number;
  other_person_id: number;
  note: string;
  created_at: string;
  undone_at: string | null;
}

export interface PersonProfile {
  id: number;
  merged_into_id?: number;
  ho_ten?: string;
  nam_sinh?: number | null;
  mst_ca_nhan?: string | null;
  lien_he?: PersonContact[];
  bang_chung?: { field: string; value: string; source_code: string; source_url: string; excerpt: string; method: string; is_inferred: boolean; fetched_at: string }[];
  roles?: PersonRoleRow[];
  candidates?: Candidate[];
  ops?: EntityOpRow[];
}

export interface GraphData {
  nodes: { id: string; type: "person" | "company"; label: string; person_id?: number; mst?: string; center?: boolean }[];
  edges: { from: string; to: string; label: string; active: boolean }[];
}

export const VERIFY_STATUS: Record<string, string> = {
  unverified: "Thu thập (chưa xác minh)",
  mx_ok: "Tên miền nhận thư (MX)",
};

// ------------------------------------------------------------------ giai đoạn 5: lọc, xuất, theo dõi, tuân thủ

export interface Condition {
  field: string;
  cmp: string;
  value?: unknown;
}

export interface FilterDef {
  op?: "and" | "or";
  q?: string;
  conditions?: (Condition | FilterDef)[];
}

export interface SearchMeta {
  fields: Record<string, { label: string; type: string; cmps: string[] }>;
  export_columns: Record<string, string>;
  alert_kinds: Record<string, string>;
}

export const CMP_LABEL: Record<string, string> = {
  contains: "chứa",
  not_contains: "không chứa",
  eq: "bằng",
  ne: "khác",
  starts: "bắt đầu bằng",
  regex: "khớp biểu thức chính quy",
  empty: "trống",
  not_empty: "có giá trị",
  in: "thuộc danh sách (phẩy)",
  gte: "≥",
  lte: "≤",
  is_true: "có",
  is_false: "không",
  has: "có tín hiệu",
};
export const NO_VALUE = new Set(["empty", "not_empty", "is_true", "is_false"]);

export interface SavedFilterRow {
  id: number;
  name: string;
  shared: boolean;
  definition: FilterDef;
  owner: string | null;
  mine: boolean;
  updated_at: string;
}

export interface WatchlistRow {
  id: number;
  name: string;
  shared: boolean;
  kinds: string[];
  email_digest: boolean;
  owner: string | null;
  mine: boolean;
  count: number;
  items?: { mst: string; added_at: string; ten: string | null; ma_ck: string | null; trang_thai: string | null }[];
}

export interface AlertRow {
  id: number;
  mst: string;
  ten: string | null;
  kind: string;
  kind_name: string;
  summary: string;
  read: boolean;
  created_at: string;
  watchlist_id: number | null;
}

export interface MarketReport {
  total: number;
  by_tinh: { key: string; count: number }[];
  by_nganh: { key: string; count: number }[];
  by_von: { key: string; count: number }[];
  by_trang_thai: { key: string; count: number }[];
  coverage: Record<string, number>;
  decision_maker: number;
}

export interface ExportLogRow {
  id: number;
  user: string;
  purpose: string;
  columns: string[];
  row_count: number;
  blocked_count: number;
  optout_count: number;
  include_inferred: boolean;
  includes_kho_b: boolean;
  status: string;
  expires_on: string | null;
  at: string;
}

export interface AccessLogRow {
  id: number;
  user: string;
  action: string;
  target: string;
  row_count: number;
  ip: string;
  at: string;
}

/** Tải file từ POST (xuất CSV): trả về tên file + số dòng / dòng bị chặn từ header. */
export async function postDownload(path: string, body: unknown): Promise<{ rows: number; blocked: number }> {
  const res = await fetch(`/api/admin${path}`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    let msg = "Không xuất được.";
    try { const d = await res.json(); if (typeof d.detail === "string") msg = d.detail; } catch {}
    throw new Error(msg);
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? "xuat.csv";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  return { rows: Number(res.headers.get("x-export-rows") ?? 0), blocked: Number(res.headers.get("x-export-blocked") ?? 0) };
}
