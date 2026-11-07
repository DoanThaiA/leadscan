// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
export default function Cta() {
  return (
    <>
      <section className="cta">
        <div className="cta-dots"></div>
        <div className="container cta-grid">
          <div className="reveal">
            <h2>Sẵn sàng tìm <b>cơ hội kinh doanh tiếp theo?</b></h2>
            <div className="cta-actions">
              <a href="#dang-ky" className="btn btn-primary">Đăng ký thành viên</a>
              <a href="#lien-he" className="btn btn-ghost">Liên hệ tư vấn</a>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
