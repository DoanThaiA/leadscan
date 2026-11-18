"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { ArticleForm, liveBadge, useArticleMeta } from "@/components/admin/ArticleForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { type ArticleAdmin, articleHref } from "@/lib/blog";

export default function EditArticlePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAdmin();
  const [a, setA] = useState<ArticleAdmin | null>(null);
  const { sections, topics } = useArticleMeta();
  const [ver, setVer] = useState(0);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<ArticleAdmin>(`/articles/${id}`).then(setA, (e) => setError(errMsg(e)));
    if (new URLSearchParams(location.search).has("saved")) {
      setFlash("Đã lưu");
      history.replaceState(null, "", location.pathname);
      setTimeout(() => setFlash(""), 2500);
    }
  }, [id]);
  useEffect(() => {
    if (a) document.title = `${a.title} · ${a.section_name}`;
  }, [a]);

  async function remove() {
    if (!a || !confirm(`Xoá bài “${a.title}”? Link bài sẽ không mở được nữa.\n\nMuốn ẩn bài nhưng giữ nội dung, hãy chuyển về “Bản nháp”.`)) return;
    try {
      await api.del(`/articles/${id}`);
      router.replace(`/admin/bai-viet${a.section_id ? `?danh_muc=${a.section_id}` : ""}`);
    } catch (e) {
      alert(errMsg(e));
    }
  }

  if (error) return <div className="adm-card adm-empty">{error}</div>;
  if (!a) return <Skeleton h={400} />;

  return (
    <>
      <Link href={`/admin/bai-viet${a.section_id ? `?danh_muc=${a.section_id}` : ""}`} className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> {a.section_name}</Link>
      <div className="adm-head">
        <div style={{ minWidth: 0 }}>
          <h1>{a.title}</h1>
          <p>
            {liveBadge(a)}
            {" · "}{a.section_name}{" · "}<span className="mono">{articleHref(a)}</span>
            {a.published_at ? ` · đăng ${fmtDateTime(a.published_at)}` : ""}
          </p>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {flash ? <span className="adm-badge s-active" role="status">{flash}</span> : null}
          {a.is_live ? <a className="adm-btn" href={articleHref(a)} target="_blank" rel="noopener"><Icon name="external" size={14} /> Xem trang</a> : null}
          {user.role === "admin" ? <button className="adm-btn danger" onClick={remove}><Icon name="trash" size={14} /> Xoá</button> : null}
        </div>
      </div>
      <ArticleForm
        key={ver}
        initialValue={a}
        sections={sections}
        topics={topics}
        submitLabel="Lưu thay đổi"
        onSubmit={async (body) => {
          const saved = await api.put<ArticleAdmin>(`/articles/${id}`, body);
          setA(saved);
          setVer((x) => x + 1);
          setFlash("Đã lưu");
          setTimeout(() => setFlash(""), 2500);
        }}
      />
    </>
  );
}
