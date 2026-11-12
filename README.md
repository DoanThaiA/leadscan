# LeadScan B2B

Nền tảng phiếu cơ hội B2B: doanh nghiệp đăng ký thành viên, AI tìm – làm giàu – chấm điểm cơ hội, khách mua phiếu bằng điểm thành viên.

Hệ thống **độc lập**: có cơ sở dữ liệu và trang quản trị riêng, không phụ thuộc hệ thống ngoài.

## Cấu trúc

```
backend/            FastAPI + SQLAlchemy + Alembic + Celery (Python 3.12, quản lý bằng uv)
  app/models.py       Company · Contact · Profile (chân dung cơ hội) · Activity · AdminUser · AdminSession
  app/routes/public.py   POST /api/registrations, GET /api/health
  app/routes/admin.py    /api/admin/* — đăng nhập, khách hàng, liên hệ, chân dung, ghi chú, nhân viên, thống kê
  app/routes/admin_commerce.py  /api/admin/* — cơ hội, đơn thanh toán, hoá đơn, enrich, ví & tài khoản thành viên
  app/routes/member.py   /api/member/* — cổng thành viên: đăng nhập, kho cơ hội, mua phiếu, ví, nạp tiền, hoá đơn
  app/routes/payments.py /api/payments/infocms/webhook — InfoCMS báo đã nhận tiền
  app/services/      payments.py (đơn & InfoCMS), einvoice.py (HĐĐT IAM Invoice), vietqr.py (mã QR NAPAS), wallet.py (sổ cái điểm), catalog.py (mua phiếu)
  app/auth.py         phiên đăng nhập (cookie HttpOnly, DB chỉ lưu sha256 token)
  app/worker.py       Celery: email báo đăng ký mới, dọn phiên hết hạn (beat mỗi giờ)
  app/cli.py          create-admin · diagnose · import-legacy
  migrations/         Alembic (PostgreSQL + pgvector trên VPS, SQLite khi dev)
  tests/              pytest
web/                Next.js 16
  app/page.tsx        landing page
  app/admin/          trang quản trị (/admin/...)
  app/thanh-vien/     cổng thành viên (/thanh-vien/...)
deploy/nginx.conf   Nginx trên VPS: /api → FastAPI, còn lại → Next.js (HTTPS bằng certbot)
docker-compose.yml  db (pgvector) · redis · migrate · api · worker · beat · web
```

## Chức năng quản trị (`/admin`)

- **Đăng nhập nhân viên**: khoá 15 phút sau 10 lần sai/IP, phiên 7 ngày, đăng xuất mọi thiết bị khi bị khoá hoặc đổi mật khẩu.
- **Tổng quan**: tổng khách hàng, đăng ký hôm nay / 7 ngày, số thành viên, biểu đồ đăng ký 30 ngày, phân bổ theo trạng thái.
- **Khách hàng**: tìm theo tên, mã, MST, email, SĐT; lọc trạng thái (Mới đăng ký → Đã liên hệ → Thành viên / Tạm khoá / Từ chối) và người phụ trách; phân trang.
- **Chi tiết khách hàng**: sửa thông tin doanh nghiệp, chân dung cơ hội, nhiều người liên hệ; đổi trạng thái, giao người phụ trách; ghi chú chăm sóc; lịch sử thay đổi đầy đủ (ai, lúc nào).
- **Nhân viên** (chỉ quản trị viên): thêm tài khoản, đổi vai trò, khoá/mở, đặt lại mật khẩu.
- **Phân quyền**: *Nhân viên* xem & chăm sóc khách hàng; *Quản trị viên* thêm quản lý tài khoản và xoá khách hàng.

## Cổng thành viên (`/thanh-vien`)

