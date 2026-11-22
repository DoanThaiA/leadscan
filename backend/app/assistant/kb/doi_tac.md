# Hướng dẫn đối tác (cổng /doi-tac)

## Menu cổng đối tác
- Tổng quan (/doi-tac/tong-quan), Gửi cơ hội (/doi-tac/gui-co-hoi), Cơ hội của tôi (/doi-tac/co-hoi), Nhu cầu đang tìm (/doi-tac/nhu-cau), Kết nối AI (/doi-tac/ket-noi-ai), Ví hoa hồng (/doi-tac/vi), Rút tiền (/doi-tac/rut-tien), Hồ sơ thanh toán (/doi-tac/ho-so-thanh-toan), Tài khoản (/doi-tac/tai-khoan), Chính sách & hướng dẫn (/doi-tac/chinh-sach).
- Thanh bên hiện mã đối tác (DT-…) và hạng. Nếu cùng email là thành viên: nút "Sang cổng thành viên".
- Dữ liệu riêng của người đang hỏi: get_my_partner_account, list_my_submissions, get_my_submission, list_my_withdrawals, list_open_needs. Mức thưởng hiện hành: get_partner_rewards.

## Đăng ký và kích hoạt bằng OTP email
- Đăng ký tại /doi-tac#dang-ky (họ tên, điện thoại/Zalo, email đăng nhập, mật khẩu ≥ 8 ký tự, Cá nhân/Tổ chức; tổ chức thêm tên và MST 10 hoặc 13 số, có nút "Tra cứu"; ngành/khu vực không bắt buộc; đồng ý Điều khoản đối tác). Miễn phí.
- Mỗi email một tài khoản đối tác; mỗi số điện thoại chỉ dùng cho 1 tài khoản ("Số điện thoại này đã đăng ký đối tác"). Email đã là thành viên → nhập đúng mật khẩu thành viên để dùng chung.
- Thành viên đã đăng nhập: dùng "Trở thành đối tác" trong cổng thành viên thay vì form này.
- Sau khi gửi, bạn được đăng nhập và chuyển tới /doi-tac/xac-thuc để nhập mã 6 số gửi tới email. Chưa xác thực thì không vào được cổng.
- Quy tắc mã: hiệu lực 15 phút; chờ 60 giây giữa 2 lần gửi ("Gửi lại sau …s"); tối đa 5 mã mỗi giờ; mỗi mã nhập sai tối đa 5 lần (sai quá → bấm "Gửi lại mã"). Không dùng SMS; số điện thoại chỉ để liên hệ.
- Không nhận được mã: kiểm tra thư mục Spam / Quảng cáo, đợi rồi bấm "Gửi lại mã". Vẫn không có hoặc đăng ký sai email: liên hệ LeadScan (hotline 0877 770 788, contact@leadscan.net); nhân viên đối chiếu rồi kích hoạt tay hoặc cập nhật email.

## Đăng nhập, mật khẩu, tài khoản
- Đăng nhập: /doi-tac/dang-nhap. Sai quá nhiều lần → thử lại sau 15 phút. Tài khoản bị khoá → liên hệ LeadScan.
- Quên mật khẩu: /doi-tac/quen-mat-khau → liên kết đặt lại hiệu lực 60 phút.
- Đổi mật khẩu: Tài khoản → "Đổi mật khẩu" (≥ 8 ký tự); áp dụng cả cổng thành viên.
- Đổi số điện thoại hoặc thông tin tổ chức: liên hệ LeadScan (không tự sửa trong cổng).

## Hạng đối tác
- 3 hạng: Mới (mặc định), Bạc, Chiến lược. Hạng quyết định tỷ lệ hoa hồng phiếu thường và hạn mức ly cafe mỗi tháng.
- Hạng do LeadScan điều chỉnh; website không công bố tiêu chí tự động lên hạng. Hạng Chiến lược có thể có thoả thuận riêng về tỷ lệ (có trần) và hạn mức ly cafe.
- Mặc định trong code: Mới 20% và 10 ly/tháng; Bạc 25% và 30 ly/tháng; Chiến lược 25% và 100 ly/tháng; trần thoả thuận riêng 30%. Hiện hành: get_partner_rewards.

