"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/admin/ui";
import { useMember } from "@/components/member/MemberContext";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";
import { fmtPts, fmtVnd, ORDER_KIND, ORDER_STATUS, ORDER_STATUS_CLASS, type Order, TX_KIND, type Tx } from "@/lib/commerce";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface WalletResp {
  transactions: { total: number; page: number; page_size: number; items: Tx[] };
  orders: Order[];
}

export default function WalletPage() {
  const { me, refresh } = useMember();
  const [page, setPage] = useState(1);
  const [d, setD] = useState<WalletResp | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Ví & nạp tiền · LeadScan B2B";
    refresh().catch(() => {});
  }, [refresh]);

  useEffect(() => {
    mapi.get<WalletResp>("/wallet" + qs({ page, page_size: 20 })).then(setD, (e) => setError(errMsg(e)));
  }, [page]);

  const c = me.company;
  const pages = d ? Math.max(1, Math.ceil(d.transactions.total / 20)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Ví & nạp tiền</h1>
          <p>1 điểm = 1đ. Phí thành viên được cộng đủ thành điểm để mua phiếu cơ hội.</p>
        </div>
        <Link className="adm-btn primary" href="/thanh-vien/nap-tien">{c.membership_active ? "Nạp thêm điểm" : "Thanh toán phí thành viên"}</Link>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        <div className="adm-card adm-stat"><small>Số dư điểm</small><b>{c.points_balance.toLocaleString("vi-VN")}</b><span>Dùng để mua phiếu</span></div>
        <div className="adm-card adm-stat">
          <small>Thành viên</small>
          <b style={{ fontSize: 22 }}>{c.membership_active ? "Đang hiệu lực" : "Chưa kích hoạt"}</b>
          <span>{c.membership_expires_at ? `Hết hạn ${fmtDate(c.membership_expires_at)}` : "Thanh toán phí để kích hoạt"}</span>
        </div>
      </div>

      <section className="adm-card" style={{ marginBottom: 16 }}>
        <div className="hd">
          <h2>Đơn thanh toán & hoá đơn</h2>
        </div>
        {!d ? (
          <div className="bd"><Skeleton h={60} /></div>
        ) : !d.orders.length ? (
          <div className="adm-empty">Chưa có đơn thanh toán nào.</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Mã đơn</th><th>Nội dung</th><th>Số tiền</th><th>Trạng thái</th><th>Hoá đơn</th><th>Ngày tạo</th></tr></thead>
              <tbody>
                {d.orders.map((o) => (
                  <tr key={o.id}>
                    <td><Link className="name mono" href={`/thanh-vien/nap-tien/${o.code}`}>{o.code}</Link></td>
                    <td>{ORDER_KIND[o.kind]}<div className="sub">+{fmtPts(o.points)}</div></td>
                    <td className="adm-neg">{fmtVnd(o.amount)}</td>
                    <td><span className={`adm-badge ${ORDER_STATUS_CLASS[o.status]}`}>{ORDER_STATUS[o.status]}</span></td>
                    <td>
                      {o.status !== "paid" ? (
                        <span className="muted">—</span>
                      ) : o.invoice ? (
                        o.invoice.status === "issued" ? (
                          <span className="adm-badge s-active">Đã xuất {o.invoice.invoice_number ? `#${o.invoice.invoice_number}` : ""}</span>
                        ) : (
                          <span className="adm-badge s-contacted">Chờ xuất</span>
                        )
                      ) : (
                        <Link className="adm-btn sm" href={`/thanh-vien/nap-tien/${o.code}#hoa-don`}>Yêu cầu xuất HĐ</Link>
                      )}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(o.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="adm-card">
        <div className="hd"><h2>Lịch sử điểm</h2></div>
        {!d ? (
          <div className="bd"><Skeleton h={80} /></div>
        ) : !d.transactions.items.length ? (
          <div className="adm-empty">Chưa có giao dịch điểm.</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Thời gian</th><th>Loại</th><th>Diễn giải</th><th style={{ textAlign: "right" }}>Điểm</th><th style={{ textAlign: "right" }}>Số dư sau</th></tr></thead>
              <tbody>
                {d.transactions.items.map((t) => (
                  <tr key={t.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(t.created_at)}</td>
                    <td>{TX_KIND[t.kind] ?? t.kind}</td>
                    <td>{t.note}</td>
                    <td style={{ textAlign: "right" }} className={t.amount > 0 ? "adm-pos" : "adm-neg"}>{t.amount > 0 ? "+" : "−"}{Math.abs(t.amount).toLocaleString("vi-VN")}</td>
                    <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{t.balance_after.toLocaleString("vi-VN")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d && pages > 1 ? (
          <div className="adm-pager">
            <span>{d.transactions.total} giao dịch</span>
            <div>
              <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
              <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}
