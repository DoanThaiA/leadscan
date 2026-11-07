import Link from "next/link";

import { Icon, ScoreChip } from "@/components/admin/ui";
import { fmtPts, type Opp } from "@/lib/commerce";
import { fromNow } from "@/lib/admin/format";

export function OppCard({ o }: { o: Opp }) {
  return (
    <Link href={`/thanh-vien/co-hoi/${o.id}`} className="adm-card adm-opp">
      <div className="top">
        <div style={{ minWidth: 0 }}>
          <div className="muted mono" style={{ fontSize: 11.5 }}>{o.code} · {o.published_at ? fromNow(o.published_at) : ""}</div>
          <h3>{o.title}</h3>
        </div>
        <ScoreChip score={o.score} />
      </div>
      {o.summary ? <p className="sum">{o.summary}</p> : null}
      <div className="tags">
        {o.industry ? <span className="adm-tag">{o.industry}</span> : null}
        {o.province || o.region ? <span className="adm-tag">{o.province || o.region}</span> : null}
        {o.source_type ? <span className="adm-tag">{o.source_type}</span> : null}
        {o.enrich_round ? <span className="adm-tag">Enrich vòng {o.enrich_round}</span> : <span className="adm-tag">Phiếu cơ bản</span>}
      </div>
      <div className="foot">
        <div className="adm-price">
          {fmtPts(o.price)}
          <small>
            {o.contact_count} đầu mối · {o.max_buyers === 1 ? "Độc quyền" : `Còn ${Math.max(0, o.max_buyers - o.sold_count)}/${o.max_buyers} lượt`}
          </small>
        </div>
        {o.purchased ? (
          <span className="adm-badge s-active">Đã mua</span>
        ) : o.sold_out ? (
          <span className="adm-badge s-suspended">Hết lượt</span>
        ) : (
          <span className="adm-btn sm primary"><Icon name="lock" size={14} /> Xem & mua</span>
        )}
      </div>
    </Link>
  );
}
