"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { Field, Icon, Skeleton } from "@/components/admin/ui";
import { MultiSelect } from "@/components/member/MultiSelect";
import { errFields, errMsg, mapi } from "@/lib/member/api";

interface JoinInfo {
  already_partner: boolean;
  prefill: { full_name: string; email: string; phone: string };
  industries: string[];
  regions: string[];
  kinds: Record<"personal" | "org", string>;
}

/** Thành viên đăng ký làm đối tác bằng chính tài khoản đang dùng — không nhập lại email / mật khẩu. */
export default function BecomePartnerPage() {
  const [d, setD] = useState<JoinInfo | null>(null);
  const [error, setError] = useState("");
  const [kind, setKind] = useState<"personal" | "org">("personal");
  const [industries, setIndustries] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Trở thành đối tác · LeadScan B2B";
    mapi.get<JoinInfo>("/partner-join").then(setD, (e) => setError(errMsg(e)));
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setMsg("");
    setFields({});
    try {
      const r = await mapi.post<{ redirect: string }>("/partner-join", {
        full_name: String(f.get("full_name") ?? ""),
        phone: String(f.get("phone") ?? ""),
        kind,
        org_name: String(f.get("org_name") ?? ""),
        org_tax_code: String(f.get("org_tax_code") ?? ""),
        industries,
        regions,
        agree: f.get("agree") === "on",
      });
      location.href = r.redirect; // sang cổng đối tác, nhập mã OTP đã gửi về email
    } catch (err) {
      setMsg(errMsg(err));
      setFields(errFields(err));
      setBusy(false);
    }
  }

  if (!d) return error ? <div className="adm-alert">{error}</div> : <Skeleton h={320} />;

  if (d.already_partner)
    return (
      <section className="adm-card">
        <div className="bd" style={{ display: "grid", gap: 12, maxWidth: 560 }}>
          <div className="adm-alert ok">Tài khoản của bạn đã là <b>đối tác LeadScan</b>.</div>
          <a className="adm-btn primary" href="/doi-tac/tong-quan" style={{ justifySelf: "start" }}><Icon name="users" size={16} /> Sang cổng đối tác</a>
        </div>
      </section>
    );

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Trở thành đối tác LeadScan</h1>
          <p>Giới thiệu cơ hội kinh doanh B2B bạn biết — LeadScan xác minh, bán phiếu và chia hoa hồng vào ví đối tác của bạn.</p>
        </div>
      </div>

      <div className="adm-grid side">
        <section className="adm-card">
          <div className="hd"><h2>Thông tin đối tác</h2></div>
          <form className="bd adm-form" onSubmit={submit} noValidate>
            {msg ? <div className="adm-alert full" role="alert">{msg}</div> : null}
            <Field label="Họ và tên" htmlFor="pj-name" error={fields.full_name}>
              <input id="pj-name" className="adm-input" name="full_name" maxLength={100} defaultValue={d.prefill.full_name} aria-invalid={!!fields.full_name} />
            </Field>
            <Field label="Số điện thoại liên hệ" htmlFor="pj-phone" error={fields.phone}>
              <input id="pj-phone" className="adm-input" name="phone" inputMode="tel" maxLength={20} defaultValue={d.prefill.phone} placeholder="09xx xxx xxx" aria-invalid={!!fields.phone} />
            </Field>
            <Field label="Email đăng nhập" full>
              <div className="adm-input" style={{ display: "flex", alignItems: "center", background: "var(--line-2)", color: "var(--muted)" }}>
                {d.prefill.email}
              </div>
            </Field>
            <Field label="Bạn tham gia với tư cách" full error={fields.kind}>
              <div className="adm-checks">
                {(Object.entries(d.kinds) as ["personal" | "org", string][]).map(([k, v]) => (
                  <label key={k}><input type="radio" name="kind" checked={kind === k} onChange={() => setKind(k)} /> {v}</label>
                ))}
              </div>
            </Field>
            {kind === "org" ? (
              <>
                <Field label="Tên tổ chức" htmlFor="pj-org" error={fields.org_name}>
                  <input id="pj-org" className="adm-input" name="org_name" maxLength={200} aria-invalid={!!fields.org_name} />
                </Field>
                <Field label="Mã số thuế tổ chức" htmlFor="pj-tax" error={fields.org_tax_code}>
                  <input id="pj-tax" className="adm-input" name="org_tax_code" inputMode="numeric" maxLength={14} aria-invalid={!!fields.org_tax_code} />
                </Field>
              </>
            ) : null}
            <div className="full">
              <MultiSelect icon="factory" label="Ngành bạn hay tiếp xúc (không bắt buộc)" options={d.industries} value={industries} onChange={setIndustries} placeholder="Gõ ngành, vd: bao bì, xây dựng…" />
            </div>
            <div className="full">
              <MultiSelect icon="map" label="Khu vực bạn hay tiếp xúc (không bắt buộc)" options={d.regions} value={regions} onChange={setRegions} placeholder="Gõ tỉnh/thành…" />
            </div>
            <div className="full" style={{ display: "grid", gap: 4 }}>
              <div className="adm-checks">
                <label>
                  <input type="checkbox" name="agree" /> Tôi đồng ý <a href="/doi-tac/dieu-khoan" target="_blank" rel="noopener" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Điều khoản đối tác và Chính sách bảo mật</a>
                </label>
              </div>
              {fields.agree ? <span className="adm-err">{fields.agree}</span> : null}
            </div>
            <div className="adm-actions full" style={{ justifyContent: "flex-start" }}>
              <button className="adm-btn primary" disabled={busy}>{busy ? "Đang đăng ký…" : "Đăng ký làm đối tác"}</button>
            </div>
          </form>
        </section>

        <section className="adm-card">
          <div className="hd"><h2>Dùng chung 1 tài khoản</h2></div>
          <div className="bd" style={{ display: "grid", gap: 12, fontSize: 13.5 }}>
            <ol className="adm-steps">
              <li>Không cần tạo tài khoản mới: đối tác dùng <b>đúng email và mật khẩu</b> bạn đang đăng nhập.</li>
              <li>Sau khi đăng ký, LeadScan gửi <b>mã xác thực</b> về email {d.prefill.email} để kích hoạt cổng đối tác.</li>
              <li>Từ đó, đăng nhập 1 lần là vào được cả cổng thành viên và cổng đối tác.</li>
            </ol>
            <p className="muted">Ví điểm của doanh nghiệp và ví hoa hồng đối tác là 2 ví riêng. <Link href="/doi-tac" target="_blank" style={{ color: "var(--brand-600)" }}>Tìm hiểu chương trình đối tác</Link></p>
          </div>
        </section>
      </div>
    </>
  );
}
