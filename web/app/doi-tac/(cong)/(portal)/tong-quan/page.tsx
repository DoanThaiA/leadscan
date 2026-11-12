"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/admin/ui";
import { usePartner } from "@/components/partner/PartnerContext";
import { fmtDate } from "@/lib/admin/format";
import { Balances } from "@/components/partner/Balances";
import { papi, type WalletSummary } from "@/lib/partner/api";
import { howCombined, vnd } from "@/lib/partner/content";
import { SUB_BADGE, type Submission } from "@/lib/partner/submissions";

interface Dash {
  wallet: WalletSummary;
  sent: number;
  open: number;
  ok: number;
  published: number;
  not_ok: number;
  sold: number;
  recent: Submission[];
}

/** Tổng quan — cơ hội đã gửi / đạt / đã bán; số dư từng loại; thu nhập tháng; hạng và hạn mức ly cafe còn lại (brief 8.2). */
export default function PartnerOverviewPage() {
  const { me, reward } = usePartner();
  const [d, setD] = useState<Dash | null>(null);
  useEffect(() => {
    document.title = "Tổng quan · Đối tác LeadScan";
    papi.get<Dash>("/dashboard").then(setD, () => {});
  }, []);

  const stat = (label: string, v: number | undefined, sub: string) => (
    <section className="adm-card adm-stat"><small>{label}</small><b>{v ?? "—"}</b><span>{sub}</span></section>
  );

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Chào {me.full_name.split(" ").at(-1)}!</h1>
          <p>Mã đối tác <b className="mono" style={{ color: "var(--brand)" }}>{me.code}</b> · Hạng {me.tier_label} · tham gia từ {fmtDate(me.created_at)}</p>
        </div>
        <Link className="adm-btn primary" href="/doi-tac/gui-co-hoi">+ Gửi cơ hội</Link>
      </div>

      {d ? <div style={{ marginBottom: 16 }}><Balances w={d.wallet} /></div> : null}
      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        {stat("Đã gửi", d?.sent, `${d?.open ?? 0} đang xác minh`)}
        {stat("Đạt xác minh", d?.ok, `${d?.published ?? 0} đã xuất bản phiếu`)}
        {stat("Đã bán được", d?.sold, "cơ hội có ≥ 1 lượt bán")}
        {stat("Trùng / không đạt", d?.not_ok, "xem lý do trong từng cơ hội")}
      </div>

      <div className="adm-grid side">
        <section className="adm-card">
          <div className="hd"><h2>Cơ hội gần đây</h2><Link href="/doi-tac/co-hoi" style={{ color: "var(--brand-600)", fontSize: 13, fontWeight: 600 }}>Xem tất cả →</Link></div>
          {d && d.recent.length ? (
            d.recent.map((s) => (
              <Link key={s.id} href={`/doi-tac/co-hoi/${s.id}`} className="ptn-list-row">
                <div style={{ minWidth: 0 }}>
                  <b>{s.company_name}</b>
                  <div className="sub mono">{s.code} · {fmtDate(s.created_at)}{s.sold_count ? ` · đã bán ${s.sold_count} lượt` : ""}{s.earned ? ` · ${vnd(s.earned)}` : ""}</div>
                </div>
                <StatusBadge status={SUB_BADGE[s.status]} label={s.status_label} />
              </Link>
            ))
          ) : d ? (
            <div className="adm-empty">
              Bạn chưa gửi cơ hội nào.<br />
              <Link href="/doi-tac/gui-co-hoi" className="adm-btn primary" style={{ marginTop: 12 }}>Gửi cơ hội đầu tiên</Link>
            </div>
          ) : <div className="adm-empty">Đang tải…</div>}
        </section>

        <section className="adm-card">
          <div className="hd"><h2>Tháng này</h2><Link href="/doi-tac/vi" style={{ color: "var(--brand-600)", fontSize: 13, fontWeight: 600 }}>Ví hoa hồng →</Link></div>
          <div className="ptn-reward" style={{ gridTemplateColumns: "1fr" }}>
            <div><small>Thu nhập ghi nhận</small><b>{vnd(d?.wallet.month ?? 0)}</b><span>Tổng các khoản ghi vào ví trong tháng.</span></div>
            <div><small>Ly cafe còn lại tháng này</small><b>{d ? `${d.wallet.cafe_left}/${d.wallet.cafe_quota}` : "—"}</b><span>Mỗi cơ hội đạt xác minh: {vnd(reward.cafe)}. Hạng {me.tier_label}.</span></div>
            <div><small>Mỗi lượt bán phiếu</small><b>{d?.wallet.rate ?? reward.rate}% doanh thu</b><span>{howCombined(reward)}</span></div>
          </div>
        </section>
      </div>
    </>
  );
}
