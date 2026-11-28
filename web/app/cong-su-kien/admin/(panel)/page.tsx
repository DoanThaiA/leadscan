import { redirect } from "next/navigation";

// /admin của cổng → thẳng vào danh sách sự kiện (cổng chỉ quản lý sự kiện)
export default function PortalAdminHome() {
  redirect("/admin/su-kien");
}
