"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon, ScoreChip, Skeleton } from "@/components/admin/ui";
import { fmtDateTime } from "@/lib/admin/format";
import { fmtPts, type Opp } from "@/lib/commerce";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface Row {
  id: number;
  price: number;
  created_at: string;
  opportunity: Opp;
}

export default function PurchasesPage() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: Row[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Phiếu đã mua · LeadScan B2B";
    setData(null);
    mapi.get<{ total: number; items: Row[] }>("/purchases" + qs({ page, page_size: 20 })).then(setData, (e) => setError(errMsg(e)));
  }, [page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Phiếu đã mua</h1>
          <p>Toàn bộ cơ hội đã mở khoá cùng đầu mối liên hệ</p>
        </div>
        <Link className="adm-btn primary" href="/thanh-vien/co-hoi">Mua thêm phiếu</Link>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        {!data ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={40} />)}</div>
        ) : !data.items.length ? (
          <div className="adm-empty">Bạn chưa mua phiếu nào. <Link href="/thanh-vien/co-hoi" style={{ color: "var(--brand-600)" }}>Xem kho cơ hội →</Link></div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr><th>Cơ hội</th><th>Bên có nhu cầu</th><th>Đầu mối chính</th><th>Điểm</th><th>Giá</th><th>Ngày mua</th></tr>
              </thead>
              <tbody>
                {data.items.map(({ id, price, created_at, opportunity: o }) => {
                  const c = o.contacts?.[0];
                  return (
                    <tr key={id}>
                      <td>
                        <Link className="name" href={`/thanh-vien/co-hoi/${o.id}`}>{o.title}</Link>
                        <div className="sub mono">{o.code} · {o.industry} · {o.province}</div>
                      </td>
                      <td>{o.buyer_name || "—"}</td>
                      <td>
                        {c ? (
                          <>
                            <div>{c.full_name}{c.title ? <span className="muted"> · {c.title}</span> : null}</div>
                            <div className="sub">{c.phone ? <a href={`tel:${c.phone}`}><Icon name="phone" size={12} /> {c.phone}</a> : c.email}</div>
                          </>
                        ) : <span className="muted">—</span>}
                        {(o.contacts?.length ?? 0) > 1 ? <div className="sub">+{(o.contacts?.length ?? 0) - 1} đầu mối khác</div> : null}
                      </td>
                      <td><ScoreChip score={o.score} /></td>
                      <td className="adm-neg">{fmtPts(price)}</td>
                      <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {data && pages > 1 ? (
          <div className="adm-pager">
            <span>{data.total} phiếu</span>
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
