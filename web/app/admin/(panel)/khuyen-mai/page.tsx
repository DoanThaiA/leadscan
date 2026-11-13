"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Dialog, Field, Icon, Skeleton } from "@/components/admin/ui";
import { api, errFields, errMsg, qs } from "@/lib/admin/api";
import { fmtDate } from "@/lib/admin/format";
import { fmtVnd } from "@/lib/commerce";

type Scope = "all" | "membership" | "topup";
type State = "active" | "scheduled" | "off" | "ended" | "used_up";

interface Promo {
  id: number;
  code: string;
  name: string;
  discount_type: "percent" | "amount";
  discount_value: number;
  max_discount: number | null;
  min_amount: number;
  applies_to: Scope;
  max_uses: number | null;
  per_company_limit: number | null;
  starts_on: string | null;
  ends_on: string | null;
  is_active: boolean;
  description: string;
  state: State;
  used: number;
  paid_count: number;
  discount_total: number;
  created_by: string | null;
}

interface Resp {
  items: Promo[];
  types: Record<string, string>;
  scopes: Record<Scope, string>;
}

const STATE: Record<State, [string, string]> = {
  active: ["Đang áp dụng", "s-active"],
  scheduled: ["Chưa tới ngày", "s-new"],
  used_up: ["Hết lượt", "s-contacted"],
  ended: ["Hết hạn", "s-suspended"],
  off: ["Đã tắt", "s-suspended"],
};

const num = (s: FormDataEntryValue | null) => {
  const v = String(s ?? "").replace(/\D/g, "");
  return v ? Number(v) : null;
};