## Cơ hội nào được nhận
- Được nhận: nhu cầu cụ thể (mặt hàng/dịch vụ, quy mô, thời điểm); có doanh nghiệp (tên hoặc MST) đứng sau; có thời điểm (sắp mua, đang tìm nhà cung cấp, sắp khởi công).
- Không nhận: tin đồn, thông tin chung chung chép từ báo; danh sách số điện thoại, email cá nhân; thông tin mật của nơi bạn đang làm việc.

## Gửi cơ hội (/doi-tac/gui-co-hoi)
- Mục 1 Doanh nghiệp có nhu cầu: Mã số thuế (không bắt buộc, 10 hoặc 13 số, "Tra cứu" để tự điền tên/tỉnh — có MST giúp xác minh nhanh và tăng điểm), Tên doanh nghiệp* (≥ 3 ký tự), Khu vực/tỉnh thành*, Ngành hàng* (chọn trong danh mục).
- Mục 2 Nhu cầu: Tiêu đề cơ hội* (10–150 ký tự; dùng làm tiêu đề phiếu khi mở bán; nêu mặt hàng + số lượng + loại bên mua; KHÔNG ghi tên doanh nghiệp), Loại cơ hội* (Đăng mua; Dự án / gói thầu; Nhà máy / FDI mới; Mở rộng sản xuất; Tìm nhà cung cấp thay thế), Nhu cầu cụ thể* (30–4.000 ký tự), Quy mô / số lượng, Thời điểm cần.
- Mục 3 Nguồn & độ chắc chắn: Bạn biết tin từ đâu?* (Trực tiếp; Mối quan hệ; Hội chợ; Nguồn công khai — nguồn công khai bắt buộc dán link http/https), Link nguồn, Mức độ chắc chắn* (Đã xác nhận với bên mua; Nghe từ người trong cuộc; Thấy công khai), Tài liệu, link chứng minh (mỗi dòng 1 link), Ảnh chứng minh.
- Mục 4 Người liên hệ (không bắt buộc): họ tên, chức vụ, điện thoại, email — điền ô nào thì phải tick xác nhận người đó đồng ý được giới thiệu hoặc là liên hệ công khai; "Bạn có thể kết nối trực tiếp với bên mua?" Có/Không.
- Tick cam kết (hợp pháp, không vi phạm bảo mật nơi làm việc, không phải dữ liệu mua bán) rồi bấm "Gửi cơ hội".
- Chặn dữ liệu cá nhân: nếu phần nhu cầu, tài liệu, quy mô, thời điểm chứa từ 3 số điện thoại hoặc từ 3 email trở lên → bị từ chối gửi ("LeadScan không nhận danh sách số điện thoại / email").
- Giới hạn: tối đa 20 cơ hội mỗi đối tác trong 24 giờ (mặc định; "Vui lòng gửi tiếp vào ngày mai"). Không gửi lại cơ hội mình đã gửi ("Bạn đã gửi cơ hội này rồi (GT-…)").
- Ảnh: tối đa 6 ảnh mỗi cơ hội, mỗi ảnh ≤ 10 MB, jpg/png/webp; không gửi ảnh giấy tờ cá nhân; GPS tự xoá. Ảnh tải lên mà không gửi cơ hội bị xoá sau 24 giờ. Nếu cổng chưa mở tải ảnh: dán link ảnh (Google Drive…) vào ô Tài liệu.
- Sửa: chỉ khi trạng thái còn "Đã gửi" — mở cơ hội → "Sửa cơ hội" (mã và thời điểm gửi giữ nguyên, thay đổi ghi vào lịch sử). Khi LeadScan đã bắt đầu xác minh thì không sửa được; cần bổ sung → liên hệ LeadScan.
- Mỗi cơ hội có mã GT-xxxxxx. Gửi qua form hay qua Kết nối AI đều xác minh và tính thưởng như nhau.

## Kiểm tra trùng và điểm chất lượng
- Ai gửi trước được ghi nhận theo dấu thời gian.
- Hệ thống tự so với phiếu cơ hội và cơ hội đối tác khác trong khoảng thời gian gần đây (mặc định 90 ngày): cùng doanh nghiệp (theo MST hoặc tên) là điều kiện để so, kết luận dựa trên độ giống mô tả nhu cầu. Đây chỉ là gợi ý cho người duyệt; đối tác không thấy mình trùng với ai.
- Điểm chất lượng 0–100 tự chấm theo quy tắc, người duyệt chốt điểm cuối. Yếu tố cộng điểm: có MST (và doanh nghiệp đang hoạt động khi tra), nhu cầu mô tả chi tiết, có quy mô, có thời điểm, độ chắc chắn (Đã xác nhận với bên mua cao nhất), nguồn (Trực tiếp cao nhất), có link/tài liệu, có người liên hệ đồng ý. Nghi trùng nhu cầu bị trừ điểm.
- Ngưỡng "Đạt xác minh" do LeadScan cấu hình (mặc định trong code: 40 điểm). Điểm chỉ hiện cho đối tác sau khi có quyết định.

