"use client";

import { useState } from "react";

const fmtDay = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
};

/** Cột đăng ký mỗi ngày: 1 chuỗi (không chú giải), di chuột/Tab để xem số; có bảng ẩn cho trình đọc màn hình. */
export function DailyBars({ data }: { data: { date: string; count: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.count), 0);
  // vạch tham chiếu ở số nguyên "đẹp" gần nửa đỉnh
  const ref = max >= 2 ? Math.max(1, Math.round(max / 2)) : 0;
  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <figure style={{ margin: 0 }}>
      <div className="adm-bars" role="img" aria-label={`Đăng ký mới 30 ngày: tổng ${total}, cao nhất ${max} trong một ngày`} onMouseLeave={() => setHover(null)}>
        {ref ? (
          <div className="adm-gridline" style={{ bottom: `${(ref / max) * 100}%` }}>
            <span>{ref}</span>
          </div>
        ) : null}
        {data.map((d, i) => (
          <div
            key={d.date}
            className={d.count ? "col" : "col zero"}
            tabIndex={0}
            onMouseEnter={() => setHover(i)}
            onFocus={() => setHover(i)}
            onBlur={() => setHover(null)}
            aria-label={`${fmtDay(d.date)}: ${d.count} đăng ký`}
          >
            <div className="bar" style={{ height: max ? `${(d.count / max) * 100}%` : 0 }} />
            {hover === i ? (
              <div className="adm-tip">
                {fmtDay(d.date)} · <b>{d.count}</b> đăng ký
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <div className="adm-bars-axis" aria-hidden="true">
        <span>{fmtDay(data[0].date)}</span>
        <span>{fmtDay(data[Math.floor(data.length / 2)].date)}</span>
        <span>Hôm nay</span>
      </div>
      <table className="sr-only" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
        <caption>Số đăng ký mới mỗi ngày</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.date}><th>{fmtDay(d.date)}</th><td>{d.count}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
