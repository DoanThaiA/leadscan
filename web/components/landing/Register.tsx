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
            <p>Chỉ cần thông tin cơ bản của doanh nghiệp và người liên hệ. Nhu cầu tìm cơ hội (tiêu chí + mô tả) bạn gửi ngay trong cổng thành viên, LeadScan tìm và enrich cơ hội theo đó.</p>
            <ol className="reg-next">
              <li><b>Gửi đăng ký</b>Điền biểu mẫu bên cạnh, mất khoảng 1 phút.</li>
              <li><b>Gửi yêu cầu tìm cơ hội</b>Vào mục “Cơ hội phù hợp”, chọn tiêu chí, mô tả nhu cầu và bấm “Enrich tìm kiếm cơ hội”.</li>
              <li><b>Nhận cơ hội, mua phiếu</b>LeadScan tìm và enrich cơ hội theo yêu cầu; bạn mua phiếu để mở khoá đầu mối hoặc lưu vào kho.</li>
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
