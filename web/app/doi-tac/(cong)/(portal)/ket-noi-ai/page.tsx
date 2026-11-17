"use client";

import { useEffect, useState } from "react";

import { Icon } from "@/components/admin/ui";
import { usePartner } from "@/components/partner/PartnerContext";
import { fmtDateTime } from "@/lib/admin/format";
import { errMsg, type McpStatus, papi } from "@/lib/partner/api";

type Tab = "claude" | "chatgpt" | "khac";

const TOOLS: [string, string][] = [
  ["Hướng dẫn đăng cơ hội", "Quy định cơ hội được nhận, danh mục ngành/khu vực, mức thưởng, số cơ hội còn được đăng hôm nay."],
  ["Đăng cơ hội lên LeadScan", "Gửi cơ hội vào hàng đợi xác minh — giống hệt form Gửi cơ hội trong cổng."],
  ["Cơ hội của tôi", "Danh sách cơ hội đã đăng, trạng thái xác minh, điểm, lượt bán, tiền thưởng."],
  ["Chi tiết cơ hội", "Xem 1 cơ hội theo mã GT-… và lịch sử trạng thái."],
];

const PROMPTS = [
  "Đăng cơ hội lên LeadScan: Công ty TNHH ABC ở KCN Quế Võ, Bắc Ninh đang tìm nhà cung cấp thùng carton 5 lớp, khoảng 20.000 thùng/tháng, cần từ tháng 1/2027. Tôi biết qua mối quan hệ, đã xác nhận với trưởng phòng mua hàng.",
  "Đây là tin nhắn Zalo khách vừa gửi tôi (dán nội dung). Soạn giúp tôi thành cơ hội để đăng lên LeadScan.",
  "Các cơ hội tôi đã đăng trên LeadScan đang ở trạng thái nào?",
  "Cho tôi xem chi tiết cơ hội GT-000123 trên LeadScan.",
];

function CopyBtn({ text, label = "Chép" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="adm-btn sm"
      onClick={() => navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1800); }, () => {})}
    >
      <Icon name={done ? "check" : "copy"} size={14} /> {done ? "Đã chép" : label}
    </button>
  );
}

