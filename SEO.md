# SEO cho LeadScan.net

Tài liệu này gồm 2 phần: những gì **đã có trong code**, và những việc **bạn cần tự làm** (Google Search Console, nội dung, liên kết) để LeadScan lên Google và hiện đẹp trong kết quả tìm kiếm.

---

## 1. Đã làm trong code

| Hạng mục | Chi tiết | File |
|---|---|---|
| `robots.txt` | Cho Google đọc trang công khai; chặn `/admin`, `/thanh-vien`, `/api/`. Trỏ tới sitemap. | `web/app/robots.ts` |
| `sitemap.xml` | Trang chủ, `/co-hoi`, `/doi-tac`, `/gioi-thieu`, `/tuyen-dung` + **từng cơ hội đang mở bán** + **từng vị trí tuyển dụng** (lấy từ API mỗi lần Google đọc). | `web/app/sitemap.ts` |
| Title / description / canonical | Mỗi trang công khai có title, mô tả, canonical riêng. Canonical không còn đặt ở layout gốc (tránh trang con bị trỏ nhầm về trang chủ). Trang chủ: “LeadScan – Sàn cơ hội B2B, tìm khách hàng doanh nghiệp đang cần mua”. | `web/app/**/page.tsx`, `web/app/layout.tsx` |
| Tên trang & logo trên Google | JSON-LD `Organization` (logo, liên hệ, MCV Network) + `WebSite` (tên “LeadScan”, tên khác “LeadScan B2B”, “LeadScan.net”). | `web/lib/seo.ts`, `web/app/page.tsx` |
| Breadcrumb | JSON-LD `BreadcrumbList` ở chi tiết cơ hội, chi tiết tuyển dụng, trang đối tác → Google hiện “leadscan.net › Cơ hội › …” thay vì URL dài. | `web/app/co-hoi/[code]`, `web/app/tuyen-dung/[slug]`, `web/app/doi-tac` |
| Hỏi đáp | JSON-LD `FAQPage` ở trang chủ và `/doi-tac` (giúp Google / AI Overviews hiểu nội dung; xem lưu ý ở mục 3). | như trên |
| Tuyển dụng | JSON-LD `JobPosting` (đã có từ trước) → tin tuyển dụng có thể hiện trong **Google Việc làm**. | `web/app/tuyen-dung/[slug]` |
| Chặn trang không cần index | Cổng thành viên, cổng đối tác, quản trị: `noindex`. Cơ hội chưa mở bán: `noindex`. | các `layout.tsx` |
| Xác minh Search Console | Thẻ meta Google / Bing lấy từ biến môi trường (xem mục 2.1). | `web/app/layout.tsx`, `.env.example` |

Kiểm tra nhanh sau khi deploy:

