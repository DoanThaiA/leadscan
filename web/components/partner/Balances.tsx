import type { WalletSummary } from "@/lib/partner/api";
import { vnd } from "@/lib/partner/content";

/** 4 loại số dư ví hoa hồng (brief mục 6.1). */
export function Balances({ w }: { w: WalletSummary }) {
  return (
    <div className="adm-grid cols-4">
      <section className="adm-card adm-stat"><small>Chờ duyệt</small><b>{vnd(w.pending)}</b><span>ly cafe chờ xuất bản phiếu, hoa hồng đang giữ</span></section>
      <section className="adm-card adm-stat ptn-avail"><small>Khả dụng</small><b>{vnd(w.available)}</b><span>có thể rút về ngân hàng</span></section>
      <section className="adm-card adm-stat"><small>Đang rút</small><b>{vnd(w.withdrawing)}</b><span>lệnh rút đang xử lý</span></section>
      <section className="adm-card adm-stat"><small>Đã rút</small><b>{vnd(w.paid)}</b><span>tổng đã chi trả</span></section>
    </div>
  );
}