export default function PromosPage() {
  const { user } = useAdmin();
  const isAdmin = user.role === "admin";
  const [d, setD] = useState<Resp | null>(null);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Promo | "new" | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(() => {
    api.get<Resp>("/promos" + qs({ q })).then(setD, (e) => setError(errMsg(e)));
  }, [q]);
  useEffect(() => {
    document.title = "Khuyến mãi · Quản trị LeadScan";
    load();
  }, [load]);

  async function toggle(p: Promo) {
    try {
      await api.put(`/promos/${p.id}`, { ...p, is_active: !p.is_active });
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  async function remove(p: Promo) {
    if (!confirm(`Xoá mã ${p.code}? Không thể hoàn tác.`)) return;
    try {
      await api.del(`/promos/${p.id}`);
      load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Mã khuyến mãi</h1>
          <p>Thành viên nhập mã khi thanh toán phí thành viên / nạp điểm để được giảm tiền (điểm vẫn cộng theo giá gốc). Đơn còn 0đ sau khi giảm được kích hoạt ngay, không cần thanh toán.</p>
        </div>
        {isAdmin ? <button className="adm-btn primary" onClick={() => setEditing("new")}><Icon name="plus" size={16} /> Tạo mã</button> : null}
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-toolbar">
          <div className="adm-search"><Icon name="search" /><input className="adm-input" type="search" placeholder="Tìm theo mã hoặc mô tả…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm mã khuyến mãi" /></div>
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={34} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">{q ? "Không có mã nào khớp." : "Chưa có mã khuyến mãi nào."}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Mã</th><th>Giảm</th><th>Áp dụng</th><th>Thời gian</th><th>Lượt dùng</th><th>Đã giảm</th><th>Trạng thái</th><th></th></tr></thead>
              <tbody>
                {d.items.map((p) => (
                  <tr key={p.id}>
                    <td><b className="mono">{p.code}</b>{p.name ? <div className="sub">{p.name}</div> : null}</td>
                    <td>{p.description}{p.min_amount ? <div className="sub">Đơn từ {fmtVnd(p.min_amount)}</div> : null}</td>
                    <td>{d.scopes[p.applies_to]}<div className="sub">{p.per_company_limit ? `${p.per_company_limit} lượt / doanh nghiệp` : "Không giới hạn / doanh nghiệp"}</div></td>
                    <td style={{ whiteSpace: "nowrap" }}>{p.starts_on || p.ends_on ? <>{p.starts_on ? fmtDate(p.starts_on) : "…"} – {p.ends_on ? fmtDate(p.ends_on) : "…"}</> : "Không thời hạn"}</td>
                    <td>
                      <b>{p.used}</b>{p.max_uses ? ` / ${p.max_uses}` : ""}
                      <div className="sub">{p.paid_count} đơn đã thanh toán</div>
                    </td>
                    <td>{fmtVnd(p.discount_total)}{p.paid_count ? <div className="sub"><Link href={`/admin/thanh-toan?promo=${p.code}`}>Xem đơn</Link></div> : null}</td>
                    <td><span className={`adm-badge ${STATE[p.state][1]}`}>{STATE[p.state][0]}</span></td>
                    <td>
                      {isAdmin ? (
                        <div className="adm-actions">
                          <button className="adm-btn sm" onClick={() => setEditing(p)}><Icon name="edit" size={14} /> Sửa</button>
                          <button className="adm-btn sm ghost" onClick={() => toggle(p)}>{p.is_active ? "Tắt" : "Bật"}</button>
                          {!p.used && !p.paid_count ? <button className="adm-btn sm ghost danger" onClick={() => remove(p)} aria-label={`Xoá ${p.code}`}><Icon name="trash" size={14} /></button> : null}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {d ? <PromoDialog promo={editing} scopes={d.scopes} onClose={() => setEditing(null)} onDone={() => { setEditing(null); load(); }} /> : null}
    </>
  );
}

function PromoDialog({ promo, scopes, onClose, onDone }: { promo: Promo | "new" | null; scopes: Record<Scope, string>; onClose: () => void; onDone: () => void }) {
  const p = promo && promo !== "new" ? promo : null;
  const [type, setType] = useState<"percent" | "amount">("percent");
  const [msg, setMsg] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setType(p?.discount_type ?? "percent");
    setMsg("");
    setFields({});
  }, [promo, p?.discount_type]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      code: String(f.get("code") ?? ""),
      name: String(f.get("name") ?? ""),
      discount_type: type,
      discount_value: num(f.get("discount_value")) ?? 0,
      max_discount: type === "percent" ? num(f.get("max_discount")) : null,
      min_amount: num(f.get("min_amount")) ?? 0,
      applies_to: String(f.get("applies_to")),
      max_uses: num(f.get("max_uses")),
      per_company_limit: num(f.get("per_company_limit")),
      starts_on: String(f.get("starts_on") ?? "") || null,
      ends_on: String(f.get("ends_on") ?? "") || null,
      is_active: f.get("is_active") === "on",
    };
    setBusy(true);
    setMsg("");
    try {
      if (p) await api.put(`/promos/${p.id}`, body);
      else await api.post("/promos", body);
      onDone();
    } catch (err) {
      setMsg(errMsg(err));
      setFields(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  const money = (v: number | null | undefined) => (v ? v.toLocaleString("vi-VN") : "");
  return (
    <Dialog open={promo !== null} title={p ? `Sửa mã ${p.code}` : "Tạo mã khuyến mãi"} onClose={onClose} wide>
      {promo !== null ? (
        <form key={p?.id ?? "new"} onSubmit={submit} className="adm-form">
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Mã (khách nhập khi thanh toán)" htmlFor="pm-code" error={fields.code}>
            <input id="pm-code" className="adm-input mono" name="code" required minLength={3} maxLength={30} defaultValue={p?.code} placeholder="VD: CHAOMUNG2027" style={{ textTransform: "uppercase" }} />
          </Field>
          <Field label="Mô tả (hiện cho khách)" htmlFor="pm-name" error={fields.name}>
            <input id="pm-name" className="adm-input" name="name" maxLength={200} defaultValue={p?.name} placeholder="VD: Ưu đãi thành viên mới" />
          </Field>
          <Field label="Kiểu giảm" full>
            <div className="adm-checks">
              <label><input type="radio" name="discount_type" checked={type === "percent"} onChange={() => setType("percent")} /> Giảm theo %</label>
              <label><input type="radio" name="discount_type" checked={type === "amount"} onChange={() => setType("amount")} /> Giảm số tiền cố định</label>
            </div>
          </Field>
          <Field label={type === "percent" ? "Mức giảm (%)" : "Số tiền giảm (đ)"} htmlFor="pm-val" error={fields.discount_value}>
            <input id="pm-val" className="adm-input" name="discount_value" inputMode="numeric" required defaultValue={type === p?.discount_type ? money(p?.discount_value) : ""} placeholder={type === "percent" ? "1 – 100" : "VD: 50.000"} />
          </Field>
          {type === "percent" ? (
            <Field label="Giảm tối đa (đ) — để trống nếu không giới hạn" htmlFor="pm-max" error={fields.max_discount}>
              <input id="pm-max" className="adm-input" name="max_discount" inputMode="numeric" defaultValue={money(p?.max_discount)} placeholder="Không giới hạn" />
            </Field>
          ) : <div />}
          <Field label="Áp dụng cho" htmlFor="pm-scope">
            <select id="pm-scope" className="adm-input" name="applies_to" defaultValue={p?.applies_to ?? "all"}>
              {Object.entries(scopes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <Field label="Giá trị đơn tối thiểu (đ)" htmlFor="pm-min" error={fields.min_amount}>
            <input id="pm-min" className="adm-input" name="min_amount" inputMode="numeric" defaultValue={money(p?.min_amount)} placeholder="0" />
          </Field>
          <Field label="Tổng số lượt — để trống nếu không giới hạn" htmlFor="pm-uses" error={fields.max_uses}>
            <input id="pm-uses" className="adm-input" name="max_uses" inputMode="numeric" defaultValue={money(p?.max_uses)} placeholder="Không giới hạn" />
          </Field>
          <Field label="Số lượt mỗi doanh nghiệp — trống = không giới hạn" htmlFor="pm-per" error={fields.per_company_limit}>
            <input id="pm-per" className="adm-input" name="per_company_limit" inputMode="numeric" defaultValue={p ? money(p.per_company_limit) : "1"} placeholder="Không giới hạn" />
          </Field>
          <Field label="Từ ngày" htmlFor="pm-start" error={fields.starts_on}>
            <input id="pm-start" className="adm-input" type="date" name="starts_on" defaultValue={p?.starts_on ?? ""} />
          </Field>
          <Field label="Đến hết ngày" htmlFor="pm-end" error={fields.ends_on}>
            <input id="pm-end" className="adm-input" type="date" name="ends_on" defaultValue={p?.ends_on ?? ""} />
          </Field>
          <div className="adm-checks full">
            <label><input type="checkbox" name="is_active" defaultChecked={p ? p.is_active : true} /> Đang bật (khách dùng được)</label>
          </div>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : p ? "Lưu thay đổi" : "Tạo mã"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}
