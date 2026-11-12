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
import PublicLinkButton from "@/components/admin/PublicLinkButton";

interface Resp {
  opportunity: Opp;
  purchases: Buyer[];
}

interface Buyer {
  id: number;
  price: number;
  created_at: string;
  company: { id: number; code: string; name: string };
  score_at_purchase: number | null;
  score_now: number | null;
  changed_fields: string[];
  refund_amount: number;
  refund_note: string;
  refunded_at: string | null;
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

  async function refund(b: Buyer) {
    const note = prompt(`Hoàn ${fmtPts(b.price)} cho ${b.company.name}.
Lý do (khách sẽ thấy trong lịch sử điểm):`, "Cơ hội đã chỉnh sửa, không còn phù hợp yêu cầu");
    if (note === null) return;
    try {
      await api.post(`/purchases/${b.id}/refund`, { note });
      await load();
    } catch (e) {
      alert(errMsg(e));
    }
  }

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
          <PublicLinkButton code={o.code} published={o.status === "published"} />
          {user.role === "admin" && !o.sold_count ? <button className="adm-btn danger" onClick={remove}><Icon name="trash" size={14} /> Xoá</button> : null}
        </div>
      </div>

      <OppForm
        key={ver}
        initial={o}
        submitLabel="Lưu thay đổi"
        onSubmit={async (body) => {
          if (o.sold_count && !confirm(`Phiếu đã có ${o.sold_count} doanh nghiệp mua. Người mua vẫn xem được bản họ đã mua; hệ thống chấm điểm lại và báo "đã chỉnh sửa sau khi mua". Bạn có thể duyệt hoàn điểm ở bảng bên dưới. Tiếp tục lưu?`)) {
            throw new Error("Chưa lưu thay đổi.");
          }
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
              <thead><tr><th>Doanh nghiệp</th><th>Giá</th><th>Ngày mua</th><th>Điểm</th><th>Nội dung</th><th></th></tr></thead>
              <tbody>
                {d.purchases.map((p) => (
                  <tr key={p.id}>
                    <td><Link className="name" href={`/admin/khach-hang/${p.company.id}`}>{p.company.name}</Link><div className="sub mono">{p.company.code}</div></td>
                    <td className="adm-neg">{fmtPts(p.price)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDateTime(p.created_at)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {p.score_at_purchase ?? "—"} → {p.score_now ?? "—"}
                      <div className="sub">điểm lúc mua → hiện tại</div>
                    </td>
                    <td>{p.changed_fields.length ? <span style={{ color: "#8a4b00" }}>Đã sửa: {p.changed_fields.join(", ")}</span> : <span className="muted">Chưa sửa</span>}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {p.refunded_at ? (
                        <span className="adm-badge s-active" title={p.refund_note}>Đã hoàn {fmtPts(p.refund_amount)}</span>
                      ) : user.role === "admin" ? (
                        <button className="adm-btn sm" onClick={() => refund(p)}>Hoàn điểm</button>
                      ) : null}
                    </td>
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
