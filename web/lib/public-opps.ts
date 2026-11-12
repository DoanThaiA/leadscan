/** Cơ hội công khai (/co-hoi) — phần xem trước như thành viên chưa mua. Gọi thẳng FastAPI phía máy chủ (SEO, ảnh chia sẻ). */

export interface PublicOpp {
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
  enrich_round: number;
  max_buyers: number;
  sold_count: number;
  remaining: number;
  exclusive: boolean;
  sold_out: boolean;
  status: string;
  contact_count: number;
  price_from: number;
  published_at: string | null;
  attachment_counts?: { images: number; files: number };
}

export interface PublicOppList {
  total: number;
  page: number;
  page_size: number;
  items: PublicOpp[];
  industries: string[];
  regions: string[];
}

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T | null> {
  const r = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`API ${path} → HTTP ${r.status}`);
  return (await r.json()) as T;
}

export async function fetchPublicOpps(params: Record<string, string>): Promise<PublicOppList | null> {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  try {
    return await get<PublicOppList>(`/api/public/opportunities${qs ? `?${qs}` : ""}`);
  } catch (e) {
    console.error("Không tải được cơ hội công khai:", e);
    return null;
  }
}

export function fetchPublicOpp(code: string): Promise<PublicOpp | null> {
  return get<PublicOpp>(`/api/public/opportunities/${encodeURIComponent(code)}`);
}

export const vnd = (n: number) => n.toLocaleString("vi-VN") + "đ";

export function fmtDay(iso: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function daysLeft(iso: string | null): number | null {
  if (!iso) return null;
  const end = new Date(iso.slice(0, 10) + "T23:59:59+07:00").getTime();
  return Math.ceil((end - Date.now()) / 86_400_000);
}
