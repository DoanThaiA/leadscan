"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EventWarning } from "@/components/admin/EventForm";
import { SiteBadge } from "@/components/admin/SiteBadge";
import { useAdminBrand } from "@/components/sites/SiteContext";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg, qs } from "@/lib/admin/api";
import { fmtDateTime, fmtNum } from "@/lib/admin/format";
import { EVENT_STATUS, EVENT_STATUS_CLASS, fmtDay, fmtVnd, parseLocal, type EventAdminListItem, type EventsMeta } from "@/lib/events";

interface Resp {
  items: EventAdminListItem[];
  counts: Record<string, number>;
}

export default function EventsAdminPage() {
  const router = useRouter();
  const brand = useAdminBrand();
  const [status, setStatus] = useState("");
  const [site, setSite] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [d, setD] = useState<Resp | null>(null);
  const [meta, setMeta] = useState<EventsMeta | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<EventsMeta>("/events/meta").then(setMeta, () => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    document.title = `Sự kiện · ${brand}`;
    setD(null);
    api.get<Resp>("/events" + qs({ status, q, site })).then(setD, (e) => setError(errMsg(e)));
  }, [status, q, site, brand]);

  const all_sites = meta?.scope === null; // nhân viên LeadScan: xem tổng hợp mọi trang

  const all = d ? Object.values(d.counts).reduce((a, b) => a + b, 0) : null;

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Sự kiện</h1>
          <p>Đăng sự kiện lên trang <a href="/su-kien" target="_blank" rel="noopener" style={{ color: "var(--brand-600)" }}>/su-kien</a>. Người tham dự đăng ký, chuyển khoản theo mã QR và nộp ảnh biên lai ngay trên trang.</p>
        </div>
        <div className="adm-actions">
          <Link className="adm-btn" href="/admin/su-kien/dang-ky"><Icon name="users" size={16} /> Đăng ký sự kiện</Link>
          <Link className="adm-btn primary" href="/admin/su-kien/moi"><Icon name="plus" size={16} /> Tạo sự kiện</Link>
        </div>
      </div>
      <EventWarning meta={meta} />
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        <div className="adm-tabs">
          <button className={!status ? "on" : undefined} onClick={() => setStatus("")}>Tất cả{all !== null ? <span>{fmtNum(all)}</span> : null}</button>
          {Object.entries(EVENT_STATUS).map(([k, v]) => (
            <button key={k} className={status === k ? "on" : undefined} onClick={() => setStatus(k)}>
              {v}{d ? <span>{fmtNum(d.counts[k] ?? 0)}</span> : null}
            </button>
          ))}
        </div>
        <div className="adm-toolbar">
          <div className="adm-search">
            <Icon name="search" />
            <input className="adm-input" type="search" placeholder="Tìm theo tên sự kiện, địa điểm, đơn vị…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Tìm sự kiện" />
          </div>
          {all_sites ? (
            <select className="adm-input" style={{ width: "auto" }} value={site} onChange={(e) => setSite(e.target.value)} aria-label="Lọc theo trang">
              <option value="">Mọi trang</option>
              {Object.entries(meta!.sites).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}
            </select>
          ) : null}
        </div>
        {!d ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={36} />)}</div>
        ) : !d.items.length ? (
          <div className="adm-empty">
            {q || status ? "Không có sự kiện nào khớp bộ lọc." : <>Chưa có sự kiện. <Link href="/admin/su-kien/moi" style={{ color: "var(--brand-600)" }}>Tạo sự kiện đầu tiên →</Link></>}
          </div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead><tr><th>Sự kiện</th>{all_sites ? <th>Trang</th> : null}<th>Trạng thái</th><th>Diễn ra</th><th>Hạn đăng ký</th><th>Phí</th><th>Vé</th><th>Đăng ký</th><th>Cập nhật</th></tr></thead>
              <tbody>
                {d.items.map((e) => {
                  const when = parseLocal(e.starts_at);
                  return (
                    <tr key={e.id} className="link" onClick={() => router.push(`/admin/su-kien/${e.id}`)}>
                      <td>
                        <Link className="name" href={`/admin/su-kien/${e.id}`} onClick={(ev) => ev.stopPropagation()}>{e.title}</Link>
                        <div className="sub">{[e.partner, e.venue].filter(Boolean).join(" · ")}</div>
                      </td>
                      {all_sites ? <td><SiteBadge site={e.site} /></td> : null}
                      <td><span className={`adm-badge ${EVENT_STATUS_CLASS[e.status] ?? ""}`}>{EVENT_STATUS[e.status] ?? e.status}</span></td>
                      <td style={{ whiteSpace: "nowrap" }}>{when ? `${when.date}${when.time ? ` ${when.time}` : ""}` : <span className="muted">—</span>}</td>
                      <td style={{ whiteSpace: "nowrap" }}>{e.deadline ? fmtDay(e.deadline) : <span className="muted">Không hạn</span>}</td>
                      <td style={{ whiteSpace: "nowrap" }}>{e.fee_member || e.fee_guest ? `${fmtVnd(e.fee_member)} / ${fmtVnd(e.fee_guest)}` : <span className="muted">Miễn phí</span>}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {e.tickets ? (
                          <>
                            <b>{fmtNum(e.tickets.registered)}</b>{e.tickets.total !== null ? ` / ${fmtNum(e.tickets.total)}` : ""}
                            <div className="sub">{e.tickets.total === null ? "Không giới hạn" : e.tickets.sold_out ? "Hết vé" : `Còn ${fmtNum(e.tickets.remaining ?? 0)}`}</div>
                          </>
                        ) : "—"}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {e.registrations ? (
                          <Link href={`/admin/su-kien/dang-ky?su_kien=${e.id}`} onClick={(ev) => ev.stopPropagation()} style={{ color: "var(--brand-600)", fontWeight: 600 }}>
                            {fmtNum(e.registrations)} lượt
                          </Link>
                        ) : <span className="muted">0</span>}
                        {e.paid ? <span className="job-new">{e.paid} đã trả</span> : null}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(e.updated_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
