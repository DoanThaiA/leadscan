"use client";

import { useRouter } from "next/navigation";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/admin/ui";
import { fromNow } from "@/lib/admin/format";
import type { MemberNotice } from "@/lib/commerce";
import { mapi } from "@/lib/member/api";

const POLL_MS = 60_000;

interface NoticeCtx {
  items: MemberNotice[] | null;
  unread: number;
  reload: () => void;
  markAll: () => Promise<void>;
  markOne: (n: MemberNotice) => Promise<void>;
}

const Ctx = createContext<NoticeCtx | null>(null);

export function useNotices(): NoticeCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNotices phải nằm trong NoticeProvider");
  return v;
}

/** Thông báo "cơ hội mới phù hợp" (phiếu tìm cơ hội tìm kiếm liên tục): tải khi mở trang, mỗi phút và khi quay lại tab */
export function NoticeProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<MemberNotice[] | null>(null);
  const [unread, setUnread] = useState(0);

  const reload = useCallback(() => {
    mapi.get<{ unread: number; items: MemberNotice[] }>("/notifications").then(
      (r) => { setItems(r.items); setUnread(r.unread); },
      () => {},
    );
  }, []);

  useEffect(() => {
    reload();
    const t = setInterval(() => { if (document.visibilityState === "visible") reload(); }, POLL_MS);
    const onVis = () => { if (document.visibilityState === "visible") reload(); };
    document.addEventListener("visibilitychange", onVis);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", onVis); };
  }, [reload]);

  const markAll = useCallback(async () => {
    setItems((xs) => xs?.map((x) => ({ ...x, read: true })) ?? xs);
    setUnread(0);
    await mapi.post("/notifications/read-all").catch(() => {});
  }, []);

  const markOne = useCallback(async (n: MemberNotice) => {
    if (n.read) return;
    setItems((xs) => xs?.map((x) => (x.id === n.id ? { ...x, read: true } : x)) ?? xs);
    setUnread((u) => Math.max(0, u - 1));
    await mapi.post(`/notifications/${n.id}/read`).catch(() => {});
  }, []);

  return <Ctx.Provider value={{ items, unread, reload, markAll, markOne }}>{children}</Ctx.Provider>;
}

/** Chuông thông báo + bảng danh sách. placement: "side" (thanh bên máy tính) | "top" (thanh trên điện thoại) */
export function NoticeBell({ placement }: { placement: "side" | "top" }) {
  const { items, unread, markAll, markOne } = useNotices();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  function go(n: MemberNotice) {
    void markOne(n);
    setOpen(false);
    router.push(n.request ? `/thanh-vien/phu-hop?yeu-cau=${n.request.id}` : `/thanh-vien/co-hoi/${n.opportunity.id}`);
  }

  return (
    <div className={`nt-wrap nt-${placement}`} ref={ref}>
      <button
        type="button"
        className="nt-bell"
        aria-label={unread ? `Thông báo, ${unread} chưa đọc` : "Thông báo"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="bell" size={19} />
        {unread ? <span className="nt-count">{unread > 99 ? "99+" : unread}</span> : null}
      </button>
      {open ? (
        <div className="nt-panel" role="dialog" aria-label="Thông báo">
          <div className="nt-head">
            <b>Thông báo</b>
            {unread ? <button type="button" className="nt-link" onClick={() => void markAll()}>Đánh dấu đã đọc tất cả</button> : null}
          </div>
          {!items ? (
            <div className="nt-empty">Đang tải…</div>
          ) : items.length ? (
            <ul className="nt-list">
              {items.map((n) => (
                <li key={n.id}>
                  <button type="button" className={n.read ? "nt-item" : "nt-item unread"} onClick={() => go(n)}>
                    <span className="nt-ic" aria-hidden="true"><Icon name="spark" size={15} /></span>
                    <span className="nt-body">
                      <span className="nt-title">Cơ hội mới phù hợp: {n.opportunity.title}</span>
                      <span className="nt-meta">
                        {n.request ? `Yêu cầu #${n.request.id} · ` : ""}{n.score} điểm phù hợp · {fromNow(n.created_at)}
                      </span>
                    </span>
                    {!n.read ? <span className="nt-dot" aria-label="Chưa đọc" /> : null}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="nt-empty">
              <Icon name="bell" size={22} />
              <span>Chưa có thông báo. Khi có cơ hội mới phù hợp với yêu cầu tìm kiếm của bạn, LeadScan sẽ báo tại đây và qua email.</span>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
