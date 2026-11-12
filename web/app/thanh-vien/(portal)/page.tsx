"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { useMember } from "@/components/member/MemberContext";
import { SearchReqList } from "@/components/member/SearchReqList";
import { fmtDate, fromNow } from "@/lib/admin/format";
import { fmtPts, type Opp, type SearchReq } from "@/lib/commerce";
import { errMsg, mapi } from "@/lib/member/api";

interface Dash {
  purchased_count: number;
  points_spent: number;
  pending_orders: number;
  saved_count: number;
  recent_purchases: { id: number; price: number; created_at: string; opportunity: Opp }[];
  new_opportunities: Opp[];
}

export default function MemberHome() {
  const { me } = useMember();
  const [d, setD] = useState<Dash | null>(null);
  const [reqs, setReqs] = useState<SearchReq[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Tổng quan · LeadScan B2B";
    mapi.get<Dash>("/dashboard").then(setD, (e) => setError(errMsg(e)));
    mapi.get<{ items: SearchReq[] }>("/search-requests?limit=3").then((r) => setReqs(r.items), (e) => setError(errMsg(e)));
  }, []);

  const c = me.company;
  return (
    <>
      <div className="adm-head">
        <div className="mt-hello">
          <h1>Xin chào, {me.full_name}</h1>
          <p className="mt-org" title={c.name}>{c.name}</p>
          <p className="mono mt-code">Mã khách hàng {c.code}</p>
        </div>
        <div className="adm-actions">
          <Link className="adm-btn" href="/thanh-vien/nap-tien">Nạp điểm</Link>
          <Link className="adm-btn primary" href="/thanh-vien/phu-hop"><Icon name="scan" size={16} /> Tìm cơ hội phù hợp</Link>
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
          <small>Kho của tôi</small>
          <b>{d ? d.saved_count.toLocaleString("vi-VN") : "…"}</b>
          <span><Link href="/thanh-vien/kho" style={{ color: "var(--brand-600)" }}>Cơ hội đã lưu</Link>{d?.pending_orders ? ` · ${d.pending_orders} đơn chờ thanh toán` : ""}</span>
        </div>
      </div>

      <section className="adm-card mt-list" style={{ marginBottom: 20 }}>
        <div className="mt-top">
          <h2>Yêu cầu tìm cơ hội</h2>
          <Link className="adm-btn sm primary" href="/thanh-vien/phu-hop"><Icon name="spark" size={14} /> Gửi yêu cầu mới</Link>
        </div>
        {!reqs ? (
          <Skeleton h={80} />
        ) : reqs.length ? (
          <>
            <SearchReqList items={reqs} />
            <div className="mt-foot"><span /><Link href="/thanh-vien/phu-hop" style={{ color: "var(--brand-600)" }}>Xem tất cả yêu cầu →</Link></div>
          </>
        ) : (
          <div className="mt-empty">
            <Icon name="scan" />
            <b style={{ color: "var(--ink)" }}>Cho LeadScan biết bạn muốn tìm cơ hội nào</b>
            <span>Chọn ngành hàng, khu vực, loại cơ hội và mô tả nhu cầu — hệ thống tìm và chấm điểm cơ hội phù hợp cho bạn ngay lập tức.</span>
            <Link className="adm-btn primary" href="/thanh-vien/phu-hop">Enrich tìm kiếm cơ hội</Link>
          </div>
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
