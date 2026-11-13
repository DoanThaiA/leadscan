import Link from "next/link";

import type { MemberTier } from "@/components/member/MemberContext";

const vnd = (n: number) => n.toLocaleString("vi-VN") + "đ";

/** Nhãn hạng thành viên: Thường / Vàng. */
export function TierBadge({ t, small }: { t: MemberTier; small?: boolean }) {
  return (
    <span className={`mt-tier ${t.key}${small ? " sm" : ""}`} title={t.key === "gold" ? "Hạng Vàng — được mua độc quyền phiếu cơ hội" : "Hạng Thường"}>
      {t.key === "gold" ? "★ " : ""}Hạng {t.label}
    </span>
  );
}

/** Thẻ hạng: tổng đã nạp, tiến độ lên hạng Vàng và quyền lợi. */
export function TierCard({ t }: { t: MemberTier }) {
  const pct = Math.min(100, Math.round((t.topup_total / Math.max(1, t.gold_threshold)) * 100));
  const mult = t.exclusive_multiplier.toLocaleString("vi-VN");
  return (
    <section className={`adm-card mt-tier-card ${t.key}`}>
      <div className="bd" style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <small className="muted">Hạng thành viên</small>
          <TierBadge t={t} />
        </div>
        <div className="mt-tier-total">Tổng đã nạp <b>{vnd(t.topup_total)}</b></div>
        {t.key === "gold" ? (
          <p className="mt-tier-perk">Bạn được <b>mua độc quyền</b> phiếu cơ hội chưa ai mua với giá ×{mult}: chỉ mình doanh nghiệp bạn có thông tin, không đối thủ nào mua được nữa.</p>
        ) : (
          <>
            <span className="bar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span>
            <p className="mt-tier-perk">
              Nạp thêm <b>{vnd(t.to_gold)}</b> để lên <b>hạng Vàng</b> (tổng nạp từ {vnd(t.gold_threshold)}): được mua độc quyền phiếu cơ hội với giá ×{mult}.
            </p>
            <Link className="adm-btn sm" href="/thanh-vien/nap-tien" style={{ justifySelf: "start" }}>Nạp điểm</Link>
          </>
        )}
      </div>
    </section>
  );
}