- https://leadscan.net/robots.txt
- https://leadscan.net/sitemap.xml
- Dán URL vào [Rich Results Test](https://search.google.com/test/rich-results) — phải thấy Organization, Breadcrumb, JobPosting… không lỗi.

---

## 2. Việc cần làm sau khi deploy (bắt buộc)

### 2.1. Google Search Console

1. Vào https://search.google.com/search-console → **Thêm sản phẩm**.
2. Chọn **Miền (Domain)** `leadscan.net` → Google đưa 1 bản ghi **TXT** → thêm vào DNS của tên miền. Cách này xác minh cả `www` lẫn `http/https`, không cần sửa code.
   - Nếu không sửa được DNS: chọn **Tiền tố URL** `https://leadscan.net` → phương thức **Thẻ HTML** → chép phần `content="…"` vào `.env` trên VPS:
     ```
     GOOGLE_SITE_VERIFICATION=chuỗi_google_đưa
     ```
     rồi build lại web: `docker compose up -d --build web`.
3. Mục **Sơ đồ trang web** → gửi `sitemap.xml`.
4. Mục **Kiểm tra URL** → dán lần lượt `https://leadscan.net/`, `/co-hoi`, `/doi-tac`, `/gioi-thieu` → **Yêu cầu lập chỉ mục**.
5. Sau 3–7 ngày xem **Trang** (đã lập chỉ mục bao nhiêu, lỗi gì) và **Hiệu suất** (từ khoá nào đang ra LeadScan).

### 2.2. Bing (và Cốc Cốc)

- https://www.bing.com/webmasters → **Nhập từ Google Search Console** (1 cú bấm). Bing còn cấp dữ liệu cho ChatGPT Search và Copilot.
- Hoặc dùng thẻ meta: đặt `BING_SITE_VERIFICATION=` trong `.env` rồi build lại web.

### 2.3. Gom `www` về 1 địa chỉ

Nginx hiện chỉ nhận `leadscan.net`. Nếu `www.leadscan.net` có bản ghi DNS, thêm khối này (rồi `certbot --nginx -d www.leadscan.net`) để Google không thấy 2 bản trùng:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name www.leadscan.net;
    return 301 https://leadscan.net$request_uri;
}
```

### 2.4. Google Business Profile

Tạo hồ sơ doanh nghiệp tại https://business.google.com (tên **LeadScan**, ngành, số điện thoại, website). Đây là cách nhanh nhất để có **khung thông tin thương hiệu bên phải** khi người ta tìm “LeadScan”.

---

## 3. Về “phần tìm kiếm được đề xuất”

Google có mấy chỗ “đề xuất” khác nhau. Code chỉ quyết định được một phần:

| Bạn muốn | Cách Google quyết định | Ta làm được gì |
|---|---|---|
| **Gợi ý khi gõ** (gõ “leads…” hiện “leadscan”) | Theo **số người thật sự tìm** cụm đó. Không cài được bằng code hay khai báo. | Làm người ta tìm tên “LeadScan”: ghi “Tìm **LeadScan** trên Google” trên Zalo OA, email, card visit, bài đăng; đặt tên thống nhất “LeadScan” mọi nơi. |
| **Link con dưới kết quả** (sitelinks: Cơ hội, Đối tác, Giới thiệu…) | Google tự chọn khi site có cấu trúc rõ và đủ lượt tìm theo tên thương hiệu. | ✅ Menu rõ, title mỗi trang khác nhau, breadcrumb, sitemap — đã làm. Phần còn lại là thời gian + lượt tìm tên thương hiệu. |
| **Tên trang “LeadScan” + logo** thay vì URL | Đọc JSON-LD `WebSite` / `Organization`, favicon. | ✅ Đã làm. |
| **Hỏi đáp xổ xuống** (FAQ rich result) | Từ 2023 Google **chỉ hiện cho trang chính phủ / y tế**. | Vẫn giữ `FAQPage`: Google và AI Overviews dùng để trả lời câu hỏi. |
| **Google Việc làm** | Đọc `JobPosting`. | ✅ Đã có cho mỗi tin tuyển dụng. |
| **Khung thương hiệu bên phải** | Google Business Profile + Organization + liên kết từ nơi khác. | Mục 2.4 và mục 5. |

---

## 4. Từ khoá và nội dung (đòn bẩy lớn nhất)

Google xếp hạng **trang trả lời đúng điều người ta gõ**. Gợi ý từ khoá theo trang:

| Trang | Từ khoá chính | Từ khoá phụ |
|---|---|---|
| Trang chủ `/` | sàn cơ hội kinh doanh B2B, tìm khách hàng B2B | tìm khách hàng doanh nghiệp, khách hàng đang cần mua |
| `/co-hoi` | cơ hội kinh doanh B2B, nhu cầu mua hàng doanh nghiệp | đơn hàng B2B, tìm nhà cung cấp, gói thầu |
| `/co-hoi/nganh/…` | nhu cầu mua + *tên ngành* (vd “nhu cầu mua bao bì, in ấn”) | doanh nghiệp đang cần mua …, tìm khách hàng ngành … |
| `/co-hoi/CH-…` | *“[mặt hàng] + [số lượng] + [tỉnh]”* (đã có sẵn trong tiêu đề cơ hội) | nhà máy cần mua …, doanh nghiệp tìm nhà cung cấp … |
| `/doi-tac` | kiếm tiền giới thiệu khách hàng, cộng tác viên giới thiệu khách hàng B2B | hoa hồng giới thiệu, chương trình đối tác |
| `/tuyen-dung` | tuyển dụng LeadScan, việc làm sales B2B | |

Việc nên làm:

1. **Tiêu đề cơ hội viết như người ta tìm**: “Nhà máy FDI Bắc Ninh cần 20.000 thùng carton 5 lớp/tháng” tốt hơn “Cơ hội bao bì #12”. Mỗi cơ hội là 1 trang có thể lên Google — đây là lợi thế lớn nhất của LeadScan.
2. **Trang cơ hội theo ngành** ✅ đã có: 15 trang `/co-hoi/nganh/<slug>` (nội dung riêng mỗi ngành: giới thiệu, nhu cầu thường gặp, ai nên theo dõi + danh sách cơ hội của ngành). Link cũ `/co-hoi?nganh=…` chuyển hẳn (308) sang trang ngành. Ngành chưa có cơ hội: `noindex` và không vào sitemap, có cơ hội là tự lên. Sửa nội dung từng ngành ở `web/lib/industries.ts`. **Bước tiếp:** trang theo tỉnh (`/co-hoi/tinh/bac-ninh`) để bắt từ khoá “doanh nghiệp Bắc Ninh cần mua…”.
3. **Bài viết / cẩm nang** (blog): “Cách tìm khách hàng B2B”, “Cách tìm nhà máy FDI mới”, “Hoa hồng giới thiệu khách hàng tính thế nào”… mỗi tuần 1 bài, liên kết về `/co-hoi` và `/doi-tac`.
4. Viết cho người đọc, không nhồi từ khoá; mỗi trang 1 chủ đề, 1 thẻ H1.

---

## 5. Liên kết từ nơi khác (off-page)

- Trang **mcv.network** đặt link về leadscan.net (và ngược lại — trang Giới thiệu đã có).
- Hồ sơ trên: Facebook Page, LinkedIn công ty, Zalo OA, YouTube (nếu có). Khi có, gửi link để thêm vào `sameAs` trong `web/lib/seo.ts` → Google nối các hồ sơ về cùng 1 thương hiệu.
- Danh bạ doanh nghiệp (Trang Vàng, Hiệp hội ngành, KCN), báo/tạp chí ngành, bài PR.
- Đối tác chia sẻ link cơ hội (`/co-hoi/CH-…`) lên Zalo/Facebook — vừa có khách vừa có tín hiệu.

---

## 6. Tốc độ trang (Core Web Vitals)

- Kiểm tra định kỳ tại https://pagespeed.web.dev (bản di động là chính).
- Đề xuất kỹ thuật tiếp theo: tự host font (chuyển Google Fonts sang `next/font`) để bỏ 1 request chặn hiển thị, cải thiện LCP.

---

## 7. Theo dõi hằng tháng

- Search Console → **Hiệu suất**: số lượt hiển thị, lượt nhấp, từ khoá mới.
- Search Console → **Trang**: trang nào “Đã thu thập – hiện chưa lập chỉ mục” → cải thiện nội dung trang đó.
- Tìm thử trên Google: `site:leadscan.net` (xem bao nhiêu trang đã vào chỉ mục).
