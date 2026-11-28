// Chi tiết sự kiện trên cổng c89 / epc: dùng chung trang của leadscan.net/su-kien/<slug>.
// API chỉ trả sự kiện của cổng đang xem (header x-leadscan-site), link tuyệt đối theo tên miền cổng.
export { default, generateMetadata } from "@/app/su-kien/[slug]/page";

export const dynamic = "force-dynamic";
