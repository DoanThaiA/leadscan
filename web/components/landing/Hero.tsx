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
          <p className="hero-sub">Bạn chỉ cần làm một bài khảo sát ngắn. Hệ thống AI của LeadScan quét hơn 10 nhóm nguồn dữ liệu, làm giàu thông tin, chấm điểm từng cơ hội — bạn chọn và mua đúng phiếu cơ hội mình cần.</p>
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
            <div className="app" aria-label="Minh hoạ giao diện LeadScan">
              <aside className="app-side">
                <div className="logo"><Logo height={20} /></div>
                <div className="side-item"><svg className="icon"><use href="#i-home" /></svg>Tổng quan</div>
                <div className="side-item"><svg className="icon"><use href="#i-clipboard" /></svg>Khảo sát của tôi</div>
                <div className="side-item active"><svg className="icon"><use href="#i-scan" /></svg>Cơ hội phù hợp</div>
                <div className="side-item"><svg className="icon"><use href="#i-ticket" /></svg>Phiếu đã mua</div>
                <div className="side-item"><svg className="icon"><use href="#i-spark" /></svg>Yêu cầu enrich</div>
                <div className="side-item"><svg className="icon"><use href="#i-wallet" /></svg>Số dư tài khoản</div>
                <div className="side-credit">
                  <small>Số dư thành viên còn lại</small>
                  <strong>7.840.000đ</strong>
                  <div className="bar"><i style={{ width: "78%" }}></i></div>
                </div>
              </aside>
              <div className="app-filter">
                <h4>Chân dung cơ hội <small>Sửa</small></h4>
                <div className="hint">Tạo từ bài khảo sát của bạn</div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-factory" /></svg>Ngành hàng</div>
                  <div className="chips"><span className="chip on">Bao bì</span><span className="chip on">Nhựa kỹ thuật</span><span className="chip">In ấn</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-map" /></svg>Khu vực</div>
                  <div className="chips"><span className="chip on">Bắc Ninh</span><span className="chip on">Hà Nội</span><span className="chip">Hải Phòng</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-users" /></svg>Quy mô</div>
                  <div className="chips"><span className="chip">50–200 NV</span><span className="chip on">200+ NV</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-layers" /></svg>Loại cơ hội</div>
                  <div className="chips"><span className="chip on">Đăng mua</span><span className="chip on">Dự án thầu</span><span className="chip">Mở nhà máy</span><span className="chip">Hội chợ</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-gauge" /></svg>Điểm chất lượng</div>
                  <div className="chips"><span className="chip on">≥ 70 điểm</span></div></div>
              </div>
              <div className="app-list">
                <div className="list-top"><h4><span>128</span> cơ hội khớp chân dung</h4><span className="btn btn-outline">Sắp xếp: Điểm cao</span></div>
                <div className="opp"><div className="opp-ic" style={{ background: "#FA5320", color: "#2B1B14" }}>TA</div><div><div className="opp-t">Cần 200.000 hộp carton 5 lớp/tháng</div><div className="opp-m"><span>App đăng mua</span><span>· Bắc Ninh</span><span>· 2 giờ trước</span></div></div><span className="score s-hi">92</span><div className="opp-p">1.250.000đ<small>Enrich vòng 2</small></div></div>
                <div className="opp"><div className="opp-ic" style={{ background: "#2563EB" }}>VP</div><div><div className="opp-t">Gói thầu bao bì nhựa cho KCN Yên Phong</div><div className="opp-m"><span>Dự án thầu</span><span>· Bắc Ninh</span><span>· Hôm nay</span></div></div><span className="score s-hi">88</span><div className="opp-p">3.900.000đ<small>Enrich vòng 3</small></div></div>
                <div className="opp"><div className="opp-ic" style={{ background: "#16A34A" }}>HK</div><div><div className="opp-t">Nhà máy điện tử mới tìm NCC khay nhựa</div><div className="opp-m"><span>Bộ Công Thương</span><span>· Hà Nội</span></div></div><span className="score s-hi">81</span><div className="opp-p">450.000đ<small>Enrich vòng 1</small></div></div>
                <div className="opp"><div className="opp-ic" style={{ background: "#9333EA" }}>MT</div><div><div className="opp-t">Hỏi giá màng co PE số lượng lớn</div><div className="opp-m"><span>Nhóm chat</span><span>· Hà Nội</span></div></div><span className="score s-md">74</span><div className="opp-p">29.000đ<small>Phiếu cơ bản</small></div></div>
                <div className="opp"><div className="opp-ic" style={{ background: "#0EA5E9" }}>GS</div><div><div className="opp-t">Gặp tại hội chợ: cần đối tác in bao bì xuất khẩu</div><div className="opp-m"><span>Đội trợ lý hội chợ</span><span>· Hải Phòng</span></div></div><span className="score s-md">72</span><div className="opp-p">180.000đ<small>Enrich vòng 1</small></div></div>
                <div className="opp"><div className="opp-ic" style={{ background: "#F59E0B" }}>NP</div><div><div className="opp-t">Doanh nghiệp FDI mới cấp phép, cần NCC bao bì</div><div className="opp-m"><span>Công báo Chính phủ</span><span>· Bắc Giang</span></div></div><span className="score s-md">70</span><div className="opp-p">29.000đ<small>Phiếu cơ bản</small></div></div>
                <div className="list-more"><span>Hiển thị 6 / 128 cơ hội</span><b>Xem thêm →</b></div>
              </div>
            </div>
            <div className="frame-bottom">
              <div><h3>Mọi thứ bạn cần để tìm cơ hội B2B chất lượng</h3><p>Khảo sát nhu cầu, quét nguồn dữ liệu, làm giàu và chấm điểm — tất cả trong một nền tảng.</p></div>
              <a href="#quy-trinh" className="btn btn-primary">Xem cách hoạt động <svg className="icon"><use href="#i-arrow" /></svg></a>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
