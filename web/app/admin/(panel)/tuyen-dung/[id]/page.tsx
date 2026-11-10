"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { JobForm, MailWarning } from "@/components/admin/JobForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { JOB_STATUS, JOB_STATUS_CLASS, type JobAdmin, type JobsMeta } from "@/lib/careers";

export default function EditJobPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAdmin();
  const [j, setJ] = useState<JobAdmin | null>(null);
  const [meta, setMeta] = useState<JobsMeta | null>(null);
  const [ver, setVer] = useState(0);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<JobAdmin>(`/jobs/${id}`).then(setJ, (e) => setError(errMsg(e)));
    api.get<JobsMeta>("/jobs/meta").then(setMeta, () => {});
    if (new URLSearchParams(location.search).has("saved")) {
      setFlash("Đã lưu");
      history.replaceState(null, "", location.pathname);
      setTimeout(() => setFlash(""), 2500);
    }
  }, [id]);
  useEffect(() => {
    if (j) document.title = `${j.title} · Tuyển dụng`;
  }, [j]);

  async function remove() {
    if (!j) return;
    const note = j.applications ? `\n${j.applications} hồ sơ đã nhận vẫn được giữ lại.` : "";
    if (!confirm(`Xoá bài “${j.title}”? Link bài sẽ không mở được nữa.${note}\n\nMuốn ẩn bài nhưng giữ link, hãy chuyển trạng thái “Đã đóng”.`)) return;
    try {
      await api.del(`/jobs/${id}`);
      router.replace("/admin/tuyen-dung");
    } catch (e) {
      alert(errMsg(e));
    }
  }

  if (error) return <div className="adm-card adm-empty">{error}</div>;
  if (!j) return <Skeleton h={400} />;

  return (
    <>
      <Link href="/admin/tuyen-dung" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Tuyển dụng</Link>
      <div className="adm-head">
        <div style={{ minWidth: 0 }}>
          <h1>{j.title}</h1>
          <p>
            <span className={`adm-badge ${JOB_STATUS_CLASS[j.status] ?? ""}`}>{JOB_STATUS[j.status] ?? j.status}</span>
            {" · "}<span className="mono">/tuyen-dung/{j.slug}</span>
            {j.published_at ? ` · đăng lúc ${fmtDateTime(j.published_at)}` : ""}
          </p>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {flash ? <span className="adm-badge s-active" role="status">{flash}</span> : null}
          {j.status !== "draft" ? (
            <a className="adm-btn" href={`/tuyen-dung/${j.slug}`} target="_blank" rel="noopener"><Icon name="external" size={14} /> Xem trang</a>
          ) : null}
          <Link className="adm-btn" href={`/admin/tuyen-dung/ho-so?job=${j.id}`}><Icon name="users" size={14} /> Hồ sơ ({j.applications})</Link>
          {user.role === "admin" ? <button className="adm-btn danger" onClick={remove}><Icon name="trash" size={14} /> Xoá</button> : null}
        </div>
      </div>
      <MailWarning meta={meta} />

      <JobForm
        key={ver}
        initial={j}
        meta={meta}
        submitLabel="Lưu thay đổi"
        onSubmit={async (body) => {
          const saved = await api.put<JobAdmin>(`/jobs/${id}`, body);
          setJ(saved);
          setVer((v) => v + 1);
          setFlash("Đã lưu");
          setTimeout(() => setFlash(""), 2500);
        }}
      />
    </>
  );
}
