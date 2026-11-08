// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
import { Logo } from "@/components/brand/Logo";

// Nhãn nguồn & màu giống components/member/OppList.tsx
const OPPS = [
  { ic: "ĐM", bg: "#FA5320", fg: "#2B1B14", t: "Cần 200.000 hộp carton 5 lớp/tháng", src: "App đăng mua", where: "Bắc Ninh", when: "2 giờ trước", score: 92, price: "1.250.000 điểm", tier: "Enrich vòng 2", saved: false },
  { ic: "DA", bg: "#2563EB", fg: "#fff", t: "Gói thầu bao bì nhựa cho KCN Yên Phong", src: "Dự án & gói thầu", where: "Bắc Ninh", when: "Hôm nay", score: 88, price: "3.900.000 điểm", tier: "Enrich vòng 3", saved: true },
  { ic: "NM", bg: "#16A34A", fg: "#fff", t: "Nhà máy điện tử mới tìm NCC khay nhựa", src: "Nhà máy / FDI mới", where: "Hà Nội", when: "", score: 81, price: "450.000 điểm", tier: "Enrich vòng 1", saved: false },
  { ic: "MX", bg: "#9333EA", fg: "#fff", t: "Hỏi giá màng co PE số lượng lớn", src: "Nhóm chat", where: "Hà Nội", when: "", score: 74, price: "29.000 điểm", tier: "Phiếu cơ bản", saved: false },
  { ic: "HC", bg: "#0369A1", fg: "#fff", t: "Gặp tại hội chợ: cần đối tác in bao bì xuất khẩu", src: "Hội chợ & triển lãm", where: "Hải Phòng", when: "", score: 72, price: "180.000 điểm", tier: "Enrich vòng 1", saved: true },
  { ic: "CT", bg: "#F59E0B", fg: "#2B1B14", t: "Doanh nghiệp FDI mới cấp phép, cần NCC bao bì", src: "Công báo Chính phủ", where: "Bắc Giang", when: "", score: 70, price: "29.000 điểm", tier: "Phiếu cơ bản", saved: false },
];

export default function Hero() {
  return (
    <>
      <section className="hero">
        <svg className="hero-rays" id="rays" preserveAspectRatio="none"></svg>
        <div className="container">
          <span className="pill"><svg className="icon star" style={{ width: "14px", height: "14px" }}><use href="#i-spark" /></svg> AI Crawl · AI Enrich · AI Scoring</span>
          <h1 className="h-display">Scan đúng <b>cơ hội kinh doanh</b> cho doanh nghiệp bạn</h1>
          <p className="hero-sub">Bạn chỉ cần chọn tiêu chí cơ hội mình muốn tìm. Hệ thống AI của LeadScan quét hơn 10 nhóm nguồn dữ liệu, làm giàu thông tin, chấm điểm từng cơ hội — bạn chọn và mua đúng phiếu cơ hội mình cần.</p>
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
            {/* Giữ khớp với trang "Cơ hội phù hợp" trong cổng thành viên (app/thanh-vien/(portal)/phu-hop) */}
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
                <h4>Tìm cơ hội phù hợp</h4>
                <div className="hint">Chọn tiêu chí — AI lọc và chấm điểm cơ hội cho bạn</div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-factory" /></svg>Ngành hàng</div>
                  <div className="chips"><span className="chip on">Bao bì &amp; in ấn</span><span className="chip on">Nhựa &amp; cao su</span><span className="chip">Điện tử</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-map" /></svg>Khu vực</div>
                  <div className="chips"><span className="chip on">Bắc Ninh</span><span className="chip on">Hà Nội</span><span className="chip">Hải Phòng</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-users" /></svg>Quy mô khách hàng</div>
                  <div className="chips"><span className="chip">50–200 nhân sự</span><span className="chip on">200+ nhân sự</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-layers" /></svg>Loại cơ hội</div>
                  <div className="chips"><span className="chip on">App đăng mua</span><span className="chip on">Dự án &amp; gói thầu</span><span className="chip">Nhà máy / FDI mới</span><span className="chip">Hội chợ</span></div></div>
                <div className="f-group"><div className="f-label"><svg className="icon"><use href="#i-gauge" /></svg>Điểm chất lượng</div>
                  <div className="chips"><span className="chip">Mọi mức</span><span className="chip on">≥ 70 điểm</span><span className="chip">≥ 80 điểm</span></div></div>
                <div className="f-save"><svg className="icon"><use href="#i-scan" /></svg>Lưu &amp; tìm cơ hội</div>
              </div>
              <div className="app-list">
                <div className="list-top"><h4><span>128</span> cơ hội phù hợp</h4><span className="btn btn-outline">Sắp xếp: Điểm cao</span></div>
                {OPPS.map((o) => (
                  <div className="opp" key={o.t}>
                    <div className="opp-ic" style={{ background: o.bg, color: o.fg }}>{o.ic}</div>
                    <div><div className="opp-t">{o.t}</div><div className="opp-m"><span>{o.src}</span><span>· {o.where}</span>{o.when ? <span>· {o.when}</span> : null}</div></div>
                    <span className={o.score >= 85 ? "score s-hi" : "score s-md"}>{o.score}</span>
                    <div className="opp-p">{o.price}<small>{o.tier}</small></div>
                    <div className="opp-a">
                      <span className="mini buy"><svg className="icon"><use href="#i-ticket" /></svg>Mua</span>
                      <span className={o.saved ? "mini save on" : "mini save"} title={o.saved ? "Đã lưu trong kho" : "Thêm vào kho"}><svg className="icon"><use href="#i-bookmark" /></svg></span>
                    </div>
                  </div>
                ))}
                <div className="list-more"><span>Hiển thị 6 / 128 cơ hội</span><b>Xem thêm →</b></div>
              </div>
            </div>
            <div className="frame-bottom">
              <div><h3>Mọi thứ bạn cần để tìm cơ hội B2B chất lượng</h3><p>Chọn tiêu chí, quét nguồn dữ liệu, làm giàu và chấm điểm — mua ngay hoặc lưu vào kho, tất cả trong một nền tảng.</p></div>
              <a href="#quy-trinh" className="btn btn-primary">Xem cách hoạt động <svg className="icon"><use href="#i-arrow" /></svg></a>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
