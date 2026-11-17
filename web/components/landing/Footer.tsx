import { Logo } from "@/components/brand/Logo";

/** base: tiền tố cho link neo khi dùng ngoài trang chủ (vd "/"). */
export default function Footer({ base = "" }: { base?: string }) {
  return (
    <>
      <footer id="lien-he">
        <div className="container">
          <div className="foot-grid">
            <div>
              <a href={base || "#top"} className="logo" aria-label={base ? "LeadScan – trang chủ" : "LeadScan – về đầu trang"}><Logo height={30} /></a>
              <p>Sàn cơ hội kinh doanh B2B: người mua đăng nhu cầu, đối tác đăng cơ hội, LeadScan kiểm duyệt, chấm điểm và kết nối hai bên.</p>
              <a href={`${base}#dang-ky`} className="btn btn-primary btn-sm">Đăng ký thành viên</a>
            </div>
            <div><h4>Sàn LeadScan</h4><ul><li><a href={`${base}#cach-hoat-dong`}>Cách hoạt động</a></li><li><a href="/co-hoi">Cơ hội đang mở</a></li><li><a href={`${base}#dang-ky`}>Đăng ký thành viên</a></li><li><a href="/doi-tac">Đăng ký đối tác</a></li></ul></div>
            <div><h4>Hỗ trợ</h4><ul><li><a href={`${base}#faq`}>Câu hỏi thường gặp</a></li><li><a href="/gioi-thieu">Giới thiệu</a></li><li><a href="/tuyen-dung">Tuyển dụng</a></li><li><a href="#">Hướng dẫn sử dụng</a></li><li><a href="#">Chính sách bảo mật</a></li><li><a href="#">Điều khoản sử dụng</a></li></ul></div>
            <div><h4>Liên hệ</h4><ul className="foot-contact">
              <li><svg className="icon"><use href="#i-globe" /></svg><a href="https://leadscan.net">leadscan.net</a></li>
              <li><svg className="icon"><use href="#i-mail" /></svg><a href="mailto:contact@leadscan.net">contact@leadscan.net</a></li>
              <li><svg className="icon"><use href="#i-phone" /></svg><a href="tel:+84877770788">Hotline: +848 7777 0788</a></li>
              <li><svg className="icon"><use href="#i-map" /></svg>Địa chỉ: (cập nhật)</li>
            </ul></div>
          </div>
          <div className="foot-bottom"><span>© 2026 leadscan.net. Bảo lưu mọi quyền.</span><span><a href="#">Bảo mật</a><a href="#">Điều khoản</a></span></div>
        </div>
      </footer>
    </>
  );
}
