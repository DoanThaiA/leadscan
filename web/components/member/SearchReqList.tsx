import { fmtDateTime } from "@/lib/admin/format";
import { criteriaTags, SEARCH_STATUS, SEARCH_STATUS_CLASS, type SearchReq } from "@/lib/commerce";

/** Danh sách yêu cầu "Enrich tìm kiếm cơ hội" đã gửi (trang Cơ hội phù hợp + Tổng quan) */
export function SearchReqList({ items }: { items: SearchReq[] }) {
  return (
    <div className="sr-list">
      {items.map((r) => (
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
          {r.reply ? (
            <div className="sr-reply"><b>LeadScan phản hồi:</b> {r.reply}</div>
          ) : r.status === "open" ? (
            <div className="muted" style={{ fontSize: 12.5 }}>LeadScan đã nhận yêu cầu và đang tìm cơ hội. Cơ hội tìm được sẽ có trong mục Tất cả cơ hội.</div>
          ) : null}
        </article>
      ))}
    </div>
  );
}
