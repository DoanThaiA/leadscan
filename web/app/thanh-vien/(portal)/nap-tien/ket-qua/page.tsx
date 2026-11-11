"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { Skeleton } from "@/components/admin/ui";
import { type MemberMe, useMember } from "@/components/member/MemberContext";
import { fmtVnd, type Order, type PaymentInfo } from "@/lib/commerce";
import { errMsg, mapi, qs } from "@/lib/member/api";

interface Resp {
  order: Order;
  payment: PaymentInfo;
  me: MemberMe;
}

const ORDER_RE = /^[A-Za-z0-9]{1,20}$/;
const CODE_RE = /^[A-Za-z0-9._:-]{1,100}$/;

/** return_url của MCV: /thanh-vien/nap-tien/ket-qua?payment_code=…&order_id=…&status=…
 *  `status` trên URL chỉ để hiển thị tạm — kết luận luôn dựa trên trạng thái backend LeadScan tra từ MCV. */
export default function PaymentResultPage() {
  return (
    <Suspense fallback={<Skeleton h={240} />}>
      <Result />
    </Suspense>
  );
}

function Result() {
  const q = useSearchParams();
  const router = useRouter();
  const { setMe } = useMember();
  const orderId = q.get("order_id") ?? "";
  const paymentCode = q.get("payment_code") ?? "";
  const urlStatus = q.get("status") ?? "";
  const valid = ORDER_RE.test(orderId) && (!paymentCode || CODE_RE.test(paymentCode));
  const [d, setD] = useState<Resp | null>(null);
  const [error, setError] = useState("");
  const tries = useRef(0);

  useEffect(() => {
    document.title = "Kết quả thanh toán · LeadScan B2B";
    if (!valid) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const check = async () => {
      try {
        const r = await mapi.get<Resp>(`/orders/${orderId}${qs({ payment_code: paymentCode })}`);
        if (stop) return;
        setD(r);
        if (r.order.status === "paid") {
          setMe(r.me);
          router.replace(`/thanh-vien/nap-tien/${r.order.code}`); // trang đơn: thành công + xuất hoá đơn
          return;
        }
      } catch (e) {
        if (!stop) setError(errMsg(e));
        return;
      }
      // Ngân hàng/MCV có thể chậm vài giây so với lúc khách được đưa về → hỏi lại tối đa ~1 phút
      if (++tries.current < 12) timer = setTimeout(check, 5000);
    };
    check();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [orderId, paymentCode, valid, router, setMe]);

  if (!valid) {
    return (
      <section className="adm-card adm-empty">
        <p>Đường dẫn kết quả thanh toán không hợp lệ.</p>
        <p style={{ marginTop: 12 }}><Link className="adm-btn primary" href="/thanh-vien/vi">Về Ví & nạp tiền</Link></p>
      </section>
    );
  }
  if (error) return <div className="adm-alert">{error}</div>;
  if (!d) {
    return (
      <section className="adm-card">
        <div className="bd" style={{ display: "grid", gap: 10 }}>
          <h2>Đang xác nhận thanh toán…</h2>
          <p className="muted">LeadScan đang kiểm tra với cổng thanh toán{urlStatus === "paid" ? " — vui lòng đợi trong giây lát" : ""}.</p>
          <Skeleton h={60} />
        </div>
      </section>
    );
  }

  const st = d.payment.mcv_status;
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Kết quả thanh toán</h1>
          <p>Đơn {d.order.code} · {fmtVnd(d.order.amount)}</p>
        </div>
      </div>
      <section className="adm-card">
        <div className="bd" style={{ display: "grid", gap: 12, justifyItems: "start" }}>
          {st === "needs_attention" ? (
            <div className="adm-alert warn">LeadScan đã nhận được tiền nhưng số tiền chưa khớp với đơn. Kế toán sẽ đối soát và liên hệ bạn.</div>
          ) : st === "expired" ? (
            <p>Mã QR đã hết hạn và LeadScan chưa nhận được tiền. Nếu bạn đã chuyển khoản, hệ thống vẫn ghi nhận khi tiền về.</p>
          ) : (
            <p>
              {tries.current >= 12 ? "LeadScan chưa nhận được xác nhận thanh toán." : "Đang chờ xác nhận từ cổng thanh toán…"} Nếu bạn đã chuyển khoản, trang đơn sẽ tự
              cập nhật khi tiền về — không cần chuyển lại.
            </p>
          )}
          <Link className="adm-btn primary" href={`/thanh-vien/nap-tien/${d.order.code}`}>Xem đơn {d.order.code}</Link>
        </div>
      </section>
    </>
  );
}
