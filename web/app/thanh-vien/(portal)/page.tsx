"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/admin/ui";
import { useMember } from "@/components/member/MemberContext";
import { OppCard } from "@/components/member/OppCard";
import { fmtDate, fromNow } from "@/lib/admin/format";
import { fmtPts, type Opp } from "@/lib/commerce";
import { errMsg, mapi } from "@/lib/member/api";

interface Dash {
  purchased_count: number;
  points_spent: number;
  pending_orders: number;
  recent_purchases: { id: number; price: number; created_at: string; opportunity: Opp }[];
  new_opportunities: Opp[];
}

export default function MemberHome() {
  const { me } = useMember();
  const [d, setD] = useState<Dash | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Tổng quan · LeadScan B2B";
    mapi.get<Dash>("/dashboard").then(setD, (e) => setError(errMsg(e)));
  }, []);

  const c = me.company;
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Xin chào, {me.full_name}</h1>
          <p>{c.name} · <span className="mono">{c.code}</span></p>
        </div>
        <div className="adm-actions">
          <Link className="adm-btn" href="/thanh-vien/nap-tien">Nạp điểm</Link>
          <Link className="adm-btn primary" href="/thanh-vien/co-hoi">Vào kho cơ hội</Link>
        </div>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        <div className="adm-card adm-stat">
          <small>Số dư điểm</small>
          <b>{c.points_balance.toLocaleString("vi-VN")}</b>
          <span>1 điểm = 1đ</span>
        </div>
        <div className="adm-card adm-stat">
          <small>Hạn thành viên</small>
          <b style={{ fontSize: 22 }}>{c.membership_expires_at ? fmtDate(c.membership_expires_at) : "—"}</b>
          <span style={{ color: c.membership_active ? "var(--ok)" : "var(--danger)" }}>{c.membership_active ? "Đang hiệu lực" : "Chưa kích hoạt"}</span>
        </div>
        <div className="adm-card adm-stat">
          <small>Phiếu đã mua</small>
          <b>{d ? d.purchased_count.toLocaleString("vi-VN") : "…"}</b>
          <span>Đã dùng {d ? fmtPts(d.points_spent) : "…"}</span>
        </div>
        <div className="adm-card adm-stat">
          <small>Đơn chờ thanh toán</small>
          <b>{d ? d.pending_orders : "…"}</b>
          <span><Link href="/thanh-vien/vi" style={{ color: "var(--brand-600)" }}>Xem ví & đơn nạp</Link></span>
        </div>
      </div>

      <section style={{ marginBottom: 20 }}>
        <div className="adm-head" style={{ marginBottom: 12 }}>
          <h2>Cơ hội mới nhất</h2>
          <Link className="adm-btn sm" href="/thanh-vien/co-hoi">Xem tất cả</Link>
        </div>
        {!d ? (
          <div className="adm-opps">{[1, 2, 3].map((i) => <Skeleton key={i} h={190} />)}</div>
        ) : d.new_opportunities.length ? (
          <div className="adm-opps">{d.new_opportunities.map((o) => <OppCard key={o.id} o={o} />)}</div>
        ) : (
          <div className="adm-card adm-empty">Chưa có cơ hội nào đang mở bán. Hệ thống sẽ cập nhật liên tục.</div>
        )}
      </section>

      <section className="adm-card">
        <div className="hd">
          <h2>Phiếu mua gần đây</h2>
          <Link className="adm-btn sm" href="/thanh-vien/phieu">Tất cả phiếu</Link>
        </div>
        {!d ? (
          <div className="bd"><Skeleton h={60} /></div>
        ) : d.recent_purchases.length ? (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <tbody>
                {d.recent_purchases.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link className="name" href={`/thanh-vien/co-hoi/${p.opportunity.id}`}>{p.opportunity.title}</Link>
                      <div className="sub mono">{p.opportunity.code}</div>
                    </td>
                    <td className="adm-neg">−{fmtPts(p.price)}</td>
                    <td className="muted" style={{ whiteSpace: "nowrap" }}>{fromNow(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="adm-empty">Bạn chưa mua phiếu nào.</div>
        )}
      </section>
    </>
  );
}
