import { daysLeft, fmtDay, type PublicOpp, vnd } from "@/lib/public-opps";

/** Thẻ cơ hội công khai — chỉ phần xem trước (không tên bên mua, không đầu mối). */
export default function PublicOppCard({ o }: { o: PublicOpp }) {
  const left = daysLeft(o.deadline);
  return (
    <a className="pub-card" href={`/co-hoi/${o.code}`}>
      <div className="pub-card-top">
        <span className="pill-tag">{o.industry || "Cơ hội B2B"}</span>
        {o.sold_out ? <span className="pub-tag off">Hết lượt</span> : o.exclusive ? <span className="pub-tag">Độc quyền</span> : <span className="pub-tag">Còn {o.remaining} lượt</span>}
      </div>
      <h3>{o.title}</h3>
      {o.summary && o.summary.trim() !== o.title.trim() ? <p>{o.summary}</p> : null}
      <ul className="pub-meta">
        {o.province ? <li><svg className="icon"><use href="#i-map" /></svg>{o.province}</li> : null}
        {o.scale ? <li><svg className="icon"><use href="#i-layers" /></svg>{o.scale}</li> : null}
        {o.deadline ? <li><svg className="icon"><use href="#i-gauge" /></svg>Hạn {fmtDay(o.deadline)}{left !== null && left >= 0 && left <= 14 ? ` · còn ${left} ngày` : ""}</li> : null}
      </ul>
      <div className="pub-card-foot">
        <span className="mono">{o.code}</span>
        <span>Giá từ <b>{vnd(o.price_from)}</b></span>
      </div>
    </a>
  );
}
