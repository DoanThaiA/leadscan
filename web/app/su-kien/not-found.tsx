export default function EventNotFound() {
  return (
    <section className="section">
      <div className="container">
        <div className="cr-empty">
          <svg className="icon"><use href="#i-search" /></svg>
          <h3>Không tìm thấy sự kiện</h3>
          <p>Sự kiện này có thể đã kết thúc, đã được gỡ xuống hoặc đường dẫn chưa đúng.</p>
          <p style={{ marginTop: 18 }}><a href="/su-kien" className="btn btn-primary">Xem các sự kiện đang mở</a></p>
        </div>
      </div>
    </section>
  );
}
