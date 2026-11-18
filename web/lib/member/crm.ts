/** CRM Lite hạng Vàng — kiểu dữ liệu khớp backend app/routes/member_crm.py */

export type StageKey = "new" | "contacting" | "interested" | "quoted" | "won" | "lost";
export interface Stage { key: StageKey; label: string }
export interface Person { id: number; full_name: string }

export interface Lead {
  id: number;
  stage: StageKey;
  stage_label: string;
  owner: Person | null;
  opportunity_id: number;
  code: string;
  title: string;
  industry: string;
  province: string;
  buyer_name: string;
  score: number;
  price: number;
  refunded: boolean;
  open_tasks: number;
  next_due: string | null;
  overdue: boolean;
  created_at: string;
  updated_at: string;
}

export interface Board {
  stages: Stage[];
  leads: Lead[]; // tối đa per_stage thẻ mỗi cột (mới cập nhật trước); tìm kiếm thì trả hết kết quả
  counts: Record<StageKey, number>;
  total: number;
  overdue: number; // số lead có việc quá hạn
  per_stage: number;
  members: Person[];
  me: number;
}

export interface Note { id: number; content: string; author: Person | null; created_at: string }
export interface Task {
  id: number;
  lead_id: number;
  title: string;
  due_date: string | null;
  overdue: boolean;
  assignee: Person | null;
  done: boolean;
  done_at: string | null;
  created_at: string;
  lead?: { id: number; code: string; title: string; stage: StageKey };
}
export interface CrmEvent { id: number; kind: string; content: string; actor: Person | null; created_at: string }

export interface OppContact { full_name: string; title?: string; phone?: string; email?: string; note?: string }
export interface LeadDetail {
  lead: Lead;
  opportunity: {
    code: string; title: string; summary?: string; detail?: string; industry?: string; province?: string; scale?: string;
    estimated_value?: string; deadline?: string | null; buyer_name?: string; source_url?: string; contacts?: OppContact[];
  };
  notes: Note[];
  tasks: Task[];
  events: CrmEvent[];
  stages: Stage[];
  members: Person[];
  ai: { budget: AiBudget; summary: AiRun | null; draft: AiRun | null };
}

export interface AiBudget { enabled: boolean; budget_usd: number; spent_usd: number; remaining_pct: number; exhausted: boolean; resets_at: string }
export interface AiRun { id: number; kind: "summary" | "draft"; result: string; member: Person | null; created_at: string }
export type DraftChannel = "email" | "zalo" | "call";
export const CHANNELS: { key: DraftChannel; label: string }[] = [
  { key: "email", label: "Email" },
  { key: "zalo", label: "Zalo / chat" },
  { key: "call", label: "Kịch bản gọi điện" },
];

/** "2026-11-18" → "18/11" (năm khác năm nay thì thêm năm) */
export function fmtDue(d: string | null): string {
  if (!d) return "";
  const [y, m, day] = d.split("-");
  return y === String(new Date().getFullYear()) ? `${day}/${m}` : `${day}/${m}/${y}`;
}

export const todayIso = () => {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
};
