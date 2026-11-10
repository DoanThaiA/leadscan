// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
import type { CSSProperties } from "react";

export default function Workflow() {
  return (
    <>
      <section className="section" id="quy-trinh" style={{ paddingBottom: "80px" }}>
        <div className="container">
          <div className="section-head reveal">
            <span className="pill-tag">Quy trình khép kín</span>
            <h2 className="h-display h2">Từ yêu cầu đến <b>phiếu cơ hội trong tay</b></h2>
            <p>Bốn bước: bạn mô tả cơ hội mình muốn, AI tìm, làm giàu và chấm điểm, còn bạn chọn mua đúng phiếu mình cần.</p>
          </div>
        </div>
        <div className="wf-tabs">
          <div className="container">
            <a href="#b1" className="wf-tab active"><svg className="icon"><use href="#i-filter" /></svg>1. Gửi yêu cầu</a>
            <a href="#b2" className="wf-tab"><svg className="icon"><use href="#i-bot" /></svg>2. AI thu thập</a>
            <a href="#b3" className="wf-tab"><svg className="icon"><use href="#i-spark" /></svg>3. Enrich & Scoring</a>
            <a href="#b4" className="wf-tab"><svg className="icon"><use href="#i-ticket" /></svg>4. Mua hoặc lưu kho</a>
          </div>
        </div>
        <div className="container">
          {/* B1 */}
          <div className="step reveal" id="b1">
            <div>
              <span className="pill-tag">Bước 1 · Gửi yêu cầu</span>
              <h3 style={{ marginTop: "14px" }}>Mô tả nhu cầu, <b>LeadScan tìm cơ hội cho bạn</b></h3>
              <p>Đăng ký chỉ cần thông tin cơ bản. Vào cổng thành viên, mục “Cơ hội phù hợp”, bạn chọn tiêu chí (ngành hàng, khu vực, quy mô khách hàng, loại cơ hội, điểm tối thiểu), viết rõ yêu cầu rồi bấm “Enrich tìm kiếm cơ hội”. Đội ngũ LeadScan nhận yêu cầu ngay.</p>
              <div className="feat"><h4><svg className="icon"><use href="#i-clipboard" /></svg>Tiêu chí + mô tả tự do</h4><p>Chọn tiêu chí bằng vài cú bấm, ngành hàng lúc đăng ký được điền sẵn; phần mô tả để nói rõ điều chỉ bạn biết.</p></div>
              <div className="feat"><h4><svg className="icon"><use href="#i-filter" /></svg>Theo dõi ngay trong cổng</h4><p>Mỗi yêu cầu có trạng thái và phản hồi của LeadScan; cơ hội tìm được được đưa vào kho để bạn chọn mua.</p></div>
              <a href="#dang-ky" className="link-arrow" style={{ marginTop: "10px" }}>Đăng ký để bắt đầu <svg className="icon"><use href="#i-arrow" /></svg></a>
            </div>
            <div className="visual">
              <div className="card">
                <h5>Tiêu chí tìm kiếm <span className="pill-tag">5 nhóm</span></h5>
                <div className="q"><label>Ngành hàng</label><div className="opts"><span className="opt on">Bao bì &amp; in ấn</span><span className="opt on">Nhựa &amp; cao su</span><span className="opt">Điện tử</span></div></div>
                <div className="q"><label>Quy mô khách hàng</label><div className="opts"><span className="opt">50–200 nhân sự</span><span className="opt on">200+ nhân sự</span><span className="opt on">Doanh nghiệp FDI</span></div></div>
                <div className="q"><label>Khu vực</label><div className="opts"><span className="opt on">Bắc Ninh</span><span className="opt on">Hà Nội</span><span className="opt">Hải Phòng</span></div></div>
              </div>
              <div className="card">
                <div className="persona"><span className="ic"><svg className="icon"><use href="#i-users" /></svg></span><div><b>Yêu cầu #12 · Đang tìm</b>Cần nhà máy điện tử/FDI tại Bắc Ninh, Hà Nội có nhu cầu carton 5 lớp và khay nhựa hằng tháng.</div></div>
              </div>
            </div>
          </div>

          {/* B2 */}
          <div className="step rev reveal" id="b2">
            <div>
              <span className="pill-tag">Bước 2 · AI thu thập</span>
              <h3 style={{ marginTop: "14px" }}>Hệ thống Crawl AI <b>quét mọi nguồn dữ liệu</b></h3>
              <p>Dựa trên yêu cầu và tiêu chí bạn gửi, hệ thống Crawl AI liên tục thu thập tín hiệu kinh doanh từ web, mạng xã hội, hội nhóm, cổng thông tin nhà nước và đội trợ lý thực địa — sau đó lưu vào cơ sở dữ liệu cơ hội.</p>
              <div className="feat"><h4><svg className="icon"><use href="#i-globe" /></svg>Hơn 10 nhóm nguồn dữ liệu</h4><p>Web trả phí, mạng xã hội, nhóm chat, trang vàng, Bộ Công Thương, công báo, dự án thầu…</p></div>
              <div className="feat"><h4><svg className="icon"><use href="#i-db" /></svg>Cơ sở dữ liệu cơ hội</h4><p>Dữ liệu được chuẩn hoá, loại trùng và cập nhật liên tục, hai chiều với hệ thống AI.</p></div>
            </div>
            <div className="visual alt">
              <div className="hub" id="hub">
                <svg className="lines" id="hubLines"></svg>
                <div className="hub-center"><div><svg className="icon"><use href="#i-bot" /></svg><b>Hệ thống<br />Crawl AI</b><small>→ CSDL cơ hội</small></div></div>
                <span className="node" style={{ left: "2%", top: "4%" }}><svg className="icon"><use href="#i-globe" /></svg>Web trả phí</span>
                <span className="node" style={{ left: "38%", top: "0%" }}><svg className="icon"><use href="#i-users" /></svg>Mạng xã hội, hội nhóm</span>
                <span className="node" style={{ right: "2%", top: "12%" }}><svg className="icon"><use href="#i-chat" /></svg>Nhóm chat</span>
                <span className="node" style={{ left: "0%", top: "30%" }}><svg className="icon"><use href="#i-brief" /></svg>Cộng đồng doanh nhân</span>
                <span className="node" style={{ right: "0%", top: "38%" }}><svg className="icon"><use href="#i-book" /></svg>Trang vàng</span>
                <span className="node" style={{ left: "0%", top: "58%" }}><svg className="icon"><use href="#i-landmark" /></svg>Bộ Công Thương</span>
                <span className="node" style={{ right: "0%", top: "64%" }}><svg className="icon"><use href="#i-landmark" /></svg>Công báo Chính phủ</span>
                <span className="node" style={{ left: "4%", bottom: "4%" }}><svg className="icon"><use href="#i-cart" /></svg>App đăng mua</span>
                <span className="node" style={{ left: "38%", bottom: "0%" }}><svg className="icon"><use href="#i-gavel" /></svg>Dự án thầu</span>
                <span className="node" style={{ right: "2%", bottom: "6%" }}><svg className="icon"><use href="#i-camera" /></svg>Đội trợ lý hội chợ</span>
              </div>
            </div>
          </div>

          {/* B3 */}
          <div className="step reveal" id="b3">
            <div>
              <span className="pill-tag">Bước 3 · Enrich & Scoring</span>
              <h3 style={{ marginTop: "14px" }}>AI làm giàu dữ liệu <b>và chấm điểm từng cơ hội</b></h3>
              <p>Mỗi cơ hội trong cơ sở dữ liệu được AI bổ sung thông tin doanh nghiệp, người liên hệ, mức độ cấp thiết — rồi chấm điểm chất lượng dựa trên mức độ khớp với tiêu chí của bạn.</p>
              <div className="feat"><h4><svg className="icon"><use href="#i-spark" /></svg>AI Enrich nhiều vòng</h4><p>Mỗi vòng enrich bổ sung thêm thông tin và đầu mối liên hệ có giá trị hơn.</p></div>
              <div className="feat"><h4><svg className="icon"><use href="#i-gauge" /></svg>AI Quality Scoring</h4><p>Điểm 0–100 giúp bạn biết cơ hội nào đáng ưu tiên trước.</p></div>
            </div>
            <div className="visual">
              <div className="card">
                <h5>Đang làm giàu dữ liệu <span className="pill-tag">Vòng enrich 2</span></h5>
                <div className="enrich-row"><span className="ok"><svg className="icon"><use href="#i-check" /></svg></span><span>Thông tin doanh nghiệp & mã số thuế</span><em>Xong</em></div>
                <div className="enrich-row"><span className="ok"><svg className="icon"><use href="#i-check" /></svg></span><span>Nhu cầu & quy mô đơn hàng</span><em>Xong</em></div>
                <div className="enrich-row"><span className="ok"><svg className="icon"><use href="#i-check" /></svg></span><span>Đầu mối 1: Vị trí / email / SĐT</span><em>Xong</em></div>
                <div className="enrich-row"><span className="spin"></span><span>Đầu mối 2: Người ra quyết định</span><em>Đang tìm…</em></div>
                <div className="enrich-row"><span className="spin" style={{ opacity: ".4", animation: "none" }}></span><span style={{ color: "var(--soft)" }}>Đầu mối 3</span><em>Vòng sau</em></div>
              </div>
              <div className="card">
                <div className="gauge">
                  <div className="ring" style={{ "--p": "88" } as CSSProperties}><div>88<small>/100</small></div></div>
                  <div className="crit">
                    <div><span>Khớp nhu cầu</span><b>95</b></div><div className="bar"><i style={{ width: "95%" }}></i></div>
                    <div><span>Độ cấp thiết</span><b>86</b></div><div className="bar"><i style={{ width: "86%" }}></i></div>
                    <div><span>Độ tin cậy nguồn</span><b>82</b></div><div className="bar"><i style={{ width: "82%" }}></i></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* B4 */}
          <div className="step rev reveal" id="b4">
            <div>
              <span className="pill-tag">Bước 4 · Mua hoặc lưu</span>
              <h3 style={{ marginTop: "14px" }}>Chọn, định giá <b>và mua phiếu cơ hội</b></h3>
              <p>Bạn xem trước thông tin tóm tắt của từng cơ hội, mua phiếu để mở khoá đầy đủ đầu mối liên hệ, hoặc thêm vào kho để xem lại sau. Giá trả theo chất lượng từng cơ hội — tiền được trừ dần vào số dư thành viên.</p>
              <div className="feat"><h4><svg className="icon"><use href="#i-ticket" /></svg>Trả theo chất lượng từng cơ hội</h4><p>Giá phiếu từ 29.000đ, tăng dần theo mỗi vòng enrich.</p></div>
              <div className="feat"><h4><svg className="icon"><use href="#i-plus" /></svg>Yêu cầu enrich thêm bất cứ lúc nào</h4><p>Cần thêm đầu mối? Bấm “Enrich” để AI tìm tiếp cho bạn.</p></div>
              <a href="#phieu-co-hoi" className="link-arrow" style={{ marginTop: "10px" }}>Xem chi tiết phiếu cơ hội <svg className="icon"><use href="#i-arrow" /></svg></a>
            </div>
            <div className="visual alt">
              <div className="ticket">
                <div className="ticket-head"><div><h5>Phiếu cơ hội #LS-20481</h5><small>Cần 200.000 hộp carton 5 lớp/tháng</small></div><span className="score s-hi">92 điểm</span></div>
                <div className="ticket-body">
                  <div className="ticket-col"><h6>Thông tin cơ hội</h6>
                    <div className="kv">Ngành: <b>Điện tử</b></div><div className="kv">Khu vực: <b>Bắc Ninh</b></div><div className="kv">Quy mô: <b>~200.000 hộp/tháng</b></div><div className="kv">Nguồn: <b>App đăng mua</b></div></div>
                  <div className="ticket-col"><h6>Đầu mối liên hệ</h6>
                    <div className="contact"><span className="n">1</span><span><b>Trưởng phòng mua hàng</b><span className="blur" aria-hidden="true">0912 345 678</span></span></div>
                    <div className="contact"><span className="n">2</span><span><b>Giám đốc nhà máy</b><span className="blur" aria-hidden="true">giamdoc@congty.vn</span></span></div>
                    <div className="contact locked"><span className="n">3</span><span><b>Đầu mối 3</b>Mở khoá ở vòng enrich 3</span></div></div>
                </div>
                <div className="ticket-foot"><span className="btn btn-outline">Giá</span><span className="btn btn-primary">Mua</span><span className="btn btn-outline"><svg className="icon" style={{ width: "14px", height: "14px" }}><use href="#i-spark" /></svg>Enrich</span><div className="price">1.250.000đ<small>Enrich vòng 2</small></div></div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
