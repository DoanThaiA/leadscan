import { ACCEPTED, howCombined, REJECTED, type Reward, vnd } from "@/lib/partner/content";

/**
 * Điều khoản đối tác & chính sách bảo mật — BẢN DỰ THẢO dựng từ Brief tính năng Đối tác v0.1.
 * Phải được luật sư duyệt trước khi mở thí điểm (cổng điều kiện MVP → thí điểm). Đổi nội dung → tăng
 * LEADSCAN_PARTNER_TERMS_VERSION ở backend để biết đối tác đã đồng ý phiên bản nào.
 */
export function PartnerTerms({ reward: R }: { reward: Reward }) {
  return (
    <div className="ptn-doc">
      <div className="adm-alert warn ptn-draft">
        Bản dự thảo, đang chờ luật sư duyệt. Nội dung chính thức sẽ được công bố trước khi mở chương trình thí điểm.
      </div>

      <h2>1. Đối tác là ai</h2>
      <p>Cá nhân hoặc tổ chức đăng ký tại leadscan.net/doi-tac, đã xác thực email, giới thiệu thông tin cơ hội kinh doanh B2B cho LeadScan. Đối tác không phải nhân viên và không đại diện cho LeadScan.</p>

      <h2>2. LeadScan trả thưởng cho gì</h2>
      <p>LeadScan trả thưởng cho <b>thông tin cơ hội kinh doanh</b> đã được xác minh là đúng, mới và đạt điểm chất lượng, không trả theo số lượng liên hệ hay dữ liệu cá nhân.</p>
      <ul>{ACCEPTED.map((x) => <li key={x}>{x}</li>)}</ul>
      <p style={{ marginTop: 8 }}>LeadScan từ chối:</p>
      <ul>{REJECTED.map((x) => <li key={x}>{x}</li>)}</ul>

      <h2>3. Thưởng và hoa hồng</h2>
      <table>
        <thead><tr><th>Khoản</th><th>Điều kiện</th><th>Mức</th></tr></thead>
        <tbody>
          <tr><td>Ly cafe cảm ơn</td><td>Cơ hội đạt xác minh, trong hạn mức tháng theo hạng</td><td>{vnd(R.cafe)}/cơ hội</td></tr>
          <tr><td>Hoa hồng phiếu thường</td><td>Mỗi lượt bán trong {R.months} tháng kể từ ngày xuất bản phiếu</td><td>{R.rate}% doanh thu thuần</td></tr>
          <tr><td>Hoa hồng cơ hội lớn</td><td>Gói thầu, dự án đầu tư lớn</td><td>{R.rateLarge}% doanh thu thuần</td></tr>
          <tr><td>Đóng góp bổ sung</td><td>Bổ sung thông tin mới có giá trị cho cơ hội LeadScan đã có</td><td>1 ly cafe, không chia doanh thu</td></tr>
        </tbody>
      </table>
      <p>{howCombined(R)} Doanh thu thuần là số tiền thành viên thực trả cho phiếu, sau khuyến mại, chưa gồm thuế GTGT.</p>

      <h2>4. Quy tắc ghi nhận</h2>
      <ul>
        <li>Ai gửi trước được ghi nhận theo dấu thời gian. Trùng được xác định theo mã số thuế (hoặc tên + địa chỉ) và nhóm nhu cầu trong 90 ngày.</li>
        <li>Không tính hoa hồng khi tài khoản thành viên mua phiếu có liên quan đến đối tác (trùng số điện thoại, email, mã số thuế, tài khoản ngân hàng).</li>
        <li>Thành viên được hoàn tiền vì thông tin sai → thu hồi hoa hồng của lượt đó. Cơ hội gian lận → thu hồi cả ly cafe và khoá tài khoản.</li>
        <li>Chương trình chỉ có 1 cấp: không có mã giới thiệu đối tác, không có hoa hồng từ kết quả của người khác, không thu phí tham gia.</li>
      </ul>

      <h2>5. Ví hoa hồng và rút tiền</h2>
      <p>Ví hoa hồng là sổ ghi khoản LeadScan phải trả cho đối tác, không phải ví điện tử: không nạp tiền, không chuyển cho người khác, chỉ rút về tài khoản ngân hàng đứng tên đối tác.</p>
      <ul>
        <li>Hoa hồng mỗi lượt bán được giữ {R.holdDays} ngày trước khi chuyển sang Khả dụng.</li>
        <li>Rút từ {vnd(R.minWithdraw)} khả dụng; LeadScan chi theo lô {R.payoutDays}.</li>
        <li>Lần rút đầu cần hồ sơ thanh toán: họ tên, số định danh cá nhân, mã số thuế, tài khoản ngân hàng chính chủ. Đối tác tổ chức xuất hoá đơn trước khi LeadScan chi.</li>
        <li>Đối tác cá nhân: LeadScan khấu trừ thuế TNCN theo quy định hiện hành và cấp chứng từ khấu trừ.</li>
      </ul>

      <h2>6. Cam kết của đối tác</h2>
      <ul>
        <li>Thông tin gửi là hợp pháp, không vi phạm nghĩa vụ bảo mật với nơi làm việc, không phải dữ liệu mua bán.</li>
        <li>Chỉ điền người liên hệ khi người đó đồng ý được giới thiệu hoặc là liên hệ công khai của doanh nghiệp.</li>
        <li>Không tạo nhiều tài khoản, không tự mua phiếu từ cơ hội của mình.</li>
      </ul>

      <h2 id="bao-mat">7. Chính sách bảo mật</h2>
      <ul>
        <li>LeadScan thu họ tên, số điện thoại, email, hình thức tham gia (và tên tổ chức, mã số thuế nếu là tổ chức) để quản lý tài khoản đối tác, xác minh và liên hệ về cơ hội.</li>
        <li>Thông tin định danh và tài khoản ngân hàng chỉ thu khi rút tiền, dùng để chi trả và kê khai thuế, được mã hoá khi lưu trữ.</li>
        <li>Thành viên mua phiếu không thấy danh tính đối tác nguồn; đối tác không thấy thành viên nào đã mua phiếu.</li>
        <li>Đối tác có thể yêu cầu xem, sửa hoặc xoá dữ liệu cá nhân của mình bằng cách liên hệ LeadScan, trừ dữ liệu phải lưu theo quy định kế toán, thuế.</li>
      </ul>
    </div>
  );
}
