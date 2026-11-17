/**
 * Trang cơ hội theo khu vực (/co-hoi/khu-vuc/<slug>): 3 miền + các tỉnh/thành công nghiệp chính.
 * `terms` gửi lên API (tham số places, ngăn bằng "|"): khớp đúng miền, hoặc tên tỉnh nằm trong địa chỉ nhập tự do.
 * Tên tỉnh theo cách doanh nghiệp vẫn gọi các khu công nghiệp (kể cả sau sáp nhập tỉnh 2025) để bắt đúng từ khoá tìm kiếm.
 */

export interface AreaPage {
  slug: string;
  name: string;
  kind: "region" | "province";
  terms: string[];
  intro: string;
  hubs: string[]; // khu công nghiệp / trung tâm kinh tế tiêu biểu
  sectors: string; // ngành nổi bật
}

const NORTH = ["Hà Nội", "Hải Phòng", "Bắc Ninh", "Bắc Giang", "Hải Dương", "Hưng Yên", "Vĩnh Phúc", "Thái Nguyên", "Quảng Ninh", "Phú Thọ", "Thái Bình", "Nam Định", "Ninh Bình", "Hà Nam"];
const CENTRAL = ["Đà Nẵng", "Quảng Nam", "Quảng Ngãi", "Bình Định", "Khánh Hòa", "Khánh Hoà", "Thanh Hóa", "Thanh Hoá", "Nghệ An", "Hà Tĩnh", "Huế", "Quảng Trị", "Quảng Bình"];
const SOUTH = ["Hồ Chí Minh", "HCM", "Sài Gòn", "Bình Dương", "Đồng Nai", "Long An", "Bà Rịa", "Vũng Tàu", "Tây Ninh", "Bình Phước", "Cần Thơ", "An Giang", "Đồng Tháp", "Tiền Giang", "Vĩnh Long", "Bến Tre"];

