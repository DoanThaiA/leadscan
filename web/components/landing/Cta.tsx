export default function Cta() {
  return (
    <section className="cta">
      <div className="cta-dots"></div>
      <div className="container cta-grid">
        <div className="reveal">
          <h2>Tham gia <b><em>sàn cơ hội B2B</em> ngay hôm nay</b></h2>
          <p>Cần tìm khách hàng — đăng ký thành viên. Biết cơ hội — đăng ký đối tác.</p>
          <div className="cta-actions">
            <a href="#dang-ky" className="btn btn-primary">Đăng ký thành viên</a>
            <a href="/doi-tac#dang-ky" className="btn btn-ghost">Đăng ký đối tác</a>
          </div>
        </div>
      </div>
    </section>
  );
}
