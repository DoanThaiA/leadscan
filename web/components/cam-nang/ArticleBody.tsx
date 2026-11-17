import type { ReactNode } from "react";

import { articleToc } from "@/lib/blog";

/**
 * Hiển thị bài cẩm nang viết bằng định dạng nhẹ kiểu Markdown (không nhận HTML → không lo chèn mã):
 *   "## Tiêu đề mục" (có id để mục lục nhảy tới) · "### Tiêu đề nhỏ"
 *   "- ý" / "1. ý" danh sách · "> câu" trích dẫn / lưu ý · "![mô tả](đường-dẫn-ảnh)" ảnh (1 dòng riêng)
 *   **đậm**, [chữ](link) — link nội bộ "/…" mở tại chỗ, link ngoài mở tab mới.
 * Dùng chung cho trang công khai và khung xem trước trong admin.
 */
export default function ArticleBody({ text }: { text: string }) {
  const ids = articleToc(text).map((t) => t.id);
  let h2 = 0;
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let quote: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const k = () => blocks.length;

  const flushPara = () => {
    if (para.length) blocks.push(<p key={k()}>{para.map((l, i) => <span key={i}>{i ? <br /> : null}{inline(l)}</span>)}</p>);
    para = [];
  };
  const flushQuote = () => {
    if (quote.length) blocks.push(<blockquote key={k()}>{quote.map((l, i) => <p key={i}>{inline(l)}</p>)}</blockquote>);
    quote = [];
  };
  const flushList = () => {
    if (list) {
      const items = list.items.map((it, i) => <li key={i}>{inline(it)}</li>);
      blocks.push(list.ordered ? <ol key={k()}>{items}</ol> : <ul key={k()}>{items}</ul>);
    }
    list = null;
  };
  const flushAll = () => { flushPara(); flushQuote(); flushList(); };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const h = line.match(/^(#{2,3})\s+(.*)$/);
    const img = line.match(/^!\[([^\]]*)\]\(([^)\s]+)\)$/);
    const ul = line.match(/^[-•*+]\s+(.*)$/);
    const ol = line.match(/^\d+[.)]\s+(.*)$/);
    const q = line.match(/^>\s?(.*)$/);
    if (!line) {
      flushAll();
    } else if (h) {
      flushAll();
      if (h[1] === "##") blocks.push(<h2 key={k()} id={ids[h2++]}>{inline(h[2])}</h2>);
      else blocks.push(<h3 key={k()}>{inline(h[2])}</h3>);
    } else if (img && safeUrl(img[2])) {
      flushAll();
      blocks.push(
        <figure key={k()}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img[2]} alt={img[1]} loading="lazy" decoding="async" />
          {img[1] ? <figcaption>{img[1]}</figcaption> : null}
        </figure>,
      );
    } else if (q) {
      flushPara();
      flushList();
      quote.push(q[1]);
    } else if (ul || ol) {
      flushPara();
      flushQuote();
      const ordered = Boolean(ol);
      if (list && list.ordered !== ordered) flushList();
      list ??= { ordered, items: [] };
      list.items.push((ul ?? ol)![1]);
    } else {
      flushQuote();
      flushList();
      para.push(line);
    }
  }
  flushAll();
  return <div className="art-body">{blocks}</div>;
}

/** Chỉ nhận link nội bộ "/…", "#…" hoặc http(s) — chặn javascript:, data: … */
function safeUrl(u: string): boolean {
  return /^(\/(?!\/)|#|https?:\/\/)/i.test(u);
}

function inline(s: string): ReactNode[] {
  return s.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^)\s]+\)|https?:\/\/[^\s)]+)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <b key={i}>{part.slice(2, -2)}</b>;
    const md = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
    const href = md ? md[2] : /^https?:\/\//.test(part) ? part : "";
    if (href && safeUrl(href)) {
      const label = md ? md[1] : part;
      return /^https?:\/\//i.test(href) && !/^https?:\/\/(www\.)?leadscan\.net/i.test(href)
        ? <a key={i} href={href} target="_blank" rel="noopener noreferrer">{label}</a>
        : <a key={i} href={href}>{label}</a>;
    }
    return md ? md[1] : part;
  });
}
