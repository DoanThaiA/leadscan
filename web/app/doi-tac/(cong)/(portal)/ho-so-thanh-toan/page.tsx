"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { Field } from "@/components/admin/ui";
import { usePartner } from "@/components/partner/PartnerContext";
import { fmtDateTime } from "@/lib/admin/format";
import { ApiError, errFields, errMsg, papi, type PayoutProfile } from "@/lib/partner/api";

interface ProfileRes {
  profile: PayoutProfile | null;
  kind: "personal" | "org";
  org_name: string;
  org_tax_code: string;
}

/** Bỏ dấu, viết hoa — gợi ý tên chủ tài khoản đúng dạng ngân hàng in trên thẻ / sao kê. */
const bankName = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toUpperCase().replace(/\s+/g, " ").trim();

/** Hồ sơ thanh toán — chỉ cần khi rút tiền lần đầu (brief 6.2). Không thu ảnh CCCD. */
export default function PayoutProfilePage() {
  const { me } = usePartner();
  const [data, setData] = useState<ProfileRes | null>(null);
  const [banks, setBanks] = useState<{ bin: string; name: string }[]>([]);
  const [editing, setEditing] = useState(false);
  const [bin, setBin] = useState("");
  const [legal, setLegal] = useState("");
  const [holder, setHolder] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Hồ sơ thanh toán · Đối tác LeadScan";
    papi.get<ProfileRes>("/payout-profile").then((d) => {
      setData(d);
      setEditing(!d.profile);
      setLegal(d.profile?.legal_name ?? (d.kind === "org" ? d.org_name : me.full_name));
      setBin(d.profile?.bank_bin ?? "");
      setHolder(d.profile?.account_holder ?? "");
    }, (e) => setMsg({ ok: false, text: errMsg(e) }));
    papi.get<{ banks: { bin: string; name: string }[] }>("/banks").then((r) => setBanks(r.banks), () => {});
  }, [me.full_name]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    setBusy(true);
    setErrors({});
    setMsg(null);
    try {
      const d = await papi.put<ProfileRes>("/payout-profile", { ...f, bank_bin: bin === "other" ? "" : bin, legal_name: legal, account_holder: holder });
      setData(d);
      setEditing(false);
      setMsg({ ok: true, text: "Đã lưu hồ sơ thanh toán. Số định danh và số tài khoản được mã hoá khi lưu." });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
      if (err instanceof ApiError) setErrors(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  if (!data) return msg ? <div className="adm-alert">{msg.text}</div> : <div className="adm-empty">Đang tải…</div>;
  const org = data.kind === "org";
  const p = data.profile;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Hồ sơ thanh toán</h1>
          <p>Tài khoản ngân hàng chính chủ để nhận tiền rút — chỉ cần khi rút lần đầu</p>
        </div>
        {p && !editing ? <button className="adm-btn" onClick={() => setEditing(true)}>Cập nhật</button> : null}
      </div>
      {msg ? <div className={msg.ok ? "adm-alert ok" : "adm-alert"} style={{ marginBottom: 16 }}>{msg.text}</div> : null}

      <div className="adm-grid side">
        <section className="adm-card">
          {p && !editing ? (
            <>
              <div className="hd"><h2>Hồ sơ hiện tại</h2></div>
              <div className="bd">
                <dl className="adm-kv">
                  <dt>{org ? "Tổ chức" : "Họ và tên"}</dt><dd>{p.legal_name}</dd>
                  {!org ? <><dt>Số định danh</dt><dd className="mono">{p.id_masked}</dd></> : null}
                  <dt>Mã số thuế</dt><dd className="mono">{p.tax_code || (org ? "—" : "Dùng số định danh")}</dd>
                  <dt>Ngân hàng</dt><dd>{p.bank_name}</dd>
                  <dt>Số tài khoản</dt><dd className="mono">{p.account_masked}</dd>
                  <dt>Chủ tài khoản</dt><dd>{p.account_holder} {p.name_match ? <span style={{ color: "var(--ok)" }}>✓ khớp tên hồ sơ</span> : null}</dd>
                  <dt>Cập nhật</dt><dd>{fmtDateTime(p.updated_at)}</dd>
                </dl>
                <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>Lệnh rút đang chờ vẫn chi về tài khoản lúc đặt lệnh. Đổi tài khoản chỉ áp dụng cho lệnh rút mới.</p>
              </div>
            </>
          ) : (
            <form onSubmit={onSubmit} noValidate>
              <div className="hd"><h2>{p ? "Cập nhật hồ sơ" : "Tạo hồ sơ thanh toán"}</h2></div>
              <div className="bd ptn-grid">
                <Field label={org ? "Tên tổ chức" : "Họ và tên (đúng như CCCD)"} error={errors.legal_name} htmlFor="pp-legal">
                  <input id="pp-legal" className="adm-input" value={legal} disabled={org} onChange={(e) => setLegal(e.target.value)} maxLength={200} />
                </Field>
                {!org ? (
                  <Field label="Số định danh cá nhân (CCCD, 12 số)" error={errors.id_number} htmlFor="pp-id">
                    <input id="pp-id" className="adm-input" name="id_number" inputMode="numeric" maxLength={12} placeholder={p ? `Nhập lại (hiện ${p.id_masked})` : ""} autoComplete="off" />
                  </Field>
                ) : null}
                <Field label={org ? "Mã số thuế tổ chức" : "MST cá nhân (không bắt buộc)"} error={errors.tax_code} htmlFor="pp-tax">
                  <input id="pp-tax" className="adm-input" name="tax_code" inputMode="numeric" maxLength={14} defaultValue={org ? data.org_tax_code : p?.tax_code ?? ""} disabled={org}
                    placeholder={org ? "" : "Để trống nếu dùng số định danh làm MST"} />
                </Field>
                <Field label="Ngân hàng" error={errors.bank_bin} htmlFor="pp-bank">
                  <select id="pp-bank" className="adm-input" value={bin} onChange={(e) => setBin(e.target.value)}>
                    <option value="">Chọn ngân hàng…</option>
                    {banks.map((b) => <option key={b.bin} value={b.bin}>{b.name}</option>)}
                    <option value="other">Ngân hàng khác…</option>
                  </select>
                </Field>
                {bin === "other" ? (
                  <Field label="Tên ngân hàng" htmlFor="pp-bname"><input id="pp-bname" className="adm-input" name="bank_name" maxLength={100} /></Field>
                ) : null}
                <Field label="Số tài khoản" error={errors.account_no} htmlFor="pp-acc">
                  <input id="pp-acc" className="adm-input" name="account_no" inputMode="numeric" maxLength={20} placeholder={p ? `Nhập lại (hiện ${p.account_masked})` : ""} autoComplete="off" />
                </Field>
                <Field label="Tên chủ tài khoản (như trên ngân hàng)" error={errors.account_holder} htmlFor="pp-holder">
                  <div style={{ display: "flex", gap: 8 }}>
                    <input id="pp-holder" className="adm-input" value={holder} onChange={(e) => setHolder(e.target.value.toUpperCase())} maxLength={200} placeholder="NGUYEN VAN A" />
                    <button type="button" className="adm-btn" onClick={() => setHolder(bankName(legal))}>Điền theo tên</button>
                  </div>
                </Field>
                <div className="full adm-actions" style={{ justifyContent: "flex-start" }}>
                  <button className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Lưu hồ sơ"}</button>
                  {p ? <button type="button" className="adm-btn" onClick={() => { setEditing(false); setErrors({}); }}>Huỷ</button> : null}
                </div>
              </div>
            </form>
          )}
        </section>

        <section className="adm-card">
          <div className="hd"><h2>Vì sao cần thông tin này?</h2></div>
          <div className="bd" style={{ display: "grid", gap: 8, fontSize: 13.5, color: "var(--ink-2)" }}>
            <p>LeadScan <b>chỉ chi về tài khoản đứng tên bạn</b>{org ? " (tên tổ chức)" : ""} — tên chủ tài khoản phải trùng tên hồ sơ.</p>
            {!org ? <p>Số định danh và MST dùng để khấu trừ, kê khai thuế TNCN và cấp chứng từ khấu trừ cho bạn. LeadScan không thu ảnh CCCD.</p>
              : <p>Đối tác tổ chức xuất hoá đơn cho khoản hoa hồng trước khi LeadScan chi.</p>}
            <p>Số định danh và số tài khoản được <b>mã hoá</b> khi lưu; trong cổng chỉ hiển thị 4 số cuối.</p>
            <p><Link href="/doi-tac/rut-tien" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Đến trang Rút tiền →</Link></p>
          </div>
        </section>
      </div>
    </>
  );
}
