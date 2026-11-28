"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EventForm, EventWarning } from "@/components/admin/EventForm";
import { Icon } from "@/components/admin/ui";
import { api } from "@/lib/admin/api";
import type { EventAdmin, EventsMeta } from "@/lib/events";

export default function NewEventPage() {
  const router = useRouter();
  const [meta, setMeta] = useState<EventsMeta | null>(null);
  useEffect(() => {
    document.title = "Tạo sự kiện · Quản trị LeadScan";
    api.get<EventsMeta>("/events/meta").then(setMeta, () => {});
  }, []);
  return (
    <>
      <Link href="/admin/su-kien" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Sự kiện</Link>
      <div className="adm-head"><div><h1>Tạo sự kiện</h1><p>Lưu ở “Bản nháp” để soạn tiếp, chọn “Đang mở” để hiện ngay trên trang sự kiện và nhận đăng ký.</p></div></div>
      <EventWarning meta={meta} />
      <EventForm
        meta={meta}
        submitLabel="Lưu sự kiện"
        onSubmit={async (body) => {
          const e = await api.post<EventAdmin>("/events", body);
          router.replace(`/admin/su-kien/${e.id}?saved=1`);
        }}
      />
    </>
  );
}
