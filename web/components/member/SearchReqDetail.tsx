"use client";

import { useEffect, useState } from "react";

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

/** Chi tiết 1 phiếu tìm cơ hội: mô tả, tiêu chí và các cơ hội phù hợp (điểm tính theo chính phiếu này).
 *  onSeen: gọi sau khi đánh dấu đã xem các cơ hội mới — để danh sách phiếu và chuông cập nhật số "mới". */
export function SearchReqDetail({ r, onSeen }: { r: SearchReq; onSeen: () => void }) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<MatchedList | null>(null);
  const [error, setError] = useState("");
  const matching = isMatching(r);
  const tags = criteriaTags(r.criteria);

  useEffect(() => setPage(1), [r.id]);

  // Tải lại khi đổi phiếu / trang, hoặc khi phiếu có thêm cơ hội (tìm kiếm liên tục)
  useEffect(() => {
    if (matching) return;
    let alive = true;
    setError("");
    mapi.get<MatchedList>(`/search-requests/${r.id}/opportunities` + qs({ page, page_size: PAGE_SIZE })).then(
      (d) => {
        if (!alive) return;
        setData(d);
        // đã hiển thị cơ hội mới → đánh dấu đã xem (nhãn "Mới" vẫn giữ tới khi rời phiếu)
        if (d.items.some((o) => o.is_new)) mapi.post(`/search-requests/${r.id}/seen`).then(onSeen, () => {});
      },
      (e) => alive && setError(errMsg(e)),
    );
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [r.id, page, matching, r.match_count, r.matched_at]);

  useEffect(() => setData(null), [r.id]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const fresh = data?.items.filter((o) => o.is_new).length ?? 0;

  return (
    <section className="adm-card sr-detail" aria-labelledby="sr-detail-title">
      <header className="sr-detail-head">
        <div>
          <h2 id="sr-detail-title">Yêu cầu #{r.id}</h2>
          <span className="muted">Gửi lúc {fmtDateTime(r.created_at)}</span>
        </div>
        <span className={`adm-badge ${SEARCH_STATUS_CLASS[r.status]}`}>{SEARCH_STATUS[r.status]}</span>
      </header>

      <p className="sr-note">{r.note}</p>
      {tags.length ? <div className="sr-tags">{tags.map((t) => <span className="adm-tag" key={t}>{t}</span>)}</div> : null}
      {r.reply ? <div className="sr-reply"><b>LeadScan phản hồi:</b> {r.reply}</div> : null}
      {r.status === "open" ? (
        <p className="sr-live-note">
          <Icon name="refresh" size={14} /> Đang tìm kiếm liên tục — cơ hội mới mở bán phù hợp với yêu cầu này sẽ tự thêm vào đây và LeadScan báo cho bạn qua chuông thông báo và email.
        </p>
      ) : (
        <p className="sr-live-note off">Yêu cầu này đã dừng tìm kiếm.</p>
      )}

      <div className="sr-res-head">
        <h3>
          Cơ hội phù hợp{data && !matching ? <> <span>({data.total})</span></> : null}
          {fresh ? <span className="sr-new">{fresh} mới</span> : null}
        </h3>
        {data && pages > 1 ? <span className="muted">Trang {data.page}/{pages}</span> : null}
      </div>

      {error ? <div className="adm-alert" role="alert">{error}</div> : null}
      {matching ? (
        <div className="sr-state" role="status">
          <Icon name="spark" size={22} />
          <b>Đang tìm và chấm điểm cơ hội cho yêu cầu này…</b>
          <span>Kết quả hiện ở đây sau ít giây.</span>
        </div>
      ) : r.match_status === "error" ? (
        <div className="sr-state" role="status">
          <Icon name="refresh" size={22} />
          <b>Chưa tìm được do lỗi hệ thống</b>
          <span>LeadScan đã ghi nhận và sẽ chạy lại cho bạn.</span>
        </div>
      ) : !data ? (
        <div style={{ display: "grid", gap: 8 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={56} />)}</div>
      ) : data.items.length ? (
        <>
          <OppList items={data.items} onChange={(o) => setData((d) => (d ? { ...d, items: d.items.map((x) => (x.id === o.id ? o : x)) } : d))} />
          {pages > 1 ? (
            <div className="mt-foot">
              <span>{data.total} cơ hội</span>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="adm-btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Trước</button>
                <button className="adm-btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Sau →</button>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <div className="sr-state">
          <Icon name="scan" size={22} />
          <b>Chưa có cơ hội đạt mức phù hợp</b>
          <span>{r.status === "open" ? "LeadScan vẫn đang tìm kiếm liên tục và sẽ báo bạn ngay khi có cơ hội mới phù hợp." : "Yêu cầu đã dừng tìm kiếm."}</span>
        </div>
      )}
    </section>
  );
}
