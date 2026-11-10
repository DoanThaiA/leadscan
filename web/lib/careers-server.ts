import type { JobCard, JobPublic } from "./careers";

// Trang /tuyen-dung render phía máy chủ (tốt cho SEO) → gọi thẳng FastAPI, không qua Nginx.
const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T | null> {
  const r = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`API ${path} → HTTP ${r.status}`);
  return (await r.json()) as T;
}

/** Danh sách vị trí đang mở; null nếu không gọi được API (trang vẫn hiển thị, báo thử lại sau). */
export async function fetchJobs(): Promise<JobCard[] | null> {
  try {
    return (await get<{ items: JobCard[] }>("/api/jobs"))?.items ?? [];
  } catch (e) {
    console.error("Không tải được danh sách tuyển dụng:", e);
    return null;
  }
}

/** Chi tiết vị trí; null = không có (404). Lỗi mạng thì ném lỗi để Next hiện trang lỗi. */
export function fetchJob(slug: string): Promise<JobPublic | null> {
  return get<JobPublic>(`/api/jobs/${encodeURIComponent(slug)}`);
}