- **Đăng ký** trên landing kèm mật khẩu → tạo luôn tài khoản và tự đăng nhập. Có quên / đặt lại mật khẩu qua email.
- **Phí thành viên** 89.000đ → cộng **89.000 điểm** (1 điểm = 1đ), hiệu lực 365 ngày; gia hạn cộng dồn.
- **Nạp thêm điểm** (gói 5/10/20/50 triệu hoặc tuỳ chọn) — chỉ khi đang là thành viên.
- **Thanh toán qua InfoCMS (VietQR)**: mỗi đơn có mã riêng làm nội dung chuyển khoản; trang thanh toán hiện QR + số tài khoản, tự cập nhật khi InfoCMS báo đã nhận tiền.
- **Xuất hoá đơn điện tử tự động (IAM Invoice)** — bật bằng `LEADSCAN_IAM_ENABLED=true` (xem `.env.example`): thanh toán xong (webhook, admin xác nhận tay, giả lập) hệ thống tự lấy tên/MST/địa chỉ doanh nghiệp đã đăng ký, gọi IAM tạo + ký số hoá đơn (chứng thư IntrustCA + PIN) và lưu số hoá đơn; khách thấy số HĐ ở trang đơn. Thiếu địa chỉ → khách điền form "Thông tin xuất hoá đơn" rồi tự xuất. Mã đơn `LSP…` là mã tra cứu bên IAM (`thirdPartyCode`) nên gọi lại không xuất trùng. IAM lỗi → thử lại 3 lần, vẫn lỗi thì email kế toán kèm lý do; admin bấm **Phát hành HĐĐT** ở trang Hoá đơn. Với method khác GET, client xoá cookie trước khi gọi IAM (yêu cầu của IAM). Code: `backend/app/services/einvoice.py`.
- **Xuất hoá đơn thủ công** (khi tắt IAM): khách nhập thông tin xuất hoá đơn → email gửi tới `LEADSCAN_INVOICE_EMAIL` (mặc định vylyy9999@gmail.com) để kế toán xuất; admin nhập số hoá đơn khi đã xuất.
- **Kho cơ hội**: lọc theo ngành, khu vực, nguồn, điểm; sắp xếp mới nhất / điểm / giá. Xem trước tóm tắt + điểm AI; tên bên có nhu cầu, chi tiết và đầu mối chỉ mở sau khi mua.
- **Mua phiếu**: trừ điểm, giới hạn số lượt bán (1 = độc quyền), không mua trùng; **phiếu đã mua** lưu lại đầy đủ; **yêu cầu enrich** thêm đầu mối.
- **Ví**: số dư, hạn thành viên, lịch sử điểm (sổ cái không sửa/xoá), đơn thanh toán & trạng thái hoá đơn. **Chân dung cơ hội** tự cập nhật.

Admin có thêm: **Cơ hội & phiếu** (nhập tay, định giá, mở bán), **Thanh toán** (xác nhận tay khi đã đối soát — dự phòng webhook), **Hoá đơn**, **Yêu cầu enrich**, và trong chi tiết khách hàng: **ví điểm, điều chỉnh điểm, tài khoản đăng nhập**.

## Đối tác LeadScan (`/doi-tac`) — Mốc 1–4: tài khoản, gửi & xác minh cơ hội, ví hoa hồng, rút tiền

Người ngoài thực địa giới thiệu cơ hội B2B, LeadScan xác minh, bán phiếu và chia doanh thu qua ví hoa hồng (brief "Tính năng Đối tác" v0.1).

- **Landing `/doi-tac`**: 9 khối theo brief (hero, nhóm đối tác, 3 bước, quyền lợi, ví dụ thu nhập, cơ hội được nhận, cam kết, form đăng ký 7 trường, hỏi đáp). Nhấn vàng để phân biệt cổng thành viên.
- **Tài khoản tách hẳn cổng thành viên**: bảng `partner_users`, cookie `ls_partner` chỉ gửi tới `/api/partner` (cookie thành viên `ls_member` chỉ tới `/api/member`). Cùng một email có thể vừa là thành viên vừa là đối tác. 1 SĐT chỉ 1 tài khoản đối tác.
- **Kích hoạt bằng mã OTP gửi qua email** (`/doi-tac/xac-thuc`, không dùng SMS): mã 6 số gửi tới email đăng nhập, hiệu lực `LEADSCAN_OTP_TTL_MINUTES` (15 phút), chờ 60 giây giữa 2 lần gửi, tối đa 5 mã/giờ, 5 lần nhập sai/mã; DB chỉ lưu hash; đổi email thì mã cũ vô hiệu. Chưa xác thực thì không vào được cổng. SĐT chỉ để liên hệ, không xác thực.
  - Email gửi qua Resend/SMTP như các email khác. Chưa cấu hình gửi mail (máy dev) thì mã chỉ ghi vào log máy chủ. Đối tác không nhận được mã → nhân viên liên hệ đối chiếu rồi bấm **Kích hoạt tay** ở `/admin/doi-tac/<id>`.
  - Đối tác đã xác thực SĐT trước đây giữ nguyên trạng thái kích hoạt (migration `b7e3f9a1c2d4`).