## Trạng thái và lý do không đạt
- Đã gửi: chờ LeadScan tiếp nhận (còn sửa được).
- Đang xác minh: đang kiểm trùng, xác minh, chấm điểm.
- Đạt xác minh: thông tin đúng, mới, đạt ngưỡng điểm; LeadScan đang hoàn thiện phiếu để mở bán.
- Đã xuất bản: phiếu đang bán trên sàn; mỗi lượt bán được chia hoa hồng.
- Trùng: cơ hội đã có hoặc đối tác khác gửi trước — không được thưởng.
- Không đạt: kèm lý do chuẩn: Thông tin sai; Không xác minh được; Điểm chất lượng dưới ngưỡng; Nhu cầu chung chung, thiếu cụ thể; Nhu cầu đã cũ hoặc đã kết thúc; Là danh sách dữ liệu cá nhân; Có dấu hiệu thông tin mật của nơi làm việc; Gian lận — thu hồi thưởng; Lý do khác (có ghi chú).
- Đóng góp bổ sung: cơ hội đã có nhưng thông tin bạn bổ sung có giá trị (người ra quyết định, ngân sách, thời điểm…).
- Ghi chú "LeadScan:" trong trang chi tiết là lời nhắn người duyệt. Kết quả xác minh được báo qua email.

## Thời hạn xác minh (SLA)
- Khoảng 2 ngày làm việc (T2–T6, chưa trừ ngày lễ). Trang chi tiết hiện "Hạn xác minh dự kiến" khi đang chờ.
- Sau khi Đạt, LeadScan hoàn thiện phiếu (tên bên mua chỉ mở cho người mua) rồi mở bán → "Đã xuất bản". Không có cam kết thời gian từ Đạt tới xuất bản.

## Thưởng: ly cafe và hoa hồng
- Ly cafe: ghi "Chờ duyệt" khi cơ hội Đạt xác minh, chuyển "Khả dụng" khi phiếu xuất bản. Chỉ trong hạn mức ly cafe/tháng theo hạng (tính theo tháng giờ Việt Nam). Vượt hạn mức: cơ hội vẫn được xác minh và chia doanh thu khi bán, chỉ không có ly cafe trả trước.
- Đóng góp bổ sung: 1 ly cafe, Khả dụng ngay, không chia doanh thu; tính vào hạn mức tháng.
- Hoa hồng: % doanh thu thuần mỗi lượt bán phiếu, trong N tháng kể từ ngày xuất bản (mọi vòng enrich). Doanh thu thuần = số thành viên thực trả cho phiếu (sau khuyến mại, trừ phần đã hoàn), chưa gồm thuế GTGT.
- Cơ hội lớn (gói thầu, dự án đầu tư lớn, do người duyệt đánh dấu): áp tỷ lệ riêng cho cơ hội lớn.
- Cách cộng (LeadScan chọn 1 phương án): "Lấy mức cao hơn" — nhận mức cao hơn giữa 1 ly cafe và % doanh thu lũy kế của cơ hội, nên luôn có ít nhất 1 ly cafe; hoặc "Cộng dồn" — 1 ly cafe cộng thêm % doanh thu mỗi lượt bán.
- Hoa hồng mỗi lượt bán ở "Chờ duyệt" trong số ngày giữ rồi sang "Khả dụng".
- Mặc định trong code: ly cafe 30.000đ; phương án "Lấy mức cao hơn"; cơ hội lớn 10%; giữ 7 ngày; chia sẻ 12 tháng. Hiện hành: get_partner_rewards. Ví dụ thu nhập trên landing chỉ minh hoạ, không cam kết.
- Không tính hoa hồng khi tài khoản mua phiếu có liên quan tới đối tác (trùng số điện thoại, email hoặc mã số thuế); lượt bán sau thời hạn chia sẻ cũng không tính.
- Thành viên được hoàn phiếu → thu hồi phần hoa hồng đã ghi vượt của lượt đó (khoản âm trong ví); ly cafe bảo đảm không bị thu hồi.
- Đổi quyết định (vd Đạt → Không đạt trước khi có phiếu) → huỷ ly cafe.
- Gian lận: huỷ khoản Chờ duyệt, thu hồi khoản Khả dụng kể cả ly cafe, khoá tài khoản. Cấm tạo nhiều tài khoản, tự mua phiếu từ cơ hội của mình. Hồ sơ thanh toán trùng tài khoản ngân hàng với đối tác khác bị gắn cờ.