export default function PartnerAiConnectPage() {
  const { reward } = usePartner();
  const [st, setSt] = useState<McpStatus | null>(null);
  const [fresh, setFresh] = useState<string>("");
  const [tab, setTab] = useState<Tab>("claude");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    document.title = "Kết nối AI · Đối tác LeadScan";
    papi.get<McpStatus>("/mcp").then(setSt, (e) => setErr(errMsg(e)));
  }, []);

  async function create() {
    if (st?.active && !confirm("Tạo URL mới sẽ ngắt URL đang dùng. Claude / ChatGPT đã kết nối bằng URL cũ cần dán lại URL mới. Tiếp tục?")) return;
    setBusy(true);
    setErr("");
    try {
      const r = await papi.post<McpStatus & { url: string }>("/mcp/token");
      setFresh(r.url);
      setSt({ ...r, endpoint: st?.endpoint ?? "" });
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    if (!confirm("Thu hồi URL kết nối? Claude / ChatGPT sẽ không đăng hay xem cơ hội của bạn được nữa.")) return;
    setBusy(true);
    setErr("");
    try {
      await papi.del("/mcp/token");
      setFresh("");
      setSt((s) => ({ active: false, endpoint: s?.endpoint ?? "" }));
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  const url = fresh || "<URL kết nối của bạn>";

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Kết nối AI</h1>
          <p>Đăng và theo dõi cơ hội ngay trong Claude hoặc ChatGPT — chỉ cần kể cho AI bạn biết gì</p>
        </div>
      </div>

      <div className="adm-grid side">
        <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
          <section className="adm-card">
            <div className="hd"><h2>URL kết nối của bạn</h2></div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              {err ? <div className="adm-alert" role="alert">{err}</div> : null}
              {!st ? (
                <p className="muted">Đang tải…</p>
              ) : fresh ? (
                <>
                  <div className="adm-alert warn">
                    Chép URL này ngay — vì lý do bảo mật LeadScan <b>chỉ hiện 1 lần</b>. Ai có URL đều đăng được cơ hội dưới tên bạn, hãy giữ như mật khẩu.
                  </div>
                  <div className="ptn-mcp-url">
                    <code>{fresh}</code>
                    <CopyBtn text={fresh} label="Chép URL" />
                  </div>
                  <p className="muted" style={{ fontSize: 13 }}>Tiếp theo: làm theo hướng dẫn bên dưới để dán URL vào Claude hoặc ChatGPT.</p>
                </>
              ) : st.active ? (
                <>
                  <dl className="adm-kv">
                    <dt>Trạng thái</dt><dd><span className="adm-badge s-active">Đang hoạt động</span></dd>
                    <dt>URL</dt><dd className="mono">…/api/mcp/lsm_…{st.hint}</dd>
                    <dt>Tạo lúc</dt><dd>{fmtDateTime(st.created_at)}</dd>
                    <dt>Dùng lần cuối</dt><dd>{st.last_used_at ? fmtDateTime(st.last_used_at) : "Chưa dùng"}</dd>
                  </dl>
                  <p className="muted" style={{ fontSize: 13 }}>
                    URL đầy đủ chỉ hiện 1 lần lúc tạo. Quên URL, cần kết nối thêm ứng dụng, hoặc nghi bị lộ? Tạo URL mới — URL cũ ngừng hoạt động ngay.
                  </p>
                </>
              ) : (
                <p>Bạn chưa có URL kết nối. Tạo URL rồi dán vào Claude hoặc ChatGPT để AI đăng cơ hội giúp bạn.</p>
              )}
              {st ? (
                <div className="adm-actions" style={{ justifyContent: "flex-start" }}>
                  <button className="adm-btn primary" onClick={create} disabled={busy}>
                    <Icon name={st.active ? "refresh" : "plus"} size={14} /> {busy ? "Đang xử lý…" : st.active ? "Tạo URL mới" : "Tạo URL kết nối"}
                  </button>
                  {st.active ? <button className="adm-btn ghost" onClick={revoke} disabled={busy}>Thu hồi</button> : null}
                </div>
              ) : null}
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Cách kết nối</h2></div>
            <div className="ptn-mcp-tabs" role="tablist" aria-label="Chọn ứng dụng AI">
              {([["claude", "Claude"], ["chatgpt", "ChatGPT"], ["khac", "Ứng dụng khác"]] as [Tab, string][]).map(([k, l]) => (
                <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : undefined} onClick={() => setTab(k)}>{l}</button>
              ))}
            </div>
            <div className="ptn-doc" role="tabpanel">
              {tab === "claude" ? (
                <>
                  <ol>
                    <li>Mở <b>claude.ai</b> (hoặc ứng dụng Claude trên máy tính) → <b>Settings</b> (Cài đặt) → <b>Connectors</b>.</li>
                    <li>Bấm <b>Add custom connector</b>.</li>
                    <li>Name: <b>LeadScan Đối tác</b>. Remote MCP server URL: dán URL kết nối. Không cần mở Advanced settings. Bấm <b>Add</b>.</li>
                    <li>Trong khung chat, bấm nút <b>+</b> (hoặc biểu tượng công cụ) và bật <b>LeadScan Đối tác</b>.</li>
                    <li>Nhắn cho Claude, vd: “Đăng cơ hội lên LeadScan: …”. Lần đầu Claude sẽ hỏi bạn cho phép dùng công cụ — chọn cho phép.</li>
                  </ol>
                  <p className="muted" style={{ fontSize: 13 }}>Không thấy mục Connectors hoặc Add custom connector: gói Claude của bạn có thể chưa hỗ trợ trình kết nối tuỳ chỉnh.</p>
                </>
              ) : tab === "chatgpt" ? (
                <>
                  <ol>
                    <li>Mở <b>chatgpt.com</b> trên máy tính → <b>Settings</b> (Cài đặt) → <b>Apps &amp; Connectors</b> → <b>Advanced settings</b> → bật <b>Developer mode</b>.</li>
                    <li>Quay lại <b>Apps &amp; Connectors</b>, bấm <b>Create</b>.</li>
                    <li>Name: <b>LeadScan Đối tác</b>. MCP Server URL: dán URL kết nối. Authentication: <b>No authentication</b>. Tick “I trust this application” → <b>Create</b>.</li>
                    <li>Trong khung chat, bấm <b>+</b> → <b>Developer mode</b> và chọn <b>LeadScan Đối tác</b>.</li>
                    <li>Nhắn cho ChatGPT như bình thường. Trước khi đăng, ChatGPT sẽ hỏi bạn xác nhận — bấm <b>Confirm</b>.</li>
                  </ol>
                  <p className="muted" style={{ fontSize: 13 }}>Developer mode chỉ có trên bản web và một số gói ChatGPT trả phí. Tên các mục có thể thay đổi theo phiên bản ChatGPT.</p>
                </>
              ) : (
                <>
                  <p>Ứng dụng hỗ trợ MCP qua HTTP (Streamable HTTP) đều dùng được — Claude Code, Cursor, VS Code…</p>
                  <p style={{ marginTop: 8 }}><b>Claude Code</b> (dòng lệnh):</p>
                  <div className="ptn-mcp-url"><code>claude mcp add --transport http leadscan {url}</code>{fresh ? <CopyBtn text={`claude mcp add --transport http leadscan ${fresh}`} /> : null}</div>
                  <p style={{ marginTop: 8 }}><b>Cấu hình JSON</b> (Cursor, VS Code…):</p>
                  <pre className="ptn-mcp-pre">{`{\n  "mcpServers": {\n    "leadscan": { "url": "${url}" }\n  }\n}`}</pre>
                  <p className="muted" style={{ fontSize: 13 }}>Ứng dụng cho thêm header có thể dùng <code>{st?.endpoint || "https://leadscan.net/api/mcp"}</code> với <code>Authorization: Bearer lsm_…</code> (phần sau /api/mcp/ trong URL).</p>
                </>
              )}
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Câu lệnh mẫu</h2></div>
            <div className="ptn-doc" style={{ display: "grid", gap: 10 }}>
              {PROMPTS.map((p) => (
                <div key={p} className="ptn-mcp-prompt"><span>{p}</span><CopyBtn text={p} /></div>
              ))}
              <p className="muted" style={{ fontSize: 13 }}>
                AI sẽ hỏi thêm phần còn thiếu (ngành, nguồn biết tin, độ chắc chắn…), đọc lại toàn bộ nội dung và chỉ đăng khi bạn xác nhận cam kết thông tin.
              </p>
            </div>
          </section>
        </div>

        <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
          <section className="adm-card">
            <div className="hd"><h2>AI làm được gì</h2></div>
            <ul className="ptn-steps">
              {TOOLS.map(([t, d], i) => (
                <li key={t}><span className="dot">{i + 1}</span><div><b>{t}</b><span>{d}</span></div></li>
              ))}
            </ul>
          </section>
          <section className="adm-card">
            <div className="hd"><h2>Lưu ý</h2></div>
            <div className="ptn-doc">
              <ul>
                <li>Cơ hội đăng qua AI được xác minh và tính thưởng như đăng bằng form: ít nhất 1 ly cafe ({reward.cafe.toLocaleString("vi-VN")}đ) cho mỗi cơ hội đạt.</li>
                <li>Cùng giới hạn số cơ hội mỗi ngày, cùng quy tắc lọc trùng và không nhận dữ liệu cá nhân.</li>
                <li>Ảnh minh chứng: thêm trong mục <a href="/doi-tac/co-hoi">Cơ hội của tôi</a> khi cơ hội còn trạng thái Đã gửi.</li>
                <li>URL chỉ đăng và xem cơ hội của bạn — không xem được ví, hồ sơ thanh toán và không rút tiền được.</li>
                <li>Giữ URL như mật khẩu. Nghi bị lộ: bấm <b>Tạo URL mới</b> hoặc <b>Thu hồi</b>.</li>
              </ul>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
