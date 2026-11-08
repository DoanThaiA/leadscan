"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { CompanyTable } from "@/components/admin/CompanyTable";
import { DailyBars } from "@/components/admin/DailyBars";
import { Skeleton, StatusBadge } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import { fmtNum } from "@/lib/admin/format";
import type { Stats } from "@/lib/admin/types";
import { fmtVnd } from "@/lib/commerce";

interface CommerceStats {
  revenue_30d: number;
  tickets_sold_30d: number;
  pending_orders: number;
  pending_invoices: number;
  open_enrich: number;
  open_search: number;
  published_opportunities: number;
}

export default function DashboardPage() {
  const { meta, user } = useAdmin();
  const [stats, setStats] = useState<Stats | null>(null);
  const [cs, setCs] = useState<CommerceStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Tổng quan · Quản trị LeadScan";
    api.get<Stats>("/stats").then(setStats, (e) => setError(e.message));
    api.get<CommerceStats>("/commerce-stats").then(setCs, () => {});
  }, []);

  const tiles = stats
    ? [
        { label: "Tổng khách hàng", value: stats.total, hint: "Tất cả hồ sơ đăng ký" },
        { label: "Đăng ký hôm nay", value: stats.new_today, hint: "Theo giờ Việt Nam" },
        { label: "7 ngày qua", value: stats.new_7d, hint: "Hồ sơ mới" },
        { label: "Thành viên", value: stats.by_status.active ?? 0, hint: "Trạng thái Thành viên" },
      ]
    : [];

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Xin chào, {user.full_name}</h1>
          <p>Tình hình đăng ký thành viên LeadScan</p>
        </div>
        <Link className="adm-btn primary" href="/admin/khach-hang?status=new">
          Xử lý hồ sơ mới{stats ? ` (${stats.by_status.new ?? 0})` : ""}
        </Link>
      </div>

      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        {stats
          ? tiles.map((t) => (
              <div className="adm-card adm-stat" key={t.label}>
                <small>{t.label}</small>
                <b>{fmtNum(t.value)}</b>
                <span>{t.hint}</span>
              </div>
            ))
          : Array.from({ length: 4 }, (_, i) => (
              <div className="adm-card adm-stat" key={i}>
                <Skeleton h={14} w="50%" />
                <div style={{ height: 10 }} />
                <Skeleton h={28} w="40%" />
              </div>
            ))}
      </div>

      <div className="adm-grid cols-4" style={{ marginBottom: 16 }}>
        {[
          { label: "Doanh thu 30 ngày", value: cs ? fmtVnd(cs.revenue_30d) : "…", hint: "Đơn đã thanh toán", href: "/admin/thanh-toan" },
          { label: "Phiếu bán 30 ngày", value: cs ? fmtNum(cs.tickets_sold_30d) : "…", hint: `${cs?.published_opportunities ?? "…"} cơ hội đang bán`, href: "/admin/co-hoi" },
          { label: "Hoá đơn chờ xuất", value: cs ? fmtNum(cs.pending_invoices) : "…", hint: "Cần kế toán xử lý", href: "/admin/hoa-don" },
          { label: "Yêu cầu tìm cơ hội mới", value: cs ? fmtNum(cs.open_search) : "…", hint: `${cs?.open_enrich ?? "…"} yêu cầu enrich phiếu · ${cs?.pending_orders ?? "…"} đơn chờ`, href: "/admin/yeu-cau-tim-co-hoi" },
        ].map((t) => (
          <Link className="adm-card adm-stat" key={t.label} href={t.href}>
            <small>{t.label}</small>
            <b style={{ fontSize: 24 }}>{t.value}</b>
            <span>{t.hint}</span>
          </Link>
        ))}
      </div>

      <div className="adm-grid side" style={{ marginBottom: 16 }}>
        <section className="adm-card">
          <div className="hd">
            <h2>Đăng ký mới theo ngày</h2>
            <span className="muted">30 ngày gần nhất</span>
          </div>
          <div className="bd">{stats ? <DailyBars data={stats.daily} /> : <Skeleton h={180} />}</div>
        </section>

        <section className="adm-card">
          <div className="hd"><h2>Theo trạng thái</h2></div>
          <div className="bd adm-status-list">
            {Object.entries(meta.statuses).map(([key, label]) => (
              <Link key={key} href={`/admin/khach-hang?status=${key}`}>
                <StatusBadge status={key} label={label} />
                <b>{stats ? fmtNum(stats.by_status[key] ?? 0) : "…"}</b>
              </Link>
            ))}
          </div>
        </section>
      </div>

      <section className="adm-card">
        <div className="hd">
          <h2>Đăng ký gần đây</h2>
          <Link className="adm-btn sm" href="/admin/khach-hang">Xem tất cả</Link>
        </div>
        <CompanyTable items={stats?.recent} statuses={meta.statuses} />
      </section>
    </>
  );
}
