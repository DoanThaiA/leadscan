"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/admin/ui";
import type { MemberTier } from "@/components/member/MemberContext";

const vnd = (n: number) => n.toLocaleString("vi-VN") + "đ";
const HIDE_KEY = "ls_gold_banner_hide_until";
const HIDE_DAYS = 7;

/** Quyền lợi hạng Vàng — chỉ ghi những gì hệ thống thật sự có */
function perks(t: MemberTier) {
  const mult = t.exclusive_multiplier.toLocaleString("vi-VN");
  return [
    { icon: "lock", title: "Mua độc quyền", text: `Phiếu chưa ai mua: giá ×${mult}, chỉ mình bạn có thông tin, đối thủ không mua được nữa.` },
    { icon: "layers", title: "CRM theo dõi đến khi chốt", text: "Mọi phiếu đã mua vào bảng pipeline, ghi chú, việc cần làm, email nhắc việc 8:00." },
    { icon: "spark", title: "Trợ lý AI", text: "Tóm tắt công ty cần mua và soạn sẵn lời mời qua email, Zalo hoặc kịch bản gọi." },
  ];
}

/** Banner hạng Vàng trên trang Tổng quan: chưa Vàng → mời lên hạng (ẩn được 7 ngày); đã Vàng → dải lối tắt tới quyền lợi. */
export function GoldBanner({ t, membershipActive }: { t: MemberTier; membershipActive: boolean }) {
  const [hidden, setHidden] = useState(true); // mặc định ẩn tới khi đọc xong lựa chọn của người dùng (tránh nháy)

  useEffect(() => {
    let until = 0;
    try {
      until = Number(localStorage.getItem(HIDE_KEY) || 0);
    } catch {}
    setHidden(Date.now() < until);
  }, []);

  if (t.key === "gold") {
    return (
      <section className="mt-gold-strip" aria-label="Quyền lợi hạng Vàng">
        <span className="mt-gold-star" aria-hidden="true">★</span>
        <div className="mt-gold-strip-text">
          <b>Bạn đang ở hạng Vàng</b>
          <span>Dùng quyền lợi của bạn để chốt cơ hội trước đối thủ.</span>
        </div>
        <div className="mt-gold-strip-links">
          <Link className="adm-btn sm" href="/thanh-vien/phu-hop"><Icon name="lock" size={14} /> Mua độc quyền</Link>
          <Link className="adm-btn sm" href="/thanh-vien/crm"><Icon name="layers" size={14} /> Mở CRM</Link>
        </div>
      </section>
    );
  }

  if (!membershipActive || hidden) return null; // chưa kích hoạt thành viên: banner phí thành viên ở trên đã đủ

  const pct = Math.min(100, Math.round((t.topup_total / Math.max(1, t.gold_threshold)) * 100));
  function hide() {
    try {
      localStorage.setItem(HIDE_KEY, String(Date.now() + HIDE_DAYS * 86400_000));
    } catch {}
    setHidden(true);
  }

  return (
    <section className="mt-gold" aria-labelledby="gold-title">
      <button type="button" className="mt-gold-close" onClick={hide} aria-label={`Ẩn trong ${HIDE_DAYS} ngày`} title={`Ẩn trong ${HIDE_DAYS} ngày`}>×</button>
      <div className="mt-gold-main">
        <span className="mt-gold-kicker"><span aria-hidden="true">★</span> Hạng Vàng</span>
        <h2 id="gold-title">Chốt cơ hội trước đối thủ với hạng Vàng</h2>
        <p>Nạp tổng từ {vnd(t.gold_threshold)} là lên hạng ngay, giữ hạng mãi mãi. Số tiền nạp vẫn thành điểm để mua phiếu.</p>
        <ul className="mt-gold-perks">
          {perks(t).map((p) => (
            <li key={p.title}>
              <span className="ic"><Icon name={p.icon} size={16} /></span>
              <div><b>{p.title}</b><span>{p.text}</span></div>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-gold-side">
        <div className="mt-gold-progress">
          <div className="row"><span>Đã nạp</span><b>{vnd(t.topup_total)}</b></div>
          <span className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Tiến độ lên hạng Vàng"><i style={{ width: `${pct}%` }} /></span>
          <div className="row small"><span>{pct}%</span><span>Mốc {vnd(t.gold_threshold)}</span></div>
        </div>
        <p className="mt-gold-need">Còn <b>{vnd(t.to_gold)}</b> nữa</p>
        <Link className="adm-btn primary mt-gold-cta" href={`/thanh-vien/nap-tien?loai=topup&so-tien=${t.to_gold}`}>
          Nạp {vnd(t.to_gold)} để lên Vàng
        </Link>
        <button type="button" className="mt-gold-later" onClick={hide}>Để sau</button>
      </div>
    </section>
  );
}
