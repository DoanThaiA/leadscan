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
            <p>Chỉ cần thông tin cơ bản của doanh nghiệp và người liên hệ. Tiêu chí tìm cơ hội (ngành hàng, khu vực, loại cơ hội…) bạn nhập ngay trong cổng thành viên, AI lọc và chấm điểm cơ hội theo đó.</p>
            <ol className="reg-next">
              <li><b>Gửi đăng ký</b>Điền biểu mẫu bên cạnh, mất khoảng 1 phút.</li>
              <li><b>Nhập tiêu chí trong cổng thành viên</b>Vào mục “Cơ hội phù hợp”, chọn ngành hàng, khu vực, loại cơ hội và điểm tối thiểu.</li>
              <li><b>Mua hoặc lưu vào kho</b>Mua phiếu để mở khoá đầu mối, hoặc thêm vào kho để xem lại sau.</li>
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
