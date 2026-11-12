"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Skeleton, StatusBadge } from "@/components/admin/ui";
import { Balances } from "@/components/partner/Balances";
import { usePartner } from "@/components/partner/PartnerContext";
import { fmtDate, fmtDateTime } from "@/lib/admin/format";
import { type Credit, errMsg, papi, type WalletSummary } from "@/lib/partner/api";
import { howCombined, vnd } from "@/lib/partner/content";

interface WalletPage {
  summary: WalletSummary;
  total: number;
  items: Credit[];
}

const STATE_BADGE = { pending: "contacted", available: "active", void: "suspended" } as const;

/** Ví hoa hồng — sổ ghi khoản LeadScan phải trả (không nạp, không chuyển; rút về ngân hàng chính chủ ở Mốc 4). */
export default function PartnerWalletPage() {
  const { reward } = usePartner();
  const [data, setData] = useState<WalletPage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Ví hoa hồng · Đối tác LeadScan";
    papi.get<WalletPage>("/wallet?page_size=100").then(setData, (e) => setError(errMsg(e)));
  }, []);

  if (error) return <div className="adm-alert">{error}</div>;
  if (!data) return <div style={{ display: "grid", gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} h={22} />)}</div>;
  const w = data.summary;

  return (
    <>
      <div className="adm-head">
        <div><h1>Ví hoa hồng</h1><p>Sổ ghi khoản LeadScan trả cho bạn — minh bạch từng cơ hội, từng lượt bán</p></div>
      </div>
      <Balances w={w} />

      <div className="adm-grid side" style={{ marginTop: 16 }}>
        <section className="adm-card">
          <div className="hd"><h2>Lịch sử ghi ví</h2><span className="muted" style={{ fontSize: 13 }}>{data.total} khoản</span></div>
          {!data.items.length ? (
            <div className="adm-empty">Chưa có khoản nào. Cơ hội đạt xác minh sẽ ghi ly cafe vào đây. <Link href="/doi-tac/gui-co-hoi" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Gửi cơ hội</Link></div>
          ) : (
            <div className="adm-table-wrap">
              <table className="adm-table">
                <thead><tr><th>Ngày</th><th>Khoản</th><th>Cơ hội</th><th style={{ textAlign: "right" }}>Số tiền</th><th>Trạng thái</th></tr></thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.id}>
                      <td style={{ whiteSpace: "nowrap" }} title={fmtDateTime(c.created_at)}>{fmtDate(c.created_at)}</td>
                      <td><div>{c.kind_label}</div><div className="sub">{c.note}</div></td>
                      <td>{c.submission ? <Link href={`/doi-tac/co-hoi/${c.submission.id}`} className="mono" style={{ color: "var(--brand-600)" }}>{c.submission.code}</Link> : "—"}</td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap", fontWeight: 600, color: c.amount < 0 ? "var(--danger)" : c.state === "void" ? "var(--muted)" : "var(--ink)", textDecoration: c.state === "void" ? "line-through" : undefined }}>
                        {c.amount > 0 ? "+" : ""}{vnd(c.amount)}
                      </td>
                      <td>
                        <StatusBadge status={STATE_BADGE[c.state]} label={c.state_label} />
                        {c.state === "pending" && c.available_at ? <div className="sub">Khả dụng {fmtDate(c.available_at)}</div> : null}
                        {c.state === "pending" && !c.available_at ? <div className="sub">Khi phiếu xuất bản</div> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Tháng này</h2></div>
            <div className="ptn-reward" style={{ gridTemplateColumns: "1fr" }}>
              <div><small>Thu nhập ghi nhận</small><b>{vnd(w.month)}</b><span>Tổng các khoản ghi trong tháng (kể cả Chờ duyệt).</span></div>
              <div><small>Ly cafe còn lại</small><b>{w.cafe_left}/{w.cafe_quota}</b><span>Vượt hạn mức: cơ hội vẫn được xác minh và chia doanh thu khi bán, chỉ không có ly cafe trả trước.</span></div>
              <div><small>Tỷ lệ hoa hồng của bạn</small><b>{w.rate}%</b><span>Phiếu thường; cơ hội lớn {reward.rateLarge}%. Trong {reward.months} tháng từ ngày xuất bản.</span></div>
            </div>
          </section>
          <section className="adm-card">
            <div className="hd"><h2>Cách ghi ví</h2></div>
            <div className="bd" style={{ display: "grid", gap: 8, fontSize: 13.5, color: "var(--ink-2)" }}>
              <p>{howCombined(reward)}</p>
              <p>Ly cafe: <b>Chờ duyệt</b> khi đạt xác minh → <b>Khả dụng</b> khi phiếu xuất bản. Hoa hồng: giữ {reward.holdDays} ngày rồi sang Khả dụng.</p>
              <p>Thành viên được hoàn phiếu vì thông tin sai → thu hồi hoa hồng của lượt đó. Bạn chỉ thấy số lượt bán và số tiền, không thấy thành viên nào mua.</p>
              <p>Rút từ {vnd(reward.minWithdraw)} Khả dụng về tài khoản ngân hàng chính chủ — <Link href="/doi-tac/rut-tien" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Rút tiền</Link>.</p>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
