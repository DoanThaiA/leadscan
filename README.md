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
- **Kết nối AI (MCP)** (`/doi-tac/ket-noi-ai`, code `backend/app/routes/partner_mcp.py`): đối tác tạo URL kết nối `https://leadscan.net/api/mcp/lsm_…` rồi dán vào Claude (Connectors → Add custom connector) hoặc ChatGPT (Developer mode → Create, No authentication) để đăng & theo dõi cơ hội bằng lời. MCP Streamable HTTP không giữ phiên (mỗi POST 1 thông điệp JSON-RPC, trả JSON; GET → 405). 4 công cụ: `get_submission_guide`, `submit_opportunity` (dùng đúng `partner_submissions.normalize/create` như form: cùng kiểm tra, giới hạn/ngày, lọc trùng, chấm điểm; nhật ký ghi "qua kết nối AI"), `list_my_opportunities`, `get_opportunity`. Khoá nằm trong URL vì Claude.ai / ChatGPT không cho thêm header; ứng dụng nhận header dùng `/api/mcp` + `Authorization: Bearer lsm_…`. DB chỉ lưu sha256 (bảng `partner_mcp_tokens`), URL hiện 1 lần khi tạo, mỗi đối tác 1 URL còn hiệu lực (tạo mới = thu hồi cũ). URL không mở ví / hồ sơ thanh toán / rút tiền. Đối tác bị khoá → URL hết tác dụng.
- **Điều khoản `/doi-tac/dieu-khoan`**: bản dự thảo, chờ luật sư duyệt. Đổi nội dung → tăng `LEADSCAN_PARTNER_TERMS_VERSION` (lưu phiên bản đối tác đã đồng ý).
- Code: `backend/app/routes/partner.py`, `partner_auth.py`, `services/otp.py`, `routes/admin_partners.py`; `web/app/doi-tac/`, `web/components/partner/`.

## Cơ hội công khai (`/co-hoi`)

- **Ai cũng xem được** danh sách `/co-hoi` (lọc ngành, khu vực, tìm theo mặt hàng / mã) và chi tiết `/co-hoi/<mã CH-…>` — đúng phần thành viên thấy khi **chưa mua**: không có tên bên có nhu cầu, chi tiết, đầu mối, link nguồn, tệp (chỉ đếm số lượng), không có đối tác nguồn. Phiếu nháp không hiện. Có thẻ chia sẻ (Zalo / Facebook) và nút "Chia sẻ cơ hội này". API: `GET /api/public/opportunities[/<mã>]`.
- **Giá "từ"** = giá khi điểm phù hợp chưa vượt ngưỡng tăng giá; giá thật của mỗi thành viên tính theo điểm phù hợp riêng.
- **Mua**: chưa đăng nhập → hộp "Đăng ký thành viên" / "Đăng nhập", xong quay lại đúng cơ hội (`?mua=1` tự tiếp tục). Đã đăng nhập → `POST /api/member/opportunities/<id>/open-shared` thêm cơ hội vào "Tất cả cơ hội" + Kho của tôi (`user_opportunities.via_share`, so khớp lại không xoá), rồi mở trong cổng thành viên để mua như thường.
- Trang quản trị phiếu có nút **Trang công khai / Sao chép link** khi phiếu đang bán. Menu trang chủ có mục "Cơ hội".

## Quét PROFIT500 (vào phân hệ làm giàu theo MST)

"Kho doanh nghiệp" (`/admin/kho-doanh-nghiep`) **đã gộp** vào phân hệ làm giàu theo MST — đây là nơi duy nhất chứa doanh nghiệp; link cũ chuyển hướng về `/admin/lam-giau`. Crawler PROFIT500 ghi thẳng vào phân hệ, mỗi lượt quét là một lô (bắt buộc khai mục đích sử dụng):

```bash
docker compose exec api python -m app.cli crawl-profit500 --chart 12 --year 2026 --purposes ban_hang_b2b
```

