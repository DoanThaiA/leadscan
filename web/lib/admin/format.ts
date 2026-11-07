const dtf = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const df = new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", year: "numeric" });

export const fmtDateTime = (iso: string | null | undefined) => (iso ? dtf.format(new Date(iso)) : "—");
export const fmtDate = (iso: string | null | undefined) => (iso ? df.format(new Date(iso)) : "—");
export const fmtNum = (n: number) => n.toLocaleString("vi-VN");

/** "3 phút trước", "2 giờ trước", "hôm qua", hoặc ngày cụ thể */
export function fromNow(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "vừa xong";
  if (s < 3600) return `${Math.floor(s / 60)} phút trước`;
  if (s < 86400) return `${Math.floor(s / 3600)} giờ trước`;
  if (s < 172800) return "hôm qua";
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} ngày trước`;
  return fmtDate(iso);
}
