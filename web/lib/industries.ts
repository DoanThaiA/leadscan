/**
 * Trang cơ hội theo ngành (/co-hoi/nganh/<slug>) — nội dung riêng cho từng ngành để Google có trang đích đúng từ khoá
 * ("nhu cầu mua bao bì", "doanh nghiệp cần mua linh kiện điện tử"…). `name` phải khớp đúng INDUSTRIES ở backend
 * (app/registration_form.py) vì API lọc theo chuỗi này.
 */

export interface IndustryPage {
  slug: string;
  name: string; // giá trị ngành trong API
  keyword: string; // cụm từ khoá chính, dùng trong H1 / title
  intro: string;
  needs: string[]; // loại nhu cầu thường gặp
  sellers: string; // ai nên theo dõi trang này
}

export const INDUSTRY_PAGES: IndustryPage[] = [
  {
    slug: "san-xuat-cong-nghiep", name: "Sản xuất công nghiệp", keyword: "nhu cầu mua hàng của nhà máy sản xuất",
    intro: "Nhà máy mới khởi công, mở rộng dây chuyền hay đổi nhà cung cấp đều phát sinh nhu cầu mua lớn và lặp lại. LeadScan tổng hợp những nhu cầu này, xác minh doanh nghiệp đứng sau và chấm điểm trước khi mở bán.",
    needs: ["Vật tư tiêu hao, phụ tùng thay thế cho dây chuyền", "Thiết bị, máy móc cho xưởng mới hoặc mở rộng", "Dịch vụ bảo trì, lắp đặt, cải tạo nhà xưởng", "Nhà cung cấp thay thế khi đơn vị cũ không đáp ứng"],
    sellers: "Nhà cung cấp vật tư công nghiệp, thiết bị, dịch vụ kỹ thuật cho nhà máy.",
  },
  {
    slug: "bao-bi-in-an", name: "Bao bì & in ấn", keyword: "nhu cầu mua bao bì, in ấn",
    intro: "Mỗi nhà máy, thương hiệu thực phẩm hay đơn vị xuất khẩu đều cần bao bì đều đặn: thùng carton, túi, nhãn, hộp in. Cơ hội trên LeadScan cho biết ai đang cần, số lượng bao nhiêu và cần từ khi nào.",
    needs: ["Thùng carton 3–5 lớp theo tháng cho nhà máy", "Túi nhựa, màng PE/OPP, bao jumbo", "Nhãn mác, tem, hộp giấy in offset", "Khay nhựa, vật tư đóng gói chống tĩnh điện"],
    sellers: "Xưởng bao bì carton, nhựa, nhà in, đơn vị cung cấp vật tư đóng gói.",
  },
  {
    slug: "nhua-cao-su", name: "Nhựa & cao su", keyword: "nhu cầu mua sản phẩm nhựa, cao su",
    intro: "Nhựa và cao su là đầu vào của hàng loạt ngành từ điện tử, ô tô đến gia dụng. LeadScan tìm doanh nghiệp đang cần linh kiện ép phun, hạt nhựa hay sản phẩm cao su kỹ thuật.",
    needs: ["Linh kiện nhựa ép phun theo khuôn", "Hạt nhựa nguyên sinh, tái sinh", "Gioăng, đệm, sản phẩm cao su kỹ thuật", "Gia công khuôn mẫu"],
    sellers: "Xưởng ép nhựa, nhà phân phối hạt nhựa, nhà sản xuất cao su kỹ thuật.",
  },
  {
    slug: "dien-tu-linh-kien", name: "Điện tử & linh kiện", keyword: "nhu cầu mua linh kiện điện tử",
    intro: "Làn sóng nhà máy điện tử FDI ở Bắc Ninh, Bắc Giang, Thái Nguyên, Hải Phòng kéo theo nhu cầu lớn về linh kiện, vật tư phụ trợ và dịch vụ. LeadScan theo dõi các nhà máy mới và nhu cầu tìm nhà cung cấp nội địa.",
    needs: ["Linh kiện, cáp, đầu nối, bo mạch", "Vật tư phòng sạch, chống tĩnh điện", "Gia công cơ khí chính xác, đồ gá", "Nhà cung cấp nội địa hoá cho nhà máy FDI"],
    sellers: "Nhà cung cấp linh kiện, vật tư phụ trợ ngành điện tử, gia công chính xác.",
  },
  {
    slug: "co-khi-may-moc", name: "Cơ khí & máy móc", keyword: "nhu cầu mua máy móc, gia công cơ khí",
    intro: "Doanh nghiệp đầu tư dây chuyền, xây xưởng hay cần gia công chi tiết đều tìm đối tác cơ khí đáng tin. Cơ hội trên LeadScan nêu rõ hạng mục, quy mô và thời điểm cần.",
    needs: ["Máy móc, thiết bị cho dây chuyền mới", "Gia công chi tiết, kết cấu thép", "Băng tải, hệ thống tự động hoá", "Bảo trì, sửa chữa, phụ tùng máy"],
    sellers: "Xưởng cơ khí, nhà phân phối máy móc, đơn vị tự động hoá.",
  },
  {
    slug: "hoa-chat-vat-tu", name: "Hoá chất & vật tư", keyword: "nhu cầu mua hoá chất, vật tư công nghiệp",
    intro: "Hoá chất, dung môi, dầu mỡ và vật tư công nghiệp là nhu cầu thường xuyên của nhà máy. LeadScan kết nối bạn với doanh nghiệp đang tìm nguồn cung ổn định.",
    needs: ["Hoá chất xử lý nước, xử lý bề mặt", "Dầu mỡ bôi trơn công nghiệp", "Sơn, keo, dung môi", "Vật tư an toàn lao động, bảo hộ"],
    sellers: "Nhà phân phối hoá chất, dầu nhớt, vật tư tiêu hao công nghiệp.",
  },
  {
    slug: "det-may-da-giay", name: "Dệt may & da giày", keyword: "nhu cầu mua nguyên phụ liệu dệt may, da giày",
    intro: "Nhà máy may mặc, da giày cần nguyên phụ liệu và dịch vụ theo mùa đơn hàng. LeadScan tìm các nhu cầu mua vải, phụ liệu, gia công và thiết bị ngành.",
    needs: ["Vải, chỉ, phụ liệu may", "Gia công may, in thêu", "Da, đế, phụ liệu giày", "Máy may công nghiệp, thiết bị hoàn tất"],
    sellers: "Nhà cung cấp nguyên phụ liệu, xưởng gia công, thiết bị dệt may.",
  },
  {
    slug: "xuat-nhap-khau", name: "Xuất nhập khẩu", keyword: "cơ hội xuất nhập khẩu, đơn hàng quốc tế",
    intro: "Nhu cầu mua từ đối tác nước ngoài và doanh nghiệp xuất khẩu cần nguồn hàng là những cơ hội giá trị lớn. LeadScan xác minh nguồn tin trước khi mở bán.",
    needs: ["Đơn hàng xuất khẩu tìm nhà sản xuất Việt Nam", "Nguồn hàng cho doanh nghiệp xuất khẩu", "Dịch vụ thủ tục hải quan, kiểm định", "Nhà nhập khẩu tìm phân phối"],
    sellers: "Nhà sản xuất có năng lực xuất khẩu, công ty thương mại, dịch vụ XNK.",
  },
  {
    slug: "thuong-mai-phan-phoi", name: "Thương mại & phân phối", keyword: "nhu cầu tìm nhà phân phối, nguồn hàng",
    intro: "Chuỗi bán lẻ, đại lý và nhà phân phối luôn tìm nguồn hàng mới hoặc đối tác phân phối khu vực. Cơ hội trên LeadScan giúp bạn gặp đúng bên đang cần.",
    needs: ["Chuỗi bán lẻ tìm nhà cung cấp", "Nhãn hàng tìm nhà phân phối khu vực", "Đại lý tìm nguồn hàng ổn định", "Thiết bị, vật dụng cho cửa hàng, siêu thị"],
    sellers: "Nhà sản xuất, nhà phân phối, đơn vị cung ứng cho bán lẻ.",
  },
  {
    slug: "logistics-van-tai", name: "Logistics & vận tải", keyword: "nhu cầu thuê vận tải, kho bãi, logistics",
    intro: "Nhà máy mới, tuyến hàng mới hay kho vừa thuê đều cần đối tác vận chuyển và kho bãi. LeadScan nắm các nhu cầu này sớm, trước khi doanh nghiệp chốt nhà cung cấp.",
    needs: ["Vận tải hàng hoá theo tuyến cố định", "Thuê kho, dịch vụ kho bãi", "Forwarding, vận tải quốc tế", "Xe nâng, giá kệ, thiết bị kho"],
    sellers: "Doanh nghiệp vận tải, kho bãi, forwarder, thiết bị kho.",
  },
  {
    slug: "xay-dung-vat-lieu", name: "Xây dựng & vật liệu", keyword: "dự án xây dựng, nhu cầu vật liệu xây dựng",
    intro: "Nhà xưởng, khu công nghiệp, công trình mới là nguồn cơ hội lớn cho nhà thầu và nhà cung cấp vật liệu. LeadScan tổng hợp dự án, gói thầu và nhu cầu vật tư đã được kiểm chứng.",
    needs: ["Xây dựng nhà xưởng, nhà kho", "Thép, xi măng, vật liệu hoàn thiện", "Cơ điện (M&E), PCCC", "Gói thầu, dự án đầu tư mới"],
    sellers: "Nhà thầu xây dựng, M&E, nhà cung cấp vật liệu xây dựng.",
  },
  {
    slug: "thuc-pham-do-uong", name: "Thực phẩm & đồ uống", keyword: "nhu cầu mua nguyên liệu thực phẩm, đồ uống",
    intro: "Nhà máy thực phẩm, chuỗi F&B và bếp ăn công nghiệp cần nguyên liệu, bao bì và dịch vụ ổn định. LeadScan tìm các nhu cầu mua đang mở trong ngành.",
    needs: ["Nguyên liệu, phụ gia thực phẩm", "Suất ăn, bếp ăn công nghiệp", "Bao bì thực phẩm, chai lọ", "Thiết bị chế biến, kho lạnh"],
    sellers: "Nhà cung cấp nguyên liệu, suất ăn công nghiệp, thiết bị chế biến.",
  },
  {
    slug: "nong-san-thuy-san", name: "Nông sản & thuỷ sản", keyword: "nhu cầu mua nông sản, thuỷ sản",
    intro: "Doanh nghiệp chế biến, xuất khẩu và thu mua nông thuỷ sản luôn tìm vùng nguyên liệu và vật tư đầu vào. LeadScan đưa các nhu cầu mua đã xác minh tới đúng người cung cấp.",
    needs: ["Thu mua nông sản theo vùng, theo vụ", "Thuỷ sản nguyên liệu cho chế biến", "Vật tư nông nghiệp: túi trồng, phân bón, giống", "Dịch vụ sơ chế, bảo quản lạnh"],
    sellers: "Hợp tác xã, nhà cung cấp nông thuỷ sản, vật tư nông nghiệp.",
  },
  {
    slug: "dich-vu-b2b", name: "Dịch vụ B2B", keyword: "doanh nghiệp đang cần dịch vụ B2B",
    intro: "Doanh nghiệp mới thành lập, nhà máy FDI mới vào hay công ty mở rộng đều cần loạt dịch vụ: kế toán, nhân sự, vệ sinh, bảo vệ, đào tạo… LeadScan tìm những nhu cầu này cho nhà cung cấp dịch vụ.",
    needs: ["Kế toán, pháp lý, tư vấn thành lập", "Cung ứng nhân sự, đào tạo", "Vệ sinh công nghiệp, bảo vệ, suất ăn", "Marketing, sự kiện, quà tặng doanh nghiệp"],
    sellers: "Công ty dịch vụ doanh nghiệp, cung ứng nhân sự, tư vấn.",
  },
  {
    slug: "cong-nghe-thong-tin", name: "Công nghệ thông tin", keyword: "doanh nghiệp đang cần giải pháp công nghệ, phần mềm",
    intro: "Chuyển đổi số tạo nhu cầu lớn về phần mềm, hạ tầng và an ninh mạng. Cơ hội trên LeadScan cho biết doanh nghiệp nào đang tìm giải pháp, quy mô và thời điểm triển khai.",
    needs: ["Phần mềm ERP, CRM, quản lý sản xuất", "Hạ tầng mạng, máy chủ, camera", "Bảo mật, an ninh mạng", "Thiết bị CNTT cho văn phòng, nhà máy mới"],
    sellers: "Công ty phần mềm, tích hợp hệ thống, nhà cung cấp thiết bị CNTT.",
  },
];

export const industryBySlug = (slug: string) => INDUSTRY_PAGES.find((x) => x.slug === slug);
export const industryByName = (name: string) => INDUSTRY_PAGES.find((x) => x.name === name);
export const industryHref = (name: string) => {
  const p = industryByName(name);
  return p ? `/co-hoi/nganh/${p.slug}` : `/co-hoi?nganh=${encodeURIComponent(name)}`;
};
