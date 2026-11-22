"use client";

import { usePathname } from "next/navigation";
import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";

import "./assistant.css";

/** Trợ lý LeadScan — nút chat nổi góc phải dưới. Mỗi cổng gọi API của đúng cổng đó (cookie riêng):
 *  khách: /api/public/assistant · thành viên: /api/member/assistant · đối tác: /api/partner/assistant.
 *  Lịch sử chỉ nằm trong trình duyệt (sessionStorage theo cổng) — máy chủ không lưu hội thoại. */

export type AssistantAudience = "guest" | "member" | "partner";

interface Msg {
  role: "user" | "assistant";
  content: string;
  id?: string;
  error?: boolean;
  rated?: boolean;
}

const API: Record<AssistantAudience, string> = {
  guest: "/api/public/assistant",
  member: "/api/member/assistant",
  partner: "/api/partner/assistant",
};

const SUGGEST: Record<AssistantAudience, string[]> = {
  guest: [
    "LeadScan hoạt động thế nào?",
    "Phí thành viên bao nhiêu, được gì?",
    "Làm đối tác thì nhận thưởng ra sao?",
    "Có cơ hội nào ngành bao bì không?",
  ],
  member: [
    "Tài khoản của tôi còn bao nhiêu điểm, hạn đến khi nào?",
    "Cách viết phiếu tìm cơ hội để kết quả chính xác?",
    "Giá phiếu cơ hội được tính thế nào?",
    "Đã chuyển khoản mà chưa thấy cộng điểm?",
  ],
  partner: [
    "Thành viên đang cần tìm những gì?",
    "Cơ hội tôi gửi đang ở trạng thái nào?",
    "Ví của tôi rút được bao nhiêu, khi nào nhận tiền?",
    "Làm sao để cơ hội đạt xác minh?",
  ],
};

const TOOL_LABEL: Record<string, string> = {
  get_pricing: "bảng giá", get_partner_rewards: "chính sách thưởng", search_opportunities: "cơ hội đang bán", get_opportunity: "phiếu cơ hội",
  list_options: "danh mục", get_my_account: "tài khoản", get_my_wallet: "ví điểm", list_my_orders: "đơn thanh toán",
  list_my_search_requests: "phiếu tìm cơ hội", list_my_purchases: "phiếu đã mua", list_my_matches: "cơ hội phù hợp",
  get_my_partner_account: "tài khoản đối tác", list_my_submissions: "cơ hội đã gửi", get_my_submission: "cơ hội đã gửi",
  list_my_withdrawals: "lệnh rút tiền", list_open_needs: "nhu cầu đang tìm",
};

const MAX_SEND_BYTES = 40_000; // Nginx giới hạn thân request /api/ 64 KB
const KEEP = 12;

// ------------------------------------------------------------------ hiển thị Markdown nhẹ (không dùng innerHTML)

