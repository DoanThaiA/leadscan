import RegisterForm from "./RegisterForm";

export default function Register() {
  return (
    <section className="section register" id="dang-ky">
      <div className="container reg-grid">
        <div className="reg-side reveal">
          <span className="pill-tag">Đăng ký thành viên</span>
          <h2 className="h-display" style={{ marginTop: "16px" }}>Đăng ký người mua <b>trong 1 phút</b></h2>
          <p>Chỉ cần thông tin doanh nghiệp và người liên hệ. Sau đó vào cổng thành viên để đăng nhu cầu và xem cơ hội trên sàn.</p>
          <ol className="reg-next">
            <li><b>Gửi đăng ký</b>Điền biểu mẫu bên cạnh, rồi thanh toán phí năm trong cổng thành viên.</li>
            <li><b>Đăng nhu cầu</b>Vào “Cơ hội phù hợp”, chọn tiêu chí và mô tả khách hàng bạn cần tìm.</li>
            <li><b>Xem trước, mua phiếu</b>Chọn cơ hội phù hợp, mua phiếu để mở khoá đầu mối hoặc lưu vào kho.</li>
          </ol>
          <div className="reg-trust">
            <span><svg className="icon"><use href="#i-shield" /></svg>Thông tin chỉ dùng để thiết lập tài khoản</span>
            <span><svg className="icon"><use href="#i-check" /></svg>Không thu phí khi gửi đăng ký</span>
          </div>
          <p className="reg-alt">Bạn muốn đăng cơ hội để nhận thưởng? <a href="/doi-tac#dang-ky">Đăng ký đối tác</a></p>
        </div>

        <div className="form-card reveal">
          <RegisterForm />
        </div>
      </div>
    </section>
  );
}
