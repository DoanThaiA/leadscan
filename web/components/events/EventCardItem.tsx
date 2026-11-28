import { TicketChip } from "@/components/events/TicketMeter";
import { daysLeft, fmtDay, fmtVnd, parseLocal, type EventCard } from "@/lib/events";

/** Thẻ sự kiện trên trang danh sách (leadscan.net/su-kien và trang chủ 2 cổng sự kiện) */
export function EventCardItem({ event: e }: { event: EventCard }) {
  const when = parseLocal(e.starts_at);
  const left = daysLeft(e.deadline);
  const href = `/su-kien/${e.slug}`;
  const fees = [e.fee_member, e.fee_guest].filter((x) => x > 0);
  const fee = fees.length ? `${fmtVnd(Math.min(...fees))}${Math.max(...fees) !== Math.min(...fees) ? ` – ${fmtVnd(Math.max(...fees))}` : ""}` : "Miễn phí";

  return (
    <a className={e.cover_image ? "cr-job has-cover" : "cr-job"} href={href}>
      {e.cover_image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="cr-job-cover" src={e.cover_image} alt="" loading="lazy" />
      ) : null}
      <div className="cr-job-top">
        <span className="pill-tag">{e.host || "Sự kiện"}{e.partner ? ` × ${e.partner}` : ""}</span>
        {e.tickets?.total != null ? <TicketChip t={e.tickets} /> : left !== null && left >= 0 ? <span className={left <= 3 ? "cr-due soon" : "cr-due"}>{left === 0 ? "Hạn đăng ký hôm nay" : `Còn ${left} ngày đăng ký`}</span> : null}
      </div>
      <h3>{e.title}</h3>
      {e.summary ? <p>{e.summary}</p> : null}
      <ul className="cr-meta">
        {when ? <li><svg className="icon"><use href="#i-calc" /></svg>{when.day}{when.time ? ` · ${when.time}` : ""}</li> : null}
        {e.venue ? <li><svg className="icon"><use href="#i-map" /></svg>{e.venue}</li> : null}
        <li><svg className="icon"><use href="#i-ticket" /></svg>{fee}</li>
        {e.deadline ? <li><svg className="icon"><use href="#i-clipboard" /></svg>Hạn đăng ký {fmtDay(e.deadline)}</li> : null}
      </ul>
      <span className="link-arrow">Xem chi tiết &amp; đăng ký <svg className="icon" style={{ width: 16, height: 16 }}><use href="#i-arrow" /></svg></span>
    </a>
  );
}