function safeHref(href: string): string | null {
  if (/^\/(?!\/)/.test(href)) return href; // đường dẫn trong site
  if (/^https:\/\/(www\.)?leadscan\.net(\/|$)/i.test(href)) return href;
  if (/^mailto:[^\s]+$/i.test(href) || /^tel:\+?[\d\s]+$/i.test(href)) return href;
  return null;
}

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)|`([^`]+)`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const k = `${key}-${i++}`;
    if (m[1]) out.push(<b key={k}>{m[1]}</b>);
    else if (m[2]) {
      const href = safeHref(m[3]);
      out.push(href ? <a key={k} href={href} target={href.startsWith("/") ? undefined : "_blank"} rel="noopener noreferrer">{m[2]}</a> : `${m[2]} (${m[3]})`);
    } else if (m[4]) out.push(<code key={k}>{m[4]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let para: string[] = [];
  const flushPara = () => {
    if (para.length) blocks.push(<p key={`p${blocks.length}`}>{para.flatMap((l, i) => (i ? [<br key={`br${i}`} />, ...inline(l, `p${blocks.length}-${i}`)] : inline(l, `p${blocks.length}-${i}`)))}</p>);
    para = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((it, i) => <li key={i}>{inline(it, `l${blocks.length}-${i}`)}</li>);
    blocks.push(list.ordered ? <ol key={`l${blocks.length}`}>{items}</ol> : <ul key={`l${blocks.length}`}>{items}</ul>);
    list = null;
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const num = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (bullet || num) {
      flushPara();
      const ordered = !!num;
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push((bullet ?? num)![1]);
    } else if (!line.trim()) {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line.replace(/^#+\s*/, ""));
    }
  }
  flushPara();
  flushList();
  return <>{blocks}</>;
}

// ------------------------------------------------------------------ widget

function load(key: string): Msg[] {
  try {
    const v = JSON.parse(sessionStorage.getItem(key) || "[]");
    return Array.isArray(v) ? v.slice(-40) : [];
  } catch {
    return [];
  }
}

function payload(msgs: Msg[]) {
  const ok = msgs.filter((m) => !m.error).slice(-KEEP).map((m) => ({ role: m.role, content: m.content.slice(0, 2000) }));
  while (ok.length > 1 && new TextEncoder().encode(JSON.stringify(ok)).length > MAX_SEND_BYTES) ok.shift();
  while (ok.length && ok[0].role !== "user") ok.shift();
  return ok;
}

export default function AssistantChat({ audience, raised = false }: { audience: AssistantAudience; raised?: boolean }) {
  const path = usePathname();
  const storeKey = `ls-assistant-${audience}`;
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [tools, setTools] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => setMsgs(load(storeKey)), [storeKey]);
  useEffect(() => {
    try {
      sessionStorage.setItem(storeKey, JSON.stringify(msgs.slice(-40)));
    } catch {}
  }, [msgs, storeKey]);
  useEffect(() => {
    if (open) {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
      inputRef.current?.focus();
    }
  }, [open, msgs.length, busy]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function send(q: string) {
    q = q.trim().slice(0, 2000);
    if (!q || busy) return;
    const next: Msg[] = [...msgs, { role: "user", content: q }];
    setMsgs(next);
    setText("");
    setBusy(true);
    setTools([]);
    let reply: Msg;
    try {
      const res = await fetch(API[audience], {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: payload(next), page: path }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && typeof data.reply === "string") {
        reply = { role: "assistant", content: data.reply, id: data.id };
        setTools(Array.isArray(data.tools) ? data.tools : []);
      } else if (res.status === 401) {
        reply = { role: "assistant", content: "Phiên đăng nhập đã hết. Bạn tải lại trang và đăng nhập lại nhé.", error: true };
      } else {
        reply = { role: "assistant", content: typeof data.detail === "string" ? data.detail : "Trợ lý đang bận, bạn thử lại sau ít phút nhé.", error: true };
      }
    } catch {
      reply = { role: "assistant", content: "Không kết nối được máy chủ. Kiểm tra mạng và thử lại.", error: true };
    }
    setMsgs((m) => [...m, reply]);
    setBusy(false);
  }

  function rate(i: number, helpful: boolean) {
    const m = msgs[i];
    if (!m?.id || m.rated) return;
    setMsgs((all) => all.map((x, j) => (j === i ? { ...x, rated: true } : x)));
    fetch(`${API[audience]}/feedback`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: m.id, helpful, note: helpful ? "" : msgs[i - 1]?.content ?? "" }),
    }).catch(() => {});
  }

  const submit = (e: FormEvent) => { e.preventDefault(); send(text); };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send(text);
    }
  };
  const clear = () => { setMsgs([]); setTools([]); };

  return (
    <div className={`asst${raised ? " raised" : ""}`}>
      {open ? (
        <div className="asst-panel" role="dialog" aria-label="Trợ lý LeadScan">
          <div className="asst-hd">
            <span className="asst-avatar" aria-hidden="true">LS</span>
            <div>
              <b>Trợ lý LeadScan</b>
              <small>Hỏi đáp về sàn, tài khoản và cách dùng</small>
            </div>
            {msgs.length ? <button type="button" className="asst-ghost" onClick={clear} title="Xoá hội thoại">Làm mới</button> : null}
            <button type="button" className="asst-x" onClick={() => setOpen(false)} aria-label="Đóng trợ lý">×</button>
          </div>

          <div className="asst-body" ref={listRef} aria-live="polite">
            {!msgs.length ? (
              <div className="asst-welcome">
                <p>Chào bạn! Mình là trợ lý AI của LeadScan. Bạn cần hỏi gì về {audience === "partner" ? "chương trình đối tác, cơ hội đã gửi, ví thưởng" : audience === "member" ? "tài khoản, phiếu cơ hội, nạp điểm" : "sàn LeadScan"}?</p>
                <div className="asst-sugs">
                  {SUGGEST[audience].map((s) => <button key={s} type="button" onClick={() => send(s)}>{s}</button>)}
                </div>
              </div>
            ) : null}
            {msgs.map((m, i) => (
              <div key={i} className={`asst-msg ${m.role}${m.error ? " err" : ""}`}>
                {m.role === "assistant" ? <Markdown text={m.content} /> : <p>{m.content}</p>}
                {m.role === "assistant" && m.id ? (
                  <div className="asst-rate">
                    {m.rated ? <span>Cảm ơn bạn đã góp ý</span> : (
                      <>
                        <button type="button" onClick={() => rate(i, true)} aria-label="Câu trả lời hữu ích">👍</button>
                        <button type="button" onClick={() => rate(i, false)} aria-label="Câu trả lời chưa đúng">👎</button>
                      </>
                    )}
                  </div>
                ) : null}
              </div>
            ))}
            {busy ? <div className="asst-msg assistant typing" aria-label="Trợ lý đang trả lời"><span /><span /><span /></div> : null}
            {!busy && tools.length ? <div className="asst-tools">Đã tra cứu: {[...new Set(tools.map((t) => TOOL_LABEL[t] ?? t))].join(", ")}</div> : null}
          </div>

          <form className="asst-form" onSubmit={submit}>
            <textarea
              ref={inputRef}
              rows={1}
              value={text}
              maxLength={2000}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKey}
              placeholder="Nhập câu hỏi…"
              aria-label="Câu hỏi cho trợ lý"
            />
            <button type="submit" disabled={busy || !text.trim()} aria-label="Gửi">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.4 20.4 21 12 3.4 3.6 3.4 10l12.6 2-12.6 2z" /></svg>
            </button>
          </form>
          <p className="asst-note">Trợ lý AI có thể nhầm — với số tiền, hạn mức hãy đối chiếu trang tương ứng hoặc liên hệ LeadScan.</p>
        </div>
      ) : null}
      <button type="button" className={`asst-fab${open ? " on" : ""}`} onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={open ? "Đóng trợ lý" : "Mở Trợ lý LeadScan"}>
        {open ? (
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
        ) : (
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z" /><path d="M8 9.5h8M8 12.5h5" /></svg>
        )}
        {!open ? <span>Hỏi trợ lý</span> : null}
      </button>
    </div>
  );
}
