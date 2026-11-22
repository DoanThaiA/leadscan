# Thu thập cơ hội từ Gmail

Thư khách gửi vào Gmail được Apps Script đẩy sang LeadScan cứ 5 phút một lần. Hệ thống lọc sơ bộ, dùng AI đọc thư và trích JSON, rồi tạo **phiếu cơ hội nháp**. Admin duyệt ở **Quản trị → Cơ hội → Cơ hội từ email** trước khi mở bán.

```
Gmail ──(Apps Script, 5 phút)──► POST /api/webhooks/gmail ──► inbound_emails
                                   (chữ ký HMAC-SHA256)              │ worker
                                                                     ▼
            lọc sơ bộ (noreply, thư ngắn, người gửi bị chặn) → AI (Cohere Command A+, dự phòng deepseek-flash) → JSON
                                                                     ▼
        đúng lĩnh vực + chắc chắn → phiếu NHÁP  ·  không chắc → Cần xem lại  ·  không phải / ngành khác → Đã loại
```

- **Chỉ gửi thư mới.** Thư nhận trước lúc chạy `setup()` không bao giờ được gửi.
- Script chỉ đọc **Hộp thư đến**. Nó bỏ qua tab Quảng cáo, Mạng xã hội, Diễn đàn và thư do chính bạn gửi.
- Script **không sửa, không gắn nhãn, không xoá** thư nào trong Gmail.
- **Thư chuyển tiếp (forward)** được đọc cả phần thư gốc bên trong. AI lấy bên có nhu cầu và người liên hệ từ thư gốc, không lấy người chuyển tiếp.
- **Tệp đính kèm** được gửi cả nội dung, máy chủ đọc chữ trong tệp rồi đưa cho AI cùng thân thư:
  - Đọc được: PDF có lớp chữ, Word `.docx`, Excel `.xlsx`, PowerPoint `.pptx`, `.txt`/`.csv`, `.html`, và thư đính kèm `.eml` (kiểu "Chuyển tiếp dưới dạng tệp đính kèm", đọc cả tệp bên trong thư đó).
  - Chưa đọc được (chỉ hiện tên và lý do, mở Gmail để xem): ảnh, PDF scan, `.doc`/`.xls`/`.ppt` đời cũ, `.zip`, `.msg`.
  - Mỗi tệp tối đa 10 MB, tổng mỗi thư 15 MB; tệp vượt mức chỉ gửi tên. PDF chỉ đọc 30 trang đầu.

## 1. Máy chủ

1. Tạo khoá:
   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Đặt khoá vào `.env`:
   ```
   LEADSCAN_GMAIL_WEBHOOK_SECRET=<khoá vừa tạo>
   # Bật AI khi pháp chế đã đồng ý gửi nội dung thư ra API AI (cần COHERE_API_KEY và/hoặc DEEPSEEK_API_KEY):
   LEADSCAN_GMAIL_AI_ENABLED=true
   LEADSCAN_GMAIL_INDUSTRIES=["Bao bì & in ấn"]
   ```
3. Chạy migration và khởi động lại các dịch vụ:
   ```
   docker compose exec api alembic upgrade head
   docker compose restart api worker beat
   ```
4. Cập nhật Nginx (`deploy/nginx.conf` có `location = /api/webhooks/gmail`, cho phép body đến 25 MB vì thư kèm nội dung tệp đính kèm), rồi `nginx -s reload`.

Nếu AI đang tắt, thư qua được lọc sơ bộ vẫn vào tab **Cần xem lại**, và admin bấm **Tạo phiếu nháp** bằng tay.

## 2. Apps Script (trong tài khoản Gmail nhận thư)

1. Mở https://script.google.com, bằng đúng tài khoản Gmail nhận thư, rồi chọn **New project**. Đặt tên, ví dụ `LeadScan Gmail`.
2. Xoá nội dung mẫu, dán toàn bộ [`Code.gs`](Code.gs) vào và lưu.
3. Vào **Project Settings** (biểu tượng bánh răng), mục **Script Properties**, chọn **Add script property**:

   | Property | Value |
   |---|---|
   | `WEBHOOK_URL` | `https://leadscan.net/api/webhooks/gmail` |
   | `WEBHOOK_SECRET` | khoá ở bước 1.1 |

