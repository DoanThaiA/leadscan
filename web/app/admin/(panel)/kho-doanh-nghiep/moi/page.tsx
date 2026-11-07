"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { KnowledgeForm } from "@/components/admin/KnowledgeForm";
import { Icon } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import type { KnowledgeCompany } from "@/lib/knowledge";

export default function NewKnowledgePage() {
  const router = useRouter();
  useEffect(() => {
    document.title = "Thêm doanh nghiệp · Quản trị LeadScan";
  }, []);
  return (
    <>
      <Link href="/admin/kho-doanh-nghiep" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Kho doanh nghiệp</Link>
      <div className="adm-head"><div><h1>Thêm doanh nghiệp</h1><p>Doanh nghiệp mới ở trạng thái “Chờ quét” để AI xử lý.</p></div></div>
      <KnowledgeForm
        submitLabel="Thêm vào kho"
        onSubmit={async (body) => {
          const k = await api.post<KnowledgeCompany>("/knowledge-companies", body);
          router.replace(`/admin/kho-doanh-nghiep/${k.id}`);
        }}
      />
    </>
  );
}
