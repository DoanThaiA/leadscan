# Kiến thức chung về LeadScan

## LeadScan là gì
- LeadScan (leadscan.net) là sàn trung gian kết nối cơ hội kinh doanh B2B. LeadScan không phải bên bán hàng.
- Người mua (thành viên) đăng nhu cầu tìm khách hàng; đối tác đăng cơ hội mình biết (một doanh nghiệp đang có nhu cầu mua). LeadScan kiểm trùng, xác minh nguồn, bổ sung thông tin doanh nghiệp, chấm điểm, rồi mở bán cơ hội dưới dạng phiếu.
- Cơ hội không đạt kiểm duyệt thì không lên sàn. Thời gian kiểm duyệt thường khoảng 2 ngày làm việc.
- LeadScan thuộc hệ sinh thái MCV Network (trang /gioi-thieu); ngoài sàn còn có đào tạo AI cho doanh nghiệp và dịch vụ phát triển phần mềm, chuyển đổi số.

## Hai vai trò
- Thành viên (người mua): doanh nghiệp cần tìm khách hàng, đơn hàng, dự án. Đóng phí thành viên năm, phí được cộng đủ thành điểm (1 điểm = 1đ) để mua phiếu. Cổng: /thanh-vien.
- Đối tác: cá nhân hoặc tổ chức biết nhu cầu mua B2B nhưng không trực tiếp bán mặt hàng đó. Tham gia miễn phí, 1 cấp, không đa cấp, không mã giới thiệu. Nhận "ly cafe" khi cơ hội đạt xác minh và hoa hồng khi phiếu được bán. Cổng: /doi-tac.
- Số liệu phí, thưởng hiện hành: dùng công cụ get_pricing (thành viên) và get_partner_rewards (đối tác). Không tự đưa con số nếu công cụ không trả về.

## Sàn vận hành thế nào (3 bước)
1. Đăng lên sàn: đối tác đăng cơ hội; thành viên đăng "phiếu tìm cơ hội" mô tả khách hàng cần tìm.
2. LeadScan kiểm duyệt: kiểm trùng, xác minh, bổ sung thông tin, chấm điểm.
3. Kết nối: thành viên xem trước miễn phí, mua phiếu để mở khoá bên có nhu cầu và đầu mối. Đối tác nhận thưởng khi cơ hội đạt và mỗi lần phiếu được bán.
- Mỗi phiếu giới hạn số người mua (do LeadScan đặt cho từng phiếu); phiếu chỉ 1 lượt mua là phiếu độc quyền.
- Ngoài cơ hội từ đối tác, LeadScan còn tự đưa phiếu lên sàn (nhập tay, nhiều nguồn).

## Trang công khai
- /co-hoi: danh sách cơ hội đang mở bán, ai cũng xem được. Lọc theo ngành, khu vực, tìm theo mặt hàng hoặc mã CH-…; có trang theo ngành và theo khu vực. Chi tiết: /co-hoi/<mã CH-…>, có nút chia sẻ (Zalo, Facebook).
- Trang chi tiết công khai hiện đúng phần thành viên thấy khi chưa mua: tiêu đề, tóm tắt, ngành, khu vực, quy mô, giá trị ước tính, hạn chót, nguồn tin, độ tin cậy nguồn, độ cấp thiết, số đầu mối, số ảnh/tệp, số lượt mua tối đa, "Giá phiếu từ".
- "Giá phiếu từ" là giá thấp nhất; giá thật của mỗi thành viên tính theo điểm phù hợp riêng.
- Bấm "Mua phiếu" khi chưa đăng nhập: hiện lựa chọn Đăng ký thành viên / Đăng nhập, xong quay lại đúng cơ hội. Đã đăng nhập: cơ hội được thêm vào "Tất cả cơ hội" và "Kho của tôi" để mua như thường (giá bằng mức "Giá phiếu từ" vì chưa so khớp với yêu cầu của doanh nghiệp).
- Công cụ: search_opportunities, get_opportunity (chỉ phần xem trước công khai); list_options (danh mục ngành, khu vực).
- /cam-nang: Cẩm nang (bài viết hướng dẫn tìm khách hàng B2B, kiếm thu nhập khi giới thiệu cơ hội, dùng LeadScan); có trang theo khu vực. /bai-viet: các danh mục bài viết khác.
- /doi-tac: giới thiệu chương trình đối tác, form đăng ký đối tác, hỏi đáp. /doi-tac/dieu-khoan: Điều khoản đối tác & Chính sách bảo mật (bản dự thảo, đang chờ luật sư duyệt).
- /gioi-thieu: giới thiệu LeadScan và MCV Network.
- /tuyen-dung: vị trí đang tuyển, nộp hồ sơ trực tuyến (link CV hoặc file PDF/DOC/DOCX ≤ 5 MB); ứng viên nhận email xác nhận.

