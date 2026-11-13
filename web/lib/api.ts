/** Client gọi API backend. Cookie phiên đăng nhập là HttpOnly nên trình duyệt tự gửi kèm. */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

/** Chuyển tới trang đăng nhập, nhớ trang đang xem (?next=) để đăng nhập xong quay lại đúng chỗ (kể cả ?ma=… của khuyến mãi). */
export function goLogin(loginPath: string) {
  if (typeof window === "undefined") return;
  location.replace(`${loginPath}?next=${encodeURIComponent(location.pathname + location.search)}`);
}

export const isUnauthorized = (e: unknown) => e instanceof ApiError && e.status === 401;

export function createApi(base: string, loginPath: string) {
  async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        method,
        credentials: "same-origin",
        cache: "no-store",
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "Không kết nối được máy chủ. Kiểm tra mạng và thử lại.");
    }
    if (res.status === 204) return undefined as T;
    let data: { detail?: unknown; fields?: Record<string, string> } & Record<string, unknown> = {};
    try {
      data = await res.json();
    } catch {}
    if (!res.ok) {
      if (res.status === 401 && !path.startsWith("/auth/")) goLogin(loginPath);
      const msg = typeof data.detail === "string" ? data.detail : "Có lỗi xảy ra, vui lòng thử lại.";
      throw new ApiError(res.status, msg, data.fields ?? {});
    }
    return data as T;
  }

  return {
    get: <T>(path: string) => request<T>("GET", path),
    post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
    patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
    put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
    del: <T = void>(path: string) => request<T>("DELETE", path),
  };
}

export function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "Có lỗi xảy ra, vui lòng thử lại.");
export const errFields = (e: unknown) => (e instanceof ApiError ? e.fields : {});
