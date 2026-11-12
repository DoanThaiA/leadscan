/** Nút "quay về" ở trang chi tiết phiếu cơ hội: về đúng trang người dùng vừa bấm vào phiếu
 *  (Cơ hội phù hợp — kể cả đúng yêu cầu tìm đang mở, Kho, Phiếu đã mua, Tổng quan…), không cố định "Tất cả cơ hội". */

const KEY = "mt-opp-back";
const DETAIL = /^\/thanh-vien\/co-hoi\/(\d+)(?:[?#]|$)/;

const LABELS: [string, string][] = [
  ["/thanh-vien/phu-hop", "Cơ hội phù hợp"],
  ["/thanh-vien/kho", "Kho của tôi"],
  ["/thanh-vien/phieu", "Phiếu đã mua"],
  ["/thanh-vien/co-hoi", "Tất cả cơ hội"],
];
export const DEFAULT_BACK = { href: "/thanh-vien/co-hoi", label: "Tất cả cơ hội" };

/** Gắn ở layout cổng thành viên (bắt sự kiện click): ghi lại trang hiện tại khi bấm vào 1 phiếu cơ hội. */
export function rememberOppSource(e: MouseEvent) {
  const a = (e.target as Element | null)?.closest?.("a[href]");
  const href = a?.getAttribute("href") ?? "";
  const m = DETAIL.exec(href);
  if (!m || DETAIL.test(location.pathname)) return;
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ id: m[1], from: location.pathname + location.search }));
  } catch {}
}

/** Trang chi tiết phiếu `id`: link + nhãn để quay về trang trước (mặc định Tất cả cơ hội). */
export function oppBackLink(id: string): { href: string; label: string } {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? "null") as { id: string; from: string } | null;
    if (v && v.id === id && v.from.startsWith("/thanh-vien")) {
      const path = v.from.split("?")[0];
      const label = path === "/thanh-vien" ? "Tổng quan" : LABELS.find(([p]) => path.startsWith(p))?.[1];
      if (label) return { href: v.from, label };
    }
  } catch {}
  return DEFAULT_BACK;
}
