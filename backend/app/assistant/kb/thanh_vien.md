# Hướng dẫn thành viên (cổng /thanh-vien)

## Menu cổng thành viên
- Tổng quan (/thanh-vien), Cơ hội phù hợp (/thanh-vien/phu-hop), Kho của tôi (/thanh-vien/kho), Phiếu đã mua (/thanh-vien/phieu), CRM (/thanh-vien/crm, hạng Vàng), Tất cả cơ hội (/thanh-vien/co-hoi), Số dư tài khoản (/thanh-vien/vi, tiêu đề trang "Ví & nạp tiền"), Tài khoản (/thanh-vien/tai-khoan).
- Chuông thông báo: cơ hội mới phù hợp với phiếu tìm cơ hội. Cuối menu: "Trở thành đối tác" hoặc "Sang cổng đối tác", "Đăng xuất".
- "Chân dung cơ hội" cũ đã gộp vào "Cơ hội phù hợp" (/thanh-vien/chan-dung tự chuyển về đó).
- Dữ liệu riêng của người đang hỏi: get_my_account, get_my_wallet, list_my_orders, list_my_search_requests, list_my_purchases, list_my_matches.

## Đăng ký, đăng nhập, mật khẩu
- Đăng ký: trang chủ → "Đăng ký thành viên" (/#dang-ky). Bắt buộc: mã số thuế 10 hoặc 13 số ("Tra cứu" để tự điền), tên doanh nghiệp, quy mô nhân sự, tỉnh/thành, ngành hàng (1–8), họ tên người liên hệ, email, điện thoại/Zalo, mật khẩu ≥ 8 ký tự, tick đồng ý.
- Lỗi thường gặp: "Mã số thuế này đã được đăng ký" → liên hệ LeadScan; "Email này đã có tài khoản LeadScan" → đăng nhập hoặc dùng email khác; email đã là đối tác → nhập đúng mật khẩu tài khoản đối tác để dùng chung.
- Đăng ký xong được tự đăng nhập, nút "Thanh toán phí thành viên" dẫn tới /thanh-vien/nap-tien.
- Đăng nhập: /thanh-vien/dang-nhap. Sai quá nhiều lần → "thử lại sau 15 phút". Tài khoản bị khoá → liên hệ LeadScan.
- Quên mật khẩu: /thanh-vien/quen-mat-khau → nhập email → nhận liên kết đặt lại (hiệu lực 60 phút). Không thấy email: kiểm tra thư rác.
- Đổi mật khẩu: Tài khoản → "Đổi mật khẩu" (mật khẩu mới ≥ 10 ký tự). Áp dụng cho cả cổng đối tác nếu cùng email.
- Sửa thông tin: Tài khoản → "Sửa thông tin" (tên doanh nghiệp, ngành, quy mô, tỉnh, địa chỉ, website, người liên hệ chính, họ tên người dùng). Không tự đổi được mã số thuế và email đăng nhập → liên hệ LeadScan.

## Phí thành viên, điểm, hiệu lực
- Phí thành viên năm được cộng đủ thành điểm vào ví (1 điểm = 1đ), hiệu lực theo số ngày cấu hình. Mặc định trong code: 89.000đ → 89.000 điểm, 365 ngày. Số liệu hiện hành: get_pricing.
- Chưa thanh toán phí: vẫn đăng nhập, gửi phiếu tìm cơ hội, xem trước; nhưng không mua phiếu và không nạp thêm điểm được. Cổng hiện thanh nhắc "Kích hoạt thành viên để mua phiếu cơ hội".
- Gia hạn: /thanh-vien/nap-tien → chọn "Gia hạn thành viên". Thời hạn mới cộng thêm từ hạn hiện tại (còn hạn) hoặc từ ngày thanh toán (đã hết hạn). Điểm gia hạn cũng được cộng vào ví.
- Hết hạn thành viên: không mua phiếu được cho tới khi gia hạn. Hệ thống không có cơ chế tự xoá điểm khi hết hạn; số dư vẫn hiển thị.
- Xem số dư, hạn thành viên, lịch sử điểm (sổ cái không sửa/xoá: Phí thành viên, Nạp điểm, Mua phiếu cơ hội, Hoàn điểm, Điều chỉnh) tại Số dư tài khoản (/thanh-vien/vi).

## Nạp điểm
- Điều kiện: đang là thành viên còn hiệu lực ("Vui lòng thanh toán phí thành viên trước khi nạp thêm điểm").
- Các bước: /thanh-vien/nap-tien → "Nạp thêm điểm" → chọn gói hoặc nhập số khác trong khoảng tối thiểu–tối đa → (tuỳ chọn) nhập mã khuyến mãi, bấm "Áp dụng" → "Tiếp tục thanh toán".
- Mặc định trong code: gói 5, 10, 20, 50 triệu; tuỳ chọn từ 1.000.000đ đến 500.000.000đ; nạp bao nhiêu được bấy nhiêu điểm. Số liệu hiện hành: get_pricing.
- Phần "Tóm tắt" hiện số tiền, giảm giá, điểm nhận được và hạng sau khi nạp.

## Thanh toán (VietQR)
- Thanh toán bằng chuyển khoản VietQR qua cổng thanh toán MCV; điểm được cộng tự động khi LeadScan nhận tiền.
- Mỗi đơn có mã riêng dạng LSP…; trang đơn /thanh-vien/nap-tien/<mã đơn> hiện mã QR, số tiền, chủ tài khoản, nội dung chuyển khoản và đồng hồ đếm ngược hạn QR.
- Quét QR bằng app ngân hàng (hoặc "Mở trang thanh toán MCV"). Không sửa số tiền và nội dung chuyển khoản. Chuyển thiếu tiền không được ghi nhận tự động.
- Mã QR có hạn ngắn (mặc định 15 phút); hết hạn bấm "Tạo mã QR mới". Đơn giữ tối đa 24 giờ (mặc định) rồi chuyển "Hết hạn". Huỷ đơn: nút "Huỷ đơn" khi đơn còn "Chờ thanh toán".
- Trạng thái đơn: Chờ thanh toán, Đã thanh toán, Hết hạn, Đã huỷ. Trạng thái mã QR: Đang chờ chuyển khoản, Đã thanh toán, Mã QR hết hạn, Đã nhận tiền nhưng chưa khớp, Lỗi — thử lại sau.
- Đã chuyển khoản nhưng chưa thấy điểm: trang đơn tự cập nhật, đợi rồi tải lại /thanh-vien/nap-tien/<mã đơn>. Chuyển theo mã QR cũ đã hết hạn vẫn được ghi nhận khi tiền về, không cần chuyển lại. "Đã nhận tiền nhưng số tiền chưa khớp": kế toán đối soát và liên hệ, không cần chuyển thêm. Vẫn chưa có: liên hệ LeadScan kèm mã đơn LSP…, thời gian, số tiền; nhân viên có thể xác nhận thủ công sau khi đối soát.
- Mỗi giao dịch chỉ được cộng điểm 1 lần. Sau khi cộng, khách nhận email báo kích hoạt / nạp thành công.

## Hoá đơn điện tử
- Xem trạng thái hoá đơn ở Số dư tài khoản → "Đơn thanh toán & hoá đơn" (Chờ xuất / Đã xuất kèm số hoá đơn).
- Khi hệ thống xuất tự động được bật: thanh toán xong, hoá đơn được xuất theo tên, MST, địa chỉ doanh nghiệp đã đăng ký và gửi về email; số hoá đơn hiện ở trang đơn.
- Nếu đơn chưa có hoá đơn: bấm "Yêu cầu xuất HĐ" → form "Thông tin xuất hoá đơn": tên đơn vị (theo ĐKKD), mã số thuế, người mua hàng, địa chỉ trên hoá đơn, email nhận hoá đơn, ghi chú → "Gửi thông tin xuất hoá đơn".
- Chỉ xuất cho đơn đã thanh toán; đơn 0đ (miễn phí nhờ mã khuyến mãi) không xuất hoá đơn; mỗi đơn gửi thông tin 1 lần.

## Mã khuyến mãi
- Nhập ở ô "Mã khuyến mãi" trang Nạp tiền, hoặc bấm từ popup khuyến mãi trên trang chủ (mã được điền sẵn).
- Giảm theo % hoặc số tiền; mỗi mã có thể giới hạn loại đơn (phí thành viên / nạp điểm), thời gian, giá trị đơn tối thiểu, tổng lượt, lượt mỗi doanh nghiệp. Cổng báo rõ lý do khi mã không dùng được.
- Điểm cộng vẫn theo giá gốc, chỉ số tiền phải trả giảm. Giảm còn 0đ → kích hoạt ngay, không cần thanh toán.

## Hạng Thường / Vàng và mua độc quyền
- Hạng tính theo tổng tiền đã thanh toán (phí thành viên + nạp điểm). Đạt ngưỡng là lên Vàng ngay, không bị hạ hạng. Mặc định ngưỡng 10.000.000đ; hiện hành: get_pricing. Cổng hiện "Còn … nữa" để lên Vàng.
- Quyền lợi Vàng: mua độc quyền phiếu, CRM theo dõi cơ hội, trợ lý AI trong CRM (khi được bật).
- Mua độc quyền: chỉ với phiếu nhiều lượt mua và chưa ai mua. Giá = hệ số × giá phiếu đang hiển thị cho doanh nghiệp (mặc định ×2). Mua xong các lượt còn lại bị đóng, không doanh nghiệp nào mua thêm được.
- Không mua độc quyền được khi: phiếu vốn chỉ 1 lượt, phiếu đã có người mua, hoặc chưa hạng Vàng.

## Phiếu tìm cơ hội (Cơ hội phù hợp)
- Vào /thanh-vien/phu-hop, khung "Tạo yêu cầu tìm kiếm":
  1. "Mô tả nhu cầu" (10–3.000 ký tự): sản phẩm/dịch vụ bạn cung cấp, loại khách cần tìm, số lượng, thị trường, thời gian.
  2. Tiêu chí (bỏ trống = không giới hạn): Ngành hàng (chọn nhiều, gõ thêm được), Khu vực, Quy mô khách hàng, Loại cơ hội, Điểm phù hợp tối thiểu (mọi mức, từ 60/70/80/90).
  3. Bấm "Enrich tìm kiếm cơ hội".
- Mẹo viết: ghi tên sản phẩm cụ thể (vd túi giữ nhiệt, không chỉ "bao bì"); quy cách, số lượng; địa điểm giao hàng (địa điểm trong mô tả được ưu tiên hơn ô Khu vực, nên chọn ô Khu vực cho khớp); loại khách, thời gian. Có mẫu "Sao chép mẫu" / "Dùng mẫu này" trong mục hướng dẫn.
- Hệ thống hiện "Sản phẩm" và "Địa điểm" nhận ra từ mô tả, cảnh báo khi mâu thuẫn với ô Khu vực.
- "AI viết lại": viết lại mô tả cho rõ theo mẫu, bạn xem lại rồi mới gửi, có "Hoàn tác". Cần ít nhất vài chữ; giới hạn lượt mỗi giờ cho mỗi doanh nghiệp (mặc định 20); báo "Trợ lý AI chưa được bật" nếu hệ thống chưa bật.
- Giới hạn: tối đa 10 yêu cầu mỗi doanh nghiệp trong 24 giờ.
- Kết quả có ngay: cơ hội đạt mức phù hợp được thêm vào "Tất cả cơ hội" và "Kho của tôi". Chưa có → "LeadScan sẽ tìm kiếm liên tục và báo bạn khi có".
- Tìm kiếm liên tục: cơ hội mới mở bán khớp yêu cầu được tự thêm và báo qua chuông và email. Nhãn "Mới" cho cơ hội chưa xem.
- Trạng thái: "Tìm kiếm liên tục" hoặc "Từ chối" (LeadScan dừng yêu cầu). LeadScan có thể ghi "LeadScan phản hồi". Cổng chưa có nút tự xoá/dừng yêu cầu — cần dừng thì liên hệ LeadScan.
- Tiêu chí lần gửi gần nhất được nhớ để điền sẵn lần sau.
- Nội dung phiếu tìm cơ hội đang tìm kiếm liên tục (của doanh nghiệp còn hạn thành viên) được hiển thị ẩn danh cho đối tác ở trang "Nhu cầu đang tìm" để họ đi tìm đúng khách; tên, mã, MST, email, SĐT, link của doanh nghiệp bị che.

## Điểm phù hợp được tính thế nào
- Tính riêng cho từng doanh nghiệp. Bước 1: cơ hội phải khớp tiêu chí bạn chọn (ngành, khu vực, loại cơ hội) mới được chấm. Bước 2: điểm = mức gần nghĩa + trùng từ khoá giữa mô tả của bạn và cơ hội, có đối chiếu sản phẩm cụ thể (khác sản phẩm bị hạ điểm).
- Phải đạt mức tối thiểu của hệ thống và mức bạn chọn mới vào danh sách.
- Độ cấp thiết và độ tin cậy nguồn chỉ để tham khảo, không cộng vào điểm.

## Tất cả cơ hội, Kho của tôi, Phiếu đã mua
- Tất cả cơ hội (/thanh-vien/co-hoi): cơ hội phù hợp gộp từ mọi phiếu tìm cơ hội (đã loại trùng) và cơ hội mở từ link chia sẻ; có lọc (Còn lượt mua, Đã mua, ngành, khu vực, điểm, nguồn), tìm kiếm và sắp xếp theo mới nhất, điểm, giá.
- Chỉ mua được cơ hội có trong "Tất cả cơ hội" của doanh nghiệp. Chưa có cơ hội nào → gửi phiếu tìm cơ hội.
- Kho của tôi (/thanh-vien/kho): cơ hội tự thêm khi hệ thống tìm thấy và cơ hội bấm "Thêm vào kho". Phiếu trong kho có thể hết lượt nếu doanh nghiệp khác mua trước.
- Phiếu đã mua (/thanh-vien/phieu): mọi phiếu đã mở khoá, bên có nhu cầu, đầu mối chính, điểm lúc mua, giá, ngày mua.

## Giá phiếu
- Giá = giá cơ bản của phiếu × hệ số điểm phù hợp × hệ số cấp thiết (hạn chót gần) × hệ số đủ thông tin × hệ số giá trị đơn hàng; làm tròn, không thấp hơn giá cơ bản và giá tối thiểu.
- Điểm phù hợp dưới ngưỡng bắt đầu tăng giá thì không tăng; điểm càng gần 100 giá càng cao. Mặc định: giá tối thiểu 29.000đ, tăng giá từ 50 điểm, tối đa ×3 khi 100 điểm. Tham số hiện hành: get_pricing.
- Giá hiển thị là giá riêng của bạn; giá đã mua được giữ cố định, đổi công thức sau đó không ảnh hưởng.

## Mua phiếu
- Mở chi tiết cơ hội → "Mua phiếu cơ hội" → hộp xác nhận hiện giá, số dư hiện tại, số dư sau khi mua → "Mua với … điểm".
- Điều kiện: thành viên còn hiệu lực; đủ điểm (thiếu → "Nạp thêm điểm"); phiếu còn lượt ("Phiếu cơ hội này đã hết lượt mua"); chưa mua phiếu này ("Bạn đã mua phiếu này rồi" — không mua trùng).
- Điểm bị trừ ngay; số lượt mua tối đa mỗi phiếu hiện "Còn x/y lượt mua" hoặc "Phiếu độc quyền — chỉ 1 doanh nghiệp mua".
- Mở khoá ngay sau khi mua: tên bên có nhu cầu, chi tiết, đầu mối liên hệ, ảnh/tài liệu kèm, link nguồn; lưu ở "Phiếu đã mua".
- Phiếu bị LeadScan sửa sau khi mua: trang chi tiết báo "Cơ hội đã được chỉnh sửa sau khi bạn mua", xem được "Bản bạn đã mua" và "Bản hiện tại".

## Yêu cầu enrich thêm
- Với phiếu đã mua: trang chi tiết → "Yêu cầu enrich thêm" → ghi cần thêm gì (vd SĐT giám đốc nhà máy) → "Gửi yêu cầu".
- Mỗi phiếu chỉ có 1 yêu cầu đang xử lý một lúc. Trạng thái: Đang xử lý, Đã xong, Từ chối; phản hồi của LeadScan hiện dưới yêu cầu. Gửi yêu cầu không tự trừ điểm.

## Hoàn điểm
- Hoàn điểm do LeadScan xem xét và thực hiện, thành viên không tự hoàn. Hoàn trả lại đúng số điểm đã trả cho phiếu, vào ví điểm, mỗi phiếu tối đa 1 lần; ghi "Hoàn điểm" trong lịch sử và "Đã hoàn …" trên phiếu.
- Trường hợp được nêu trong cổng: cơ hội bị sửa sau khi mua và không còn phù hợp yêu cầu — LeadScan sẽ xem xét. Trường hợp khác: liên hệ LeadScan kèm mã phiếu CH-…; không hứa hẹn kết quả.
- Không có quy định hoàn tiền mặt cho phí thành viên hay điểm đã nạp trên website.

## CRM Lite (hạng Vàng)
- Ai dùng: thành viên hạng Vàng (có thể đang chạy thử với một số doanh nghiệp Vàng — khi đó cổng báo "sẽ sớm mở cho bạn"). Chưa Vàng: trang CRM hiện quyền lợi và số tiền cần nạp thêm.
- Mỗi phiếu đã mua tự thành một lead trên bảng: Mới → Đang liên hệ → Có nhu cầu → Báo giá → Thắng / Thua; kéo thẻ để đổi giai đoạn.
- Chi tiết lead: giao người phụ trách, ghi chú (SĐT/email không thuộc đầu mối của phiếu tự bị ẩn), việc cần làm có hạn và người làm. Trang "Việc cần làm" (/thanh-vien/crm/viec); email nhắc việc 8:00 hằng ngày, báo cáo tuần sáng thứ Hai.
- "Xuất Excel": chỉ dữ liệu doanh nghiệp, không kèm người liên hệ.
- Trợ lý AI (khi hệ thống bật): "Tóm tắt công ty", "Soạn tin mời" (email, Zalo hoặc kịch bản gọi) — bản nháp để tự sửa, tự gửi; có hạn mức theo tháng; AI không nhận tên/SĐT/email người liên hệ.

## Trở thành đối tác
- Cổng thành viên → "Trở thành đối tác" (/thanh-vien/tro-thanh-doi-tac): họ tên, số điện thoại liên hệ, Cá nhân/Tổ chức (tổ chức: tên, MST), ngành/khu vực hay tiếp xúc (không bắt buộc), đồng ý điều khoản → "Đăng ký làm đối tác".
- Dùng đúng email và mật khẩu đang đăng nhập. Sau đó nhập mã OTP gửi về email để kích hoạt cổng đối tác. Mỗi số điện thoại chỉ cho 1 tài khoản đối tác.
- Không tính hoa hồng khi phiếu từ cơ hội của đối tác được mua bởi tài khoản liên quan đến chính đối tác.
