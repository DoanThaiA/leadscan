import "../landing.css";
import "./partner-landing.css";

import type { Metadata } from "next";

import Footer from "@/components/landing/Footer";
import IconSprite from "@/components/landing/IconSprite";
import LandingEffects from "@/components/landing/LandingEffects";
import MobileCta from "@/components/landing/MobileCta";
import PartnerHeader from "@/components/partner/PartnerHeader";
import SignupForm from "@/components/partner/SignupForm";
import { ACCEPTED, benefits, faq, GROUPS, howCombined, PROMISES, REJECTED, type Reward, SLOGAN, vnd } from "@/lib/partner/content";
import { getReward } from "@/lib/partner/reward-server";

const TITLE = "Đối tác LeadScan – Thấy cơ hội? Giới thiệu đi. Ít nhất 1 ly cafe.";
const DESC =
  "Bạn thấy cơ hội B2B nhưng không tự bán được? Giới thiệu cho LeadScan: nhận 1 ly cafe cho mỗi cơ hội đạt xác minh và 20% doanh thu mỗi lượt bán phiếu trong 12 tháng. Miễn phí, 1 cấp.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESC,
  alternates: { canonical: "/doi-tac" },
  openGraph: { type: "website", locale: "vi_VN", siteName: "LeadScan B2B", url: "/doi-tac", title: TITLE, description: DESC },
};

const Ic = ({ name }: { name: string }) => <svg className="icon"><use href={`#i-${name}`} /></svg>;

// Ví dụ khối 5: 3 cơ hội đạt chưa bán × ly cafe + 2 cơ hội bán được, mỗi cơ hội 2 lượt × 500.000đ (theo cách cộng đang áp dụng)
const EX = { sent: 10, ok: 5, sold: 2, perSale: 500_000, salesEach: 2 };
/** Đối tác nhận gì từ 1 cơ hội có doanh thu `revenue` (PA2: mức cao hơn; PA1: cộng dồn) */
const earn = (R: Reward, revenue: number) => (R.mode === "sum" ? R.cafe + (R.rate * revenue) / 100 : Math.max(R.cafe, (R.rate * revenue) / 100));

