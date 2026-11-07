import { createApi } from "@/lib/api";

export { ApiError, errFields, errMsg, qs } from "@/lib/api";

/** API quản trị (/api/admin/*); hết phiên → chuyển tới /admin/login */
export const api = createApi("/api/admin", "/admin/login");
