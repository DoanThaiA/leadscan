import { type Reward, rewardShort, vnd } from "@/lib/partner/content";

const items = (R: Reward): [string, string][] => [
  ["LeadScan là bên bán hay sàn trung gian?", "Sàn trung gian. Cơ hội do đối tác đăng, nhu cầu do người mua đăng. LeadScan xác minh, chấm điểm, mở bán cơ hội dưới dạng phiếu và chia doanh thu cho đối tác đã đăng."],
  ["Cơ hội trên sàn được kiểm duyệt thế nào?", "Mỗi cơ hội được kiểm trùng, xác minh nguồn, bổ sung thông tin doanh nghiệp và chấm điểm 0–100 trước khi mở bán, thường trong khoảng 2 ngày làm việc. Cơ hội không đạt sẽ không lên sàn."],
  ["Người mua có được xem trước trước khi trả tiền không?", "Có. Tóm tắt và điểm chất lượng xem miễn phí. Tên bên có nhu cầu và đầu mối liên hệ chỉ mở khoá sau khi mua phiếu. Mỗi phiếu giới hạn số người mua để bạn ít phải cạnh tranh."],
  ["Đối tác được trả tiền thế nào?", `${rewardShort(R)} Rút về tài khoản ngân hàng từ ${vnd(R.minWithdraw)}, chi theo lô ${R.payoutDays}.`],
  ["Tôi vừa muốn mua vừa muốn đăng cơ hội được không?", "Được. Một tài khoản dùng cho cả cổng thành viên và cổng đối tác; ví điểm và ví hoa hồng tách riêng. Trong cổng thành viên, bấm “Trở thành đối tác” là xong."],
  ["Thanh toán và hoá đơn ra sao?", "Chuyển khoản VietQR qua cổng thanh toán MCV, điểm được cộng tự động khi nhận tiền. Bạn nhập thông tin xuất hoá đơn trong cổng thành viên, hoá đơn điện tử được xuất sau khi thanh toán."],
];

export default function Faq({ reward }: { reward: Reward }) {
  return (
    <section className="section" id="faq">
      <div className="container">
        <div className="section-head reveal">
          <h2 className="h-display h2">Câu hỏi <b>thường gặp</b></h2>
        </div>
        <div className="faq reveal">
          {items(reward).map(([q, a], i) => (
            <details key={q} open={i === 0}><summary>{q}<svg className="icon"><use href="#i-plus" /></svg></summary><p>{a}</p></details>
          ))}
        </div>
      </div>
    </section>
  );
}
