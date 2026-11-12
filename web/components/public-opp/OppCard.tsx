import { fmtDay, type PublicOpp, vnd } from "@/lib/public-opps";

/** Nhãn nổi bật: Mới / Sắp hết hạn / Độc quyền / Hết lượt — dùng chung thẻ & trang chi tiết. */
export function OppBadges({ o }: { o: PublicOpp }) {
  const soon = o.days_left !== null && o.days_left >= 0 && o.days_left <= 7;
  return (
    <>
      {o.sold_out ? <span className="pub-badge off">Hết lượt</span> : null}
      {!o.sold_out && o.is_new ? <span className="pub-badge new">Mới</span> : null}
      {!o.sold_out && soon ? <span className="pub-badge hot">{o.days_left === 0 ? "Hết hạn hôm nay" : `Còn ${o.days_left} ngày`}</span> : null}
      {!o.sold_out && o.exclusive ? <span className="pub-badge ex">Độc quyền</span> : null}
    </>
  );
}

/** Thanh lượt mua: đã bán / tối đa — khan hiếm thật theo số lượt còn lại. */
export function SlotBar({ o }: { o: PublicOpp }) {
  const pct = Math.min(100, Math.round((o.sold_count / Math.max(1, o.max_buyers)) * 100));
  return (
    <div className="pub-slots">
      <div className="pub-slots-row">
        <span>{o.sold_out ? "Đã hết lượt mua" : o.exclusive ? "Chỉ 1 thành viên được mua" : `Còn ${o.remaining}/${o.max_buyers} lượt mua`}</span>
        {o.sold_count ? <span className="pub-sold">Đã bán {o.sold_count}</span> : null}
      </div>
      {o.sold_count ? <i className="pub-bar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></i> : null}
    </div>
  );
}

/** Thẻ cơ hội công khai — chỉ phần xem trước (không tên bên mua, không đầu mối). */
export default function PublicOppCard({ o }: { o: PublicOpp }) {
  return (
    <a className={o.sold_out ? "pub-card is-off" : "pub-card"} href={`/co-hoi/${o.code}`}>
      <div className="pub-card-top">
        <span className="pub-ind">{o.industry || "Cơ hội B2B"}</span>
        <span className="pub-badges"><OppBadges o={o} /></span>
      </div>
      <h3>{o.title}</h3>
      {o.summary && o.summary.trim() !== o.title.trim() ? <p>{o.summary}</p> : null}
      <ul className="pub-meta">
        {o.province ? <li><svg className="icon"><use href="#i-map" /></svg>{o.province}</li> : null}
        {o.scale ? <li><svg className="icon"><use href="#i-layers" /></svg>{o.scale}</li> : null}
        {o.estimated_value ? <li><svg className="icon"><use href="#i-wallet" /></svg>{o.estimated_value}</li> : null}
        {o.deadline ? <li><svg className="icon"><use href="#i-gauge" /></svg>Hạn {fmtDay(o.deadline)}</li> : null}
      </ul>
      <div className="pub-lockline">
        <svg className="icon"><use href="#i-shield" /></svg>
        <span>Bên mua <i className="pub-blur" aria-hidden="true">Công ty TNHH ••••••</i></span>
        {o.contact_count ? <b>{o.contact_count} đầu mối</b> : null}
      </div>
      <SlotBar o={o} />
      <div className="pub-card-foot">
        <span><small>Giá phiếu từ</small><b>{vnd(o.price_from)}</b></span>
        <span className="pub-go">Xem chi tiết <svg className="icon"><use href="#i-arrow" /></svg></span>
      </div>
    </a>
  );
}