4. Quay lại Editor, chọn hàm `kiemTraKetNoi` và bấm **Run**.
   - Lần đầu Google sẽ hỏi quyền đọc Gmail và gọi URL bên ngoài. Màn hình "Google hasn't verified this app" là bình thường, vì đây là script của chính bạn: chọn **Advanced**, rồi **Go to … (unsafe)**, rồi **Allow**.
   - Log hiện `Kết nối OK` là đạt.
5. Chọn hàm `setup` và bấm **Run**. Script ghi lại mốc bắt đầu và tạo trigger chạy 5 phút một lần.

**Đã cài bản cũ (chỉ gửi tên tệp)?** Mở project Apps Script, dán đè toàn bộ `Code.gs` mới rồi lưu. Không cần chạy lại `setup()`: trigger dùng bản mới từ lượt chạy kế tiếp.

Kiểm tra: gửi một thư thử vào Gmail đó. Sau khoảng 5 phút, thư sẽ xuất hiện trong trang quản trị **Cơ hội từ email**.

### Dừng và bật lại

- Chạy `stop()` để dừng (xoá trigger).
- Chạy `setup()` để bật lại. Mốc `START_TS` được giữ nguyên, nên thư nhận trong lúc dừng sẽ được gửi bù.
- Muốn bỏ qua những thư nhận trong lúc dừng: xoá property `START_TS` và `CURSOR_TS` trước khi chạy `setup()`.

### Giới hạn của Gmail cá nhân

- Mỗi lần chạy tối đa 6 phút. Script gửi tối đa 30 thư mỗi lượt; thư còn lại được gửi ở lượt sau.
- Tổng thời gian trigger tối đa 90 phút mỗi ngày và khoảng 20.000 lượt gọi URL mỗi ngày, dư cho vài trăm thư một ngày.
- Xem lịch sử chạy và lỗi ở mục **Executions** trong Apps Script.

## 3. Duyệt trong trang quản trị

Trang **Quản trị → Cơ hội → Cơ hội từ email** gồm các tab sau:

| Tab | Ý nghĩa | Việc cần làm |
|---|---|---|
| Đã tạo nháp | AI chắc chắn là cơ hội đúng lĩnh vực, phiếu nháp đã tạo | Mở phiếu, kiểm tra, đặt giá, rồi mở bán |
| Cần xem lại | AI chưa chắc chắn, hoặc AI đang tắt | Bấm **Tạo phiếu nháp** hoặc **Loại** |
| Gộp vào phiếu có sẵn | Thư trả lời trong cùng luồng với thư đã có phiếu | Đọc thêm thông tin để bổ sung vào phiếu |
| Không phải cơ hội | AI loại: không phải nhu cầu mua, hoặc ngoài lĩnh vực | Thỉnh thoảng rà lại, loại nhầm thì bấm **Tạo phiếu nháp** |
| Bỏ qua | Lọc sơ bộ: noreply, thư quá ngắn, người gửi bị chặn | Không cần làm gì |
| Lỗi | AI lỗi | **Xử lý lại** |

- **Tiêu đề và tóm tắt** của phiếu hiện công khai cho người chưa mua, nên AI được dặn không ghi tên bên mua ở hai trường này. Admin vẫn cần kiểm tra lại trước khi mở bán.
- **Quyền riêng tư:** thư bị loại hoặc bỏ qua sẽ bị xoá nội dung sau 7 ngày (`LEADSCAN_GMAIL_BODY_KEEP_DAYS`), chỉ giữ người gửi, tiêu đề và lý do.
- **Chi phí AI** hiện ở đầu trang. Khi chạm trần `LEADSCAN_GMAIL_AI_BUDGET_USD` (mặc định 10 USD/tháng), thư nằm chờ tới tháng sau hoặc tới khi bạn nâng trần.
