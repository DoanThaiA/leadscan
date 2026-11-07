"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { OppForm } from "@/components/admin/OppForm";
import { Icon } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import type { Opp } from "@/lib/commerce";

export default function NewOppPage() {
  const router = useRouter();
  useEffect(() => {
    document.title = "Thêm cơ hội · Quản trị LeadScan";
  }, []);
  return (
    <>
      <Link href="/admin/co-hoi" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Cơ hội</Link>
      <div className="adm-head"><div><h1>Thêm cơ hội</h1><p>Để “Nháp” nếu chưa muốn khách hàng thấy.</p></div></div>
      <OppForm
        submitLabel="Tạo cơ hội"
        onSubmit={async (body) => {
          const o = await api.post<Opp>("/opportunities", body);
          router.replace(`/admin/co-hoi/${o.id}`);
        }}
      />
    </>
  );
}