## Ví hoa hồng (/doi-tac/vi)
- Là sổ ghi khoản LeadScan phải trả, không phải ví điện tử: không nạp, không chuyển cho người khác, chỉ rút về ngân hàng chính chủ.
- 4 số dư: Chờ duyệt (ly cafe chờ xuất bản phiếu, hoa hồng đang giữ); Khả dụng (rút được); Đang rút (lệnh đang xử lý); Đã rút.
- Loại khoản: Ly cafe cảm ơn, Đóng góp bổ sung, Hoa hồng lượt bán, Thu hồi hoa hồng (hoàn phiếu), Thu hồi do gian lận, Điều chỉnh; trạng thái khoản: Chờ duyệt, Khả dụng, Đã huỷ.
- Khối "Tháng này": thu nhập ghi nhận, ly cafe còn lại, tỷ lệ hoa hồng của bạn.

## Hồ sơ thanh toán (/doi-tac/ho-so-thanh-toan)
- Chỉ cần khi rút tiền lần đầu. Cá nhân: họ và tên (đúng như CCCD), số định danh cá nhân 12 số, MST cá nhân (không bắt buộc), ngân hàng, số tài khoản (6–20 số), tên chủ tài khoản. Tổ chức: tên tổ chức và MST lấy theo hồ sơ đối tác, ngân hàng, số tài khoản, chủ tài khoản.
- Tên chủ tài khoản phải trùng tên hồ sơ (so không dấu) — LeadScan chỉ chi về tài khoản chính chủ. Nút "Điền theo tên" gợi ý dạng chữ in không dấu.
- Không thu ảnh CCCD. Số định danh và số tài khoản được mã hoá; cổng chỉ hiện 4 số cuối.
- Đổi tài khoản chỉ áp dụng cho lệnh rút mới; lệnh đang chờ vẫn chi về tài khoản lúc đặt.

## Rút tiền (/doi-tac/rut-tien)
- Điều kiện: đã có hồ sơ thanh toán; số dư Khả dụng từ mức tối thiểu; không có lệnh khác đang xử lý (mỗi lúc 1 lệnh); chưa vượt số lệnh tối đa trong tháng (lệnh bị huỷ/từ chối không tính). Nếu cổng báo "Rút tiền chưa được mở" → liên hệ LeadScan.
- Các bước: nhập số tiền (hoặc "Rút hết") → xem Trừ khỏi ví, Thuế TNCN, Thực nhận, Dự kiến chi → "Tạo lệnh rút". Lệnh có mã RT-….
- Trạng thái: Chờ duyệt → Đã duyệt — chờ chi → Đã chi; hoặc Từ chối (kèm lý do, tiền trở lại Khả dụng), Đối tác huỷ. Huỷ được khi còn "Chờ duyệt" (nút "Huỷ").
- LeadScan chi theo lô vào các ngày cố định trong tháng; trang ghi tiền về trong 3 ngày làm việc. Đối tác nhận email ở mỗi bước.
- Thuế TNCN (cá nhân): mỗi lệnh từ ngưỡng trở lên bị khấu trừ % trên toàn bộ số tiền lệnh, LeadScan cấp chứng từ khấu trừ (số chứng từ hiện trong lịch sử). Ví dụ với mặc định: rút 6.000.000đ → thực nhận 5.400.000đ.
- Tổ chức: không khấu trừ thuế TNCN; phải xuất hoá đơn cho khoản hoa hồng, LeadScan chi sau khi có hoá đơn.
- Mặc định trong code: tối thiểu 100.000đ; tối đa 2 lệnh/tháng; chi ngày 5 và 20; ngưỡng thuế 5.000.000đ/lần, thuế 10%. Hiện hành: get_partner_rewards.