- `--chart`: 12 = Top 500 lợi nhuận tốt nhất, 13 = Top 500 tư nhân, 17 = Top 50 xuất sắc. `--limit 20` để thử.
- Nguồn `profit500` (tin cậy 0,7 — trên nhập lô 0,5, dưới ĐKKD 0,95). Ghi: tên, tên tiếng Anh, địa chỉ / tỉnh, điện thoại, fax, email, website, ngành (→ nhóm ngành), năm thành lập, giới thiệu, mã CK + niêm yết, **xếp hạng** (tín hiệu "Xếp hạng"). **Không** lưu tên CEO (dữ liệu cá nhân) và logo. Doanh nghiệp không có MST bị bỏ qua (MST là khoá).
- Mặc định bỏ qua doanh nghiệp đã có bằng chứng PROFIT500 (không tải lại trang hồ sơ); `--update` tải lại — nội dung không đổi thì không sinh bằng chứng mới.
- Đi chậm 1 giây/request (`--delay`), 500 doanh nghiệp mất khoảng 10 phút. Mỗi bằng chứng trỏ về trang hồ sơ và ghi "Nguồn: Vietnam Report".

Bảng `knowledge_companies` của kho cũ đã chuyển sang phân hệ (501 doanh nghiệp, lô #4 và #5) rồi **xoá** ở migration `c4e1f7a9b3d2` — tên CEO, logo, trạng thái AI, ghi chú nội bộ của kho cũ không còn.

## Làm giàu dữ liệu theo MST (`/admin/lam-giau`) — Giai đoạn 1: nền dữ liệu

Theo tài liệu "Yêu cầu nghiệp vụ — Hệ thống làm giàu dữ liệu doanh nghiệp theo mã số thuế". MST là khoá của toàn hệ thống.

- **Hai kho tách biệt** (`backend/app/models_enrich.py`): PostgreSQL có 3 schema `kho_a` (doanh nghiệp), `kho_b` (dữ liệu cá nhân), `thu_thap` (lô, nguồn, bản gốc, hàng đợi). SQLite khi dev/test bỏ tên schema (`schema_translate_map` trong `app/db.py`).
- **Không ghi đè giá trị**: mỗi lần một nguồn nói một điều là một dòng bằng chứng (`enrich_company_evidence`). Cột trên hồ sơ chỉ là giá trị hiển thị do `app/enrich/merge.py` chọn (biên tập viên > độ tin cậy nguồn > mới hơn); đổi giá trị thì ghi `enrich_company_changes`. **Trường không có bằng chứng thì không hiển thị.**
- **Nhập lô MST** (`/admin/lam-giau/nhap-lo`): CSV hoặc .xlsx ≤ 10 MB, cột "MST" bắt buộc, "Tên doanh nghiệp" tuỳ chọn. Bấm *Kiểm tra file* để xem số dòng hợp lệ / trùng / sai định dạng trước khi nhập. MST 9 hoặc 12 số (Excel làm rơi số 0) được bù số 0 và báo riêng. Mỗi lô bắt buộc khai nguồn danh sách và **mục đích sử dụng được phép**; hồ sơ truy ngược được về lô + dòng trong file. 20.000 MST nhập mất khoảng 5 giây.
  - **Cột phụ nhận theo tiêu đề** (`EXTRA_HEADERS` trong `app/enrich/importer.py`, chỉ đọc sheet đầu): địa chỉ (tự tách tỉnh), tỉnh/thành, điện thoại, email, website, ngành nghề ĐKKD ("ngành nghề kinh doanh…"), **nhóm ngành** ("Ngành nghề" / "Nhóm ngành" trơn — phân loại của danh sách, không phải ngành ĐKKD), **nhóm sản phẩm**, **mã HS**, tình trạng, ngày thành lập, vốn. Mỗi giá trị là bằng chứng của nguồn *nhập lô* (tin cậy 0,5) → dữ liệu ĐKKD / nguồn chính thức nhập sau được ưu tiên hiển thị. Điện thoại / email chung vào bảng liên hệ doanh nghiệp (hiện ở hồ sơ, xuất được); số Excel đã đổi sang dạng khoa học (`8.4E+11`) hoặc thiếu mã vùng bị bỏ và liệt kê trong biên bản. Cột nhạy cảm (CCCD…) bị bỏ qua; cột không nhận ra chỉ nằm trong trích đoạn. Nhóm ngành / nhóm sản phẩm / mã HS lọc được ở Bộ lọc nâng cao và có trong cột xuất. Migration `a7b3c9d1e5f2`.
  - Nhận thêm tiêu đề: tên tiếng Anh, fax, năm thành lập, giới thiệu. Migration `b2c8d4e6f0a1`.
- **Hồ sơ doanh nghiệp** (`/admin/lam-giau/<MST>`): Thông tin pháp lý (mỗi trường kèm nguồn, đường dẫn, thời điểm, số bằng chứng, cờ xung đột) · Người liên quan · Tín hiệu · Lịch sử thay đổi · Nguồn gốc.
- **Vai trò** (gán ở trang Nhân viên, cột "Làm giàu theo MST"; quản trị viên mặc định là *Quản trị hệ thống*, nhân viên chưa gán thì không vào được phân hệ):

  | Vai trò | Kho A | Tên, chức danh, liên hệ công việc | MST cá nhân, năm sinh | Tra cứu thẳng kho B | Nhập lô |
  |---|---|---|---|---|---|
  | Quản trị hệ thống, Biên tập dữ liệu | ✓ | ✓ | ✓ | ✓ | ✓ |
  | Thẩm định / pháp chế | ✓ | ✓ | ✓ | ✓ | — |
  | Nhân viên kinh doanh | ✓ | ✓ (trong hồ sơ DN) | — | — | — |
  | Phân tích thị trường | ✓ | — | — | — | — |

- **Kho B chỉ đọc qua `app/enrich/khob.py`**: kiểm quyền, lọc trường theo vai trò, ẩn người / email / SĐT trong danh sách từ chối, và ghi `enrich_access_logs`. Nhật ký này **chỉ ghi thêm** — trigger trong CSDL chặn UPDATE/DELETE, nên tài khoản đã từng xem kho B chỉ khoá được, không xoá được.
- Kho B không có cột nào cho CCCD, hộ khẩu, tài khoản ngân hàng, sức khoẻ, quan hệ gia đình (`tests/test_enrich.py` kiểm tra).
- **Nginx**: endpoint nhập lô cần body lớn hơn mức 64 KB của `/api/` — xem block `location ~ ^/api/admin/enrich/batches` trong `deploy/nginx.conf`. Trên VPS đã chạy certbot, **chép riêng block này** vào `/etc/nginx/sites-available/leadscan.conf` (đặt trước `location /api/`) rồi `sudo nginx -t && sudo systemctl reload nginx` — đừng chép đè cả file vì sẽ mất phần HTTPS certbot đã thêm.

### Giai đoạn 2: nguồn chính thức và thu thập

- **Connector** (`backend/app/enrich/connectors/`): mỗi nguồn là một lớp độc lập — thêm nguồn = thêm lớp + đăng ký trong `registry.py`. Ba kiểu: *tự động* (http), *tra cứu thủ công* (nguồn có captcha — không bao giờ tự vượt), *nhập file*. Nguồn hiện có: dữ liệu mua ĐKKD (tin cậy 0,95), tra cứu Cổng ĐKKD và tra cứu người nộp thuế (thủ công), danh sách nợ thuế, kết quả đấu thầu (file). Cơ sở pháp lý từng nguồn là bản nháp — **pháp chế cần duyệt**; nguồn chưa khai cơ sở pháp lý không bật được.
- **Nhập nguồn chính thức** (`/admin/lam-giau/nhap-nguon`): file CSV/.xlsx, tự nhận cột theo tiêu đề (dòng tiêu đề có thể nằm dưới tên bảng). Chỉ ghi cho MST đã có trong hệ thống; cột CCCD / ngày sinh / địa chỉ cá nhân… bị bỏ qua và liệt kê trong biên bản. Dữ liệu ĐKKD sinh người đại diện pháp luật vào kho B (chỉ họ tên + chức danh).
- **Chuẩn hoá** (`normalize.py`, `titles.py`): tỉnh/thành theo 34 đơn vị sau 1/7/2025 (địa chỉ ghi tên tỉnh cũ vẫn tách đúng), loại hình doanh nghiệp, tình trạng hoạt động, điện thoại +84, tiền, ngày, website/tên miền, chức danh → danh mục cố định + cờ người ra quyết định.
- **Điểm tin cậy từng trường**: độ tin cậy nguồn được chọn + 0,05 mỗi nguồn khác đồng thuận (so không phân biệt hoa thường/dấu), × 0,7 khi quá hạn tái thu thập (hiện nhãn "Dữ liệu cũ").
- **Khử trùng**: cùng nội dung (mã băm trang / nội dung dòng file) chỉ sinh một bằng chứng; nhập lại cùng file không tạo gì mới.
- **Vòng thu thập** (`/admin/lam-giau/vong`, `app/enrich/runner.py`): mỗi MST × nguồn là một `CrawlJob` lưu trong CSDL → dừng/chạy lại không mất tiến độ, MST đang có việc mở không bị tạo trùng, việc bị bỏ dở > 30 phút tự trả về hàng đợi. Celery beat giao việc mỗi phút (`leadscan.enrich_dispatch`). Lỗi tạm thời thử lại lùi dần; quá số lần thì "Lỗi".
- **Giới hạn tốc độ**: mỗi request đặt lượt trên `enrich_domain_slots` (khoá dòng) → mọi worker cách nhau ≥ 2 giây/tên miền (cấu hình không cho thấp hơn); tôn trọng robots.txt; mỗi request ghi `enrich_fetch_logs` — trang Nguồn hiện khoảng cách nhỏ nhất theo tên miền làm bằng chứng.
- **Tự tạm dừng nguồn hỏng**: > 20% request lỗi trong 1 giờ (từ 10 request) → tắt nguồn, ghi lý do, email `LEADSCAN_NOTIFY_EMAIL`.
- **Dừng khẩn cấp / khung giờ chạy** ở trang Nguồn & cấu hình (quản trị hệ thống).
- **Bản gốc**: lưu gzip theo mã băm trên R2 (nếu đã cấu hình) hoặc `LEADSCAN_ENRICH_RAW_DIR` (mặc định `backend/data/enrich-raw`). Nút bóc tách lại (API `POST /api/admin/enrich/sources/{code}/reparse`) chạy lại bộ bóc tách trên bản gốc, không tải lại.
- **Hàng đợi thủ công** (`/admin/lam-giau/thu-cong`): mỗi lần một MST + nút mở trang tra cứu + form; giữ việc 15 phút cho người đang mở; "Bỏ qua" đẩy sang 24 giờ sau.
- Quyền mới: *Quản trị hệ thống* cấu hình nguồn, dừng khẩn cấp, tạo vòng; *Biên tập* nhập file nguồn và làm hàng đợi thủ công; *Thẩm định* xem vòng thu thập.
- Nginx: block nhập file lớn nay là `location ~ ^/api/admin/enrich/(batches|imports)(/preview)?$` — trên VPS sửa lại block đã chép ở giai đoạn 1.

### Giai đoạn 3: doanh nghiệp niêm yết (`/admin/lam-giau/niem-yet`)

- **Gắn mã CK**: nhập "Danh sách niêm yết (HOSE, HNX, UPCoM)" ở trang Nhập nguồn chính thức (cột Mã CK + Mã số thuế) → MST trong hệ thống được gắn `ma_ck`, `niem_yet`.
- **Nạp tài liệu công bố thông tin** (báo cáo tình hình quản trị, báo cáo thường niên, nghị quyết): tải file lên (.pdf / .html / .txt) hoặc khai danh sách đường dẫn (mỗi dòng: mã CK hoặc MST, URL, kỳ). Hệ thống **không tự dò cả trang công bố** — chỉ tải đúng đường dẫn được khai, qua cùng giới hạn tốc độ / robots.txt / nhật ký với connector tự động (Celery `leadscan.enrich_fetch_document`, giao việc trong `leadscan.enrich_dispatch`).
- **Bóc tách ba tầng** (`app/enrich/governance.py`): (1) bảng theo mẫu Phụ lục V Thông tư 96/2020/TT-BTC; (2) dòng "Ông/Bà … – chức danh" trong từng mục; (3) mô hình ngôn ngữ (`app/enrich/llm.py`) — **tắt mặc định**. Nhận được cả PDF bị mất dấu khi trích chữ. Ngày sinh, trình độ không bao giờ được đọc; ngày bổ nhiệm / miễn nhiệm được ghi vào vai trò (miễn nhiệm → `den_ngay`).
- **Bảo vệ dữ liệu**: mục "Danh sách người có liên quan / người nội bộ", "Giao dịch cổ phiếu của người nội bộ" và mọi thứ sau đó bị **cắt trước khi bóc tách** (kể cả trước khi gửi mô hình); bảng có cột CCCD / địa chỉ / quan hệ bị bỏ qua. Tài liệu + kết quả bóc tách nằm trong kho B; xem chi tiết hoặc bản gốc cần quyền xem bằng chứng kho B và luôn ghi nhật ký.
- **Tự ghi hay chờ duyệt**: đủ HĐQT + Ban điều hành (≥ 3 người) bằng bảng/luật → ghi luôn. Còn lại (thiếu nhóm, PDF ảnh, kết quả mô hình) → hàng chờ duyệt: biên tập viên sửa / thêm / bỏ người rồi duyệt; phần sửa / thêm ghi là quyết định biên tập (vòng sau không đè).
- **Tín hiệu bổ nhiệm**: tài liệu mới có người ra quyết định mới (so với các tài liệu trước của cùng doanh nghiệp) → tín hiệu "Bổ nhiệm" ở kho A (chỉ ghi chức danh, không ghi tên).
- **Độ phủ**: trang Niêm yết hiện tỷ lệ DN niêm yết có đủ HĐQT + Ban điều hành (mục tiêu ≥ 90%), lọc DN còn thiếu.
- **Mô hình ngôn ngữ (tuỳ chọn)**: `LEADSCAN_ENRICH_LLM_ENABLED=true` + `ANTHROPIC_API_KEY`. Mặc định `claude-opus-5-5` (`LEADSCAN_ENRICH_LLM_MODEL`), effort `low` (`LEADSCAN_ENRICH_LLM_EFFORT`), có fallback phía máy chủ khi model từ chối. Chỉ gửi văn bản đã cắt mục nhạy cảm, không gửi file gốc; kết quả lưu đệm theo mã băm nội dung (`kho_b.enrich_llm_cache`) và **luôn qua duyệt**. Gửi văn bản ra API nước ngoài là chuyển dữ liệu cá nhân xuyên biên giới — cần pháp chế đồng ý trước khi bật.
- Nginx: thêm `documents/upload` vào block upload lớn: `location ~ ^/api/admin/enrich/(batches|imports|documents/upload)(/preview)?$`.

### Giai đoạn 4: doanh nghiệp chưa niêm yết, người & quan hệ (`/admin/lam-giau/nguoi`)

- **Connector website** (`app/enrich/connectors/website.py`, mã `website`, tự động — **mặc định tắt**, quản trị bật ở trang Nguồn): chỉ tải website đã có trong hồ sơ (từ ĐKKD / tài liệu / nhập tay, không tìm qua Google), từ trang chủ đi tiếp tối đa `max_pages` (mặc định 5) trang **cùng website** có từ khoá giới thiệu / liên hệ / ban lãnh đạo; trang phụ bị robots.txt chặn thì bỏ qua. Bóc tách JSON-LD schema.org (tầng cấu trúc) rồi dòng "Ông/Bà … – chức danh", "Chức danh: Ông/Bà …", tên + chức danh ở dòng kế (tầng luật). Chỉ nhận người khi từ đầu là họ Việt Nam phổ biến; email chỉ nhận khi cùng tên miền doanh nghiệp, và chỉ gắn cho người khi nằm ngay cạnh tên **và** phần trước @ khớp tên — còn lại là liên hệ chung của doanh nghiệp.
- **Khớp người** (`app/enrich/people.py`, B06): MST cá nhân → cùng doanh nghiệp + cùng tên chuẩn hoá → hồ sơ mới. Cùng tên ở doanh nghiệp khác **không tự gộp**: tạo cặp "Nghi trùng" (điểm < 0,85) chờ biên tập viên chọn Gộp vào A / Gộp vào B / Hai người khác nhau. Chỉ tự gộp khi MST cá nhân chứng minh.
- **Gộp / tách có hoàn tác** (B07): gộp chuyển vai trò, liên hệ, bằng chứng sang hồ sơ giữ lại, hồ sơ kia ẩn (`merged_into_id`) chứ không xoá; tách chuyển các vai trò đã chọn sang hồ sơ mới cùng tên. Mọi thao tác ghi `kho_b.enrich_entity_ops` (ai, lúc nào, đã chuyển gì) và hoàn tác được; hai MST cá nhân khác nhau thì không gộp được.
- **Nhập MST cá nhân nội bộ**: file có MST cá nhân, Họ và tên, MST doanh nghiệp (tuỳ chọn Chức danh). Bắt buộc ghi nguồn và xác nhận **không mua từ bên thứ ba** (T03). MST cá nhân chỉ để khớp người, không bao giờ có trong bản xuất (T04).
- **Hồ sơ người** (C02) + **đồ thị quan hệ** (C03): vai trò hiện tại / trước đây ở các doanh nghiệp, đồ thị người ↔ doanh nghiệp ↔ người cùng doanh nghiệp, **xuất danh sách bên liên quan** (CSV, bắt buộc khai mục đích, không có MST cá nhân, email suy luận chỉ khi tick chọn). Nhân viên kinh doanh xem được hồ sơ + đồ thị (không MST cá nhân), không xuất được.
- **Suy luận email** (`app/enrich/emails.py`, B10/B11): học mẫu đặt tên (an.nguyen, annv, nguyenvanan…) từ email **thật** của người cùng tên miền; không có email thật → không suy luận. Tra **MX** của tên miền trước khi lưu (thư viện `dnspython`); không có MX / không tra được → không lưu. Chỉ cho người ra quyết định đang tại vị, bỏ người / email trong danh sách từ chối. Email suy luận luôn có cờ "Suy luận" + trạng thái `mx_ok` + bằng chứng ghi mẫu đã dùng. Chạy bằng nút "Suy luận email" (trang Người & quan hệ) hoặc API `POST /api/admin/enrich/emails/infer`.
- Quyền mới `people.manage` (Quản trị hệ thống, Biên tập): gộp / tách / hoàn tác, nhập MST cá nhân, suy luận email.
- Nginx: thêm `persons/import-mst` vào block upload lớn: `location ~ ^/api/admin/enrich/(batches|imports|documents/upload|persons/import-mst)(/preview)?$`.

### Giai đoạn 5: vận hành và tuân thủ

**Chạy tự động** (Celery beat — `app/enrich/scheduler.py`):

| Việc | Chu kỳ | Ghi chú |
|---|---|---|
| `enrich_dispatch` | 1 phút | giao việc thu thập + tải tài liệu |
| `enrich_recrawl` | mỗi ngày | A12: MST quá "Tái thu thập sau (ngày)" của từng nguồn tự động / thủ công đang bật → vòng mới (tối đa `daily_limit` MST/nguồn/ngày). Tra cứu ĐKKD mặc định **30 ngày** (mục tiêu phát hiện thay đổi trong 30 ngày), tra cứu NNT 30 ngày, nợ thuế / đấu thầu 7 ngày (nguồn file: trang Nguồn hiện nhắc nhập lại) |
| `enrich_alerts` | 10 phút | C06: thay đổi địa chỉ / tình trạng, tín hiệu nợ thuế / trúng thầu / bổ nhiệm, người ra quyết định thôi giữ chức → cảnh báo cho chủ danh sách theo dõi (chỉ thay đổi sau lúc bắt đầu theo dõi; nội dung không ghi tên người) |
| `enrich_digest` | mỗi giờ | email tổng hợp cảnh báo (danh sách bật email) |
| `enrich_raw_purge` | mỗi ngày | N07: xoá bản gốc quá `LEADSCAN_ENRICH_RAW_RETENTION_DAYS` (365); bằng chứng giữ lại |

- **Lọc nâng cao** (trang Hồ sơ doanh nghiệp → "Bộ lọc nâng cao", `app/enrich/search.py`): mọi trường, AND/OR (nhóm lồng qua API), biểu thức chính quy, trường dẫn xuất (có người ra quyết định, có tín hiệu trong N ngày, thuộc lô, được phép cho mục đích). 20.000 hồ sơ lọc dưới 2 giây (có test). **Lưu bộ lọc**, chia sẻ cho nhóm.
- **Xuất CSV** (`app/enrich/export.py`): bắt buộc khai mục đích; doanh nghiệp mà lô không cho phép mục đích đó bị **chặn** (cả bộ lọc bị chặn → từ chối xuất); cột kho B (người ra quyết định, email) chỉ cho Quản trị / Thẩm định — vai trò khác tự bị loại; **không bao giờ** có MST cá nhân; email suy luận chỉ khi tick; người / email / SĐT từ chối bị loại; dòng đầu file ghi mục đích + **hạn sử dụng** (`LEADSCAN_ENRICH_EXPORT_VALID_DAYS`, 90 ngày); mọi lần xuất (kể cả bị chặn) ghi `thu_thap.enrich_exports`. Phân tích thị trường chỉ xem / tải **Báo cáo thị trường** (số liệu tổng hợp).
- **Theo dõi & cảnh báo** (`/admin/lam-giau/canh-bao`): danh sách theo dõi (chọn loại cảnh báo, email tổng hợp, chia sẻ nhóm); thêm doanh nghiệp từ kết quả lọc ("Theo dõi kết quả").
- **Tuân thủ** (`/admin/lam-giau/tuan-thu`, Quản trị + Thẩm định / pháp chế): danh sách từ chối (C10); **yêu cầu của chủ thể dữ liệu** — tìm theo tên / email / MST cá nhân, "Dữ liệu đang lưu" (T06, tải JSON trả lời), **Ẩn vĩnh viễn** hoặc **Xoá** (T05: xoá vai trò, liên hệ, bằng chứng; email / SĐT vào danh sách từ chối; tên + doanh nghiệp và MST cá nhân lưu dạng **khoá băm** để không thu thập lại); rà soát hồ sơ không dùng 24 tháng (T07, `LEADSCAN_ENRICH_RETENTION_MONTHS`); nhật ký xuất (C09); nhật ký truy cập kho B (N06); **báo cáo đánh giá tác động** (T10, tải JSON).
- **Mã hoá** (N05, `app/enrich/crypto.py`): MST cá nhân lưu bằng **AES-SIV** (tất định — vẫn tìm bằng `==`, vẫn duy nhất); bản gốc trang / file nguồn nén rồi mã hoá **Fernet** trước khi ghi R2 / đĩa. Khoá: `LEADSCAN_ENRICH_DATA_KEY` — tạo bằng `docker compose exec api python -m app.cli gen-data-key`, đặt vào `.env` **trước khi có dữ liệu thật** và cất bản sao ở nơi khác (mất khoá = mất MST cá nhân và bản gốc). Thiếu khoá thì dùng khoá phát triển cố định (có cảnh báo trong log).
- **Sao lưu mã hoá** (N08): `deploy/backup.sh` (pg_dump → gzip → `openssl` AES-256 với `BACKUP_PASSPHRASE`, giữ `BACKUP_KEEP_DAYS` ngày, kèm volume bản gốc), cron 2:30 hằng ngày — cách cài ở đầu file. `deploy/restore-test.sh` phục hồi bản mới nhất vào CSDL tạm, đếm bảng chính, ghi `~/leadscan-restore-test.log` — chạy ít nhất mỗi quý. Hai script chưa chạy thử trên VPS thật.
- Quyền mới: `a.export` (Quản trị, Biên tập, Kinh doanh, Thẩm định), `b.export` (Quản trị, Thẩm định), `compliance.read` / `compliance.manage` (Quản trị, Thẩm định).

Chưa làm: tự dò đường dẫn tài liệu trên trang công bố HOSE / HNX / UBCKNN và connector tự động cho Cổng ĐKKD / nợ thuế / đấu thầu (cần khảo sát trang + pháp chế duyệt); xác minh email sâu hơn MX; tách quyền ở mức **tài khoản CSDL** cho kho B (hiện tách bằng schema + kiểm quyền ở ứng dụng); API nội bộ đọc theo MST (C12 — giai đoạn sau theo tài liệu); tích hợp CRM.

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
| Quét PROFIT500 vào phân hệ làm giàu MST | `docker compose exec api python -m app.cli crawl-profit500 --chart 12 --year 2026 --purposes ban_hang_b2b` (thêm `--limit 20` để thử, `--update` để tải lại DN đã có) |
| Nhập hồ sơ JSON từ bản PHP cũ | copy thư mục `storage/submissions` vào container rồi `python -m app.cli import-legacy <thư mục>` |
| Xem log | `docker compose logs -f api worker` |
| Sao lưu DB | `docker compose exec db pg_dump -U leadscan leadscan > backup.sql` |
