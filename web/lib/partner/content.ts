/**
 * Nội dung tính năng Đối tác (theo Brief tính năng Đối tác LeadScan v0.1) — dùng chung cho landing /doi-tac, điều khoản
 * và mục "Chính sách & hướng dẫn" trong cổng. Mức thưởng lấy từ cấu hình đang áp dụng (GET /api/partner/reward-config,
 * admin chỉnh ở /admin/doi-tac/cau-hinh); DEFAULT_REWARD chỉ dùng khi không gọi được API.
 */

import type { RewardConfig } from "@/lib/partner/api";

export interface Reward {
  cafe: number; // 1 ly cafe cảm ơn / cơ hội đạt xác minh
  rate: number; // % doanh thu mỗi lượt bán phiếu thường (hạng Mới)
  rateSilver: number;
  rateLarge: number; // % cơ hội lớn (gói thầu, dự án lớn)
  months: number; // thời hạn chia sẻ doanh thu kể từ ngày xuất bản phiếu
  holdDays: number; // hoa hồng giữ trước khi chuyển sang Khả dụng
  mode: "max" | "sum"; // max = lấy mức cao hơn (PA2), sum = cộng dồn (PA1)
  minWithdraw: number;
  payoutDays: string;
  taxThreshold: number;
}

export const DEFAULT_REWARD: Reward = {
  cafe: 30_000,
  rate: 20,
  rateSilver: 25,
  rateLarge: 10,
  months: 12,
  holdDays: 7,
  mode: "max",
  minWithdraw: 100_000,
  payoutDays: "ngày 5 và 20 hằng tháng",
  taxThreshold: 5_000_000,
};

export function rewardFrom(c: RewardConfig | null | undefined): Reward {
  if (!c) return DEFAULT_REWARD;
  return {
    ...DEFAULT_REWARD, cafe: c.cafe, rate: c.rate, rateSilver: c.rate_silver, rateLarge: c.rate_large, months: c.months, holdDays: c.hold_days, mode: c.mode,
    minWithdraw: c.min_withdraw ?? DEFAULT_REWARD.minWithdraw, taxThreshold: c.tax_threshold ?? DEFAULT_REWARD.taxThreshold,
    payoutDays: c.payout_days ? payDaysText(c.payout_days) : DEFAULT_REWARD.payoutDays,
  };
}

/** "5,20" → "ngày 5 và 20 hằng tháng" */
export function payDaysText(days: string): string {
  const d = days.split(",").map((x) => x.trim()).filter(Boolean);
  return `ngày ${d.length > 1 ? d.slice(0, -1).join(", ") + " và " + d[d.length - 1] : d[0]} hằng tháng`;
}

export const vnd = (n: number) => n.toLocaleString("vi-VN") + "đ";

export const SLOGAN =
  "Nếu bạn nhìn thấy cơ hội nhưng không có khả năng thực thi, hãy giới thiệu cho người phù hợp — ít nhất bạn sẽ nhận được 1 ly cafe cảm ơn.";

/** Một câu giải thích cách cộng ly cafe & hoa hồng theo phương án đang áp dụng */
export function howCombined(r: Reward): string {
  return r.mode === "sum"
    ? `Bạn nhận 1 ly cafe (${vnd(r.cafe)}) khi cơ hội đạt xác minh, cộng thêm ${r.rate}% doanh thu mỗi lượt bán phiếu.`
    : `Bạn nhận mức cao hơn giữa 1 ly cafe (${vnd(r.cafe)}) và ${r.rate}% doanh thu phiếu của cơ hội — vì vậy luôn có ít nhất 1 ly cafe. Khi cơ hội bán tốt, hoa hồng thay cho ly cafe.`;
}

/** 6 nhóm đối tác (brief mục 3) — icon lấy từ IconSprite của landing */
export const GROUPS = [
  { icon: "users", title: "Sales, môi giới tự do", sees: "Khách hỏi mặt hàng ngoài danh mục bạn bán.", why: "Thêm thu nhập mà không mất khách." },
  { icon: "cart", title: "Mua hàng, kho vận, QA", sees: "Nhà cung cấp hiện tại không đáp ứng, phát sinh nhu cầu mới.", why: "Thu nhập phụ, giúp đơn vị tìm nguồn." },
  { icon: "truck", title: "Logistics, tài xế, forwarder", sees: "Nhà máy mới, tuyến hàng mới, kho xưởng vừa thuê.", why: "Thấy trước dòng hàng." },
  { icon: "calc", title: "Kế toán dịch vụ, tư vấn thành lập DN", sees: "Doanh nghiệp mới thành lập, FDI mới vào.", why: "Tăng giá trị cho khách hàng của mình." },
  { icon: "factory", title: "Môi giới BĐS công nghiệp, ban quản lý KCN", sees: "Nhà đầu tư thuê đất, xây xưởng, cần nhà thầu và vật tư.", why: "Thêm doanh thu dịch vụ." },
  { icon: "landmark", title: "Hiệp hội ngành, đơn vị tổ chức hội chợ", sees: "Nhu cầu mua của hội viên, khách tham quan.", why: "Doanh thu dịch vụ thêm." },
] as const;

