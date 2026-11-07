// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
export default function Cta() {
  return (
    <>
      <section className="cta">
        <div className="cta-dots"></div>
        <div className="container cta-grid">
          <div className="reveal">
            <h2>Sẵn sàng tìm <b>cơ hội kinh doanh tiếp theo?</b></h2>
            <p>Làm khảo sát để vẽ chân dung cơ hội tốt — hệ thống AI của LeadScan sẽ bắt đầu tìm, làm giàu và chấm điểm cơ hội cho doanh nghiệp bạn.</p>
            <div className="cta-actions">
              <a href="#dang-ky" className="btn btn-primary">Đăng ký thành viên</a>
              <a href="#lien-he" className="btn btn-ghost">Liên hệ tư vấn</a>
            </div>
          </div>
          <div className="code reveal" aria-hidden="true">
      <span className="c">// Phiếu cơ hội #LS-20481</span><br />{" {"}<br />{"   "}<span className="k">"co_hoi"</span>: <span className="s">"Cần 200.000 hộp carton/tháng"</span>,<br />{"   "}<span className="k">"nguon"</span>: <span className="s">"App đăng mua"</span>,<br />{"   "}<span className="k">"khu_vuc"</span>: <span className="s">"Bắc Ninh"</span>,<br />{"   "}<span className="k">"diem_chat_luong"</span>: <span className="n">92</span>,<br />{"   "}<span className="k">"vong_enrich"</span>: <span className="n">2</span>,<br />{"   "}<span className="k">"dau_moi"</span>: [<span className="s">"Trưởng phòng mua hàng"</span>, <span className="s">"Giám đốc nhà máy"</span>],<br />{"   "}<span className="k">"gia"</span>: <span className="n">1250000</span><br />{" } "}</div>
        </div>
      </section>
    </>
  );
}
