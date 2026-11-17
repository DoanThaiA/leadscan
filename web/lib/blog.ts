/** Cẩm nang (blog SEO) — kiểu dữ liệu, gọi API phía máy chủ, tiện ích chung cho trang công khai và trình soạn admin. */

export interface ArticleCard {
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  cover_image: string;
  published_at: string | null;
  updated_at: string | null;
  reading_minutes: number;
}

export interface Article extends ArticleCard {
  seo_title: string;
  body: string;
  author_name: string;
  related: ArticleCard[];
}

export interface ArticleList {
  total: number;
  page: number;
  page_size: number;
  items: ArticleCard[];
  categories: [string, number][];
}

export interface ArticleAdmin extends Omit<Article, "related"> {
  id: number;
  status: string;
  created_at: string;
  is_live: boolean;
}

export const ARTICLE_STATUS: Record<string, string> = { draft: "Bản nháp", published: "Đã đăng" };

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T | null> {
  const r = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`API ${path} → HTTP ${r.status}`);
  return (await r.json()) as T;
}

/** Danh sách bài đã đăng; null nếu API lỗi (trang vẫn hiện, báo thử lại). */
export async function fetchArticles(params: Record<string, string>): Promise<ArticleList | null> {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  try {
    return await get<ArticleList>(`/api/articles${qs ? `?${qs}` : ""}`);
  } catch (e) {
    console.error("Không tải được cẩm nang:", e);
    return null;
  }
}

export function fetchArticle(slug: string): Promise<Article | null> {
  return get<Article>(`/api/articles/${encodeURIComponent(slug)}`);
}

/** "Tìm khách hàng B2B" → "tim-khach-hang-b2b" (id tiêu đề mục lục, tham số chủ đề) */
export function slugify(s: string): string {
  return s
    .replace(/đ/g, "d").replace(/Đ/g, "D")
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export const fmtDate = (iso: string | null) =>
  iso ? new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Asia/Ho_Chi_Minh" }).format(new Date(iso)) : "";

/** Bỏ ký hiệu định dạng → chữ thuần (mục lục, mô tả tự sinh) */
export const plain = (s: string) => s.replace(/!\[[^\]]*\]\([^)]*\)/g, "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*/g, "").trim();

/** Mục lục từ các dòng "## " */
export function articleToc(body: string): { id: string; text: string }[] {
  const seen = new Map<string, number>();
  return body.split("\n").flatMap((l) => {
    const m = l.trim().match(/^##\s+(.*)$/);
    if (!m) return [];
    const text = plain(m[1]);
    let id = slugify(text) || "muc";
    const n = seen.get(id) ?? 0;
    seen.set(id, n + 1);
    if (n) id = `${id}-${n + 1}`;
    return [{ id, text }];
  });
}
