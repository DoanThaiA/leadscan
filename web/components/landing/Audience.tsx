// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
export default function Audience() {
  return (
    <>
      <section className="section audience" id="doi-tuong">
        <div className="container">
          <div className="section-head reveal" style={{ textAlign: "left", marginLeft: "0" }}>
            <h2 className="h-display h2">Doanh nghiệp đang tìm khách hàng mới? <b>LeadScan dành cho bạn.</b></h2>
            <p>Thay vì để đội kinh doanh mất hàng tuần tự tìm, lọc và xác minh thông tin, LeadScan mang cơ hội đã được sàng lọc đến tận tay bạn.</p>
          </div>
          <div className="aud-grid">
            <div className="aud reveal"><div className="ic"><svg className="icon"><use href="#i-factory" /></svg></div><h3>Doanh nghiệp sản xuất</h3><p>Tìm nhà máy, dự án mới đang cần nguyên vật liệu, linh kiện, bao bì và dịch vụ gia công.</p></div>
            <div className="aud reveal"><div className="ic"><svg className="icon"><use href="#i-ship" /></svg></div><h3>Xuất nhập khẩu</h3><p>Nắm bắt nhu cầu đăng mua, đối tác gặp tại hội chợ và doanh nghiệp FDI mới vào thị trường.</p></div>
            <div className="aud reveal"><div className="ic"><svg className="icon"><use href="#i-truck" /></svg></div><h3>Thương mại & phân phối</h3><p>Phát hiện đại lý, chuỗi bán lẻ và khách sỉ đang mở rộng ở khu vực bạn phục vụ.</p></div>
            <div className="aud reveal"><div className="ic"><svg className="icon"><use href="#i-brief" /></svg></div><h3>Dịch vụ B2B & nhà thầu</h3><p>Theo dõi gói thầu, dự án và doanh nghiệp mới thành lập cần đúng dịch vụ của bạn.</p></div>
          </div>
          <div className="aud-note reveal"><span>LeadScan giúp chủ doanh nghiệp, giám đốc kinh doanh và đội sales tìm đúng khách hàng, đúng thời điểm.</span><a href="#quy-trinh" className="link-arrow">Xem quy trình 4 bước <svg className="icon"><use href="#i-arrow" /></svg></a></div>
        </div>
      </section>
    </>
  );
}
