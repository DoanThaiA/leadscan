// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
import RegisterForm from "./RegisterForm";

export default function Register() {
  return (
    <>
      <section className="section register" id="dang-ky">
        <div className="container reg-grid">
          <div className="reg-side reveal">
            <span className="pill-tag">Đăng ký thành viên</span>
            <h2 className="h-display" style={{ marginTop: "16px" }}>Bắt đầu với <b>một biểu mẫu ngắn</b></h2>
            <p>Cho chúng tôi biết doanh nghiệp bạn bán gì và muốn tìm khách hàng nào. LeadScan dùng thông tin này để dựng “chân dung cơ hội tốt” và thiết lập hệ thống AI quét cơ hội riêng cho bạn.</p>
            <div className="reg-price"><b>10.000.000đ</b><span>/năm</span><em>Trừ dần vào phiếu</em></div>
            <ol className="reg-next">
              <li><b>Gửi đăng ký</b>Điền biểu mẫu bên cạnh, mất khoảng 3 phút.</li>
              <li><b>LeadScan thiết lập hồ sơ</b>Dự án của doanh nghiệp bạn được tạo trên hệ thống, đội ngũ liên hệ xác nhận.</li>
              <li><b>Nhận cơ hội & mua phiếu</b>AI quét, enrich và chấm điểm; bạn chọn phiếu từ 29.000đ.</li>
            </ol>
            <div className="reg-trust">
              <span><svg className="icon"><use href="#i-shield" /></svg>Thông tin chỉ dùng để thiết lập dịch vụ</span>
              <span><svg className="icon"><use href="#i-check" /></svg>Không thu phí khi gửi đăng ký</span>
            </div>
          </div>

          <div className="form-card reveal">
      <RegisterForm />
          </div>
        </div>
      </section>
    </>
  );
}
