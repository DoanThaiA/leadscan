// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
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
              <p>Nền tảng scan cơ hội kinh doanh B2B bằng AI: chọn tiêu chí cơ hội, thu thập đa nguồn, làm giàu & chấm điểm, bán phiếu cơ hội theo chất lượng.</p>
              <a href={`${base}#dang-ky`} className="btn btn-primary btn-sm">Đăng ký thành viên</a>
            </div>
            <div><h4>Sản phẩm</h4><ul><li><a href={`${base}#quy-trinh`}>Quy trình</a></li><li><a href={`${base}#phieu-co-hoi`}>Phiếu cơ hội</a></li><li><a href={`${base}#bang-gia`}>Bảng giá</a></li></ul></div>
            <div><h4>Hỗ trợ</h4><ul><li><a href={`${base}#faq`}>Câu hỏi thường gặp</a></li><li><a href="/gioi-thieu">Giới thiệu</a></li><li><a href="/tuyen-dung">Tuyển dụng</a></li><li><a href="#">Hướng dẫn sử dụng</a></li><li><a href="#">Chính sách bảo mật</a></li><li><a href="#">Điều khoản sử dụng</a></li></ul></div>
            <div><h4>Liên hệ</h4><ul className="foot-contact">
              <li><svg className="icon"><use href="#i-globe" /></svg>LeadScanB2B.com</li>
              <li><svg className="icon"><use href="#i-mail" /></svg>contact@leadscanb2b.com</li>
              <li><svg className="icon"><use href="#i-phone" /></svg>Hotline: (cập nhật)</li>
              <li><svg className="icon"><use href="#i-map" /></svg>Địa chỉ: (cập nhật)</li>
            </ul></div>
          </div>
          <div className="foot-bottom"><span>© 2026 LeadScanB2B.com. Bảo lưu mọi quyền.</span><span><a href="#">Bảo mật</a><a href="#">Điều khoản</a></span></div>
        </div>
      </footer>
    </>
  );
}
