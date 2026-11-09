"use client";

import { useState } from "react";

import { Icon, Skeleton } from "@/components/admin/ui";
import { OppList } from "@/components/member/OppList";
import { fmtDateTime } from "@/lib/admin/format";
import { criteriaTags, isMatching, type Opp, SEARCH_STATUS, SEARCH_STATUS_CLASS, type SearchReq } from "@/lib/commerce";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface MatchedList {
  total: number;
  page: number;
  page_size: number;
  items: Opp[];
}

const PAGE_SIZE = 10;

/** Danh sách phiếu "Enrich tìm kiếm cơ hội" đã gửi. Bấm vào phiếu để xem các cơ hội phù hợp với phiếu đó. */
export function SearchReqList({ items }: { items: SearchReq[] }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const [data, setData] = useState<Record<number, MatchedList>>({});
  const [loading, setLoading] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function load(id: number, page: number) {
    setLoading(id);
    setError("");
    try {
      const r = await mapi.get<MatchedList>(`/search-requests/${id}/opportunities` + qs({ page, page_size: PAGE_SIZE }));
      setData((d) => ({ ...d, [id]: r }));
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(null);
    }
  }

  function toggle(id: number) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    if (!data[id]) void load(id, 1);
  }

  return (
    <div className="sr-list">
      {items.map((r) => {
        const d = data[r.id];
        const open = openId === r.id;
        const pages = d ? Math.max(1, Math.ceil(d.total / PAGE_SIZE)) : 1;
        return (
          <article className="sr-item" key={r.id}>
            <div className="sr-head">
              <b>Yêu cầu #{r.id}</b>
              <span className="muted">{fmtDateTime(r.created_at)}</span>
              <span className={`adm-badge ${SEARCH_STATUS_CLASS[r.status]}`}>{SEARCH_STATUS[r.status]}</span>
            </div>
            {criteriaTags(r.criteria).length ? (
              <div className="sr-tags">{criteriaTags(r.criteria).map((t) => <span className="adm-tag" key={t}>{t}</span>)}</div>
            ) : null}
            <p className="sr-note">{r.note}</p>
            {r.reply ? <div className="sr-reply"><b>LeadScan phản hồi:</b> {r.reply}</div> : null}
            {isMatching(r) ? (
              <div className="muted" role="status" style={{ fontSize: 12.5 }}>
                <Icon name="spark" size={13} /> Đang tìm và chấm điểm cơ hội phù hợp với phiếu này…
              </div>
            ) : r.match_status === "error" ? (
              <div className="muted" role="status" style={{ fontSize: 12.5 }}>
                Chưa tìm được cơ hội do lỗi hệ thống. LeadScan đã ghi nhận và sẽ chạy lại cho bạn.
              </div>
            ) : (
              <div>
                <button type="button" className="adm-btn sm" aria-expanded={open} onClick={() => toggle(r.id)}>
                  <Icon name="scan" size={14} /> {open ? "Ẩn" : "Xem"} {r.match_count ?? 0} cơ hội phù hợp
                </button>
              </div>
            )}
            {open && !isMatching(r) ? (
              <div style={{ marginTop: 6 }}>
                {error ? <div className="adm-alert" role="alert">{error}</div> : null}
                {!d ? (
                  <div style={{ display: "grid", gap: 8 }}>{[1, 2].map((i) => <Skeleton key={i} h={52} />)}</div>
                ) : d.items.length ? (
                  <>
                    <OppList
                      items={d.items}
                      onChange={(o) => setData((all) => ({ ...all, [r.id]: { ...d, items: d.items.map((x) => (x.id === o.id ? o : x)) } }))}
                    />
                    {pages > 1 ? (
                      <div className="mt-foot">
                        <span>Trang {d.page}/{pages}</span>
                        <div style={{ display: "flex", gap: 6 }}>
                          <button className="adm-btn sm" disabled={d.page <= 1 || loading === r.id} onClick={() => load(r.id, d.page - 1)}>← Trước</button>
                          <button className="adm-btn sm" disabled={d.page >= pages || loading === r.id} onClick={() => load(r.id, d.page + 1)}>Sau →</button>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="muted" style={{ fontSize: 12.5 }}>
                    Chưa có cơ hội nào đạt mức phù hợp với phiếu này. Cơ hội mới mở bán sẽ tự được so khớp và thêm vào Tất cả cơ hội của bạn.
                  </div>
                )}
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
