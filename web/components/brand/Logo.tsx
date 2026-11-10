/**
 * Logo LeadScan theo Brand Kit v1.2 (xanh #004B87, chấm vàng #FFCD00) — luôn dùng file gốc trong public/brand, không vẽ lại.
 *   logo / logo-reverse   logo ngang (nền sáng / nền xanh hoặc tối), tối thiểu 100px chiều rộng
 *   logo-mono-blue        một màu xanh — dùng khi đặt trên nền vàng
 *   logo-mono-white       một màu trắng — ảnh tối, khắc, dập nổi
 *   mark / mark-reverse   biểu tượng đứng riêng (≥ 24px)
 *   mark-small            biểu tượng bản nhỏ (< 24px)
 * Không thêm "B2B" vào logo, không đổi màu chấm vàng, không đặt logo màu lên nền vàng (dùng bản mono-blue).
 */

const FILES = {
  logo: { src: "/brand/leadscan-logo.svg", ratio: 251.14 / 48 },
  "logo-reverse": { src: "/brand/leadscan-logo-reverse.svg", ratio: 251.14 / 48 },
  "logo-mono-blue": { src: "/brand/leadscan-logo-mono-blue.svg", ratio: 251.14 / 48 },
  "logo-mono-white": { src: "/brand/leadscan-logo-mono-white.svg", ratio: 251.14 / 48 },
  mark: { src: "/brand/leadscan-mark.svg", ratio: 1 },
  "mark-reverse": { src: "/brand/leadscan-mark-reverse.svg", ratio: 1 },
  "mark-small": { src: "/brand/leadscan-mark-small.svg", ratio: 1 },
} as const;

export type LogoVariant = keyof typeof FILES;

export function Logo({ variant = "logo", height = 24, className }: { variant?: LogoVariant; height?: number; className?: string }) {
  const f = FILES[variant];
  const width = Math.round(height * f.ratio * 100) / 100;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={f.src} alt="LeadScan" width={width} height={height} className={className} style={{ display: "block", flex: "none" }} />;
}
