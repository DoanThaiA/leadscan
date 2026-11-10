export default function JobNotFound() {
  return (
    <section className="section">
      <div className="container">
        <div className="cr-empty">
          <svg className="icon"><use href="#i-search" /></svg>
          <h3>Không tìm thấy vị trí tuyển dụng</h3>
          <p>Vị trí này có thể đã được gỡ xuống hoặc đường dẫn chưa đúng.</p>
          <p style={{ marginTop: 18 }}><a href="/tuyen-dung" className="btn btn-primary">Xem các vị trí đang tuyển</a></p>
        </div>
      </div>
    </section>
  );
}