export function benefits(r: Reward) {
  return [
    { icon: "check", title: "Ít nhất 1 ly cafe", text: `${vnd(r.cafe)} cho mỗi cơ hội đạt xác minh, kể cả khi chưa bán được.` },
    { icon: "ticket", title: `${r.rate}% mỗi lượt bán`, text: `Chia doanh thu từng lượt bán phiếu trong ${r.months} tháng, mọi vòng enrich.` },
    { icon: "wallet", title: "Ví minh bạch", text: "Theo dõi trạng thái cơ hội và số dư theo thời gian thực." },
    { icon: "landmark", title: "Rút về ngân hàng", text: `Từ ${vnd(r.minWithdraw)}, chi theo lô ${r.payoutDays}.` },
    { icon: "shield", title: "Miễn phí tham gia", text: "Không thu phí, không đặt cọc, không chỉ tiêu." },
    { icon: "spark", title: "Không cần bán hàng", text: "Bạn chỉ giới thiệu. LeadScan xác minh, enrich và bán phiếu." },
  ];
}

export const ACCEPTED = [
  "Nhu cầu cụ thể: mặt hàng/dịch vụ, quy mô, thời điểm cần",
  "Có doanh nghiệp (tên hoặc mã số thuế) đứng sau nhu cầu",
  "Có thời điểm: sắp mua, đang tìm nhà cung cấp, sắp khởi công",
] as const;

export const REJECTED = [
  "Tin đồn, thông tin chung chung chép từ báo",
  "Danh sách số điện thoại, email cá nhân (dữ liệu cá nhân)",
  "Thông tin mật của nơi bạn đang làm việc",
] as const;

export const PROMISES = [
  { icon: "shield", title: "Không mua bán dữ liệu cá nhân", text: "LeadScan trả thưởng cho thông tin cơ hội kinh doanh, không trả theo số điện thoại hay email." },
  { icon: "users", title: "1 cấp, không đa cấp", text: "Không mã giới thiệu, không hoa hồng tầng dưới, không phí tham gia." },
  { icon: "clipboard", title: "Đối soát minh bạch", text: "Mọi thay đổi trạng thái và số dư đều được ghi nhật ký, xem được trong cổng." },
] as const;

export function faq(r: Reward) {
  return [
    {
      q: "Khi nào tôi nhận được tiền?",
      a: `Ly cafe được ghi vào ví khi cơ hội đạt xác minh và chuyển sang Khả dụng khi phiếu được xuất bản. Hoa hồng mỗi lượt bán giữ ${r.holdDays} ngày rồi chuyển sang Khả dụng. Từ ${vnd(r.minWithdraw)} khả dụng bạn tạo lệnh rút; LeadScan chi theo lô ${r.payoutDays}, tiền về trong 3 ngày làm việc.`,
    },
    { q: "Ly cafe và hoa hồng được cộng dồn không?", a: howCombined(r) },
    {
      q: "Thuế thu nhập cá nhân thế nào?",
      a: `Với đối tác cá nhân, LeadScan khấu trừ 10% thuế TNCN cho mỗi lần chi trả từ ${vnd(r.taxThreshold)} trở lên theo quy định hiện hành và cấp chứng từ khấu trừ. Đối tác tổ chức xuất hoá đơn cho khoản hoa hồng trước khi LeadScan chi.`,
    },
    {
      q: "Cơ hội bị trùng thì sao?",
      a: "Ai gửi trước được ghi nhận (theo dấu thời gian). Cơ hội LeadScan đã có không được thưởng, trừ khi bạn bổ sung thông tin mới có giá trị như người ra quyết định, ngân sách, thời điểm — khi đó bạn nhận 1 ly cafe.",
    },
    {
      q: "Tham gia có mất phí không?",
      a: "Không. Đăng ký và gửi cơ hội hoàn toàn miễn phí. Ví hoa hồng không nạp tiền và không chuyển cho người khác — chỉ rút về tài khoản ngân hàng đứng tên bạn.",
    },
    {
      q: "Tôi đã là thành viên LeadScan, dùng chung tài khoản được không?",
      a: "Cổng đối tác dùng tài khoản riêng, tách hẳn cổng thành viên. Bạn có thể đăng ký đối tác bằng chính email đang dùng — hai tài khoản độc lập. Lưu ý: không tính hoa hồng khi tài khoản thành viên mua phiếu có liên quan đến chính bạn.",
    },
  ];
}