- **Cổng đối tác**: Tổng quan, Tài khoản (đổi mật khẩu), Chính sách & hướng dẫn; quên/đặt lại mật khẩu qua email. Gửi cơ hội, ví, rút tiền: Mốc 2–4.
- **Quản trị `/admin/doi-tac`**: lọc chờ xác thực / đã kích hoạt / tạm khoá, tìm theo tên, mã `DT-…`, email, SĐT, MST; chi tiết có nhật ký (ai, khi nào, vì sao). Nhân viên: kích hoạt tay (xác nhận email), ghi chú. Quản trị viên: khoá (bắt buộc lý do, đăng xuất mọi phiên) / mở khoá, đổi hạng.
- **Gửi cơ hội** (`/doi-tac/gui-co-hoi`, Mốc 2): form theo brief mục 8.3 (doanh nghiệp/MST có tra cứu, khu vực, ngành, loại cơ hội, nhu cầu, quy mô, thời điểm, nguồn, độ chắc chắn, link chứng minh, người liên hệ kèm xác nhận đồng ý, cam kết). Chặn danh sách SĐT/email (dữ liệu cá nhân), tối đa `LEADSCAN_PARTNER_SUBMIT_PER_DAY` cơ hội/ngày, không gửi lại cơ hội mình đã gửi.
  - **Kiểm tra trùng tự động** trong `LEADSCAN_PARTNER_DUP_DAYS` ngày: theo MST, hoặc tên doanh nghiệp (bỏ dấu, bỏ "Công ty TNHH…") + tỉnh; so với phiếu cơ hội và cơ hội đối tác khác. Chỉ là gợi ý cho người duyệt — đối tác không thấy mình trùng với ai.
  - **Điểm chất lượng tự động** (theo quy tắc: MST, độ chi tiết, quy mô, thời điểm, độ chắc chắn, nguồn, bằng chứng, người liên hệ; trừ điểm khi nghi trùng). Người duyệt chốt điểm cuối; Đạt cần ≥ `LEADSCAN_PARTNER_MIN_SCORE` (60). Chưa dùng LLM.
  - **Cơ hội của tôi** (`/doi-tac/co-hoi`): trạng thái Đã gửi → Đang xác minh → Đạt / Trùng / Không đạt (lý do chuẩn hoá) / Đóng góp bổ sung → Đã xuất bản; email báo đối tác khi có kết quả.
- **Xác minh** (`/admin/xac-minh-doi-tac`): hàng đợi theo hạn SLA (`LEADSCAN_PARTNER_SLA_WORKDAYS` ngày làm việc), nhận/giao việc, nghi trùng, điểm, quyết định kèm ghi chú gửi đối tác + ghi chú nội bộ. Đổi quyết định đã đưa ra: chỉ quản trị viên, và chỉ khi chưa có phiếu.
  - **Tạo phiếu nháp** từ cơ hội Đạt: điền sẵn tiêu đề, tóm tắt (không lộ tên bên mua), chi tiết, đầu mối (nếu đồng ý), gắn `source_partner_id` / `source_submission_id` (thành viên không thấy). Mở bán phiếu ở trang Cơ hội & phiếu → cơ hội đối tác tự chuyển "Đã xuất bản" (listener `before_flush` trong `models.py`).
