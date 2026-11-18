"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { ArticleForm, notifySectionsChanged, useArticleMeta } from "@/components/admin/ArticleForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import type { ArticleAdmin } from "@/lib/blog";

function NewArticle() {
  const router = useRouter();
  const pre = Number(useSearchParams().get("danh_muc")) || undefined; // mở từ danh sách đang lọc danh mục
  const { sections, topics } = useArticleMeta();
  const section = sections.find((x) => x.id === pre);
  useEffect(() => {
    document.title = "Viết bài mới · Quản trị LeadScan";
  }, []);
  // Chờ danh mục tải xong để ô "Danh mục" có giá trị mặc định đúng
  if (!sections.length) return <Skeleton h={400} />;
  const fallback = sections.find((x) => x.slug === "cam-nang") ?? sections[0];
  return (
    <>
      <Link href={`/admin/bai-viet${pre ? `?danh_muc=${pre}` : ""}`} className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> {section?.name ?? "Bài viết"}</Link>
      <div className="adm-head"><div><h1>Viết bài mới</h1><p>Chọn danh mục cho bài. Lưu “Bản nháp” để soạn tiếp, chọn “Đã đăng” để hiện công khai (hoặc đặt ngày đăng để hẹn giờ).</p></div></div>
      <ArticleForm
        sections={sections}
        topics={topics}
        defaultSectionId={section?.id ?? fallback?.id}
        submitLabel="Lưu bài viết"
        onSubmit={async (body) => {
          const a = await api.post<ArticleAdmin>("/articles", body);
          notifySectionsChanged();
          router.replace(`/admin/bai-viet/${a.id}?saved=1`);
        }}
      />
    </>
  );
}

export default function NewArticlePage() {
  return (
    <Suspense fallback={<Skeleton h={400} />}>
      <NewArticle />
    </Suspense>
  );
}
