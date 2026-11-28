import { type TicketStats, ticketsLow, ticketsPct } from "@/lib/events";

const n = (x: number) => x.toLocaleString("vi-VN");

/** Khối "Tổng người tham dự · Đã đăng ký · Còn lại" kèm thanh tiến độ, đặt cạnh nội dung sự kiện. */
export function TicketMeter({ t, open }: { t: TicketStats; open: boolean }) {
  const low = ticketsLow(t);
  const limited = t.total !== null;
  const cls = ["ev-meter", t.sold_out ? "out" : low ? "low" : ""].filter(Boolean).join(" ");
  return (
    <div className={cls}>
      <div className="ev-meter-hd">
        <span className="ev-live" aria-hidden="true" />
        {t.sold_out ? "Đã hết vé" : low ? `Sắp hết vé – chỉ còn ${n(t.remaining!)} chỗ` : "Vé tham dự đang mở"}
      </div>
      <dl className="ev-meter-nums">
        <div><dt>Tổng người tham dự</dt><dd>{limited ? n(t.total!) : "Không giới hạn"}</dd></div>
        <div><dt>Đã đăng ký</dt><dd>{n(t.registered)}</dd></div>
        {limited ? <div className="rest"><dt>Còn lại</dt><dd>{n(t.remaining!)}</dd></div> : null}
      </dl>
      {limited ? (
        <>
          <div className="ev-bar" role="progressbar" aria-valuemin={0} aria-valuemax={t.total!} aria-valuenow={t.registered} aria-label="Số chỗ đã đăng ký">
            <span style={{ width: `${ticketsPct(t)}%` }} />
          </div>
          <p className="ev-meter-note">
            {t.sold_out
              ? "Toàn bộ chỗ đã được đăng ký. Liên hệ ban tổ chức để vào danh sách chờ."
              : `${ticketsPct(t)}% số chỗ đã có người đăng ký${open ? " — giữ chỗ ngay hôm nay." : "."}`}
          </p>
        </>
      ) : null}
      {open && !t.sold_out ? <a href="#dang-ky" className="btn btn-primary">Giữ chỗ ngay</a> : null}
    </div>
  );
}

/** Nhãn ngắn trên thẻ danh sách / hero: "Còn 63/100 chỗ" */
export function TicketChip({ t }: { t: TicketStats | undefined }) {
  if (!t || t.total === null) return null;
  if (t.sold_out) return <span className="ev-chip out">Hết vé</span>;
  return <span className={ticketsLow(t) ? "ev-chip low" : "ev-chip"}>Còn {n(t.remaining!)}/{n(t.total)} chỗ</span>;
}