- **Ví hoa hồng** (Mốc 3, `/doi-tac/vi`, code `services/partner_wallet.py`): sổ ghi khoản LeadScan phải trả (bảng `partner_credits`) — không nạp, không chuyển. Số tiền mỗi khoản không sửa; thu hồi = khoản âm mới; số dư = tổng theo trạng thái (Chờ duyệt / Khả dụng). Đang rút / Đã rút: Mốc 4.
  - **Ly cafe**: Đạt xác minh → Chờ duyệt (trong hạn mức ly cafe/tháng theo hạng, tính theo tháng giờ VN); phiếu mở bán → Khả dụng. Vượt hạn mức: không có ly cafe trả trước nhưng vẫn chia doanh thu. Đóng góp bổ sung: 1 ly cafe, Khả dụng ngay. Đổi quyết định → huỷ ly cafe.
  - **Hoa hồng** (gắn trong `catalog.buy` / `catalog.refund`, cùng transaction, khoá dòng cơ hội đối tác): PA2 `max(0; tỷ lệ × doanh thu thuần lũy kế − tổng đã ghi kể cả ly cafe)` hoặc PA1 cộng dồn; giữ N ngày rồi Khả dụng (job `leadscan.partner_release_due` mỗi giờ + khi mở ví). Doanh thu thuần = điểm thực trả − phần hoàn, **tách thuế GTGT** theo `LEADSCAN_IAM_VAT_RATE`. Chỉ tính trong N tháng từ ngày xuất bản; **không tính** khi tài khoản mua trùng SĐT / email / MST với đối tác. Mỗi khoản lưu căn cứ tính (`calc`). Lỗi tính không chặn giao dịch của thành viên — ghi log + nhật ký "LỖI tính thưởng" để điều chỉnh tay.
  - **Hoàn phiếu** → thu hồi phần đã ghi vượt (không thu hồi ly cafe bảo đảm). **Gian lận** (nút trên trang xác minh, quản trị viên): huỷ khoản Chờ duyệt, thu hồi khoản Khả dụng kể cả ly cafe, khoá tài khoản.
  - **Cấu hình thưởng** `/admin/doi-tac/cau-hinh` (quản trị viên, có lịch sử): giá trị ly cafe, PA2/PA1, tỷ lệ theo hạng / cơ hội lớn / trần thoả thuận, hạn mức ly cafe theo hạng, số ngày giữ, số tháng chia sẻ. Áp dụng cho khoản ghi sau khi đổi. Landing, điều khoản, cổng đối tác hiển thị theo cấu hình (`GET /api/partner/reward-config`; landing làm mới tối đa 5 phút).
  - Chi tiết đối tác (admin): ví, lịch sử khoản ghi kèm căn cứ tính, **điều chỉnh tay** và **thoả thuận riêng** (tỷ lệ / hạn mức ly cafe cho hạng Chiến lược) — chỉ quản trị viên.
- **Rút tiền** (Mốc 4, `/doi-tac/rut-tien`, `/doi-tac/ho-so-thanh-toan`, code `services/partner_payouts.py`):
  - **Bắt buộc đặt `LEADSCAN_PARTNER_SECRET_KEY`** (khoá Fernet) trước khi mở: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Số định danh và số tài khoản mã hoá bằng khoá này — **mất khoá = không đọc lại được số tài khoản đã lưu**, sao lưu khoá cùng bí mật khác. Chưa đặt khoá → cổng báo "Rút tiền chưa được mở".
  - Hồ sơ thanh toán (chỉ cần khi rút lần đầu): họ tên, số định danh 12 số, MST (cá nhân không bắt buộc), ngân hàng, số tài khoản, tên chủ tài khoản — **phải trùng tên hồ sơ** (so sau khi bỏ dấu). Không thu ảnh CCCD. Cùng tài khoản ngân hàng với đối tác khác → cờ gian lận trong nhật ký + cảnh báo ở trang duyệt.
  - Lệnh rút: từ `min_withdraw` Khả dụng, mỗi lúc 1 lệnh, tối đa `max_withdrawals_month` lệnh/tháng; đối tác huỷ được khi còn Chờ duyệt. Số dư: Khả dụng = đã ghi khả dụng − Đang rút − Đã rút. Lệnh lưu ảnh chụp tài khoản lúc đặt (đổi hồ sơ sau đó không làm sai lệnh đang chi).
  - **Thuế TNCN** (cá nhân): lệnh từ `tax_threshold` (5.000.000đ) khấu trừ `tax_rate` (10%) — rút 6tr → thực nhận 5,4tr. Tổ chức: không khấu trừ, cần **số hoá đơn** trước khi vào lô chi. Báo cáo thuế theo tháng + nhập số chứng từ khấu trừ ở trang quản trị. ⚠ Kế toán cần xác nhận cách xác định "lần chi trả" theo Nghị định 253/2026.
  - Quản trị `/admin/rut-tien-doi-tac` (quản trị viên): duyệt / từ chối (lý do, tiền trở lại Khả dụng) → **lập lô** theo ngày chi (`payout_days`, mặc định 5 và 20) → **tải file chi CSV** (UTF-8 BOM, có số tài khoản đầy đủ, ghi nhật ký; cột mẫu chung — dán sang mẫu chi hộ của ngân hàng) → chuyển khoản → **đánh dấu đã chi** (mã giao dịch ngân hàng). Đối tác nhận email ở mỗi bước. Chưa kết nối API ngân hàng để chi tự động.
