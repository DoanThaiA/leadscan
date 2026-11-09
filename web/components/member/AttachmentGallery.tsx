"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/admin/ui";
import { type Attachment, fmtBytes } from "@/lib/commerce";

const extOf = (name: string) => (name.includes(".") ? name.split(".").pop()!.toUpperCase() : "TỆP");

/** Ảnh & tài liệu của phiếu đã mua: lưới ảnh (bấm để xem lớn) + danh sách tài liệu tải về.
 *  Link ký sẵn hết hạn sau ~15 phút → ảnh lỗi thì gọi onExpired để tải lại link mới (1 lần). */
export function AttachmentGallery({ items, onExpired }: { items: Attachment[]; onExpired: () => void }) {
  const images = items.filter((a) => a.kind === "image");
  const files = items.filter((a) => a.kind === "file");
  const [open, setOpen] = useState<number | null>(null);
  const refreshed = useRef(false);

  const expired = useCallback(() => {
    if (refreshed.current) return;
    refreshed.current = true;
    onExpired();
    setTimeout(() => { refreshed.current = false; }, 30_000);
  }, [onExpired]);

  return (
    <section className="adm-card">
      <div className="hd"><h2>Ảnh &amp; tài liệu ({items.length})</h2></div>
      <div className="bd at-view">
        {images.length ? (
          <ul className="at-thumbs">
            {images.map((a, i) => (
              <li key={a.id}>
                <button type="button" onClick={() => setOpen(i)} aria-label={`Xem ảnh ${a.caption || a.filename}`}>
                  <img src={a.thumb_url ?? a.url ?? ""} alt={a.caption || a.filename} loading="lazy" onError={expired} />
                </button>
                {a.caption ? <span className="at-cap-view">{a.caption}</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
        {files.length ? (
          <ul className="at-files">
            {files.map((a) => (
              <li key={a.id}>
                <span className="at-ext sm">{extOf(a.filename)}</span>
                <div className="at-file-main">
                  <b title={a.filename}>{a.filename}</b>
                  <span className="muted">{fmtBytes(a.size)}{a.caption ? ` · ${a.caption}` : ""}</span>
                </div>
                {a.download_url ? (
                  <a className="adm-btn sm" href={a.download_url} rel="noopener noreferrer"><Icon name="external" size={13} /> Tải về</a>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {open !== null && images[open] ? <Lightbox images={images} index={open} onIndex={setOpen} onClose={() => setOpen(null)} onError={expired} /> : null}
    </section>
  );
}

function Lightbox({ images, index, onIndex, onClose, onError }: { images: Attachment[]; index: number; onIndex: (i: number) => void; onClose: () => void; onError: () => void }) {
  const a = images[index];
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") onIndex((index + 1) % images.length);
      if (e.key === "ArrowLeft") onIndex((index - 1 + images.length) % images.length);
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [index, images.length, onClose, onIndex]);

  return (
    <div className="at-lightbox" role="dialog" aria-modal="true" aria-label={a.caption || a.filename} onClick={onClose}>
      <div className="at-lb-bar" onClick={(e) => e.stopPropagation()}>
        <span>{index + 1}/{images.length} · {a.caption || a.filename}</span>
        <div style={{ display: "flex", gap: 6 }}>
          {a.download_url ? <a className="adm-btn sm" href={a.download_url}>Tải ảnh gốc</a> : null}
          <button ref={closeRef} type="button" className="adm-btn sm" onClick={onClose} aria-label="Đóng">✕</button>
        </div>
      </div>
      <img src={a.url ?? ""} alt={a.caption || a.filename} onClick={(e) => e.stopPropagation()} onError={onError} />
      {images.length > 1 ? (
        <>
          <button type="button" className="at-lb-nav prev" aria-label="Ảnh trước" onClick={(e) => { e.stopPropagation(); onIndex((index - 1 + images.length) % images.length); }}>‹</button>
          <button type="button" className="at-lb-nav next" aria-label="Ảnh sau" onClick={(e) => { e.stopPropagation(); onIndex((index + 1) % images.length); }}>›</button>
        </>
      ) : null}
    </div>
  );
}
