// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
import { Logo } from "@/components/brand/Logo";

export default function Hero() {
  return (
    <>
      <section className="hero">
        <svg className="hero-rays" id="rays" preserveAspectRatio="none"></svg>
        <div className="container">
          <span className="pill"><svg className="icon star" style={{ width: "14px", height: "14px" }}><use href="#i-spark" /></svg> AI Crawl · AI Enrich · AI Scoring</span>
          <h1 className="h-display">Scan đúng <b>cơ hội kinh doanh</b> cho doanh nghiệp bạn</h1>
          <p className="hero-sub">Bạn chỉ cần mô tả cơ hội mình muốn tìm. Hệ thống AI của LeadScan quét hơn 10 nhóm nguồn dữ liệu, làm giàu thông tin, chấm điểm từng cơ hội — bạn chọn và mua đúng phiếu cơ hội mình cần.</p>
          <div className="hero-cta">
            <a href="#dang-ky" className="btn btn-primary">Đăng ký ngay <svg className="icon"><use href="#i-arrow" /></svg></a>
            <a href="#bang-gia" className="btn btn-outline">Xem bảng giá</a>
          </div>
          <div className="hero-chips">
            <span className="pill"><svg className="icon"><use href="#i-check" /></svg> Phiếu cơ hội từ 29.000đ</span>
            <span className="pill"><svg className="icon"><use href="#i-check" /></svg> Trả tiền theo chất lượng cơ hội</span>
            <span className="pill"><svg className="icon"><use href="#i-check" /></svg> Phí năm trừ dần vào phiếu đã mua</span>
          </div>

          <div className="frame reveal">
            {/* Giữ khớp với trang "Cơ hội phù hợp" (form gửi yêu cầu) trong cổng thành viên: app/thanh-vien/(portal)/phu-hop */}
            <div className="app" aria-label="Minh hoạ giao diện LeadScan">
              <aside className="app-side">
                <div className="logo"><Logo height={20} /></div>
                <div className="side-item"><svg className="icon"><use href="#i-home" /></svg>Tổng quan</div>
                <div className="side-item active"><svg className="icon"><use href="#i-scan" /></svg>Cơ hội phù hợp</div>
                <div className="side-item"><svg className="icon"><use href="#i-bookmark" /></svg>Kho của tôi</div>
                <div className="side-item"><svg className="icon"><use href="#i-ticket" /></svg>Phiếu đã mua</div>
                <div className="side-item"><svg className="icon"><use href="#i-grid" /></svg>Tất cả cơ hội</div>
                <div className="side-item"><svg className="icon"><use href="#i-wallet" /></svg>Số dư tài khoản</div>
                <div className="side-item"><svg className="icon"><use href="#i-user" /></svg>Tài khoản</div>
                <div className="side-credit">
                  <small>Số dư thành viên còn lại</small>
                  <strong>7.840.000 điểm</strong>
                  <div className="bar"><i style={{ width: "78%" }}></i></div>
                </div>
              </aside>
              <div className="app-filter">
                <h4>Tiêu chí tìm kiếm</h4>
                <div className="hint">Bỏ trống nhóm nào thì không giới hạn nhóm đó</div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-factory" /></svg>Ngành hàng</div>
                  <div className="msx"><i>Bao bì &amp; in ấn ×</i><i>Nhựa &amp; cao su ×</i><svg className="icon"><use href="#i-search" /></svg></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-map" /></svg>Khu vực</div>
                  <div className="msx open"><i>Bắc Ninh ×</i><i>Hà Nội ×</i><span className="caret">hải|</span></div>
                  <div className="msx-list"><b>Hải Phòng</b><span>Hải Dương</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-users" /></svg>Quy mô khách hàng</div>
                  <div className="msx"><i>200+ nhân sự ×</i><span>Chọn quy mô…</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-layers" /></svg>Loại cơ hội</div>
                  <div className="msx"><i>App đăng mua ×</i><i>Dự án &amp; gói thầu ×</i></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-gauge" /></svg>Điểm chất lượng tối thiểu</div>
                  <div className="msx sel"><span style={{ color: "var(--ink-2)" }}>Từ 70 điểm trở lên</span><em>▾</em></div></div>
              </div>
              <div className="app-list">
                <div className="list-top"><h4>Mô tả yêu cầu</h4></div>
                <div className="req-box">Chúng tôi sản xuất thùng carton 5 lớp và khay nhựa, công suất 300.000 sản phẩm/tháng. Cần tìm nhà máy điện tử, doanh nghiệp FDI tại Bắc Ninh – Hà Nội có nhu cầu bao bì thường xuyên; ưu tiên đơn hàng hằng tháng.</div>
                <div className="req-tags"><span>Tiêu chí đính kèm:</span><i>Bao bì &amp; in ấn</i><i>Nhựa &amp; cao su</i><i>Bắc Ninh</i><i>Hà Nội</i><i>200+ nhân sự</i><i>≥ 70 điểm</i></div>
                <div className="req-btn"><svg className="icon"><use href="#i-spark" /></svg>Enrich tìm kiếm cơ hội</div>
                <div className="list-top" style={{ marginTop: "18px" }}><h4>Yêu cầu đã gửi <span>(2)</span></h4></div>
                <div className="req-item">
                  <div className="req-head"><b>Yêu cầu #12</b><small>Hôm nay, 09:20</small><em className="st-open">Đang tìm</em></div>
                  <p>Tìm nhà nhập khẩu bao PP dệt tại châu Phi, đơn từ 1 container/tháng.</p>
                </div>
                <div className="req-item">
                  <div className="req-head"><b>Yêu cầu #11</b><small>03/11, 14:05</small><em className="st-done">Đã có kết quả</em></div>
                  <p>Nhà máy FDI mới tại Bắc Giang cần nhà cung cấp màng PE, khay nhựa.</p>
                  <div className="req-reply"><b>LeadScan phản hồi:</b> Đã thêm 5 cơ hội phù hợp, điểm từ 74 — xem trong mục Tất cả cơ hội.</div>
                </div>
              </div>
            </div>
            <div className="frame-bottom">
              <div><h3>Mọi thứ bạn cần để tìm cơ hội B2B chất lượng</h3><p>Gửi yêu cầu tìm cơ hội, LeadScan quét nguồn dữ liệu, làm giàu và chấm điểm — bạn chọn mua đúng phiếu mình cần, tất cả trong một nền tảng.</p></div>
              <a href="#quy-trinh" className="btn btn-primary">Xem cách hoạt động <svg className="icon"><use href="#i-arrow" /></svg></a>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
