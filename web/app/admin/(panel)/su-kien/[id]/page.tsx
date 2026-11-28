"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { EventForm, EventWarning } from "@/components/admin/EventForm";
import { SiteBadge } from "@/components/admin/SiteBadge";
import { useAdminBrand } from "@/components/sites/SiteContext";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { EVENT_STATUS, EVENT_STATUS_CLASS, eventPublicUrl, type EventAdmin, type EventsMeta } from "@/lib/events";

export default function EditEventPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAdmin();
  const brand = useAdminBrand();
  const [e, setE] = useState<EventAdmin | null>(null);
  const [meta, setMeta] = useState<EventsMeta | null>(null);
  const [ver, setVer] = useState(0);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<EventAdmin>(`/events/${id}`).then(setE, (err) => setError(errMsg(err)));
    api.get<EventsMeta>("/events/meta").then(setMeta, () => {});
    if (new URLSearchParams(location.search).has("saved")) {
      setFlash("Đã lưu");
      history.replaceState(null, "", location.pathname);
      setTimeout(() => setFlash(""), 2500);
    }
  }, [id]);
  useEffect(() => {
    if (e) document.title = `${e.title} · ${brand}`;
  }, [e, brand]);

  async function remove() {
    if (!e) return;
    const note = e.registrations ? `\n${e.registrations} lượt đăng ký đã nhận vẫn được giữ lại.` : "";
    if (!confirm(`Xoá sự kiện “${e.title}”? Link sẽ không mở được nữa.${note}\n\nMuốn ẩn nhưng giữ link, hãy chuyển trạng thái “Đã đóng”.`)) return;
    try {
      await api.del(`/events/${id}`);
      router.replace("/admin/su-kien");
    } catch (err) {
      alert(errMsg(err));
    }
  }

  if (error) return <div className="adm-card adm-empty">{error}</div>;
  if (!e) return <Skeleton h={400} />;

  return (
    <>
      <Link href="/admin/su-kien" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Sự kiện</Link>
      <div className="adm-head">
        <div style={{ minWidth: 0 }}>
          <h1>{e.title}</h1>
          <p>
            {meta?.scope === null ? <><SiteBadge site={e.site} />{" "}</> : null}
            <span className={`adm-badge ${EVENT_STATUS_CLASS[e.status] ?? ""}`}>{EVENT_STATUS[e.status] ?? e.status}</span>
            {" · "}<span className="mono">{eventPublicUrl(meta, e.site, e.slug)}</span>
            {e.published_at ? ` · đăng lúc ${fmtDateTime(e.published_at)}` : ""}
          </p>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {flash ? <span className="adm-badge s-active" role="status">{flash}</span> : null}
          {e.status !== "draft" ? (
            <a className="adm-btn" href={eventPublicUrl(meta, e.site, e.slug)} target="_blank" rel="noopener"><Icon name="external" size={14} /> Xem trang</a>
          ) : null}
          <Link className="adm-btn" href={`/admin/su-kien/dang-ky?su_kien=${e.id}`}><Icon name="users" size={14} /> Đăng ký ({e.registrations})</Link>
          {user.role === "admin" ? <button className="adm-btn danger" onClick={remove}><Icon name="trash" size={14} /> Xoá</button> : null}
        </div>
      </div>
      <EventWarning meta={meta} />

      <EventForm
        key={ver}
        initial={e}
        meta={meta}
        submitLabel="Lưu thay đổi"
        onSubmit={async (body) => {
          const saved = await api.put<EventAdmin>(`/events/${id}`, body);
          setE(saved);
          setVer((v) => v + 1);
          setFlash("Đã lưu");
          setTimeout(() => setFlash(""), 2500);
        }}
      />
    </>
  );
}
