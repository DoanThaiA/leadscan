// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
export default function Sources() {
  return (
    <>
      <section className="section" id="nguon-du-lieu" style={{ paddingTop: "40px" }}>
        <div className="container">
          <div className="section-head reveal">
            <span className="pill-tag">Nguồn dữ liệu</span>
            <h2 className="h-display h2">Cơ hội đến từ <b>mọi nơi doanh nghiệp xuất hiện</b></h2>
            <p>LeadScan kết hợp dữ liệu trực tuyến, nguồn chính thống của nhà nước và đội trợ lý thực địa để không bỏ lỡ cơ hội nào.</p>
          </div>
          <div className="src-grid">
            <div className="src reveal"><div className="ic"><svg className="icon"><use href="#i-globe" /></svg></div><h3>Web & dữ liệu trả phí</h3><p>Crawl từ website doanh nghiệp, sàn B2B và các nguồn dữ liệu trả phí uy tín.</p><ul><li>Crawl web</li><li>Nguồn trả phí</li></ul></div>
            <div className="src reveal"><div className="ic"><svg className="icon"><use href="#i-users" /></svg></div><h3>Mạng xã hội & cộng đồng</h3><p>Theo dõi nhu cầu thật được đăng trong hội nhóm, nhóm chat và cộng đồng doanh nhân.</p><ul><li>Mạng xã hội</li><li>Hội nhóm</li><li>Nhóm chat</li><li>Cộng đồng doanh nhân</li></ul></div>
            <div className="src reveal"><div className="ic"><svg className="icon"><use href="#i-landmark" /></svg></div><h3>Nguồn chính thống</h3><p>Thông tin doanh nghiệp, chính sách và dự án từ các cổng thông tin nhà nước và danh bạ.</p><ul><li>Trang vàng</li><li>Bộ Công Thương</li><li>Công báo Chính phủ</li></ul></div>
            <div className="src reveal"><div className="ic"><svg className="icon"><use href="#i-cart" /></svg></div><h3>App đăng mua</h3><p>Nhu cầu mua hàng được doanh nghiệp đăng trực tiếp — tín hiệu mua rõ ràng nhất.</p><ul><li>Yêu cầu báo giá</li><li>Tìm nhà cung cấp</li></ul></div>
            <div className="src reveal"><div className="ic"><svg className="icon"><use href="#i-gavel" /></svg></div><h3>Dự án & gói thầu</h3><p>Cập nhật dự án đầu tư, gói thầu mới để bạn tiếp cận từ giai đoạn đầu.</p><ul><li>Dự án thầu</li><li>Dự án đầu tư</li></ul></div>
            <div className="src reveal"><div className="ic"><svg className="icon"><use href="#i-db" /></svg></div><h3>Cơ sở dữ liệu cơ hội</h3><p>Mọi tín hiệu được hợp nhất, loại trùng và liên kết hai chiều với hệ thống Crawl AI.</p><ul><li>Chuẩn hoá</li><li>Loại trùng</li><li>Cập nhật liên tục</li></ul></div>
            <div className="src wide reveal">
              <div>
                <span className="pill-tag">Đội trợ lý · Mini App</span>
                <h3 style={{ fontSize: "26px", marginTop: "14px" }}>Đội trợ lý thực địa tại các hội chợ</h3>
                <p>Không chỉ dữ liệu online: đội trợ lý của LeadScan trực tiếp đi hội chợ, triển lãm, chụp ảnh gian hàng và danh thiếp qua Mini App. AI tự động làm giàu và chấm điểm chất lượng ngay sau đó.</p>
                <a href="#dang-ky" className="link-arrow">Nhận cơ hội từ hội chợ <svg className="icon"><use href="#i-arrow" /></svg></a>
              </div>
              <div className="mini-steps">
                <div className="ms"><span className="k">01</span><div className="ic" style={{ display: "grid", placeItems: "center" }}><svg className="icon"><use href="#i-map" /></svg></div><b>Đi hội chợ</b><small>Triển lãm, sự kiện ngành</small></div>
                <div className="ms"><span className="k">02</span><div className="ic" style={{ display: "grid", placeItems: "center" }}><svg className="icon"><use href="#i-camera" /></svg></div><b>Chụp ảnh</b><small>Gian hàng, danh thiếp</small></div>
                <div className="ms"><span className="k">03</span><div className="ic" style={{ display: "grid", placeItems: "center" }}><svg className="icon"><use href="#i-spark" /></svg></div><b>AI Enrich</b><small>Bổ sung thông tin</small></div>
                <div className="ms"><span className="k">04</span><div className="ic" style={{ display: "grid", placeItems: "center" }}><svg className="icon"><use href="#i-gauge" /></svg></div><b>AI Quality Scoring</b><small>Chấm điểm chất lượng</small></div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
