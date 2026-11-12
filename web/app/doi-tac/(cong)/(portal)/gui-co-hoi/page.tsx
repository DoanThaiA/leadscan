"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, Suspense, useEffect, useRef, useState } from "react";

import { type BusinessInfo, lookupBusiness, normalizeTaxCode } from "@/lib/business-lookup";
import ImageUploader from "@/components/partner/ImageUploader";
import { ApiError, errFields, errMsg, papi } from "@/lib/partner/api";
import type { PartnerImage, SubOptions, Submission } from "@/lib/partner/submissions";

type Errors = Record<string, string>;
const ORDER = ["title", "company_name", "tax_code", "province", "industry", "kind", "need", "source_type", "source_url", "certainty",
  "contact_phone", "contact_email", "contact_consent", "commitment"];

function Choice({ name, options, value, onChange, error }: {
  name: string; options: Record<string, string>; value: string; onChange: (v: string) => void; error?: string;
}) {
  return (
    <div className="ptn-choice" role="radiogroup" aria-invalid={error ? true : undefined}>
      {Object.entries(options).map(([k, label]) => (
        <label key={k} className={value === k ? "on" : undefined}>
          <input type="radio" name={name} value={k} checked={value === k} onChange={() => onChange(k)} />
          {label}
        </label>
      ))}
    </div>
  );
}

function F({ label, hint, error, children, full, id }: { label: ReactNode; hint?: ReactNode; error?: string; children: ReactNode; full?: boolean; id?: string }) {
  return (
    <div className={full ? "adm-field full" : "adm-field"}>
      <label htmlFor={id}>{label}</label>
      {children}
      {hint ? <span className="muted" style={{ fontSize: 12.5 }}>{hint}</span> : null}
      {error ? <span className="adm-err" data-err>{error}</span> : null}
    </div>
  );
}

