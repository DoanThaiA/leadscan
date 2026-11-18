"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ArticleForm } from "@/components/admin/ArticleForm";
import { Icon } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import type { ArticleAdmin } from "@/lib/blog";

export default function NewArticlePage() {
  const router = useRouter();
  const [cats, setCats] = useState<string[]>([]);
  useEffect(() => {
    document.title = "Viết bài cẩm nang · Quản trị LeadScan";
    api.get<{ categories: string[] }>("/articles/meta").then((m) => setCats(m.categories), () => {});
  }, []);
  return (
    <>
      <Link href="/admin/cam-nang" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Cẩm nang</Link>
      <div className="adm-head"><div><h1>Viết bài cẩm nang</h1><p>Lưu “Bản nháp” để soạn tiếp, chọn “Đã đăng” để hiện trên /cam-nang (hoặc đặt ngày đăng để hẹn giờ).</p></div></div>
      <ArticleForm
        categories={cats}
        submitLabel="Lưu bài viết"
        onSubmit={async (body) => {
          const a = await api.post<ArticleAdmin>("/articles", body);
          router.replace(`/admin/cam-nang/${a.id}?saved=1`);
        }}
      />
    </>
  );
}
