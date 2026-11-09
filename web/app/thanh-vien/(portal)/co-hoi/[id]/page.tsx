"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { Dialog, Icon, ScoreChip, Skeleton } from "@/components/admin/ui";
import { useMember } from "@/components/member/MemberContext";
import { fmtDate, fmtDateTime, fromNow } from "@/lib/admin/format";
import { AttachmentGallery } from "@/components/member/AttachmentGallery";
import { type Attachment, ENRICH_STATUS, type EnrichReq, fmtPts, type Opp } from "@/lib/commerce";
import { ApiError, errMsg, mapi } from "@/lib/member/api";

interface Resp {
  opportunity: Opp;
  purchase: { id: number; price: number; created_at: string; enrich_requests: EnrichReq[] } | null;
  attachments?: Attachment[]; // chỉ khi đã mua — link xem/tải ký sẵn ngắn hạn
  attachment_counts?: { images: number; files: number }; // chưa mua: chỉ biết số lượng
}

export default function OppDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { me, refresh } = useMember();
  const [d, setD] = useState<Resp | null>(null);
  const [error, setError] = useState("");
  const [buying, setBuying] = useState(false);
  const [buyErr, setBuyErr] = useState<{ text: string; status: number } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => mapi.get<Resp>(`/opportunities/${id}`).then(setD, (e) => setError(errMsg(e))), [id]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (d) document.title = `${d.opportunity.title} · LeadScan B2B`;
  }, [d]);

  async function buy() {
    setBusy(true);
    setBuyErr(null);
    try {
      await mapi.post(`/opportunities/${id}/purchase`);
      setBuying(false);
      await Promise.all([load(), refresh()]);
    } catch (e) {
      setBuyErr({ text: errMsg(e), status: e instanceof ApiError ? e.status : 0 });
    } finally {
      setBusy(false);
    }
  }

  const [saving, setSaving] = useState(false);
  async function toggleSave() {
    if (!d) return;
    setSaving(true);
    try {
      if (d.opportunity.saved) await mapi.del(`/saved/${id}`);
      else await mapi.post(`/saved/${id}`);
      setD({ ...d, opportunity: { ...d.opportunity, saved: !d.opportunity.saved } });
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div className="adm-card adm-empty">{error} <p style={{ marginTop: 12 }}><Link className="adm-btn" href="/thanh-vien/co-hoi">← Tất cả cơ hội</Link></p></div>;
  if (!d) return <div style={{ display: "grid", gap: 16 }}><Skeleton h={32} w="50%" /><Skeleton h={260} /></div>;

  const o = d.opportunity;
  const owned = !!d.purchase;
  const enough = me.company.points_balance >= o.price;

  return (
    <>
      <Link href="/thanh-vien/co-hoi" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}>
        <Icon name="back" size={16} /> Tất cả cơ hội
      </Link>
      <div className="adm-head">
        <div style={{ minWidth: 0 }}>
          <p className="mono">{o.code} · Đăng {o.published_at ? fromNow(o.published_at) : ""}</p>
          <h1 style={{ marginTop: 4 }}>{o.title}</h1>
        </div>
        <ScoreChip score={o.score} />
      </div>

      <div className="adm-grid side">
        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><h2>Thông tin cơ hội</h2></div>
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              {o.summary ? <p style={{ whiteSpace: "pre-wrap", color: "var(--ink)" }}>{o.summary}</p> : null}
              <dl className="adm-kv">
                <dt>Ngành</dt><dd>{o.industry || "—"}</dd>
                <dt>Khu vực</dt><dd>{[o.province, o.region].filter(Boolean).join(" · ") || "—"}</dd>
                <dt>Nguồn tin</dt><dd>{o.source_type || "—"}</dd>
                <dt>Quy mô</dt><dd>{o.scale || "—"}</dd>
                <dt>Giá trị ước tính</dt><dd>{o.estimated_value || "—"}</dd>
                <dt>Hạn chót</dt><dd>{o.deadline ? fmtDate(o.deadline) : "—"}</dd>
                <dt>Mức enrich</dt><dd>{o.enrich_round ? `Vòng ${o.enrich_round}` : "Phiếu cơ bản"}</dd>
              </dl>
            </div>
          </section>

          {owned ? (
            <>
              <section className="adm-card">
                <div className="hd"><h2>Bên có nhu cầu & chi tiết</h2><span className="adm-badge s-active">Đã mở khoá</span></div>
                <div className="bd" style={{ display: "grid", gap: 12 }}>
                  <dl className="adm-kv">
                    <dt>Đơn vị</dt><dd><b>{o.buyer_name || "—"}</b></dd>
                    {o.source_url ? (<><dt>Link nguồn</dt><dd><a href={o.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brand-600)" }}>{o.source_url}</a></dd></>) : null}
                  </dl>
                  {o.detail ? <p style={{ whiteSpace: "pre-wrap" }}>{o.detail}</p> : null}
                </div>
              </section>
              <section className="adm-card">
                <div className="hd"><h2>Đầu mối liên hệ ({o.contacts?.length ?? 0})</h2></div>
                <div className="bd" style={{ paddingTop: 4, paddingBottom: 4 }}>
                  {o.contacts?.length ? o.contacts.map((c, i) => (
                    <div className="adm-contact" key={c.id}>
                      <div className="lines">
                        <div><b>{i + 1}. {c.full_name || "(chưa có tên)"}</b>{c.title ? <span className="muted"> · {c.title}</span> : null}</div>
                        {c.phone ? <a href={`tel:${c.phone}`}><Icon name="phone" size={13} /> {c.phone}</a> : null}
                        {c.email ? <a href={`mailto:${c.email}`} className="muted"><Icon name="mail" size={13} /> {c.email}</a> : null}
                        {c.note ? <span className="muted">{c.note}</span> : null}
                      </div>
                    </div>
                  )) : <p className="muted" style={{ padding: "12px 0" }}>Chưa có đầu mối — gửi yêu cầu enrich để LeadScan tìm thêm.</p>}
                </div>
              </section>
              {d.attachments?.length ? <AttachmentGallery items={d.attachments} onExpired={load} /> : null}
              <EnrichBox purchaseId={d.purchase!.id} requests={d.purchase!.enrich_requests} onDone={load} />
            </>
          ) : (
            <section className="adm-card">
              <div className="bd adm-locked">
                <Icon name="lock" />
                <span>
                  Tên bên có nhu cầu, mô tả chi tiết và <b>{o.contact_count} đầu mối liên hệ</b>
                  {lockedFiles(d.attachment_counts) ? <>, kèm <b>{lockedFiles(d.attachment_counts)}</b></> : null} sẽ mở khoá sau khi mua phiếu.
                </span>
              </div>
            </section>
          )}
        </div>

        <div className="adm-grid">
          <section className="adm-card">
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              <div className="adm-price" style={{ fontSize: 26 }}>
                {fmtPts(o.price)}
                <small>{o.max_buyers === 1 ? "Phiếu độc quyền — chỉ 1 doanh nghiệp mua" : `Còn ${Math.max(0, o.max_buyers - o.sold_count)}/${o.max_buyers} lượt mua`}</small>
              </div>
              {owned ? (
                <div className="adm-alert ok">Bạn đã mua phiếu này lúc {fmtDateTime(d.purchase!.created_at)} ({fmtPts(d.purchase!.price)}).</div>
              ) : o.sold_out ? (
                <div className="adm-alert">Phiếu đã hết lượt mua.</div>
              ) : !me.company.membership_active ? (
                <Link className="adm-btn primary" href="/thanh-vien/nap-tien" style={{ height: 42 }}>Kích hoạt thành viên để mua</Link>
              ) : (
                <button className="adm-btn primary" style={{ height: 42 }} onClick={() => { setBuyErr(null); setBuying(true); }}>
                  <Icon name="ticket" size={16} /> Mua phiếu cơ hội
                </button>
              )}
              {!owned ? (
                <button className={o.saved ? "adm-btn saved" : "adm-btn"} onClick={toggleSave} disabled={saving} aria-pressed={!!o.saved}
                  style={o.saved ? { color: "var(--brand-600)", borderColor: "var(--brand-100)", background: "var(--brand-50)" } : undefined}>
                  <Icon name="bookmark" size={16} /> {o.saved ? "Đã lưu trong kho" : "Thêm vào kho"}
                </button>
              ) : null}
              <p className="muted" style={{ fontSize: 12.5 }}>Số dư hiện tại: <b style={{ color: "var(--ink)" }}>{fmtPts(me.company.points_balance)}</b></p>
            </div>
          </section>
          <section className="adm-card">
            <div className="hd"><h2>Điểm phù hợp với bạn</h2><ScoreChip score={o.score} /></div>
            <div className="bd adm-meter">
              {[["Khớp yêu cầu của bạn", o.score_fit], ["Độ cấp thiết", o.score_urgency], ["Độ tin cậy nguồn", o.score_trust]].map(([label, v]) => (
                <div key={label as string}>
                  <span>{label}</span>
                  <span className="track"><i style={{ width: `${v}%` }} /></span>
                  <b>{v}</b>
                </div>
              ))}
            </div>
            <div className="bd" style={{ display: "grid", gap: 6, paddingTop: 0 }}>
              {o.reasons?.length ? (
                <ul className="muted" style={{ fontSize: 12.5, paddingLeft: 18, margin: 0 }}>
                  {o.reasons.map((r) => <li key={r}>{r}</li>)}
                </ul>
              ) : null}
              <p className="muted" style={{ fontSize: 12 }}>Điểm tính riêng cho doanh nghiệp bạn từ các phiếu tìm cơ hội; điểm càng cao thì giá phiếu càng cao.</p>
            </div>
          </section>
        </div>
      </div>

      <Dialog
        open={buying}
        title="Xác nhận mua phiếu"
        onClose={() => setBuying(false)}
        footer={
          <>
            <button className="adm-btn" onClick={() => setBuying(false)}>Huỷ</button>
            {buyErr?.status === 402 && buyErr.text.includes("Số dư") ? (
              <Link className="adm-btn primary" href="/thanh-vien/nap-tien">Nạp thêm điểm</Link>
            ) : (
              <button className="adm-btn primary" onClick={buy} disabled={busy || !enough}>{busy ? "Đang mua…" : `Mua với ${fmtPts(o.price)}`}</button>
            )}
          </>
        }
      >
        <p><b>{o.title}</b></p>
        <dl className="adm-kv">
          <dt>Giá phiếu</dt><dd><b>{fmtPts(o.price)}</b></dd>
          <dt>Số dư hiện tại</dt><dd>{fmtPts(me.company.points_balance)}</dd>
          <dt>Số dư sau khi mua</dt><dd style={{ color: enough ? "var(--ink)" : "var(--danger)" }}>{fmtPts(me.company.points_balance - o.price)}</dd>
        </dl>
        {!enough ? <div className="adm-alert">Số dư không đủ. Vui lòng nạp thêm điểm.</div> : null}
        {buyErr ? <div className="adm-alert">{buyErr.text}</div> : null}
        <p className="muted" style={{ fontSize: 12.5 }}>Sau khi mua, thông tin bên có nhu cầu và đầu mối liên hệ được mở khoá ngay và lưu trong mục “Phiếu đã mua”.</p>
      </Dialog>
    </>
  );
}

function EnrichBox({ purchaseId, requests, onDone }: { purchaseId: number; requests: EnrichReq[]; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const open = requests.some((r) => r.status === "open");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      await mapi.post(`/purchases/${purchaseId}/enrich`, { note });
      setNote("");
      onDone();
    } catch (err) {
      setMsg(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="adm-card">
      <div className="hd">
        <div>
          <h2>Yêu cầu enrich thêm</h2>
          <p className="muted" style={{ fontSize: 12.5 }}>Cần thêm đầu mối (người ra quyết định, kế toán…)? LeadScan sẽ tìm và bổ sung.</p>
        </div>
      </div>
      <div className="bd" style={{ display: "grid", gap: 12 }}>
        {!open ? (
          <form onSubmit={submit} style={{ display: "grid", gap: 8 }}>
            {msg ? <div className="adm-alert">{msg}</div> : null}
            <textarea className="adm-input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ví dụ: cần số điện thoại giám đốc nhà máy hoặc trưởng phòng kỹ thuật" maxLength={2000} aria-label="Nội dung yêu cầu enrich" />
            <div className="adm-actions"><button className="adm-btn primary sm" disabled={busy || note.trim().length < 3}>{busy ? "Đang gửi…" : "Gửi yêu cầu"}</button></div>
          </form>
        ) : null}
        {requests.length ? (
          <ul className="adm-timeline">
            {requests.map((r) => (
              <li key={r.id} className={r.status === "done" ? "k-status" : "k-note"}>
                <span className="dot"><Icon name="spark" /></span>
                <div>
                  <div className="txt">{r.note}</div>
                  <div className="meta">{ENRICH_STATUS[r.status]} · {fromNow(r.created_at)}</div>
                  {r.reply ? <div className="txt" style={{ marginTop: 6, padding: 8, background: "var(--line-2)", borderRadius: 6 }}>LeadScan: {r.reply}</div> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}

/** "3 ảnh và 2 tài liệu" — số tệp đính kèm mở khoá sau khi mua */
function lockedFiles(c?: { images: number; files: number }): string {
  if (!c) return "";
  const parts = [c.images ? `${c.images} ảnh` : "", c.files ? `${c.files} tài liệu` : ""].filter(Boolean);
  return parts.join(" và ");
}
