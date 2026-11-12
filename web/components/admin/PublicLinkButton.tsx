"use client";

import { useState } from "react";

import { Icon } from "@/components/admin/ui";

/** Sao chép link công khai /co-hoi/<mã> của phiếu đang bán (gửi Zalo, email…). */
export default function PublicLinkButton({ code, published }: { code: string; published: boolean }) {
  const [done, setDone] = useState(false);
  if (!published) return <span className="muted" style={{ fontSize: 12.5 }} title="Link công khai chỉ mở khi phiếu ở trạng thái Đang bán">Link công khai: khi mở bán</span>;
  const url = `${typeof location !== "undefined" ? location.origin : ""}/co-hoi/${code}`;
  return (
    <>
      <a className="adm-btn" href={`/co-hoi/${code}`} target="_blank" rel="noopener"><Icon name="external" size={14} /> Trang công khai</a>
      <button className="adm-btn" onClick={async () => { await navigator.clipboard.writeText(url).catch(() => {}); setDone(true); setTimeout(() => setDone(false), 2000); }}>
        <Icon name="copy" size={14} /> {done ? "Đã sao chép" : "Sao chép link"}
      </button>
    </>
  );
}
