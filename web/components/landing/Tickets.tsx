// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
export default function Tickets() {
  return (
    <>
      <section className="section" id="phieu-co-hoi">
        <div className="container">
          <div className="section-head reveal">
            <span className="pill-tag">Phiếu cơ hội</span>
            <h2 className="h-display h2">Trả tiền theo <b>chất lượng từng cơ hội</b></h2>
            <p>Mỗi phiếu gồm thông tin cơ hội và danh sách đầu mối liên hệ. Giá sẽ tăng theo mỗi vòng enrich — thông tin càng đầy đủ, cơ hội càng giá trị.</p>
          </div>
          <div className="ladder reveal">
            <div className="rung"><div className="lv">Phiếu cơ bản</div><h4>Thông tin cơ hội</h4><p>Nhu cầu, ngành, khu vực, nguồn tin và 1 đầu mối liên hệ cơ bản.</p><div className="lvls" aria-label="Mức giá 1/4"><i className="on"></i><i></i><i></i><i></i></div><div className="pr">29.000đ <small>/phiếu</small></div></div>
            <div className="rung"><div className="lv">Enrich vòng 1</div><h4>+ Hồ sơ doanh nghiệp</h4><p>Bổ sung thông tin pháp lý, quy mô, đầu mối 1 đã xác minh: vị trí / email / SĐT.</p><div className="lvls" aria-label="Mức giá 2/4"><i className="on"></i><i className="on"></i><i></i><i></i></div><div className="pr sm">↑ Giá tăng sau vòng 1</div></div>
            <div className="rung"><div className="lv">Enrich vòng 2+</div><h4>+ Người ra quyết định</h4><p>Thêm đầu mối 2, 3 — người có thẩm quyền mua hàng, mức độ cấp thiết.</p><div className="lvls" aria-label="Mức giá 3/4"><i className="on"></i><i className="on"></i><i className="on"></i><i></i></div><div className="pr sm">↑ Giá tăng theo mỗi vòng</div></div>
            <div className="rung"><div className="lv">Cơ hội lớn</div><h4>Dự án giá trị cao</h4><p>Gói thầu, dự án đầu tư lớn được enrich chuyên sâu nhiều vòng.</p><div className="lvls" aria-label="Mức giá 4/4"><i className="on"></i><i className="on"></i><i className="on"></i><i className="on"></i></div><div className="pr">Tới 100 triệu <small>/phiếu</small></div></div>
          </div>
          <div className="steps-bar reveal"></div>
          <div className="steps-bar-l"><span>29.000đ</span><span>Giá phiếu dao động theo chất lượng & số vòng enrich</span><span>100.000.000đ</span></div>
        </div>
      </section>
    </>
  );
}
