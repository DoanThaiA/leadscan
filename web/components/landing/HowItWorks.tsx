const STEPS: [string, string][] = [
  ["Đăng lên sàn", "Đối tác đăng cơ hội kinh doanh mình biết. Người mua đăng nhu cầu: cần tìm khách hàng ngành nào, ở đâu, quy mô ra sao."],
  ["LeadScan kiểm duyệt", "Kiểm trùng, xác minh nguồn, bổ sung thông tin doanh nghiệp và chấm điểm 0–100, khoảng 2 ngày làm việc. Cơ hội không đạt không lên sàn."],
  ["Kết nối hai bên", "Người mua xem trước miễn phí, mua phiếu để mở khoá bên có nhu cầu và đầu mối liên hệ. Đối tác nhận thưởng khi cơ hội đạt và mỗi lần phiếu được bán."],
];

export default function HowItWorks() {
  return (
    <section className="section steps3-sec" id="cach-hoat-dong">
      <div className="container">
        <div className="section-head reveal">
          <span className="pill-tag">Cách hoạt động</span>
          <h2 className="h-display h2">Sàn vận hành <b>trong 3 bước</b></h2>
          <p>Cơ hội trên sàn do người dùng đăng. LeadScan đứng giữa để bảo đảm mỗi cơ hội là thật, còn mới và đủ thông tin.</p>
        </div>
        <ol className="steps3">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="reveal"><span className="n">{i + 1}</span><h3>{t}</h3><p>{d}</p></li>
          ))}
        </ol>
        <div className="aud-note reveal">
          <span>Muốn xem sàn đang có gì? Tóm tắt cơ hội được công khai, ai cũng xem được.</span>
          <a href="/co-hoi" className="link-arrow">Xem cơ hội đang mở <svg className="icon"><use href="#i-arrow" /></svg></a>
        </div>
      </div>
    </section>
  );
}
