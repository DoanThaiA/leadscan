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
  app/services/      payments.py (đơn & InfoCMS), vietqr.py (mã QR NAPAS), wallet.py (sổ cái điểm), catalog.py (mua phiếu)
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
- **Phí thành viên** 10.000.000đ → cộng **10.000.000 điểm** (1 điểm = 1đ), hiệu lực 365 ngày; gia hạn cộng dồn.
- **Nạp thêm điểm** (gói 5/10/20/50 triệu hoặc tuỳ chọn) — chỉ khi đang là thành viên.
- **Thanh toán qua InfoCMS (VietQR)**: mỗi đơn có mã riêng làm nội dung chuyển khoản; trang thanh toán hiện QR + số tài khoản, tự cập nhật khi InfoCMS báo đã nhận tiền.
- **Xuất hoá đơn**: sau khi thanh toán, khách nhập thông tin xuất hoá đơn → email gửi tới `LEADSCAN_INVOICE_EMAIL` (mặc định vylyy9999@gmail.com) để kế toán xuất thủ công; admin nhập số hoá đơn khi đã xuất.
- **Kho cơ hội**: lọc theo ngành, khu vực, nguồn, điểm; sắp xếp mới nhất / điểm / giá. Xem trước tóm tắt + điểm AI; tên bên có nhu cầu, chi tiết và đầu mối chỉ mở sau khi mua.
- **Mua phiếu**: trừ điểm, giới hạn số lượt bán (1 = độc quyền), không mua trùng; **phiếu đã mua** lưu lại đầy đủ; **yêu cầu enrich** thêm đầu mối.
- **Ví**: số dư, hạn thành viên, lịch sử điểm (sổ cái không sửa/xoá), đơn thanh toán & trạng thái hoá đơn. **Chân dung cơ hội** tự cập nhật.

Admin có thêm: **Cơ hội & phiếu** (nhập tay, định giá, mở bán), **Thanh toán** (xác nhận tay khi đã đối soát — dự phòng webhook), **Hoá đơn**, **Yêu cầu enrich**, và trong chi tiết khách hàng: **ví điểm, điều chỉnh điểm, tài khoản đăng nhập**.

## Tích hợp InfoCMS — cần hoàn tất khi có tài liệu

InfoCMS (Smart Collect của InfoPlus) chưa công bố tài liệu API công khai. Hệ thống đã làm sẵn:

1. VietQR chuẩn NAPAS tới tài khoản thu: điền `LEADSCAN_PAYMENT_BANK_BIN`, `..._ACCOUNT_NO`, `..._ACCOUNT_NAME`, `..._BANK_NAME`.
2. Webhook `POST https://<tên miền>/api/payments/infocms/webhook`, xác thực **HMAC-SHA256 trên body** với `LEADSCAN_INFOCMS_WEBHOOK_SECRET` (header `X-Signature`), đọc mã giao dịch / số tiền / nội dung chuyển khoản và tìm mã đơn `LSP…` trong nội dung. Giao dịch trùng không cộng điểm 2 lần; chuyển thiếu tiền không cộng và ghi chú để admin xử lý.

Khi InfoCMS gửi tài liệu (định dạng webhook, cách ký), chỉ cần chỉnh hàm `parse_infocms_webhook()` trong `backend/app/services/payments.py`. Trong lúc chờ, có thể đặt `LEADSCAN_PAYMENT_PROVIDER=mock` để chạy thử (có nút giả lập thanh toán) — **không dùng mock trên production**.

## Gửi email (Resend)

Email (yêu cầu xuất hoá đơn → kế toán, đặt lại mật khẩu, báo đăng ký mới) gửi qua [Resend](https://resend.com) bằng HTTP API.
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
2. Trỏ DNS `leadscan.net` và `www.leadscan.net` (bản ghi A) về IP VPS.
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
   sudo cp deploy/nginx.conf /etc/nginx/sites-available/leadscan
   sudo ln -s /etc/nginx/sites-available/leadscan /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d leadscan.net -d www.leadscan.net
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
| Chẩn đoán DB, Redis, email (Resend/SMTP) | `docker compose exec api python -m app.cli diagnose` |
| Nhập hồ sơ JSON từ bản PHP cũ | copy thư mục `storage/submissions` vào container rồi `python -m app.cli import-legacy <thư mục>` |
| Xem log | `docker compose logs -f api worker` |
| Sao lưu DB | `docker compose exec db pg_dump -U leadscan leadscan > backup.sql` |
