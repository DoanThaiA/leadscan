"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/admin/ui";
import { fmtDate } from "@/lib/admin/format";
import { fmtPts, fmtVnd } from "@/lib/commerce";
import { errMsg, mapi } from "@/lib/member/api";

interface Packages {
  membership_active: boolean;
  membership_expires_at: string | null;
  membership: { amount: number; points: number; days: number };
  topup: { packs: number[]; min: number; max: number };
}

export default function TopupPage() {
  const router = useRouter();
  const [p, setP] = useState<Packages | null>(null);
  const [kind, setKind] = useState<"membership" | "topup">("membership");
  const [amount, setAmount] = useState<number>(0);
  const [custom, setCustom] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Nạp tiền · LeadScan B2B";
    mapi.get<Packages>("/packages").then((r) => {
      setP(r);
      setKind(r.membership_active ? "topup" : "membership");
      setAmount(r.topup.packs[0] ?? r.topup.min);
    }, (e) => setError(errMsg(e)));
  }, []);

  const value = kind === "membership" ? p?.membership.amount ?? 0 : custom ? Number(custom.replace(/\D/g, "")) : amount;

  async function create() {
    setBusy(true);
    setError("");
    try {
      const r = await mapi.post<{ order: { code: string } }>("/orders", kind === "membership" ? { kind } : { kind, amount: value });
      router.push(`/thanh-vien/nap-tien/${r.order.code}`);
    } catch (e) {
      setError(errMsg(e));
      setBusy(false);
    }
  }

  if (!p) return error ? <div className="adm-alert">{error}</div> : <Skeleton h={300} />;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Nạp tiền</h1>
          <p>Thanh toán bằng chuyển khoản VietQR qua InfoCMS — điểm được cộng tự động khi nhận tiền.</p>
        </div>
      </div>

      <div className="adm-grid side">
        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><h2>Chọn loại thanh toán</h2></div>
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              <div className="adm-packs">
                <button type="button" className={kind === "membership" ? "adm-pack on" : "adm-pack"} onClick={() => setKind("membership")}>
                  <span>{p.membership_active ? "Gia hạn thành viên" : "Phí thành viên"}</span>
                  <b>{fmtVnd(p.membership.amount)}</b>
                  <span>+{fmtPts(p.membership.points)} · {p.membership.days} ngày</span>
                </button>
                <button
                  type="button"
                  className={kind === "topup" ? "adm-pack on" : "adm-pack"}
                  onClick={() => setKind("topup")}
                  disabled={!p.membership_active}
                  style={!p.membership_active ? { opacity: 0.5, cursor: "not-allowed" } : undefined}
                  title={!p.membership_active ? "Kích hoạt thành viên trước khi nạp thêm" : undefined}
                >
                  <span>Nạp thêm điểm</span>
                  <b>Tuỳ chọn</b>
                  <span>{p.membership_active ? "1đ = 1 điểm" : "Cần là thành viên"}</span>
                </button>
              </div>
              {p.membership_active && kind === "membership" ? (
                <p className="muted" style={{ fontSize: 13 }}>Gia hạn sẽ cộng thêm {p.membership.days} ngày tính từ hạn hiện tại ({p.membership_expires_at ? fmtDate(p.membership_expires_at) : "—"}).</p>
              ) : null}
            </div>
          </section>

          {kind === "topup" ? (
            <section className="adm-card">
              <div className="hd"><h2>Số tiền nạp</h2></div>
              <div className="bd" style={{ display: "grid", gap: 14 }}>
                <div className="adm-packs">
                  {p.topup.packs.map((v) => (
                    <button type="button" key={v} className={!custom && amount === v ? "adm-pack on" : "adm-pack"} onClick={() => { setAmount(v); setCustom(""); }}>
                      <b>{fmtVnd(v)}</b>
                      <span>+{fmtPts(v)}</span>
                    </button>
                  ))}
                </div>
                <div className="adm-field">
                  <label htmlFor="custom">Hoặc nhập số khác ({fmtVnd(p.topup.min)} – {fmtVnd(p.topup.max)})</label>
                  <input id="custom" className="adm-input" inputMode="numeric" placeholder="Ví dụ 3.000.000" value={custom ? Number(custom.replace(/\D/g, "") || 0).toLocaleString("vi-VN") : ""} onChange={(e) => setCustom(e.target.value.replace(/\D/g, ""))} style={{ maxWidth: 260 }} />
                </div>
              </div>
            </section>
          ) : null}
        </div>

        <section className="adm-card">
          <div className="hd"><h2>Tóm tắt</h2></div>
          <div className="bd" style={{ display: "grid", gap: 14 }}>
            <dl className="adm-kv">
              <dt>Nội dung</dt><dd>{kind === "membership" ? (p.membership_active ? "Gia hạn thành viên" : "Phí thành viên 1 năm") : "Nạp thêm điểm"}</dd>
              <dt>Số tiền</dt><dd><b>{fmtVnd(value)}</b></dd>
              <dt>Điểm nhận được</dt><dd className="adm-pos">+{fmtPts(kind === "membership" ? p.membership.points : value)}</dd>
            </dl>
            {error ? <div className="adm-alert">{error}</div> : null}
            <button className="adm-btn primary" style={{ height: 42 }} onClick={create} disabled={busy || value <= 0}>{busy ? "Đang tạo đơn…" : "Tiếp tục thanh toán"}</button>
            <p className="muted" style={{ fontSize: 12.5 }}>Sau khi thanh toán, bạn có thể nhập thông tin để LeadScan xuất hoá đơn VAT.</p>
          </div>
        </section>
      </div>
    </>
  );
}