export default async function PartnerLandingPage() {
  const R = await getReward();
  const exUnsold = (EX.ok - EX.sold) * R.cafe;
  const exSold = EX.sold * earn(R, EX.perSale * EX.salesEach);
  const heroTotal = earn(R, 2_000_000);
  return (
    <>
      <IconSprite />
      <PartnerHeader />
      <main id="main">
        {/* 1. Hero */}
        <section className="hero ptl-hero">
          <div className="container ptl-hero-grid">
            <div>
              <span className="pill ptl-pill"><Ic name="spark" /> Chương trình Đối tác LeadScan</span>
              <h1 className="h-display">Thấy cơ hội? Giới thiệu đi. <b>Ít nhất 1 ly cafe.</b></h1>
              <p className="hero-sub">{SLOGAN}</p>
              <div className="hero-cta">
                <a href="#dang-ky" className="btn btn-primary">Đăng ký đối tác <Ic name="arrow" /></a>
                <a href="/doi-tac/dang-nhap" className="btn btn-outline">Đăng nhập đối tác</a>
              </div>
              <div className="hero-chips">
                <span className="pill"><Ic name="check" />Miễn phí tham gia</span>
                <span className="pill"><Ic name="check" />1 cấp, không đa cấp</span>
                <span className="pill"><Ic name="check" />Rút về ngân hàng</span>
              </div>
            </div>
            <div className="ptl-signal" aria-label="Minh hoạ: một cơ hội đối tác gửi đi qua các bước">
              <div className="ptl-signal-hd"><span>Cơ hội của tôi</span><small>minh hoạ</small></div>
              <ol>
                <li className="done"><i /><div><b>Đã gửi</b><span>Nhà máy FDI cần 20.000 thùng carton/tháng · Bắc Ninh</span></div></li>
                <li className="done"><i /><div><b>Đạt xác minh</b><span>Điểm chất lượng 78 · thông tin mới</span></div><em>+{vnd(R.cafe)}</em></li>
                <li className="done"><i /><div><b>Đã xuất bản phiếu</b><span>Ly cafe chuyển sang Khả dụng</span></div></li>
                <li className="live"><i /><div><b>Đã bán 2 lượt × {vnd(1_000_000)}</b><span>{R.rate}% = {vnd((R.rate * 2_000_000) / 100)}{R.mode === "sum" ? ", cộng thêm ngoài ly cafe" : ", đã gồm ly cafe — ghi thêm phần vượt"}</span></div><em>+{vnd(heroTotal - R.cafe)}</em></li>
              </ol>
              <div className="ptl-signal-ft"><span>Tổng nhận</span><b>{vnd(heroTotal)}</b></div>
            </div>
          </div>
        </section>

        {/* 2. Bạn là ai? */}
        <section className="section" id="ban-la-ai">
          <div className="container">
            <div className="section-head reveal">
              <span className="pill-tag">Bạn là ai?</span>
              <h2 className="h-display h2">Bạn tiếp xúc nhu cầu mua hàng mỗi ngày <b>nhưng không bán đúng mặt hàng đó</b></h2>
              <p>Người biết sớm thường không phải người bán được hàng. LeadScan tìm người làm được — bạn nhận phần cảm ơn.</p>
            </div>
            <div className="ptl-groups">
              {GROUPS.map((g) => (
                <div key={g.title} className="aud reveal">
                  <div className="ic"><Ic name={g.icon} /></div>
                  <h3>{g.title}</h3>
                  <p><b>Bạn thấy:</b> {g.sees}</p>
                  <p className="why">{g.why}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 3. 3 bước */}
        <section className="section ptl-steps-sec" id="cach-hoat-dong">
          <div className="container">
            <div className="section-head reveal">
              <span className="pill-tag">Cách hoạt động</span>
              <h2 className="h-display h2">3 bước, <b>bạn chỉ làm bước đầu tiên</b></h2>
            </div>
            <ol className="ptl-steps">
              <li className="reveal"><span className="n">1</span><h3>Gửi cơ hội</h3><p>Điền form trong cổng đối tác: doanh nghiệp/MST, nhu cầu cụ thể, khu vực, nguồn biết tin. Khoảng 2 phút.</p></li>
              <li className="reveal"><span className="n">2</span><h3>LeadScan xác minh & enrich</h3><p>Kiểm tra trùng, AI chấm điểm và người duyệt xác minh trong khoảng 2 ngày làm việc. Bạn theo dõi trạng thái trong cổng.</p></li>
              <li className="reveal"><span className="n">3</span><h3>Nhận cafe + hoa hồng</h3><p>Đạt xác minh: ít nhất 1 ly cafe. Phiếu được bán: {R.rate}% doanh thu mỗi lượt trong {R.months} tháng.</p></li>
            </ol>
          </div>
        </section>

        {/* 4. Quyền lợi */}
        <section className="section" id="quyen-loi">
          <div className="container">
            <div className="section-head reveal">
              <span className="pill-tag">Quyền lợi</span>
              <h2 className="h-display h2">Ít nhất 1 ly cafe. <b>Nhiều hơn khi phiếu bán tốt.</b></h2>
              <p>{howCombined(R)}</p>
            </div>
            <div className="ptl-benefits">
              {benefits(R).map((b) => (
                <div key={b.title} className="ptl-benefit reveal"><div className="ic"><Ic name={b.icon} /></div><div><h3>{b.title}</h3><p>{b.text}</p></div></div>
              ))}
            </div>
          </div>
        </section>

        {/* 5. Ví dụ thu nhập */}
        <section className="section ptl-example-sec">
          <div className="container ptl-example reveal">
            <div>
              <span className="pill-tag">Ví dụ thu nhập</span>
              <h2 className="h-display" style={{ marginTop: 16 }}>Gửi 10 cơ hội, <b>nhận {vnd(exUnsold + exSold)}</b></h2>
              <p className="muted-note">Minh hoạ, không cam kết thu nhập. Thu nhập thực tế phụ thuộc số cơ hội đạt xác minh và số lượt phiếu được bán.</p>
            </div>
            <div className="ptl-calc">
              <div className="row"><span>Cơ hội gửi</span><b>{EX.sent}</b></div>
              <div className="row"><span>Đạt xác minh</span><b>{EX.ok}</b></div>
              <div className="row"><span>{EX.ok - EX.sold} cơ hội đạt, chưa bán × {vnd(R.cafe)}</span><b>{vnd(exUnsold)}</b></div>
              <div className="row"><span>{EX.sold} cơ hội bán được, mỗi cơ hội {EX.salesEach} lượt × {vnd(EX.perSale)} × {R.rate}%{R.mode === "sum" ? " + ly cafe" : ""}</span><b>{vnd(exSold)}</b></div>
              <div className="row total"><span>Tổng nhận</span><b>{vnd(exUnsold + exSold)}</b></div>
            </div>
          </div>
        </section>

        {/* 6. Cơ hội thế nào được nhận */}
        <section className="section" id="co-hoi-duoc-nhan">
          <div className="container">
            <div className="section-head reveal">
              <span className="pill-tag">Cơ hội thế nào được nhận</span>
              <h2 className="h-display h2">Thông tin cơ hội kinh doanh, <b>không phải dữ liệu cá nhân</b></h2>
            </div>
            <div className="ptl-accept">
              <div className="reveal yes"><h3><Ic name="check" /> Được nhận</h3><ul>{ACCEPTED.map((x) => <li key={x}>{x}</li>)}</ul></div>
              <div className="reveal no"><h3><Ic name="info" /> Không nhận</h3><ul>{REJECTED.map((x) => <li key={x}>{x}</li>)}</ul></div>
            </div>
          </div>
        </section>

        {/* 7. Cam kết */}
        <section className="section ptl-promise-sec">
          <div className="container">
            <div className="ptl-promises">
              {PROMISES.map((p) => (
                <div key={p.title} className="reveal"><div className="ic"><Ic name={p.icon} /></div><h3>{p.title}</h3><p>{p.text}</p></div>
              ))}
            </div>
          </div>
        </section>

        {/* 8. Form đăng ký */}
        <section className="section register" id="dang-ky">
          <div className="container reg-grid">
            <div className="reg-side reveal">
              <span className="pill-tag">Đăng ký đối tác</span>
              <h2 className="h-display" style={{ marginTop: 16 }}>Đăng ký <b>trong khoảng 1 phút</b></h2>
              <p>Chỉ cần thông tin liên hệ. CCCD, mã số thuế cá nhân và tài khoản ngân hàng chỉ cần khi bạn rút tiền lần đầu.</p>
              <ol className="reg-next">
                <li><b>Đăng ký</b>Điền form đăng ký, khoảng 1 phút.</li>
                <li><b>Xác thực email</b>Nhập mã OTP gửi tới email để kích hoạt tài khoản.</li>
                <li><b>Gửi cơ hội đầu tiên</b>Trong cổng đối tác, theo dõi trạng thái và số dư theo thời gian thực.</li>
              </ol>
              <p className="ptl-login-hint">Đã có tài khoản? <a href="/doi-tac/dang-nhap">Đăng nhập cổng đối tác</a></p>
            </div>
            <div className="form-card reveal">
              <SignupForm />
            </div>
          </div>
        </section>

        {/* 9. Hỏi đáp */}
        <section className="section" id="hoi-dap">
          <div className="container">
            <div className="section-head reveal">
              <h2 className="h-display h2">Câu hỏi <b>thường gặp</b></h2>
            </div>
            <div className="faq reveal">
              {faq(R).map((f, i) => (
                <details key={f.q} open={i === 0}>
                  <summary>{f.q}<svg className="icon"><use href="#i-plus" /></svg></summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Footer base="/" />
      <MobileCta small="Mỗi cơ hội đạt xác minh" value="Ít nhất 1 ly cafe" label="Đăng ký đối tác" />
      <LandingEffects />
    </>
  );
}
