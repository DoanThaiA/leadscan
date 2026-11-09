"use client";

import Link from "next/link";

import { fmtDateTime } from "@/lib/admin/format";
import { criteriaTags, isMatching, SEARCH_STATUS, SEARCH_STATUS_CLASS, type SearchReq } from "@/lib/commerce";

/** Nội dung 1 phiếu tìm cơ hội dạng thẻ gọn: số phiếu, ngày, mô tả, trạng thái, số cơ hội phù hợp và số cơ hội mới */
export function SearchReqSummary({ r }: { r: SearchReq }) {
  const tags = criteriaTags(r.criteria);
  return (
    <>
      <span className="sr-card-top">
        <b>Yêu cầu #{r.id}</b>
        <span className="muted">{fmtDateTime(r.created_at)}</span>
        {r.new_count ? <span className="sr-new">{r.new_count} mới</span> : null}
      </span>
      <span className="sr-card-note">{r.note}</span>
      {tags.length ? (
        <span className="sr-card-tags">
          {tags.slice(0, 3).map((t) => <span className="adm-tag" key={t}>{t}</span>)}
          {tags.length > 3 ? <span className="adm-tag">+{tags.length - 3}</span> : null}
        </span>
      ) : null}
      <span className="sr-card-foot">
        <span className={`adm-badge ${SEARCH_STATUS_CLASS[r.status]}`}>{SEARCH_STATUS[r.status]}</span>
        <span className="sr-card-count">
          {isMatching(r) ? "Đang chấm điểm…" : r.match_status === "error" ? "Đang thử lại" : `${r.match_count ?? 0} cơ hội phù hợp`}
        </span>
      </span>
    </>
  );
}

/** Danh sách phiếu tìm cơ hội gọn (trang Tổng quan): bấm vào phiếu để mở trang Tìm cơ hội phù hợp ở đúng phiếu đó. */
export function SearchReqList({ items }: { items: SearchReq[] }) {
  return (
    <div className="sr-grid">
      {items.map((r) => (
        <Link key={r.id} className="sr-card boxed" href={`/thanh-vien/phu-hop?yeu-cau=${r.id}`}>
          <SearchReqSummary r={r} />
        </Link>
      ))}
    </div>
  );
}
