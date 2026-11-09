"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { OppList } from "@/components/member/OppList";
import type { Opp } from "@/lib/commerce";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface SavedList {
  total: number;
  page: number;
  page_size: number;
  items: Opp[];
}

const PAGE_SIZE = 20;

export default function SavedPage() {
  const [d, setD] = useState<SavedList | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Kho của tôi · LeadScan B2B";
    setD(null);
    mapi.get<SavedList>("/saved" + qs({ page, page_size: PAGE_SIZE })).then(setD, (e) => setError(errMsg(e)));
  }, [page]);

  const pages = d ? Math.max(1, Math.ceil(d.total / PAGE_SIZE)) : 1;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Kho của tôi</h1>
          <p>Cơ hội phù hợp được tự thêm vào kho khi hệ thống tìm thấy, cùng các cơ hội bạn tự lưu. Phiếu có thể hết lượt nếu doanh nghiệp khác mua trước.</p>
        </div>
        <Link className="adm-btn primary" href="/thanh-vien/phu-hop"><Icon name="scan" size={16} /> Tìm cơ hội phù hợp</Link>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card mt-list">
        <div className="mt-top"><h2>{d ? <><span>{d.total.toLocaleString("vi-VN")}</span> cơ hội đã lưu</> : "Cơ hội đã lưu"}</h2></div>
        {!d ? (
          <div style={{ display: "grid", gap: 10 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={56} />)}</div>
        ) : d.items.length ? (
          <>
            <OppList
              items={d.items}
              onChange={(o) => setD({ ...d, total: o.saved === false ? d.total - 1 : d.total, items: o.saved === false ? d.items.filter((x) => x.id !== o.id) : d.items.map((x) => (x.id === o.id ? o : x)) })}
            />
            {pages > 1 ? (
              <div className="mt-foot">
                <span>Trang {page}/{pages}</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
                  <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="mt-empty">
            <Icon name="bookmark" />
            <b style={{ color: "var(--ink)" }}>Kho đang trống</b>
            <span>Gửi phiếu ở mục “Cơ hội phù hợp”: cơ hội tìm thấy sẽ tự vào kho, bạn cũng có thể bấm “Thêm vào kho” để lưu thêm.</span>
          </div>
        )}
      </section>
    </>
  );
}
