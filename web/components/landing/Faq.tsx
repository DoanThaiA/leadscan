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
            <details open><summary>LeadScan B2B hoạt động như thế nào?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Bạn làm khảo sát để mô tả chân dung cơ hội tốt. Hệ thống Crawl AI dùng thông tin đó để quét các nguồn dữ liệu, lưu vào cơ sở dữ liệu cơ hội, sau đó AI làm giàu (enrich) và chấm điểm (scoring). Bạn xem trước, chọn và mua phiếu cơ hội phù hợp.</p></details>
            <details><summary>Phí thành viên 10 triệu/năm được tính như thế nào?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Phí đăng ký 10.000.000đ/năm được ghi nhận thành số dư tài khoản. Mỗi khi bạn mua phiếu cơ hội, giá phiếu sẽ được trừ dần vào số dư này.</p></details>
            <details><summary>Một phiếu cơ hội có giá bao nhiêu?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Giá phiếu bắt đầu từ 29.000đ và phụ thuộc vào chất lượng cơ hội. Giá tăng theo mỗi vòng enrich; các dự án lớn, giá trị cao có thể lên tới 100.000.000đ/phiếu.</p></details>
            <details><summary>Phiếu cơ hội gồm những thông tin gì?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Mỗi phiếu gồm thông tin cơ hội (nhu cầu, ngành, khu vực, quy mô, nguồn tin) và danh sách đầu mối liên hệ: vị trí, email, số điện thoại. Bạn có thể bấm “Enrich” để AI tìm thêm đầu mối.</p></details>
            <details><summary>Dữ liệu được lấy từ những nguồn nào?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Crawl từ web và nguồn trả phí, mạng xã hội, hội nhóm, nhóm chat, cộng đồng doanh nhân, Trang vàng, Bộ Công Thương, Công báo Chính phủ, app đăng mua, dự án thầu và đội trợ lý thực địa tại hội chợ.</p></details>
            <details><summary>Tôi có được xem trước cơ hội trước khi mua không?<svg className="icon"><use href="#i-plus" /></svg></summary><p>Có. Bạn xem được tóm tắt cơ hội và điểm chất lượng AI trước khi quyết định mua. Thông tin liên hệ đầy đủ chỉ được mở khoá sau khi mua phiếu.</p></details>
          </div>
        </div>
      </section>
    </>
  );
}
