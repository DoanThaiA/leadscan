"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Skeleton, StatusBadge } from "@/components/admin/ui";
import { fmtDate } from "@/lib/admin/format";
import { errMsg, papi, qs } from "@/lib/partner/api";
import { vnd } from "@/lib/partner/content";
import { SUB_BADGE, type SubPage, type SubStatus } from "@/lib/partner/submissions";

const TABS: [string, string, SubStatus[]][] = [
  ["", "Tất cả", []],
  ["open", "Đang xử lý", ["submitted", "verifying"]],
  ["verified", "Đạt xác minh", ["verified"]],
  ["published", "Đã xuất bản", ["published"]],
  ["supplement", "Đóng góp bổ sung", ["supplement"]],
  ["duplicate", "Trùng", ["duplicate"]],
  ["rejected", "Không đạt", ["rejected"]],
];
const PAGE = 20;

function MyList() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const status = params.get("status") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [data, setData] = useState<SubPage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Cơ hội của tôi · Đối tác LeadScan";
    setData(null);
    papi.get<SubPage>("/submissions" + qs({ status, page, page_size: PAGE })).then(setData, (e) => setError(errMsg(e)));
  }, [status, page]);

  const go = (next: Record<string, string | number | undefined>) => router.replace(pathname + qs({ status, page: page > 1 ? page : undefined, ...next }), { scroll: false });
  const count = (sts: SubStatus[]) => (data ? (sts.length ? sts.reduce((a, s) => a + (data.counts[s] ?? 0), 0) : Object.values(data.counts).reduce((a, b) => a + (b ?? 0), 0)) : null);
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;

  return (
    <>
      <div className="adm-head">
        <div><h1>Cơ hội của tôi</h1><p>Trạng thái từng cơ hội bạn đã gửi, lý do nếu không đạt</p></div>
        <Link className="adm-btn primary" href="/doi-tac/gui-co-hoi">+ Gửi cơ hội</Link>
      </div>
      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}
      <section className="adm-card">
        <div className="adm-tabs" role="tablist" aria-label="Lọc theo trạng thái">
          {TABS.map(([key, label, sts]) => {
            const n = count(sts);
            if (key && n === 0 && status !== key) return null;
            return (
              <button key={key} role="tab" aria-selected={status === key} className={status === key ? "on" : undefined} onClick={() => go({ status: key, page: undefined })}>
                {label}{n !== null ? <span>{n}</span> : null}
              </button>
            );
          })}
        </div>
        {!data ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} h={22} />)}</div>
        ) : !data.items.length ? (
          <div className="adm-empty">
            {status ? "Không có cơ hội ở trạng thái này." : <>Bạn chưa gửi cơ hội nào. <Link href="/doi-tac/gui-co-hoi" style={{ color: "var(--brand-600)", fontWeight: 600 }}>Gửi cơ hội đầu tiên</Link></>}
          </div>
        ) : (
          <div>
            {data.items.map((s) => (
              <Link key={s.id} href={`/doi-tac/co-hoi/${s.id}`} className="ptn-list-row">
                <div style={{ minWidth: 0 }}>
                  <b>{s.title || s.company_name}</b>
                  <div className="sub" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.kind_label} · {s.need}</div>
                  <div className="sub mono">{s.code} · gửi {fmtDate(s.created_at)}{s.reject_label ? ` · ${s.reject_label}` : ""}{s.sold_count ? ` · đã bán ${s.sold_count} lượt` : ""}{s.earned ? ` · đã nhận ${vnd(s.earned)}` : ""}</div>
                </div>
                <StatusBadge status={SUB_BADGE[s.status]} label={s.status_label} />
              </Link>
            ))}
          </div>
        )}
        {data && data.total > PAGE ? (
          <div className="adm-pager">
            <span>{(page - 1) * PAGE + 1}–{Math.min(page * PAGE, data.total)} / {data.total}</span>
            <div>
              <button className="adm-btn sm" disabled={page <= 1} onClick={() => go({ page: page - 1 > 1 ? page - 1 : undefined })}>← Trước</button>
              <button className="adm-btn sm" disabled={page >= pages} onClick={() => go({ page: page + 1 })}>Sau →</button>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}

export default function MySubmissionsPage() {
  return (
    <Suspense>
      <MyList />
    </Suspense>
  );
}
