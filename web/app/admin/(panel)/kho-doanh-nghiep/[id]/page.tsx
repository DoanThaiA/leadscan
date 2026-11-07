"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { KnowledgeForm } from "@/components/admin/KnowledgeForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { AI_STATUS, AI_STATUS_CLASS, type KnowledgeCompany, KNOWLEDGE_SOURCE } from "@/lib/knowledge";

export default function EditKnowledgePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAdmin();
  const [k, setK] = useState<KnowledgeCompany | null>(null);
  const [ver, setVer] = useState(0);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => api.get<KnowledgeCompany>(`/knowledge-companies/${id}`).then(setK, (e) => setError(errMsg(e))), [id]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (k) document.title = `${k.name} · Kho doanh nghiệp`;
  }, [k]);

  async function remove() {
    if (!k || !confirm(`Xoá “${k.name}” khỏi kho doanh nghiệp? Không thể hoàn tác.`)) return;
    try {
      await api.del(`/knowledge-companies/${id}`);
      router.replace("/admin/kho-doanh-nghiep");
    } catch (e) {
      alert(errMsg(e));
    }
  }

  if (error) return <div className="adm-card adm-empty">{error}</div>;
  if (!k) return <Skeleton h={400} />;

  return (
    <>
      <Link href="/admin/kho-doanh-nghiep" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Kho doanh nghiệp</Link>
      <div className="adm-head">
        <div style={{ display: "flex", gap: 14, alignItems: "center", minWidth: 0 }}>
          {k.logo_url ? <img src={k.logo_url} alt="" width={52} height={52} style={{ objectFit: "contain", borderRadius: 8, border: "1px solid var(--line)", background: "#fff", flex: "none" }} /> : null}
          <div style={{ minWidth: 0 }}>
            <h1>{k.name}</h1>
            <p>
              <span className="mono">{k.tax_code || "Chưa có MST"}</span> · {KNOWLEDGE_SOURCE[k.source] ?? k.source}
              {k.rank ? ` · hạng #${k.rank}${k.rank_year ? ` (${k.rank_year})` : ""}` : ""}
              {" · "}<span className={`adm-badge ${AI_STATUS_CLASS[k.ai_status] ?? ""}`}>{AI_STATUS[k.ai_status] ?? k.ai_status}</span>
            </p>
          </div>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {flash ? <span className="adm-badge s-active" role="status">{flash}</span> : null}
          {user.role === "admin" ? <button className="adm-btn danger" onClick={remove}><Icon name="trash" size={14} /> Xoá</button> : null}
        </div>
      </div>

      <KnowledgeForm
        key={ver}
        initial={k}
        submitLabel="Lưu thay đổi"
        onSubmit={async (body) => {
          const saved = await api.put<KnowledgeCompany>(`/knowledge-companies/${id}`, body);
          setK(saved);
          setVer((v) => v + 1);
          setFlash("Đã lưu");
          setTimeout(() => setFlash(""), 2500);
        }}
      />
    </>
  );
}
