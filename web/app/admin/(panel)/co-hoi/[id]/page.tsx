"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { OppForm } from "@/components/admin/OppForm";
import { Icon, Skeleton } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/admin/api";
import { fmtDateTime } from "@/lib/admin/format";
import { fmtPts, type Opp, OPP_STATUS } from "@/lib/commerce";

interface Resp {
  opportunity: Opp;
  purchases: { id: number; price: number; created_at: string; company: { id: number; code: string; name: string } }[];
}

export default function EditOppPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAdmin();
  const [d, setD] = useState<Resp | null>(null);
  const [ver, setVer] = useState(0);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => api.get<Resp>(`/opportunities/${id}`).then(setD, (e) => setError(errMsg(e))), [id]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (d) document.title = `${d.opportunity.code} · Quản trị LeadScan`;
  }, [d]);

  async function remove() {
    if (!confirm("Xoá vĩnh viễn cơ hội này?")) return;
    try {
      await api.del(`/opportunities/${id}`);
      router.replace("/admin/co-hoi");
    } catch (e) {
      alert(errMsg(e));
    }
  }

  if (error) return <div className="adm-card adm-empty">{error}</div>;
  if (!d) return <Skeleton h={400} />;
  const o = d.opportunity;

  return (
    <>
      <Link href="/admin/co-hoi" className="muted" style={{ display: "inline-flex", gap: 6, alignItems: "center", marginBottom: 10 }}><Icon name="back" size={16} /> Cơ hội</Link>
      <div className="adm-head">
        <div>
          <h1>{o.title}</h1>
          <p><span className="mono">{o.code}</span> · {OPP_STATUS[o.status ?? "draft"]} · đã bán {o.sold_count}/{o.max_buyers}</p>
        </div>
        <div className="adm-actions" style={{ alignItems: "center" }}>
          {flash ? <span className="adm-badge s-active" role="status">{flash}</span> : null}
          {user.role === "admin" && !o.sold_count ? <button className="adm-btn danger" onClick={remove}><Icon name="trash" size={14} /> Xoá</button> : null}
        </div>
      </div>

      <OppForm
        key={ver}
        initial={o}
        submitLabel="Lưu thay đổi"
        onSubmit={async (body) => {
          await api.put(`/opportunities/${id}`, body);
          await load();
          setVer((v) => v + 1);
          setFlash("Đã lưu");
          setTimeout(() => setFlash(""), 2500);
        }}
      />

      <section className="adm-card" style={{ marginTop: 16 }}>
        <div className="hd"><h2>Doanh nghiệp đã mua ({d.purchases.length})</h2></div>
        {d.purchases.length ? (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <tbody>
                {d.purchases.map((p) => (
                  <tr key={p.id}>
                    <td><Link className="name" href={`/admin/khach-hang/${p.company.id}`}>{p.company.name}</Link><div className="sub mono">{p.company.code}</div></td>
                    <td className="adm-neg">{fmtPts(p.price)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="adm-empty">Chưa có ai mua.</div>}
      </section>
    </>
  );
}