## Cách đăng ký
- Thành viên: trang chủ → "Đăng ký thành viên" (/#dang-ky): mã số thuế (bấm "Tra cứu" để tự điền), thông tin doanh nghiệp, người liên hệ, email, mật khẩu ≥ 8 ký tự. Gửi đăng ký không mất phí; xong được tự đăng nhập rồi thanh toán phí thành viên trong cổng. Mỗi mã số thuế chỉ đăng ký 1 lần.
- Đối tác: /doi-tac#dang-ky: họ tên, điện thoại/Zalo, email, mật khẩu, Cá nhân/Tổ chức; sau đó nhập mã OTP gửi qua email để kích hoạt. Không hỏi CCCD hay ngân hàng ở bước này. Thành viên muốn làm đối tác: bấm "Trở thành đối tác" trong cổng thành viên.

## Một tài khoản cho cả hai cổng
- Cùng một email dùng được cả cổng thành viên và cổng đối tác, cùng một mật khẩu. Đăng nhập một cổng là vào được cổng kia (nút "Sang cổng đối tác" / "Sang cổng thành viên").
- Email đã có ở một cổng: khi đăng ký cổng còn lại phải nhập đúng mật khẩu đang dùng.
- Đổi mật khẩu ở một cổng áp dụng cho cả hai.
- Ví điểm của doanh nghiệp (thành viên) và ví hoa hồng (đối tác) là 2 ví tách riêng.

## Nguyên tắc riêng tư
- Trước khi mua, người mua chỉ thấy phần xem trước: không có tên bên có nhu cầu, mô tả chi tiết, đầu mối, link nguồn, tệp (chỉ đếm số lượng).
- Sau khi mua: mở khoá tên bên có nhu cầu, chi tiết nhu cầu, đầu mối liên hệ (họ tên, chức vụ, điện thoại, email), ảnh/tài liệu kèm, link nguồn.
- Thành viên mua phiếu không thấy danh tính đối tác nguồn; đối tác không thấy thành viên nào đã mua (chỉ thấy số lượt bán và số tiền).
- Đối tác chỉ được điền người liên hệ khi người đó đồng ý được giới thiệu hoặc là liên hệ công khai của doanh nghiệp. LeadScan trả thưởng cho thông tin cơ hội, không trả theo số điện thoại hay email, không nhận danh sách dữ liệu cá nhân.
- Hồ sơ thanh toán đối tác được mã hoá; "Nhu cầu đang tìm" cho đối tác chỉ hiện phiếu tìm cơ hội đã ẩn danh (không tên, MST, email, SĐT, link của thành viên).

## Liên hệ & hỗ trợ
- Email: contact@leadscan.net
- Hotline: +84 877 770 788 (gọi trong nước: 0877 770 788)
- Địa chỉ: 169 Nguyễn Ngọc Vũ, Phường Yên Hòa, thành phố Hà Nội
- Facebook: facebook.com/leadscan.net
- Website: leadscan.net
- Những việc chỉ nhân viên LeadScan làm được: đổi mã số thuế hoặc email đăng nhập thành viên, đổi số điện thoại/thông tin tổ chức của đối tác, kích hoạt tay tài khoản đối tác không nhận được OTP, mở khoá tài khoản bị khoá, hoàn điểm phiếu, đối soát thanh toán chưa khớp.
- Không có thông tin về giờ làm việc của bộ phận hỗ trợ trên website — không tự đưa ra.

## Thuật ngữ
- Phiếu cơ hội (mã CH-xxxxxx): một doanh nghiệp đang có nhu cầu mua, đã được LeadScan kiểm duyệt, bán cho thành viên bằng điểm.
- Phiếu tìm cơ hội / yêu cầu tìm cơ hội: thành viên mô tả sản phẩm mình bán và khách hàng cần tìm, kèm tiêu chí; hệ thống so khớp ngay và tìm kiếm liên tục.
- Điểm (ví điểm): đơn vị thanh toán trong cổng thành viên, 1 điểm = 1đ.
- Điểm phù hợp (0–100): mức khớp giữa phiếu cơ hội và yêu cầu của từng doanh nghiệp, tính riêng cho từng doanh nghiệp; điểm càng cao giá phiếu càng cao.
- Độ tin cậy nguồn, độ cấp thiết: chỉ số tham khảo của phiếu (theo loại nguồn, số vòng làm giàu, đầu mối; theo hạn chót), không cộng vào điểm phù hợp.
- Điểm chất lượng (0–100) của cơ hội đối tác: điểm LeadScan chấm khi xác minh cơ hội đối tác gửi.
- Độc quyền: phiếu chỉ 1 người mua; hoặc thành viên hạng Vàng mua độc quyền một phiếu nhiều lượt chưa ai mua (giá nhân hệ số, đóng các lượt còn lại).
- Hạng thành viên: Thường / Vàng (theo tổng tiền đã nạp). Hạng đối tác: Mới / Bạc / Chiến lược.
- Enrich (làm giàu): bổ sung thông tin, đầu mối cho phiếu. "Mức enrich: Vòng N" trên phiếu; thành viên đã mua có thể gửi "Yêu cầu enrich thêm".
- Kho của tôi: danh sách cơ hội đã lưu (tự thêm khi hệ thống tìm thấy, hoặc bấm "Thêm vào kho").
- Ly cafe: khoản thưởng cố định cho mỗi cơ hội đối tác đạt xác minh (trong hạn mức tháng theo hạng).
- Hoa hồng: phần trăm doanh thu thuần mỗi lượt bán phiếu từ cơ hội đối tác, trong thời hạn chia sẻ.
- Đóng góp bổ sung: cơ hội LeadScan đã có nhưng đối tác bổ sung thông tin mới có giá trị — được 1 ly cafe, không chia doanh thu.
- Ví hoa hồng: sổ ghi khoản LeadScan phải trả đối tác; chỉ rút về ngân hàng chính chủ.
- Mã thường gặp: LS-… (mã khách hàng thành viên), LSP… (mã đơn thanh toán, cũng là nội dung chuyển khoản), DT-… (mã đối tác), GT-… (cơ hội đối tác gửi), RT-… (lệnh rút tiền), NC-… (nhu cầu đang tìm).
