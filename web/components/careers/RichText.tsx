import type { ReactNode } from "react";

/**
 * Hiển thị nội dung bài tuyển dụng viết bằng định dạng nhẹ (không dùng HTML → không lo chèn mã độc):
 *   "## Tiêu đề nhỏ"     → tiêu đề nhóm
 *   "- ý" hoặc "• ý"     → gạch đầu dòng
 *   "1. ý"               → danh sách đánh số
 *   **chữ đậm**, link http(s) tự thành liên kết; dòng trống = sang đoạn mới.
 */
export function RichText({ text, className }: { text: string; className?: string }) {
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flushPara = () => {
    if (para.length) {
      blocks.push(
        <p key={blocks.length}>
          {para.map((l, i) => (
            <span key={i}>
              {i > 0 ? <br /> : null}
              {inline(l)}
            </span>
          ))}
        </p>,
      );
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      const items = list.items.map((it, i) => <li key={i}>{inline(it)}</li>);
      blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
      list = null;
    }
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const h = line.match(/^#{2,3}\s+(.*)$/);
    const ul = line.match(/^[-•*+]\s+(.*)$/);
    const ol = line.match(/^\d+[.)]\s+(.*)$/);
    if (!line) {
      flushPara();
      flushList();
    } else if (h) {
      flushPara();
      flushList();
      blocks.push(<h4 key={blocks.length}>{inline(h[1])}</h4>);
    } else if (ul || ol) {
      flushPara();
      const ordered = Boolean(ol);
      if (list && list.ordered !== ordered) flushList();
      list ??= { ordered, items: [] };
      list.items.push((ul ?? ol)![1]);
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return <div className={className ? `rich ${className}` : "rich"}>{blocks}</div>;
}

function inline(s: string): ReactNode[] {
  return s.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s)]+)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <b key={i}>{part.slice(2, -2)}</b>;
    if (/^https?:\/\//.test(part))
      return (
        <a key={i} href={part} target="_blank" rel="noopener noreferrer nofollow">
          {part}
        </a>
      );
    return part;
  });
}
