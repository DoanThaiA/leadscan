// Chuyển từ landing HTML gốc; sửa trực tiếp tại đây.
import { Logo } from "@/components/brand/Logo";

export default function Footer() {
  return (
    <>
      <footer id="lien-he">
        <div className="container">
          <div className="foot-grid">
            <div>
              <a href="#top" className="logo" aria-label="LeadScan – về đầu trang"><Logo height={30} /></a>
              <p>Nền tảng scan cơ hội kinh doanh B2B bằng AI: khảo sát nhu cầu, thu thập đa nguồn, làm giàu & chấm điểm, bán phiếu cơ hội theo chất lượng.</p>
              <a href="#dang-ky" className="btn btn-primary btn-sm">Đăng ký thành viên</a>
            </div>
            <div><h4>Sản phẩm</h4><ul><li><a href="#quy-trinh">Quy trình</a></li><li><a href="#phieu-co-hoi">Phiếu cơ hội</a></li><li><a href="#bang-gia">Bảng giá</a></li></ul></div>
            <div><h4>Hỗ trợ</h4><ul><li><a href="#faq">Câu hỏi thường gặp</a></li><li><a href="#">Hướng dẫn sử dụng</a></li><li><a href="#">Chính sách bảo mật</a></li><li><a href="#">Điều khoản sử dụng</a></li></ul></div>
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