- **Ảnh gắn vào cơ hội gửi**: đối tác tải tối đa `LEADSCAN_PARTNER_ATTACH_MAX` (6) ảnh jpg/png/webp lên R2 (thư mục `partner-submissions/`; xoá EXIF/GPS, tạo ảnh nhỏ), sửa được khi cơ hội còn "Đã gửi"; admin xem ở trang xác minh; tạo phiếu từ cơ hội → **chép ảnh sang phiếu** (phần mở khoá sau khi mua). Ảnh tải lên mà không gửi cơ hội: xoá sau 24 giờ. Chưa cấu hình R2 → form nhắc dán link ảnh.
- **Lọc trùng theo nhu cầu** (`services/partner_dedup.py`): cùng doanh nghiệp (MST / tên) chỉ là điều kiện để so — kết luận theo độ giống mô tả nhu cầu (0.6 × ngữ nghĩa embedding + 0.4 × từ khoá, cùng sản phẩm +10, khác sản phẩm tối đa 25; không tính "thời điểm cần"): ≥ 70% **trùng nhu cầu** (nghi trùng, −30 điểm, đối tác không gửi lại được), 45–70% **gần giống** (−10), dưới 45% **nhu cầu khác** (không trừ điểm). Cùng tỉnh + ngành nhưng khác tên doanh nghiệp mà mô tả giống ≥ 80% → cảnh báo người duyệt (không chặn). Vector mô tả lưu ở `partner_submissions.embedding` (1 lần gọi Cohere mỗi lần gửi / sửa mô tả); vector của phiếu không bị ghi đè. Khoảng cosine Cohere: `LEADSCAN_PARTNER_DUP_COS_LOW/HIGH` (mặc định 0.45 / 0.85 — chỉnh theo dữ liệu thật).
- **Điều khoản `/doi-tac/dieu-khoan`**: bản dự thảo, chờ luật sư duyệt. Đổi nội dung → tăng `LEADSCAN_PARTNER_TERMS_VERSION` (lưu phiên bản đối tác đã đồng ý).
- Code: `backend/app/routes/partner.py`, `partner_auth.py`, `services/otp.py`, `routes/admin_partners.py`; `web/app/doi-tac/`, `web/components/partner/`.

## Cơ hội công khai (`/co-hoi`)

- **Ai cũng xem được** danh sách `/co-hoi` (lọc ngành, khu vực, tìm theo mặt hàng / mã) và chi tiết `/co-hoi/<mã CH-…>` — đúng phần thành viên thấy khi **chưa mua**: không có tên bên có nhu cầu, chi tiết, đầu mối, link nguồn, tệp (chỉ đếm số lượng), không có đối tác nguồn. Phiếu nháp không hiện. Có thẻ chia sẻ (Zalo / Facebook) và nút "Chia sẻ cơ hội này". API: `GET /api/public/opportunities[/<mã>]`.
- **Giá "từ"** = giá khi điểm phù hợp chưa vượt ngưỡng tăng giá; giá thật của mỗi thành viên tính theo điểm phù hợp riêng.
- **Mua**: chưa đăng nhập → hộp "Đăng ký thành viên" / "Đăng nhập", xong quay lại đúng cơ hội (`?mua=1` tự tiếp tục). Đã đăng nhập → `POST /api/member/opportunities/<id>/open-shared` thêm cơ hội vào "Tất cả cơ hội" + Kho của tôi (`user_opportunities.via_share`, so khớp lại không xoá), rồi mở trong cổng thành viên để mua như thường.
- Trang quản trị phiếu có nút **Trang công khai / Sao chép link** khi phiếu đang bán. Menu trang chủ có mục "Cơ hội".

