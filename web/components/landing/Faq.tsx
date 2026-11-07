// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
export default function Faq() {
  return (
    <>
      <section className="section" id="faq">
        <div className="container">
          <div className="section-head reveal">
            <h2 className="h-display h2">Câu hỏi <b>thường gặp</b></h2>
          </div>
          <div className="faq reveal">
            <details open><summary>Tôi có được xem trước cơ hội trước khi mua không?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Có. Bạn xem được tóm tắt cơ hội và điểm chất lượng AI trước khi quyết định mua. Thông tin liên hệ đầy đủ chỉ được mở khoá sau khi mua phiếu.</p></details>
            <details><summary>Thanh toán phí thành viên bằng cách nào?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Chuyển khoản ngân hàng bằng mã VietQR hiện trong cổng thành viên. Mỗi đơn có mã riêng làm nội dung chuyển khoản; số dư được cộng sau khi LeadScan nhận được tiền.</p></details>
            <details><summary>Dùng hết số dư trước hạn thì sao?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Bạn nạp thêm bất cứ lúc nào trong cổng thành viên, chọn gói 5, 10, 20, 50 triệu hoặc số tiền tuỳ chọn (1 điểm = 1đ), rồi tiếp tục mua phiếu.</p></details>
            <details><summary>LeadScan có xuất hoá đơn không?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Có. Sau khi thanh toán, bạn nhập thông tin xuất hoá đơn ngay trong cổng thành viên; bộ phận kế toán sẽ xuất và gửi hoá đơn cho bạn.</p></details>
          </div>
        </div>
      </section>
    </>
  );
}
