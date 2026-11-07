// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
import Calculator from "./Calculator";

export default function Pricing() {
  return (
    <>
      <section className="section pricing" id="bang-gia">
        <div className="container">
          <div className="section-head reveal">
            <span className="pill-tag">Bảng giá</span>
            <h2 className="h-display h2">Đơn giản, minh bạch, <b>không phí ẩn</b></h2>
            <p>Đăng ký thành viên một lần mỗi năm. Toàn bộ phí được chuyển thành số dư và trừ dần khi bạn mua phiếu cơ hội.</p>
          </div>
          <div className="plans">
            <div className="plan main reveal">
              <span className="badge">Gói thành viên</span>
              <h3>Thành viên LeadScan</h3>
              <p className="desc">Dành cho doanh nghiệp muốn tìm cơ hội kinh doanh đều đặn cả năm.</p>
              <div className="price">10.000.000đ <small>/năm</small></div>
              <div className="note"><svg className="icon"><use href="#i-info" /></svg><span>Phí đăng ký được trừ dần vào giá các phiếu cơ hội bạn mua trong năm — bạn không mất thêm khoản nào.</span></div>
              <Calculator />
              <div className="plan-chips"><span><svg className="icon"><use href="#i-check" /></svg>Không phí ẩn</span><span><svg className="icon"><use href="#i-check" /></svg>Trừ đúng giá phiếu</span><span><svg className="icon"><use href="#i-check" /></svg>Nạp thêm khi cần</span></div>
              <a href="#dang-ky" className="btn btn-primary">Đăng ký thành viên ngay</a>
            </div>
            <div className="plan reveal">
              <h3>Quyền lợi thành viên</h3>
              <p className="desc">Mọi thứ bạn nhận được với gói thành viên 1 năm.</p>
              <ul>
                <li><svg className="icon"><use href="#i-check" /></svg>Khảo sát & xây dựng chân dung cơ hội tốt không giới hạn</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Truy cập kho cơ hội từ hơn 10 nhóm nguồn dữ liệu</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Xem trước tóm tắt & điểm chất lượng của mọi cơ hội</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Mua phiếu cơ hội từ 29.000đ, trừ thẳng vào số dư</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Yêu cầu AI enrich thêm đầu mối bất cứ lúc nào</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Nhận cơ hội từ đội trợ lý thực địa tại hội chợ</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Thông báo cơ hội mới khớp chân dung theo thời gian thực</li>
                <li><svg className="icon"><use href="#i-check" /></svg>Hỗ trợ tư vấn từ đội ngũ LeadScan</li>
              </ul>
              <div className="plan-sub">Phí thành viên được trừ như thế nào?</div>
              <ol className="fee-flow">
                <li><b>Đóng phí 10.000.000đ/năm</b>Toàn bộ số tiền được ghi nhận thành số dư tài khoản của bạn.</li>
                <li><b>Mua phiếu cơ hội</b>Giá mỗi phiếu (từ 29.000đ) được trừ dần vào số dư.</li>
                <li><b>Theo dõi & nạp thêm</b>Xem số dư còn lại bất cứ lúc nào; dùng hết trước hạn có thể nạp thêm để tiếp tục mua.</li>
              </ol>
              <a href="#faq" className="btn btn-outline">Xem câu hỏi thường gặp</a>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