## Kho doanh nghiệp (`/admin/kho-doanh-nghiep`)

Bảng `knowledge_companies` — danh sách doanh nghiệp làm đầu vào cho AI quét tìm cơ hội. Admin thêm / sửa / xoá, lọc theo trạng thái AI (Chờ quét · Đã quét · Lỗi · Bỏ qua), nguồn, tìm theo tên / MST / ngành / tỉnh.

Nạp dữ liệu từ bảng xếp hạng PROFIT500 (phần "Giới thiệu chung" của từng doanh nghiệp: tên, tên tiếng Anh, MST, mã CK, trụ sở, điện thoại, fax, email, website, năm thành lập, ngành nghề, CEO, đoạn giới thiệu, logo, hạng):

```bash
docker compose exec api python -m app.cli crawl-profit500 --chart 12 --year 2026
```

- `--chart`: 12 = Top 500 lợi nhuận tốt nhất, 13 = Top 500 tư nhân, 17 = Top 50 xuất sắc.
- Mặc định chỉ thêm doanh nghiệp mới (khớp theo mã doanh nghiệp tại nguồn, rồi theo MST); `--update` làm mới bản ghi đã có nhưng **giữ nguyên** trạng thái AI và ghi chú nội bộ.
- Đi chậm 1 giây/request (`--delay`), 500 doanh nghiệp mất khoảng 10 phút. Mỗi bản ghi lưu link nguồn — khi dùng lại thông tin cần ghi nguồn "Vietnam Report".

## Tuyển dụng (`/tuyen-dung`)

- **Trang công khai** `/tuyen-dung`: danh sách vị trí đang mở (lọc theo phòng ban), "Vì sao chọn LeadScan", quy trình 4 bước. `/tuyen-dung/<slug>`: mô tả đánh số 01–05 (mục tiêu, mô tả, yêu cầu, quyền lợi, cách ứng tuyển), cột "Thông tin chung", form ứng tuyển, JSON-LD `JobPosting` cho Google Jobs.
- **Form ứng tuyển**: họ tên, SĐT, email, link CV **hoặc** file CV (PDF/DOC/DOCX ≤ 5 MB), portfolio, giới thiệu ngắn. Chống spam: honeypot, thời gian điền tối thiểu, tối đa 5 hồ sơ/IP/giờ.
- **File CV lưu trên Cloudflare R2**, thư mục `CV/<năm-tháng>/<uuid>/<tên file>` (cùng bucket riêng tư `LEADSCAN_R2_*` với tệp phiếu cơ hội); DB chỉ giữ key. File đi qua backend để kiểm tra đúng PDF/DOC/DOCX rồi mới đẩy lên R2. Admin tải CV bằng link ký sẵn ngắn hạn; xoá hồ sơ thì xoá luôn file trên R2. Chưa cấu hình R2 → form chỉ nhận link CV.
- **Email**: mỗi hồ sơ gửi về `LEADSCAN_RECRUIT_EMAIL` (hoặc email riêng đặt trong từng bài; trống thì dùng `LEADSCAN_NOTIFY_EMAIL`), **đính kèm file CV** (lấy từ R2), Reply-To là email ứng viên → bấm Trả lời là liên hệ được ngay. Ứng viên nhận email xác nhận đã nhận hồ sơ.
- **Quản trị** `/admin/tuyen-dung`: đăng / sửa bài (Bản nháp → Đang tuyển → Đã đóng; tự ẩn khi quá hạn nộp), xem trước nội dung. `/admin/tuyen-dung/ho-so`: danh sách hồ sơ, tải CV, đổi trạng thái (Mới nhận → Đang xem xét → Hẹn phỏng vấn → Đã tuyển / Chưa phù hợp), ghi chú, gửi lại email khi lần gửi trước lỗi.
- Nội dung bài viết bằng định dạng nhẹ: `## ` tiêu đề nhóm, `- ` gạch đầu dòng, `1. ` danh sách số, `**đậm**`.
- Nginx: endpoint `/api/jobs/<slug>/apply` được nới `client_max_body_size 8m` (file CV gửi kèm) — cập nhật `deploy/nginx.conf` lên VPS.

