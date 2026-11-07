// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
export default function Stats() {
  return (
    <>
      <section className="dark">
        <div className="container">
          <p className="lead reveal">LeadScan biến dữ liệu rời rạc thành <b>cơ hội kinh doanh có thể hành động ngay</b> — bạn chỉ trả tiền cho những cơ hội thực sự phù hợp.</p>
          <div className="stats">
            <div className="stat reveal"><h3>Nhóm nguồn dữ liệu</h3><small>Online, chính thống & thực địa</small><div className="num" data-count="10" data-suffix="+">0</div></div>
            <div className="stat reveal"><h3>Giá phiếu cơ hội</h3><small>Khởi điểm cho mỗi phiếu</small><div className="num" data-count="29" data-suffix="K">0</div></div>
            <div className="stat reveal"><h3>Bước từ khảo sát đến phiếu</h3><small>Khảo sát · Thu thập · Enrich · Mua</small><div className="num" data-count="4">0</div></div>
            <div className="stat reveal"><h3>Hệ thống AI vận hành</h3><small>Quét & cập nhật liên tục</small><div className="num">24/7</div></div>
          </div>
        </div>
      </section>
    </>
  );
}
