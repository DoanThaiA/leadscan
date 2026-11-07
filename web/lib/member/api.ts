import { createApi } from "@/lib/api";

export { ApiError, errFields, errMsg, qs } from "@/lib/api";

/** API cổng thành viên (/api/member/*); hết phiên → chuyển tới trang đăng nhập thành viên */
export const mapi = createApi("/api/member", "/thanh-vien/dang-nhap");