export const AREA_PAGES: AreaPage[] = [
  {
    slug: "mien-bac", name: "Miền Bắc", kind: "region", terms: ["Miền Bắc", ...NORTH],
    intro: "Miền Bắc là trung tâm của làn sóng nhà máy điện tử, linh kiện và công nghiệp phụ trợ, với cụm Hà Nội – Bắc Ninh – Bắc Giang – Hải Phòng – Thái Nguyên. Nhà máy mới, mở rộng và nội địa hoá chuỗi cung ứng tạo nhu cầu mua liên tục.",
    hubs: ["Hà Nội, Bắc Ninh, Bắc Giang", "Hải Phòng, Hải Dương, Hưng Yên", "Thái Nguyên, Vĩnh Phúc, Quảng Ninh"],
    sectors: "Điện tử & linh kiện, cơ khí, bao bì, logistics, xây dựng nhà xưởng.",
  },
  {
    slug: "mien-trung", name: "Miền Trung", kind: "region", terms: ["Miền Trung", ...CENTRAL],
    intro: "Miền Trung có các khu kinh tế ven biển, cảng biển và vùng nguyên liệu lớn. Dự án hạ tầng, du lịch, chế biến nông thuỷ sản và công nghiệp nặng là nguồn cơ hội đáng chú ý.",
    hubs: ["Đà Nẵng, Quảng Nam", "Quảng Ngãi (Dung Quất), Bình Định", "Thanh Hoá, Nghệ An, Hà Tĩnh"],
    sectors: "Xây dựng & vật liệu, nông thuỷ sản, thực phẩm, logistics cảng biển.",
  },
  {
    slug: "mien-nam", name: "Miền Nam", kind: "region", terms: ["Miền Nam", ...SOUTH],
    intro: "Miền Nam, với TP. Hồ Chí Minh và vành đai công nghiệp Bình Dương – Đồng Nai – Long An – Bà Rịa-Vũng Tàu, tập trung đông doanh nghiệp sản xuất, xuất khẩu và phân phối nhất cả nước.",
    hubs: ["TP. Hồ Chí Minh", "Bình Dương, Đồng Nai", "Long An, Bà Rịa-Vũng Tàu, Cần Thơ"],
    sectors: "Sản xuất công nghiệp, dệt may & da giày, nhựa, thực phẩm, xuất nhập khẩu, phân phối.",
  },
  {
    slug: "ha-noi", name: "Hà Nội", kind: "province", terms: ["Hà Nội"],
    intro: "Thủ đô tập trung trụ sở doanh nghiệp, cơ quan, dự án hạ tầng và các khu công nghiệp vành đai. Nhu cầu mua đa dạng từ dịch vụ B2B, công nghệ đến thiết bị và vật tư.",
    hubs: ["KCN Thăng Long, Quang Minh, Nội Bài", "Khu công nghệ cao Hoà Lạc"], sectors: "Dịch vụ B2B, công nghệ thông tin, xây dựng, điện tử, thương mại.",
  },
  {
    slug: "tp-ho-chi-minh", name: "TP. Hồ Chí Minh", kind: "province", terms: ["Hồ Chí Minh", "HCM", "Sài Gòn"],
    intro: "Trung tâm kinh tế lớn nhất cả nước, nơi đặt văn phòng của phần lớn doanh nghiệp FDI và tập đoàn phân phối. Cơ hội trải từ sản xuất, xuất nhập khẩu đến dịch vụ doanh nghiệp.",
    hubs: ["KCX Tân Thuận, KCN Hiệp Phước", "Khu công nghệ cao TP.HCM"], sectors: "Thương mại & phân phối, xuất nhập khẩu, dịch vụ B2B, công nghệ, thực phẩm.",
  },
  {
    slug: "hai-phong", name: "Hải Phòng", kind: "province", terms: ["Hải Phòng"],
    intro: "Thành phố cảng với hệ thống khu công nghiệp thu hút nhiều nhà máy FDI quy mô lớn. Nhu cầu logistics, vật tư công nghiệp và dịch vụ cho nhà máy luôn cao.",
    hubs: ["KCN Đình Vũ, Tràng Duệ, DEEP C", "Cảng Lạch Huyện"], sectors: "Điện tử, logistics & vận tải, cơ khí, hoá chất, xây dựng.",
  },
  {
    slug: "bac-ninh", name: "Bắc Ninh", kind: "province", terms: ["Bắc Ninh"],
    intro: "Thủ phủ điện tử của miền Bắc với hàng trăm nhà máy FDI. Nhà máy mới và mở rộng dây chuyền liên tục cần linh kiện, bao bì, vật tư phòng sạch và dịch vụ hỗ trợ.",
    hubs: ["KCN Yên Phong, Quế Võ, VSIP Bắc Ninh", "KCN Tiên Sơn, Thuận Thành"], sectors: "Điện tử & linh kiện, bao bì, nhựa, cơ khí chính xác, logistics.",
  },
  {
    slug: "bac-giang", name: "Bắc Giang", kind: "province", terms: ["Bắc Giang"],
    intro: "Điểm đến mới của các nhà máy điện tử và linh kiện, nhiều dự án đang xây dựng và mở rộng. Đây là thời điểm nhà cung cấp tiếp cận sớm trước khi chuỗi cung ứng định hình.",
    hubs: ["KCN Quang Châu, Vân Trung, Đình Trám", "KCN Song Khê – Nội Hoàng"], sectors: "Điện tử & linh kiện, xây dựng nhà xưởng, dệt may, logistics.",
  },
  {
    slug: "hai-duong", name: "Hải Dương", kind: "province", terms: ["Hải Dương"],
    intro: "Nằm giữa Hà Nội và Hải Phòng, Hải Dương có nhiều khu công nghiệp phục vụ sản xuất linh kiện, dệt may và cơ khí, kết nối thuận tiện tới cảng biển.",
    hubs: ["KCN Đại An, Nam Sách, Phúc Điền", "KCN Lai Vu, Tân Trường"], sectors: "Cơ khí, dệt may, điện tử, vật liệu xây dựng.",
  },
  {
    slug: "hung-yen", name: "Hưng Yên", kind: "province", terms: ["Hưng Yên"],
    intro: "Cửa ngõ phía đông Hà Nội với các khu công nghiệp lớn của nhà đầu tư Nhật Bản, Hàn Quốc. Nhu cầu về vật tư, linh kiện và dịch vụ cho nhà máy ổn định.",
    hubs: ["KCN Phố Nối A, Thăng Long II", "KCN Minh Đức, Yên Mỹ"], sectors: "Cơ khí, điện tử, thực phẩm, nhựa, logistics.",
  },
  {
    slug: "vinh-phuc", name: "Vĩnh Phúc", kind: "province", terms: ["Vĩnh Phúc"],
    intro: "Trung tâm công nghiệp ô tô, xe máy và linh kiện phía tây bắc Hà Nội. Các nhà máy lắp ráp và nhà cung cấp phụ trợ tạo nhu cầu mua vật tư, gia công thường xuyên.",
    hubs: ["KCN Bình Xuyên, Khai Quang", "KCN Bá Thiện"], sectors: "Cơ khí, linh kiện ô tô – xe máy, điện tử, nhựa.",
  },
  {
    slug: "thai-nguyen", name: "Thái Nguyên", kind: "province", terms: ["Thái Nguyên"],
    intro: "Nơi đặt các tổ hợp sản xuất điện tử lớn, kéo theo mạng lưới nhà cung cấp linh kiện, vật tư và dịch vụ cho người lao động.",
    hubs: ["KCN Yên Bình", "KCN Điềm Thuỵ, Sông Công"], sectors: "Điện tử & linh kiện, cơ khí, dịch vụ B2B, xây dựng.",
  },
  {
    slug: "quang-ninh", name: "Quảng Ninh", kind: "province", terms: ["Quảng Ninh"],
    intro: "Tỉnh có cảng biển, khu kinh tế cửa khẩu và nhiều dự án hạ tầng, du lịch. Cơ hội tập trung ở logistics, xây dựng và các khu công nghiệp mới.",
    hubs: ["KCN Đông Mai, Việt Hưng", "Khu kinh tế Vân Đồn, cảng Cái Lân"], sectors: "Logistics, xây dựng & vật liệu, năng lượng, du lịch – dịch vụ.",
  },
  {
    slug: "da-nang", name: "Đà Nẵng", kind: "province", terms: ["Đà Nẵng"],
    intro: "Trung tâm kinh tế miền Trung với cảng biển, sân bay quốc tế và khu công nghệ cao. Cơ hội trải từ công nghệ, du lịch – dịch vụ đến sản xuất.",
    hubs: ["KCN Hoà Khánh, Liên Chiểu", "Khu công nghệ cao Đà Nẵng"], sectors: "Công nghệ thông tin, dịch vụ B2B, xây dựng, thực phẩm, logistics.",
  },
  {
    slug: "binh-duong", name: "Bình Dương", kind: "province", terms: ["Bình Dương"],
    intro: "Một trong những vùng công nghiệp sôi động nhất cả nước, dày đặc nhà máy sản xuất và xuất khẩu. Nhu cầu bao bì, vật tư, máy móc và logistics rất lớn.",
    hubs: ["KCN VSIP, Mỹ Phước, Bàu Bàng", "KCN Sóng Thần, Việt Hương"], sectors: "Sản xuất công nghiệp, đồ gỗ, nhựa, bao bì, dệt may, logistics.",
  },
  {
    slug: "dong-nai", name: "Đồng Nai", kind: "province", terms: ["Đồng Nai"],
    intro: "Vùng công nghiệp lâu đời với nhiều khu công nghiệp lớn, gắn với cảng hàng không Long Thành. Doanh nghiệp sản xuất và xuất khẩu liên tục tìm nhà cung cấp mới.",
    hubs: ["KCN Biên Hoà, Amata, Long Thành", "KCN Nhơn Trạch"], sectors: "Sản xuất công nghiệp, hoá chất, dệt may & da giày, cơ khí, logistics.",
  },
  {
    slug: "long-an", name: "Long An", kind: "province", terms: ["Long An"],
    intro: "Cửa ngõ miền Tây giáp TP. Hồ Chí Minh, thu hút nhiều nhà máy và kho vận mới. Nông sản, thực phẩm và sản xuất là các nhóm cơ hội nổi bật.",
    hubs: ["KCN Đức Hoà, Tân Đức, Long Hậu", "KCN Phúc Long"], sectors: "Sản xuất, thực phẩm, nông sản, logistics & kho bãi.",
  },
  {
    slug: "ba-ria-vung-tau", name: "Bà Rịa - Vũng Tàu", kind: "province", terms: ["Bà Rịa", "Vũng Tàu"],
    intro: "Trung tâm cảng nước sâu, dầu khí và công nghiệp nặng phía Nam. Cơ hội tập trung ở logistics cảng, hoá chất, thép và dịch vụ công nghiệp.",
    hubs: ["Cảng Cái Mép – Thị Vải", "KCN Phú Mỹ"], sectors: "Logistics cảng biển, hoá chất, thép, năng lượng, xây dựng.",
  },
  {
    slug: "can-tho", name: "Cần Thơ", kind: "province", terms: ["Cần Thơ"],
    intro: "Trung tâm của Đồng bằng sông Cửu Long, đầu mối nông sản, thuỷ sản và chế biến thực phẩm. Doanh nghiệp thu mua, chế biến và xuất khẩu là nguồn cơ hội chính.",
    hubs: ["KCN Trà Nóc, Hưng Phú"], sectors: "Nông sản & thuỷ sản, thực phẩm, logistics, vật tư nông nghiệp.",
  },
];

