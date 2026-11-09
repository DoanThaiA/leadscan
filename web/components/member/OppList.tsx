"use client";

import Link from "next/link";
import { useState } from "react";

import { Dialog, Icon } from "@/components/admin/ui";
import { useMember } from "@/components/member/MemberContext";
import { fromNow } from "@/lib/admin/format";
import { fmtPts, type Opp, scoreClass } from "@/lib/commerce";
import { ApiError, errMsg, mapi } from "@/lib/member/api";

/** Nhãn màu theo nguồn tin — dùng chung với ảnh minh hoạ ở trang chủ (Hero.tsx) */
const SOURCE_BADGE: Record<string, [string, string, string]> = {
  "App đăng mua": ["ĐM", "#FA5320", "#2B1B14"],
  "Dự án & gói thầu": ["DA", "#2563EB", "#fff"],
  "Nhà máy / FDI mới": ["NM", "#16A34A", "#fff"],
  "Hội chợ & triển lãm": ["HC", "#0369A1", "#fff"],
  "Mạng xã hội & nhóm chat": ["MX", "#9333EA", "#fff"],
  "Website doanh nghiệp": ["WB", "#475569", "#fff"],
  "Nguồn chính thống": ["CT", "#F59E0B", "#2B1B14"],
  "Email hỏi hàng": ["EM", "#0F766E", "#fff"],
  "Kết nối giao thương": ["KN", "#B45309", "#fff"],
};

function badge(o: Opp): [string, string, string] {
  if (SOURCE_BADGE[o.source_type]) return SOURCE_BADGE[o.source_type];
  const w = (o.industry || o.title).trim().split(/\s+/);
  return [((w[0]?.[0] ?? "") + (w[1]?.[0] ?? "")).toUpperCase() || "CH", "#475569", "#fff"];
}

export function OppList({ items, onChange }: { items: Opp[]; onChange: (o: Opp) => void }) {
  const { me, refresh } = useMember();
  const [buying, setBuying] = useState<Opp | null>(null);
  const [busy, setBusy] = useState(false);
  const [buyErr, setBuyErr] = useState<{ text: string; status: number } | null>(null);
  const [saving, setSaving] = useState<number | null>(null);
  const [toast, setToast] = useState<{ ok: boolean; text: string } | null>(null);

  async function toggleSave(o: Opp) {
    setSaving(o.id);
    try {
      if (o.saved) await mapi.del(`/saved/${o.id}`);
      else await mapi.post(`/saved/${o.id}`);
      onChange({ ...o, saved: !o.saved });
      setToast({ ok: true, text: o.saved ? "Đã bỏ khỏi kho." : "Đã thêm vào kho của bạn." });
    } catch (e) {
      setToast({ ok: false, text: errMsg(e) });
    } finally {
      setSaving(null);
      setTimeout(() => setToast(null), 2500);
    }
  }

  async function buy() {
    if (!buying) return;
    setBusy(true);
    setBuyErr(null);
    try {
      await mapi.post(`/opportunities/${buying.id}/purchase`);
      onChange({ ...buying, purchased: true, sold_count: buying.sold_count + 1 });
      setBuying(null);
      await refresh();
    } catch (e) {
      setBuyErr({ text: errMsg(e), status: e instanceof ApiError ? e.status : 0 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {toast ? <div className={toast.ok ? "adm-alert ok" : "adm-alert"} role="status" style={{ margin: "0 0 8px" }}>{toast.text}</div> : null}
      <div>
        {items.map((o) => {
          const [txt, bg, fg] = badge(o);
          const left = Math.max(0, o.max_buyers - o.sold_count);
          return (
            <div className="mt-row" key={o.id}>
              <span className="mt-ic" style={{ background: bg, color: fg }} aria-hidden="true">{txt}</span>
              <div style={{ minWidth: 0 }}>
                <Link className="mt-t" href={`/thanh-vien/co-hoi/${o.id}`}>{o.title}</Link>
                <div className="mt-m">
                  {o.source_type ? <span>{o.source_type}</span> : null}
                  {o.province || o.region ? <span>· {o.province || o.region}</span> : null}
                  {o.published_at ? <span>· {fromNow(o.published_at)}</span> : null}
                  {!o.purchased && !o.sold_out ? <span>· {o.max_buyers === 1 ? "Độc quyền" : `Còn ${left}/${o.max_buyers} lượt`}</span> : null}
                </div>
                {o.reasons?.length ? <div className="mt-m"><span>✓ {o.reasons.slice(0, 2).join(" · ")}</span></div> : null}
              </div>
              <span className={`mt-score ${scoreClass(o.score)}`} title="Điểm phù hợp với bạn (0–100)">{o.score}</span>
              <div className="mt-p">
                {fmtPts(o.price)}
                <small>{o.enrich_round ? `Enrich vòng ${o.enrich_round}` : "Phiếu cơ bản"}</small>
              </div>
              <div className="mt-act">
                {o.purchased ? (
                  <Link className="adm-btn sm" href={`/thanh-vien/co-hoi/${o.id}`}><Icon name="check" size={14} /> Đã mua · Xem</Link>
                ) : o.sold_out ? (
                  <span className="adm-badge s-suspended">Hết lượt</span>
                ) : (
                  <button type="button" className="adm-btn sm primary" onClick={() => { setBuyErr(null); setBuying(o); }}>
                    <Icon name="ticket" size={14} /> Mua
                  </button>
                )}
                {!o.purchased ? (
                  <button
                    type="button"
                    className={o.saved ? "adm-btn sm saved" : "adm-btn sm"}
                    onClick={() => toggleSave(o)}
                    disabled={saving === o.id}
                    aria-pressed={o.saved}
                    title={o.saved ? "Bỏ khỏi kho" : "Thêm vào kho để xem/mua sau"}
                  >
                    <Icon name="bookmark" size={14} /> {o.saved ? "Đã lưu" : "Thêm vào kho"}
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <Dialog
        open={!!buying}
        title="Mua phiếu cơ hội"
        onClose={() => setBuying(null)}
        footer={
          <>
            <button className="adm-btn" onClick={() => setBuying(null)} disabled={busy}>Huỷ</button>
            {!me.company.membership_active ? (
              <Link className="adm-btn primary" href="/thanh-vien/nap-tien">Kích hoạt thành viên</Link>
            ) : buyErr?.status === 402 ? (
              <Link className="adm-btn primary" href="/thanh-vien/nap-tien">Nạp thêm điểm</Link>
            ) : (
              <button className="adm-btn primary" onClick={buy} disabled={busy}>{busy ? "Đang mua…" : `Mua ${buying ? fmtPts(buying.price) : ""}`}</button>
            )}
          </>
        }
      >
        {buying ? (
          <div style={{ display: "grid", gap: 10 }}>
            <p><b style={{ color: "var(--ink)" }}>{buying.title}</b></p>
            <p className="muted">
              Giá phiếu <b style={{ color: "var(--ink)" }}>{fmtPts(buying.price)}</b> · Số dư hiện tại{" "}
              <b style={{ color: "var(--ink)" }}>{fmtPts(me.company.points_balance)}</b>
            </p>
            <p className="muted">Sau khi mua, bạn xem được bên có nhu cầu, mô tả chi tiết và {buying.contact_count} đầu mối liên hệ.</p>
            {!me.company.membership_active ? <div className="adm-alert">Bạn cần thanh toán phí thành viên trước khi mua phiếu.</div> : null}
            {buyErr ? <div className="adm-alert" role="alert">{buyErr.text}</div> : null}
          </div>
        ) : null}
      </Dialog>
    </>
  );
}
