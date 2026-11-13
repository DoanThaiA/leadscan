"use client";

import { type KeyboardEvent as ReactKeyboardEvent, type TouchEvent, useCallback, useEffect, useRef, useState } from "react";

/** Banner khuyến mãi (GET /api/promos) — admin bật "Hiện banner trên trang chủ" khi tạo mã. */
interface Banner {
  id: number;
  code: string;
  title: string;
  text: string;
  description: string;
  applies_to: "all" | "membership" | "topup";
  applies_label: string;
  image: string;
  ends_on: string | null;
}

const AUTO_MS = 5000;
const IMG_WAIT_MS = 1200; // chờ ảnh đầu tải xong tối đa chừng này rồi hiện luôn (tránh khung trống)

const fmtDate = (iso: string) => {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

/** Popup nổi trên trang chủ: trượt lần lượt giữa các khuyến mãi, có nút ✕ để tắt. */
export default function PromoPopup() {
  const [items, setItems] = useState<Banner[]>([]);
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const [copied, setCopied] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);
  const touchX = useRef<number | null>(null);

  // Vào trang chủ là hỏi khuyến mãi ngay và hiện popup mỗi lần mở trang (đóng bằng ✕ / Esc / bấm ra ngoài)
  useEffect(() => {
    let alive = true;
    fetch("/api/promos", { credentials: "omit" })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d: { items?: Banner[] }) => {
        const list = (d.items ?? []).filter((b) => b.image);
        if (!alive || !list.length) return;
        setItems(list);
        // tải sẵn ảnh đầu: hiện popup ngay khi ảnh sẵn sàng (hoặc sau IMG_WAIT_MS) để không hiện khung trống
        const img = new Image();
        let shown = false;
        const show = () => {
          if (!shown && alive) {
            shown = true;
            setOpen(true);
          }
        };
        img.onload = img.onerror = show;
        img.src = list[0].image;
        setTimeout(show, IMG_WAIT_MS);
        list.slice(1).forEach((b) => (new Image().src = b.image)); // các ảnh sau tải nền để trượt không bị giật
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const close = useCallback(() => setOpen(false), []);

  const go = useCallback((n: number) => setI((n + items.length) % items.length), [items.length]);

  // khoá cuộn trang + đưa focus vào popup khi mở; trả lại focus cũ khi đóng
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    const before = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    boxRef.current?.focus(); // focus vào khung popup (không vào nút) để không làm dừng tự trượt
    return () => {
      document.body.style.overflow = prev;
      before?.focus?.();
    };
  }, [open]);

  // phím Esc đóng, ← → chuyển khuyến mãi
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") go(i + 1);
      else if (e.key === "ArrowLeft") go(i - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close, go, i]);

  // tự trượt sang khuyến mãi tiếp theo (dừng khi rê chuột / đang thao tác / người dùng muốn giảm chuyển động)
  useEffect(() => {
    if (!open || paused || items.length < 2) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t = setTimeout(() => go(i + 1), AUTO_MS);
    return () => clearTimeout(t);
  }, [open, paused, items.length, i, go]);

  async function copy(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(code);
      setTimeout(() => setCopied(""), 1600);
    } catch {}
  }

  const onTouchStart = (e: TouchEvent) => {
    touchX.current = e.touches[0].clientX;
    setPaused(true);
  };
  const onTouchEnd = (e: TouchEvent) => {
    const start = touchX.current;
    touchX.current = null;
    setPaused(false);
    if (start === null) return;
    const dx = e.changedTouches[0].clientX - start;
    if (Math.abs(dx) > 40) go(dx < 0 ? i + 1 : i - 1);
  };

  // giữ Tab trong popup
  const trapTab = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Tab") return;
    const els = e.currentTarget.querySelectorAll<HTMLElement>("a[href],button:not([disabled])");
    const visible = [...els].filter((el) => el.offsetParent !== null);
    if (!visible.length) return;
    const first = visible[0];
    const last = visible[visible.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  if (!open || !items.length) return null;
  const many = items.length > 1;

  return (
    <div className="pp-scrim" onClick={close}>
      <div
        className="pp"
        role="dialog"
        aria-modal="true"
        aria-roledescription="carousel"
        aria-label="Khuyến mãi LeadScan"
        onClick={(e) => e.stopPropagation()}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        ref={boxRef}
        tabIndex={-1}
        onFocus={(e) => e.target !== e.currentTarget && setPaused(true)} // đang tab qua các nút → dừng tự trượt
        onBlur={() => setPaused(false)}
        onKeyDown={trapTab}
      >
        <button type="button" className="pp-close" onClick={close} aria-label="Đóng khuyến mãi">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
        </button>

        <div className="pp-viewport" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
          <div className="pp-track" style={{ transform: `translateX(-${i * 100}%)` }}>
            {items.map((b, n) => (
              <article
                key={b.id}
                className="pp-slide"
                role="group"
                aria-roledescription="slide"
                aria-label={`${n + 1} / ${items.length}`}
                aria-hidden={n !== i}
                inert={n !== i}
              >
                <div className="pp-img">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={b.image} alt={b.title} loading={n === 0 ? "eager" : "lazy"} />
                </div>
                <div className="pp-body">
                  <span className="pp-tag">Ưu đãi · {b.applies_label}</span>
                  <h2 id={`pp-title-${b.id}`}>{b.title}</h2>
                  {b.text ? <p className="pp-text">{b.text}</p> : null}
                  <div className="pp-code">
                    <span>
                      Mã <b>{b.code}</b> · {b.description}
                      {b.ends_on ? <small> · đến hết {fmtDate(b.ends_on)}</small> : null}
                    </span>
                    <button type="button" onClick={() => copy(b.code)}>{copied === b.code ? "Đã chép ✓" : "Chép mã"}</button>
                  </div>
                  <a className="btn btn-primary pp-cta" href={`/thanh-vien/nap-tien?ma=${encodeURIComponent(b.code)}${b.applies_to !== "all" ? `&loai=${b.applies_to}` : ""}`}>Dùng mã ngay</a>
                </div>
              </article>
            ))}
          </div>
        </div>

        {many ? (
          <>
            <button type="button" className="pp-nav prev" onClick={() => go(i - 1)} aria-label="Khuyến mãi trước">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>
            </button>
            <button type="button" className="pp-nav next" onClick={() => go(i + 1)} aria-label="Khuyến mãi tiếp theo">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
            </button>
            <div className="pp-dots" role="tablist" aria-label="Chọn khuyến mãi">
              {items.map((b, n) => (
                <button
                  key={b.id}
                  type="button"
                  role="tab"
                  aria-selected={n === i}
                  aria-label={`Khuyến mãi ${n + 1}: ${b.title}`}
                  className={n === i ? "on" : undefined}
                  onClick={() => setI(n)}
                />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