/** Tỉnh/thành → miền (slug). Trang cẩm nang của tỉnh gom cả bài cấp miền; trang miền chỉ gom bài của miền. */
const REGION_OF: Record<string, string> = {
  "ha-noi": "mien-bac", "hai-phong": "mien-bac", "bac-ninh": "mien-bac", "bac-giang": "mien-bac", "hai-duong": "mien-bac",
  "hung-yen": "mien-bac", "vinh-phuc": "mien-bac", "thai-nguyen": "mien-bac", "quang-ninh": "mien-bac",
  "da-nang": "mien-trung",
  "tp-ho-chi-minh": "mien-nam", "binh-duong": "mien-nam", "dong-nai": "mien-nam", "long-an": "mien-nam", "ba-ria-vung-tau": "mien-nam", "can-tho": "mien-nam",
};
export const regionOf = (slug: string): string => REGION_OF[slug] ?? "";
/** Các slug khu vực mà bài cẩm nang có thể gắn để hiện trên trang của khu vực này (chính nó + miền của nó) */
export const articleAreasFor = (slug: string): string[] => [slug, regionOf(slug)].filter(Boolean);

export const areaBySlug = (slug: string) => AREA_PAGES.find((x) => x.slug === slug);
export const areaByName = (name: string) => AREA_PAGES.find((x) => x.name === name);
/** Trang khu vực cho 1 giá trị tỉnh (nhập tự do): tỉnh khớp trước, rồi tới miền */
export function areaForProvince(province: string, region = ""): AreaPage | undefined {
  const p = province.trim();
  if (p) {
    const hit = AREA_PAGES.find((x) => x.kind === "province" && x.terms.some((t) => p.includes(t)));
    if (hit) return hit;
  }
  return region ? areaByName(region) : undefined;
}