/** Form gửi cơ hội (brief mục 8.3). ?sua=<id> → sửa cơ hội đã gửi khi LeadScan chưa bắt đầu xác minh. */
function SubmitForm() {
  const router = useRouter();
  const editId = useSearchParams().get("sua");
  const [initial, setInitial] = useState<Submission | null>(null);
  const [locked, setLocked] = useState<Submission | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [opts, setOpts] = useState<SubOptions | null>(null);
  const [kind, setKind] = useState("");
  const [source, setSource] = useState("");
  const [certainty, setCertainty] = useState("");
  const [connect, setConnect] = useState("");
  const [lookup, setLookup] = useState<BusinessInfo | null>(null);
  const [taxNote, setTaxNote] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [banner, setBanner] = useState("");
  const [busy, setBusy] = useState(false);
  const [images, setImages] = useState<PartnerImage[]>([]);

  useEffect(() => {
    document.title = editId ? "Sửa cơ hội · Đối tác LeadScan" : "Gửi cơ hội · Đối tác LeadScan";
    papi.get<SubOptions>("/submission-options").then(setOpts, (e) => setBanner(errMsg(e)));
  }, [editId]);

  useEffect(() => {
    if (!editId) return;
    papi.get<Submission>(`/submissions/${editId}`).then((s) => {
      if (!s.editable) return setLocked(s);
      setInitial(s);
      setKind(s.kind);
      setSource(s.source_type);
      setCertainty(s.certainty);
      setConnect(s.can_connect);
      setImages(s.images ?? []);
    }, (e) => setBanner(errMsg(e)));
  }, [editId]);

  function field(name: string) {
    return formRef.current?.elements.namedItem(name) as HTMLInputElement | null;
  }

  async function runLookup() {
    const tax = normalizeTaxCode(field("tax_code")?.value ?? "");
    if (!tax) return setTaxNote("Mã số thuế gồm 10 hoặc 13 chữ số.");
    setTaxNote("Đang tra cứu…");
    const r = await lookupBusiness(tax);
    if (!r.ok) {
      setLookup(null);
      return setTaxNote(r.message);
    }
    setLookup(r.data);
    const name = field("company_name");
    if (name) name.value = r.data.name;
    const prov = field("province");
    if (prov && r.data.province && !prov.value) prov.value = r.data.province;
    setErrors(({ company_name: _a, tax_code: _b, province: _c, ...rest }) => rest);
    setTaxNote(r.data.active ? `Đã điền: ${r.data.name}` : `Đã điền: ${r.data.name} — lưu ý trạng thái thuế: ${r.data.status}`);
  }

  function showErrors(er: Errors) {
    setErrors(er);
    const first = ORDER.find((n) => er[n]);
    if (!first) return;
    setTimeout(() => {
      const el = formRef.current?.querySelector<HTMLElement>(`[name="${first}"]`) ?? formRef.current?.querySelector<HTMLElement>("[data-err]");
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
      el?.focus?.({ preventScroll: true });
    }, 50);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (n: string) => String(f.get(n) ?? "").trim();
    const er: Errors = {};
    if (v("title").length < 10) er.title = "Đặt tiêu đề ngắn gọn cho cơ hội (ít nhất 10 ký tự).";
    if (v("company_name").length < 3) er.company_name = "Vui lòng nhập tên doanh nghiệp có nhu cầu.";
    if (v("tax_code") && !normalizeTaxCode(v("tax_code"))) er.tax_code = "Mã số thuế gồm 10 hoặc 13 chữ số (để trống nếu chưa biết).";
    if (!v("province")) er.province = "Vui lòng nhập khu vực / tỉnh thành.";
    if (!v("industry")) er.industry = "Vui lòng chọn ngành hàng.";
    if (!kind) er.kind = "Vui lòng chọn loại cơ hội.";
    if (v("need").length < 30) er.need = "Mô tả nhu cầu cụ thể hơn: mặt hàng/dịch vụ, quy mô, thời điểm cần (ít nhất 30 ký tự).";
    if (!source) er.source_type = "Vui lòng chọn nguồn biết tin.";
    if (source === "public" && !/^https?:\/\/\S+\.\S+$/i.test(v("source_url"))) er.source_url = "Nguồn công khai: vui lòng dán link.";
    if (!certainty) er.certainty = "Vui lòng chọn mức độ chắc chắn.";
    const hasContact = ["contact_name", "contact_title", "contact_phone", "contact_email"].some((n) => v(n));
    if (hasContact && f.get("contact_consent") === null) er.contact_consent = "Vui lòng tick xác nhận người liên hệ đồng ý được giới thiệu.";
    if (f.get("commitment") === null) er.commitment = "Bạn cần cam kết trước khi gửi.";
    if (Object.keys(er).length) return showErrors(er);

    const body = {
      title: v("title"), company_name: v("company_name"), tax_code: v("tax_code"), province: v("province"), industry: v("industry"),
      tax_lookup: lookup && normalizeTaxCode(v("tax_code")) === lookup.taxCode ? { name: lookup.name, status: lookup.status, active: lookup.active } : null,
      kind, need: v("need"), scale: v("scale"), timing: v("timing"),
      source_type: source, source_url: v("source_url"), certainty, evidence: v("evidence"),
      contact_name: v("contact_name"), contact_title: v("contact_title"), contact_phone: v("contact_phone"), contact_email: v("contact_email"),
      contact_consent: f.get("contact_consent") !== null, can_connect: connect, commitment: true,
      attachment_ids: images.map((i) => i.id),
    };
    setBusy(true);
    setBanner("");
    try {
      if (initial) {
        await papi.put<Submission>(`/submissions/${initial.id}`, body);
        router.push(`/doi-tac/co-hoi/${initial.id}?da-sua=1`);
        return;
      }
      const s = await papi.post<Submission>("/submissions", body);
      router.push(`/doi-tac/co-hoi/${s.id}?moi=1`);
    } catch (err) {
      setBusy(false);
      setBanner(errMsg(err));
      if (err instanceof ApiError) showErrors(errFields(err));
    }
  }

  const clear = (e: FormEvent<HTMLFormElement>) => {
    const n = (e.target as HTMLInputElement).name;
    if (n && errors[n]) setErrors(({ [n]: _, ...rest }) => rest);
  };

  if (locked) {
    return (
      <div className="adm-alert warn" style={{ display: "grid", gap: 8 }}>
        <span>Cơ hội <b>{locked.code}</b> đang ở trạng thái “{locked.status_label}” nên không sửa được nữa — LeadScan đã bắt đầu xác minh. Cần bổ sung thông tin? Liên hệ LeadScan.</span>
        <Link href={`/doi-tac/co-hoi/${locked.id}`} style={{ textDecoration: "underline" }}>← Về cơ hội {locked.code}</Link>
      </div>
    );
  }
  if (!opts || (editId && !initial)) return banner ? <div className="adm-alert">{banner}</div> : <div className="adm-empty">Đang tải…</div>;
  const iv = (k: keyof Submission) => (initial ? String(initial[k] ?? "") : undefined);
  const hadContact = !!initial && [initial.contact_name, initial.contact_title, initial.contact_phone, initial.contact_email].some(Boolean);

  return (
    <>
      <div className="adm-head">
        <div>
          {initial ? <Link href={`/doi-tac/co-hoi/${initial.id}`} className="muted" style={{ fontSize: 13 }}>← {initial.code}</Link> : null}
          <h1 style={initial ? { marginTop: 4 } : undefined}>{initial ? `Sửa cơ hội ${initial.code}` : "Gửi cơ hội"}</h1>
          <p>{initial ? "Sửa được cho tới khi LeadScan bắt đầu xác minh. Mã cơ hội và thời điểm gửi giữ nguyên." : "Doanh nghiệp đang có nhu cầu mua hàng / dịch vụ mà bạn biết. Khoảng 2 phút."}</p>
        </div>
        <Link className="adm-btn" href="/doi-tac/chinh-sach">Cơ hội thế nào được nhận?</Link>
      </div>

      <form ref={formRef} noValidate onSubmit={onSubmit} onInput={clear} onChange={clear} className="ptn-form">
        {banner ? <div className="adm-alert" role="alert" style={{ marginBottom: 16 }}>{banner}</div> : null}

        <section className="adm-card">
          <div className="hd"><h2>1. Doanh nghiệp có nhu cầu</h2></div>
          <div className="bd ptn-grid">
            <F label={<>Mã số thuế <span className="muted">(nếu biết — tự điền tên)</span></>} error={errors.tax_code} id="s-tax"
              hint={taxNote || "Có MST giúp xác minh nhanh và tăng điểm chất lượng."}>
              <div style={{ display: "flex", gap: 8 }}>
                <input id="s-tax" className="adm-input" name="tax_code" inputMode="numeric" maxLength={14} placeholder="10 hoặc 13 chữ số" defaultValue={iv("tax_code")}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); runLookup(); } }} />
                <button type="button" className="adm-btn" onClick={runLookup}>Tra cứu</button>
              </div>
            </F>
            <F label="Tên doanh nghiệp *" error={errors.company_name} id="s-name">
              <input id="s-name" className="adm-input" name="company_name" maxLength={200} placeholder="Công ty TNHH ABC" defaultValue={iv("company_name")} />
            </F>
            <F label="Khu vực / tỉnh thành *" error={errors.province} id="s-prov">
              <input id="s-prov" className="adm-input" name="province" maxLength={80} list="s-prov-list" placeholder="Bắc Ninh" defaultValue={iv("province")} />
              <datalist id="s-prov-list">{opts.regions.map((r) => <option key={r} value={r} />)}</datalist>
            </F>
            <F label="Ngành hàng *" error={errors.industry} id="s-ind">
              <select id="s-ind" className="adm-input" name="industry" defaultValue={iv("industry") ?? ""}>
                <option value="" disabled>Chọn ngành hàng…</option>
                {opts.industries.map((x) => <option key={x}>{x}</option>)}
              </select>
            </F>
          </div>
        </section>

        <section className="adm-card">
          <div className="hd"><h2>2. Nhu cầu</h2></div>
          <div className="bd ptn-grid">
            <F label="Tiêu đề cơ hội *" error={errors.title} full id="s-title"
              hint="Dùng làm tiêu đề phiếu cơ hội khi LeadScan mở bán. Nêu mặt hàng + số lượng + loại bên mua; KHÔNG ghi tên doanh nghiệp (tên chỉ mở cho người mua phiếu).">
              <input id="s-title" className="adm-input" name="title" maxLength={150} defaultValue={iv("title")}
                placeholder="Vd: Nhà máy điện tử FDI cần 20.000 thùng carton 5 lớp/tháng" />
            </F>
            <F label="Loại cơ hội *" error={errors.kind} full>
              <Choice name="kind" options={opts.kinds} value={kind} onChange={(v) => { setKind(v); setErrors(({ kind: _, ...r }) => r); }} error={errors.kind} />
            </F>
            <F label="Nhu cầu cụ thể *" error={errors.need} full id="s-need"
              hint="Mặt hàng / dịch vụ cần, yêu cầu kỹ thuật, bối cảnh. Không dán danh sách số điện thoại, email.">
              <textarea id="s-need" className="adm-input" name="need" rows={5} maxLength={4000} defaultValue={iv("need")}
                placeholder="Vd: Nhà máy điện tử vừa mở line SMT thứ 3, cần NCC thùng carton 5 lớp và khay chống tĩnh điện, giao hàng tuần…" />
            </F>
            <F label="Quy mô / số lượng" id="s-scale"><input id="s-scale" className="adm-input" name="scale" maxLength={200} placeholder="Vd: 20.000 thùng/tháng" defaultValue={iv("scale")} /></F>
            <F label="Thời điểm cần" id="s-time"><input id="s-time" className="adm-input" name="timing" maxLength={200} placeholder="Vd: Từ tháng 1/2027" defaultValue={iv("timing")} /></F>
          </div>
        </section>

        <section className="adm-card">
          <div className="hd"><h2>3. Nguồn & độ chắc chắn</h2></div>
          <div className="bd ptn-grid">
            <F label="Bạn biết tin từ đâu? *" error={errors.source_type} full>
              <Choice name="source_type" options={opts.sources} value={source} onChange={(v) => { setSource(v); setErrors(({ source_type: _, ...r }) => r); }} error={errors.source_type} />
            </F>
            <F label={source === "public" ? "Link nguồn công khai *" : "Link nguồn (nếu có)"} error={errors.source_url} full id="s-url">
              <input id="s-url" className="adm-input" name="source_url" type="url" maxLength={500} placeholder="https://…" defaultValue={iv("source_url")} />
            </F>
            <F label="Mức độ chắc chắn *" error={errors.certainty} full>
              <Choice name="certainty" options={opts.certainty} value={certainty} onChange={(v) => { setCertainty(v); setErrors(({ certainty: _, ...r }) => r); }} error={errors.certainty} />
            </F>
            <F label="Tài liệu, link chứng minh" full id="s-ev" hint="Mỗi dòng 1 link (thông báo mời thầu, bài đăng, ảnh chụp đã tải lên Drive…).">
              <textarea id="s-ev" className="adm-input" name="evidence" rows={2} maxLength={2000} defaultValue={iv("evidence")} />
            </F>
            <F label="Ảnh chứng minh" full hint="">
              <ImageUploader value={images} onChange={setImages} />
            </F>
          </div>
        </section>

        <section className="adm-card">
          <div className="hd"><h2>4. Người liên hệ <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>(không bắt buộc)</span></h2></div>
          <div className="bd ptn-grid">
            <p className="muted full" style={{ fontSize: 13 }}>
              Chỉ điền khi người đó <b>đồng ý được giới thiệu</b>, hoặc là liên hệ công khai của doanh nghiệp. LeadScan trả thưởng cho thông tin cơ hội, không cho số điện thoại.
            </p>
            <F label="Họ tên" id="s-cn"><input id="s-cn" className="adm-input" name="contact_name" maxLength={100} defaultValue={iv("contact_name")} /></F>
            <F label="Chức vụ" id="s-ct"><input id="s-ct" className="adm-input" name="contact_title" maxLength={100} defaultValue={iv("contact_title")} /></F>
            <F label="Điện thoại" error={errors.contact_phone} id="s-cp"><input id="s-cp" className="adm-input" name="contact_phone" type="tel" maxLength={30} defaultValue={iv("contact_phone")} /></F>
            <F label="Email" error={errors.contact_email} id="s-ce"><input id="s-ce" className="adm-input" name="contact_email" type="email" maxLength={150} defaultValue={iv("contact_email")} /></F>
            <div className="adm-field full">
              <label className="ptn-check"><input type="checkbox" name="contact_consent" defaultChecked={hadContact} /> Người liên hệ đã đồng ý được giới thiệu, hoặc đây là liên hệ công khai của doanh nghiệp</label>
              {errors.contact_consent ? <span className="adm-err" data-err>{errors.contact_consent}</span> : null}
            </div>
            <F label="Bạn có thể kết nối trực tiếp với bên mua?" full>
              <Choice name="can_connect" options={{ yes: "Có", no: "Không" }} value={connect} onChange={setConnect} />
            </F>
          </div>
        </section>

        <section className="adm-card">
          <div className="bd" style={{ display: "grid", gap: 12 }}>
            <label className="ptn-check">
              <input type="checkbox" name="commitment" />
              <span>Tôi cam kết thông tin này hợp pháp, <b>không vi phạm nghĩa vụ bảo mật với nơi tôi làm việc</b>, không phải dữ liệu mua bán.</span>
            </label>
            {errors.commitment ? <span className="adm-err" data-err>{errors.commitment}</span> : null}
            <div className="adm-actions" style={{ justifyContent: "flex-start" }}>
              {initial ? <Link className="adm-btn" href={`/doi-tac/co-hoi/${initial.id}`} style={{ height: 40, display: "inline-flex", alignItems: "center" }}>Huỷ</Link> : null}
              <button className="adm-btn primary" disabled={busy} style={{ height: 40, padding: "0 22px" }}>{busy ? (initial ? "Đang lưu…" : "Đang gửi…") : initial ? "Lưu thay đổi" : "Gửi cơ hội"}</button>
              <span className="muted" style={{ fontSize: 12.5, alignSelf: "center" }}>{initial ? "Thay đổi được ghi vào lịch sử cơ hội." : "LeadScan xác minh trong khoảng 2 ngày làm việc. Ai gửi trước được ghi nhận."}</span>
            </div>
          </div>
        </section>
      </form>
    </>
  );
}

export default function SubmitOpportunityPage() {
  return (
    <Suspense fallback={<div className="adm-empty">Đang tải…</div>}>
      <SubmitForm />
    </Suspense>
  );
}
