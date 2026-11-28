import type { EventCard, EventPublic } from "./events";

// Trang /su-kien render phía máy chủ (tốt cho SEO) → gọi thẳng FastAPI, không qua Nginx.
const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T | null> {
  const r = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`API ${path} → HTTP ${r.status}`);
  return (await r.json()) as T;
}

/** Sự kiện đang mở đăng ký; null nếu không gọi được API (trang vẫn hiển thị, báo thử lại sau). */
export async function fetchEvents(): Promise<EventCard[] | null> {
  try {
    return (await get<{ items: EventCard[] }>("/api/events"))?.items ?? [];
  } catch (e) {
    console.error("Không tải được danh sách sự kiện:", e);
    return null;
  }
}

/** Chi tiết sự kiện; null = không có (404). Lỗi mạng thì ném lỗi để Next hiện trang lỗi. */
export function fetchEvent(slug: string): Promise<EventPublic | null> {
  return get<EventPublic>(`/api/events/${encodeURIComponent(slug)}`);
}
