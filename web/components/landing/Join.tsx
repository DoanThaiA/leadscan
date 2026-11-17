import { type Reward, rewardShort, vnd } from "@/lib/partner/content";

const Check = () => <svg className="icon"><use href="#i-check" /></svg>;

/** Hai vai trò trên sàn, mỗi vai trò dẫn sang đúng trang đăng ký. */
export default function Join({ reward: R }: { reward: Reward }) {
  return (
    <section className="section pricing" id="tham-gia">
      <div className="container">
        <div className="section-head reveal">
          <span className="pill-tag">Tham gia sàn</span>
          <h2 className="h-display h2">Bạn là <b>người mua</b> hay <b>đối tác</b>?</h2>
          <p>Một tài khoản dùng được cả hai vai trò. Bắt đầu từ vai trò phù hợp với bạn.</p>
        </div>
        <div className="plans join">
          <div className="plan main reveal" id="thanh-vien">
            <span className="badge">Người mua</span>
            <h3>Thành viên LeadScan</h3>
            <p className="desc">Doanh nghiệp cần tìm khách hàng, đơn hàng, dự án mới.</p>
            <div className="price">89.000đ <small>/năm</small></div>
            <div className="note"><svg className="icon"><use href="#i-info" /></svg><span>Phí năm được cộng đủ thành 89.000 điểm (1 điểm = 1đ) để mua phiếu — không mất thêm khoản nào.</span></div>
            <ul>
              <li><Check />Đăng nhu cầu, được báo khi có cơ hội khớp</li>
              <li><Check />Xem trước tóm tắt và điểm chất lượng miễn phí</li>
              <li><Check />Mua phiếu từ 29.000đ, mỗi phiếu giới hạn số người mua</li>
              <li><Check />Đã mua phiếu vẫn yêu cầu tìm thêm đầu mối được</li>
              <li><Check />Hạng Vàng được mua độc quyền phiếu</li>
            </ul>
            <a href="#dang-ky" className="btn btn-primary">Đăng ký thành viên</a>
            <a href="/co-hoi" className="join-more">Xem cơ hội đang mở</a>
          </div>
          <div className="plan main reveal" id="doi-tac">
            <span className="badge">Đối tác</span>
            <h3>Đối tác LeadScan</h3>
            <p className="desc">Cá nhân, tổ chức biết nhu cầu mua B2B nhưng không trực tiếp bán mặt hàng đó.</p>
            <div className="price">Miễn phí</div>
            <div className="note"><svg className="icon"><use href="#i-info" /></svg><span>{rewardShort(R)}</span></div>
            <ul>
              <li><Check />Đăng cơ hội trong khoảng 2 phút</li>
              <li><Check />Theo dõi trạng thái xác minh và hoa hồng trong ví</li>
              <li><Check />Rút về tài khoản ngân hàng từ {vnd(R.minWithdraw)}</li>
              <li><Check />Không phí tham gia, 1 cấp, không đa cấp</li>
            </ul>
            <a href="/doi-tac#dang-ky" className="btn btn-primary">Đăng ký đối tác</a>
            <a href="/doi-tac" className="join-more">Tìm hiểu chương trình đối tác</a>
          </div>
        </div>
      </div>
    </section>
  );
}