## Kết nối AI (/doi-tac/ket-noi-ai)
- Đăng và theo dõi cơ hội bằng lời trong Claude, ChatGPT hoặc ứng dụng hỗ trợ MCP (Claude Code, Cursor, VS Code…).
- Bấm "Tạo URL kết nối" → nhận URL dạng https://leadscan.net/api/mcp/lsm_…; URL chỉ hiện 1 lần, giữ như mật khẩu. Mỗi đối tác 1 URL hiệu lực; "Tạo URL mới" ngắt URL cũ; "Thu hồi" để huỷ. Tài khoản bị khoá thì URL hết tác dụng.
- Claude: Settings → Connectors → Add custom connector → dán URL → Add, rồi bật trong khung chat (nút +). ChatGPT (bản web, một số gói trả phí): Settings → Apps & Connectors → Advanced settings → bật Developer mode → Create → dán URL, chọn "No authentication". Hướng dẫn chi tiết có trên trang.
- AI làm được: xem hướng dẫn đăng, đăng cơ hội (cùng kiểm tra, giới hạn, lọc trùng như form; AI phải xin xác nhận cam kết trước khi đăng), xem cơ hội của tôi và chi tiết theo mã GT-…, xem Nhu cầu đang tìm.
- URL không xem được ví, hồ sơ thanh toán, không rút tiền. Ảnh minh chứng thêm trong cổng khi cơ hội còn "Đã gửi".

## Nhu cầu đang tìm (/doi-tac/nhu-cau)
- Trang mới: danh sách ẩn danh các phiếu tìm cơ hội của thành viên — họ bán gì, cần loại khách hàng/cơ hội nào, ngành, khu vực, quy mô khách, sản phẩm và địa điểm nhận ra từ mô tả. Dùng để biết nên đi tìm doanh nghiệp có nhu cầu mua nào.
- Chỉ gồm yêu cầu đang "Tìm kiếm liên tục", gửi trong 180 ngày gần nhất, của doanh nghiệp còn hạn thành viên. Mã hiển thị NC-xxxxxx.
- Không có tên, mã, MST, email, SĐT, link của thành viên (đã được che trong mô tả).
- Mỗi nhu cầu hiện "N cơ hội đã khớp" hoặc "Chưa có cơ hội phù hợp" (chưa có phiếu đang bán nào khớp — nên ưu tiên đi tìm); nhãn "Mới" cho nhu cầu gửi trong 7 ngày; "Xem đầy đủ" để đọc hết mô tả. Đầu trang có số liệu tổng và "Ngành nhiều nhu cầu".
- Lọc: ô tìm theo sản phẩm/khách hàng, Ngành hàng, Khu vực, tick "Chỉ nhu cầu chưa có cơ hội".
- Không cần liên hệ thành viên: tìm được doanh nghiệp đang cần mua đúng như vậy thì bấm "Gửi cơ hội phù hợp" (hoặc "Gửi cơ hội") và gửi như bình thường. Trang này không bảo đảm phiếu sẽ bán được.

## Điều khoản đối tác
- Điều khoản đối tác & Chính sách bảo mật (/doi-tac/dieu-khoan, cũng có trong "Chính sách & hướng dẫn") hiện là BẢN DỰ THẢO, đang chờ luật sư duyệt; nội dung chính thức sẽ công bố trước khi mở chương trình thí điểm. Khi trả lời phải nói rõ điều này.
- Nội dung chính: đối tác không phải nhân viên, không đại diện LeadScan; quy tắc thưởng, ghi nhận, ví, rút tiền, thuế; cam kết của đối tác; chính sách bảo mật (định danh và ngân hàng chỉ thu khi rút, được mã hoá; đối tác có thể yêu cầu xem, sửa, xoá dữ liệu cá nhân qua LeadScan, trừ dữ liệu phải lưu theo quy định kế toán, thuế).

## Mẹo để cơ hội đạt xác minh
- Ghi MST bên mua; tiêu đề rõ mặt hàng, số lượng, loại bên mua; mô tả chi tiết quy cách, quy mô, thời điểm, bối cảnh.
- Xác nhận trực tiếp với bên mua; đính kèm link mời thầu, bài đăng, ảnh hiện trường.
- Chỉ thêm người liên hệ khi họ đồng ý; không dán danh sách SĐT/email, không gửi thông tin mật.
- Gửi sớm; có thông tin mới cho cơ hội đã có thì ghi rõ để được xét Đóng góp bổ sung. Xem "Nhu cầu đang tìm" để tìm đúng loại khách thành viên đang cần.
