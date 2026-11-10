"use client";

import { type CSSProperties, useState } from "react";

const FEE = 89_000; // phí thành viên = số điểm được nạp (khớp LEADSCAN_MEMBERSHIP_FEE)
const fmt = (n: number) => n.toLocaleString("vi-VN");
const fill = (v: number, min: number, max: number) => ({ "--fill": `${((v - min) / (max - min)) * 100}%` }) as CSSProperties;

/** Ước tính số dư thành viên sau khi mua phiếu. */
export default function Calculator() {
  const [qty, setQty] = useState(3);
  const [avg, setAvg] = useState(29000);
  const total = qty * avg;
  const remain = FEE - total;
  const used = Math.min((total / FEE) * 100, 100);
  const enough = remain >= 0;

  return (
    <div className="calc">
      <h4><svg className="icon"><use href="#i-calc" /></svg>Ước tính số dư của bạn</h4>
      <div className="calc-row">
        <label htmlFor="qty">Số phiếu cơ hội mua <b id="vQty">{qty} phiếu</b></label>
        <input type="range" id="qty" min={1} max={100} value={qty} style={fill(qty, 1, 100)} onChange={(e) => setQty(+e.target.value)} />
      </div>
      <div className="calc-row">
        <label htmlFor="avg">Giá trung bình mỗi phiếu <b id="vAvg">{fmt(avg)}đ</b></label>
        <input type="range" id="avg" min={29000} max={2000000} step={1000} value={avg} style={fill(avg, 29000, 2000000)} onChange={(e) => setAvg(+e.target.value)} />
      </div>
      <div className="calc-out">
        <div><small>Tổng giá trị phiếu</small><b id="oTotal">{fmt(total)}đ</b></div>
        <div id="oBox" className={enough ? undefined : "warn"}>
          <small id="oLabel">{enough ? "Số dư còn lại" : "Cần nạp thêm"}</small>
          <b id="oRemain">{fmt(Math.abs(remain))}đ</b>
        </div>
      </div>
      <div className="calc-bar">
        <div className="bar"><i id="oBar" style={{ width: `${used}%` }}></i></div>
        <p id="oNote">
          {enough
            ? `Đã dùng ${Math.round(used)}% số dư thành viên`
            : "Đã dùng hết số dư thành viên — nạp thêm để tiếp tục mua phiếu"}
        </p>
      </div>
    </div>
  );
}