## Tích hợp InfoCMS — cần hoàn tất khi có tài liệu

InfoCMS (Smart Collect của InfoPlus) chưa công bố tài liệu API công khai. Hệ thống đã làm sẵn:

1. VietQR chuẩn NAPAS tới tài khoản thu: điền `LEADSCAN_PAYMENT_BANK_BIN`, `..._ACCOUNT_NO`, `..._ACCOUNT_NAME`, `..._BANK_NAME`.
2. Webhook `POST https://<tên miền>/api/payments/infocms/webhook`, xác thực **HMAC-SHA256 trên body** với `LEADSCAN_INFOCMS_WEBHOOK_SECRET` (header `X-Signature`), đọc mã giao dịch / số tiền / nội dung chuyển khoản và tìm mã đơn `LSP…` trong nội dung. Giao dịch trùng không cộng điểm 2 lần; chuyển thiếu tiền không cộng và ghi chú để admin xử lý.

Khi InfoCMS gửi tài liệu (định dạng webhook, cách ký), chỉ cần chỉnh hàm `parse_infocms_webhook()` trong `backend/app/services/payments.py`. Trong lúc chờ, có thể đặt `LEADSCAN_PAYMENT_PROVIDER=mock` để chạy thử (có nút giả lập thanh toán) — **không dùng mock trên production**.

## Gửi email (Resend)

Các email hệ thống gửi:

| Khi nào | Gửi tới |
|---|---|
| Khách gửi form đăng ký | Quản trị (`LEADSCAN_NOTIFY_EMAIL`): báo đăng ký mới · Khách: email chào mừng + link đăng nhập, bước tiếp theo |
| Đơn phí thành viên / nạp điểm được ghi nhận (webhook, admin xác nhận tay) | Khách: kích hoạt thành viên / nạp điểm thành công, số dư, link xuất hoá đơn · Quản trị: đã nhận thanh toán |
| Khách gửi thông tin xuất hoá đơn | Kế toán (`LEADSCAN_INVOICE_EMAIL`) |
| Khách bấm "Quên mật khẩu" | Khách: link đặt lại mật khẩu (60 phút) |
| Ứng viên gửi hồ sơ trên /tuyen-dung | Tuyển dụng (`LEADSCAN_RECRUIT_EMAIL` hoặc email riêng của bài): hồ sơ + file CV đính kèm · Ứng viên: xác nhận đã nhận hồ sơ |

