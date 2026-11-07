"use client";

import { type FormEvent, useEffect, useState } from "react";

import { Field, Skeleton } from "@/components/admin/ui";
import { fmtDateTime } from "@/lib/admin/format";
import { errMsg, mapi } from "@/lib/member/api";

interface Profile {
  offering: string;
  target_customers: string;
  target_regions: string[];
  opp_types: string[];
  expected_tickets: string;
  notes: string;
  updated_at: string;
}

const REGIONS = ["Miền Bắc", "Miền Trung", "Miền Nam", "Toàn quốc", "Quốc tế"];
const OPP_TYPES = [
  "Đăng mua (App đăng mua)",
  "Dự án & gói thầu",
  "Nhà máy / dự án FDI mới",
  "Hội chợ & triển lãm",
  "Mạng xã hội & nhóm chat",
  "Nguồn chính thống (Trang vàng, Bộ Công Thương, Công báo)",
];
const TICKETS = ["Dưới 50 phiếu", "50–200 phiếu", "200–1.000 phiếu", "Trên 1.000 phiếu", "Chưa xác định"];

export default function ProfilePage() {
  const [p, setP] = useState<Profile | null | undefined>(undefined);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Chân dung cơ hội · LeadScan B2B";
    mapi.get<Profile | null>("/profile").then(setP, (e) => setMsg({ ok: false, text: errMsg(e) }));
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setMsg(null);
    try {
      const r = await mapi.put<Profile>("/profile", {
        offering: String(fd.get("offering") ?? ""),
        target_customers: String(fd.get("target_customers") ?? ""),
        target_regions: fd.getAll("target_regions").map(String),
        opp_types: fd.getAll("opp_types").map(String),
        expected_tickets: String(fd.get("expected_tickets") ?? ""),
        notes: String(fd.get("notes") ?? ""),
      });
      setP(r);
      setMsg({ ok: true, text: "Đã lưu chân dung cơ hội. AI sẽ dùng thông tin mới để tìm và chấm điểm cơ hội cho bạn." });
    } catch (err) {
      setMsg({ ok: false, text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  }

  if (p === undefined) return <Skeleton h={360} />;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Chân dung cơ hội</h1>
          <p>Mô tả càng rõ, cơ hội AI tìm được càng sát nhu cầu.{p ? ` Cập nhật lần cuối ${fmtDateTime(p.updated_at)}.` : ""}</p>
        </div>
      </div>
      <section className="adm-card" style={{ maxWidth: 860 }}>
        <form className="bd adm-form" onSubmit={submit}>
          {msg ? <div className={msg.ok ? "adm-alert ok full" : "adm-alert full"} role="status">{msg.text}</div> : null}
          <Field label="Sản phẩm / dịch vụ bạn cung cấp" full htmlFor="p-off">
            <textarea id="p-off" className="adm-input" name="offering" defaultValue={p?.offering} maxLength={2000} />
          </Field>
          <Field label="Khách hàng lý tưởng" full htmlFor="p-tgt">
            <textarea id="p-tgt" className="adm-input" name="target_customers" defaultValue={p?.target_customers} maxLength={2000} />
          </Field>
          <div className="adm-field full">
            <span className="lbl">Khu vực ưu tiên</span>
            <div className="adm-checks">
              {REGIONS.map((r) => <label key={r}><input type="checkbox" name="target_regions" value={r} defaultChecked={p?.target_regions.includes(r)} />{r}</label>)}
            </div>
          </div>
          <div className="adm-field full">
            <span className="lbl">Loại cơ hội quan tâm</span>
            <div className="adm-checks">
              {OPP_TYPES.map((o) => <label key={o}><input type="checkbox" name="opp_types" value={o} defaultChecked={p?.opp_types.includes(o)} />{o}</label>)}
            </div>
          </div>
          <Field label="Dự kiến số phiếu mua/năm" htmlFor="p-tk">
            <select id="p-tk" className="adm-input" name="expected_tickets" defaultValue={p?.expected_tickets ?? ""}>
              <option value="">Chưa chọn</option>
              {TICKETS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="Ghi chú thêm" full htmlFor="p-notes">
            <textarea id="p-notes" className="adm-input" name="notes" defaultValue={p?.notes} maxLength={2000} />
          </Field>
          <div className="adm-actions full"><button className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Lưu chân dung"}</button></div>
        </form>
      </section>
    </>
  );
}
