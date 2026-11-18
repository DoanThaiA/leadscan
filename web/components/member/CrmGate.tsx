"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Icon } from "@/components/admin/ui";
import { useMember } from "@/components/member/MemberContext";

const vnd = (n: number) => n.toLocaleString("vi-VN") + "đ";

/** CRM chỉ dành cho hạng Vàng: hạng Thường thấy giới thiệu + đường lên hạng thay cho nội dung. */
export function CrmGate({ children }: { children: ReactNode }) {
  const { me } = useMember();
  const t = me.company.tier;
  if (me.company.crm?.access) return <>{children}</>;
  if (t.key === "gold") { // hạng Vàng nhưng chưa nằm trong đợt chạy thử
    return (
      <>
        <div className="adm-head"><div><h1>CRM</h1><p>Theo dõi cơ hội đã mua đến khi chốt đơn</p></div></div>
        <section className="adm-card crm-gate">
          <div className="bd">
            <span className="crm-gate-ic"><Icon name="layers" /></span>
            <h2>Sắp có cho bạn</h2>
            <p className="muted">{me.company.crm?.reason || "CRM đang chạy thử với một số doanh nghiệp hạng Vàng."} Phiếu bạn đã mua sẽ có sẵn trong CRM khi mở.</p>
          </div>
        </section>
      </>
    );
  }
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>CRM</h1>
          <p>Theo dõi cơ hội đã mua đến khi chốt đơn</p>
        </div>
      </div>
      <section className="adm-card crm-gate">
        <div className="bd">
          <span className="crm-gate-ic"><Icon name="lock" /></span>
          <h2>CRM dành cho thành viên hạng Vàng</h2>
          <ul>
            <li>Mọi phiếu đã mua tự vào bảng theo dõi: Mới → Đang liên hệ → Có nhu cầu → Báo giá → Thắng / Thua</li>
            <li>Ghi chú, việc cần làm có hạn, giao việc cho đồng nghiệp</li>
            <li>Lịch sử chăm sóc đầy đủ cho từng cơ hội</li>
          </ul>
          <p className="muted">Nạp thêm <b>{vnd(t.to_gold)}</b> để lên hạng Vàng (tổng nạp từ {vnd(t.gold_threshold)}). Phiếu bạn đã mua sẽ có sẵn trong CRM.</p>
          <Link className="adm-btn primary" href="/thanh-vien/nap-tien">Nạp điểm lên hạng Vàng</Link>
        </div>
      </section>
    </>
  );
}

/** Thanh chuyển giữa Bảng pipeline và Việc cần làm */
export function CrmTabs({ active }: { active: "board" | "tasks" }) {
  return (
    <nav className="crm-tabs" aria-label="CRM">
      <Link href="/thanh-vien/crm" className={active === "board" ? "on" : undefined} aria-current={active === "board" ? "page" : undefined}>
        <Icon name="layers" size={15} /> Bảng pipeline
      </Link>
      <Link href="/thanh-vien/crm/viec" className={active === "tasks" ? "on" : undefined} aria-current={active === "tasks" ? "page" : undefined}>
        <Icon name="check" size={15} /> Việc cần làm
      </Link>
    </nav>
  );
}