Email gửi qua [Resend](https://resend.com) bằng HTTP API.
Cấu hình `LEADSCAN_RESEND_API_KEY`, `LEADSCAN_NOTIFY_FROM` (vd `no-reply@mcv.network` — tên miền phải được xác minh trong Resend) và `LEADSCAN_MAIL_FROM_NAME`.
Không có Resend thì hệ thống dùng SMTP (`LEADSCAN_SMTP_*`). Gửi lỗi không làm hỏng thao tác của khách; admin thấy "Chưa gửi được" ở trang Hoá đơn và bấm gửi lại.

## Chạy trên máy dev

Cần Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 24. Redis tuỳ chọn (không có thì chỉ không gửi email nền).

```bash
cd backend && uv sync && uv run alembic upgrade head
```

```bash
cd backend && uv run python -m app.cli create-admin --email ban@congty.vn --name "Tên bạn"
```

```bash
cd backend && LEADSCAN_COOKIE_SECURE=false uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd web && npm install && npm run dev
```

Mở http://localhost:3000 (landing) và http://localhost:3000/admin (quản trị). Next.js chuyển tiếp `/api/*` sang backend cổng 8000. Cấu hình backend đặt trong `backend/.env` (các biến `LEADSCAN_*`, xem `.env.example`).

```bash
cd backend && uv run pytest
```

Chạy test trên PostgreSQL (giống production): đặt `LEADSCAN_TEST_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db_test` trước khi chạy pytest.

## Deploy lên VPS (Ubuntu)

> Hướng dẫn chi tiết từng bước (chuẩn bị VPS, DNS, deploy key, `.env`, HTTPS, Resend, sao lưu, xử lý sự cố): xem **[DEPLOY.md](DEPLOY.md)**. Dưới đây là bản tóm tắt.

Kiến trúc: **Nginx cài trên VPS** nhận cổng 80/443 (HTTPS bằng certbot) → chuyển `/api/*` vào container `api` (127.0.0.1:8012), còn lại vào container `web` (127.0.0.1:3012). Các container khác không mở cổng ra ngoài.

1. Cài Docker, Nginx, certbot; mở firewall cho SSH, 80, 443:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo apt install -y nginx certbot python3-certbot-nginx
   sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
   ```
2. Trỏ DNS `leadscan.net` (bản ghi A) về IP VPS.
3. Lấy code và tạo cấu hình:
   ```bash
   git clone <repo> leadscan && cd leadscan && cp .env.example .env
   ```
   Điền trong `.env`: `SITE_URL`, `LEADSCAN_ADMIN_URL`, `LEADSCAN_MEMBER_URL`, `POSTGRES_PASSWORD` (vd `openssl rand -hex 32`), `LEADSCAN_RESEND_API_KEY` để gửi email, và cấu hình thanh toán. Nếu VPS đã có ứng dụng khác chiếm cổng 8012/3012 thì đổi `API_PORT` / `WEB_PORT`.
4. Khởi động (migration chạy tự động mỗi lần deploy):
   ```bash
   docker compose up -d --build
   ```
5. Cấu hình Nginx + HTTPS (sửa `server_name` trong file nếu dùng tên miền khác, và 2 `upstream` nếu đã đổi cổng):
   ```bash
   sudo cp deploy/nginx.conf /etc/nginx/sites-available/leadscan.conf
   sudo ln -s /etc/nginx/sites-available/leadscan.conf /etc/nginx/sites-enabled/leadscan.conf
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d leadscan.net
   ```
   Certbot tự thêm chứng chỉ, chuyển hướng HTTP → HTTPS và tự gia hạn.
6. Tạo tài khoản quản trị đầu tiên:
   ```bash
   docker compose exec api python -m app.cli create-admin --email ban@congty.vn --name "Tên bạn"
   ```
7. Kiểm tra:
   ```bash
   docker compose exec api python -m app.cli diagnose
   ```

Cập nhật phiên bản mới: `git pull && docker compose up -d --build` (không cần đụng vào Nginx).

> **Lưu ý bảo mật:** cổng của `api`/`web` phải giữ dạng `127.0.0.1:...` trong `docker-compose.yml`. Docker tự mở firewall cho cổng nó publish (bỏ qua `ufw`), nên nếu bỏ `127.0.0.1` thì backend lộ ra Internet và khách có thể gửi `X-Real-IP` giả để lách giới hạn đăng nhập/đăng ký.

## Vận hành

| Việc | Lệnh |
|---|---|
| Tạo / đặt lại mật khẩu quản trị | `docker compose exec api python -m app.cli create-admin --email ...` |
| Gửi thử 1 email (kiểm tra Resend/SMTP) | `docker compose exec api python -m app.cli send-test-mail --to ban@gmail.com` |
| Chẩn đoán DB, Redis, email (Resend/SMTP) | `docker compose exec api python -m app.cli diagnose` |
| Quét PROFIT500 vào kho doanh nghiệp | `docker compose exec api python -m app.cli crawl-profit500 --chart 12 --year 2026` (thêm `--limit 20` để thử, `--update` để làm mới bản ghi đã có) |
| Nhập hồ sơ JSON từ bản PHP cũ | copy thư mục `storage/submissions` vào container rồi `python -m app.cli import-legacy <thư mục>` |
| Xem log | `docker compose logs -f api worker` |
| Sao lưu DB | `docker compose exec db pg_dump -U leadscan leadscan > backup.sql` |
