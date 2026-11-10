"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { JobForm, MailWarning } from "@/components/admin/JobForm";
import { Icon } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import type { JobAdmin, JobsMeta } from "@/lib/careers";

export default function NewJobPage() {
  const router = useRouter();
  const [meta, setMeta] = useState<JobsMeta | null>(null);
  useEffect(() => {
    document.title = "Đăng bài tuyển dụng · Quản trị LeadScan";
    api.get<JobsMeta>("/jobs/meta").then(setMeta, () => {});
  }, []);
  return (
    <>
      <Link href="/admin/tuyen-dung" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Tuyển dụng</Link>
      <div className="adm-head"><div><h1>Đăng bài tuyển dụng</h1><p>Lưu ở “Bản nháp” để soạn tiếp, chọn “Đang tuyển” để hiện ngay trên trang tuyển dụng.</p></div></div>
      <MailWarning meta={meta} />
      <JobForm
        meta={meta}
        submitLabel="Lưu bài tuyển dụng"
        onSubmit={async (body) => {
          const j = await api.post<JobAdmin>("/jobs", body);
          router.replace(`/admin/tuyen-dung/${j.id}?saved=1`);
        }}
      />
    </>
  );
}
