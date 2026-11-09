# Hướng dẫn deploy LeadScan lên VPS (từ đầu)

Triển khai thủ công, không dùng CI/CD: **máy bạn → GitHub → VPS**.

```
Máy bạn (Windows)            GitHub                       VPS (Ubuntu)
  sửa code
  git commit + push  ─────►  DoanThaiA/leadscan (main)
                                    │
                                    └──── git pull ◄─────  docker compose up -d --build
                                                           Nginx (80/443, HTTPS) → api / web
```

Trên VPS:

| Thành phần | Chạy ở đâu | Vai trò |
|---|---|---|
| Nginx + certbot | Cài thẳng trên VPS | Nhận 80/443, HTTPS, `/api/*` → api, còn lại → web |
| `api` | Docker, `127.0.0.1:8012` | FastAPI |
| `web` | Docker, `127.0.0.1:3012` | Next.js (landing, `/admin`, `/thanh-vien`) |
| `worker`, `beat` | Docker | Celery: gửi email nền, việc định kỳ |
| `db` | Docker | PostgreSQL 17 + pgvector (dữ liệu trong volume `pgdata`) |
| `redis` | Docker | Hàng đợi Celery |
| `migrate` | Docker, chạy xong tự thoát | Cập nhật cấu trúc DB mỗi lần deploy |

---

## Phần 0 — Chuẩn bị

- [ ] **VPS** Ubuntu 22.04 hoặc 24.04, tối thiểu **2 vCPU / 4 GB RAM / 40 GB ổ**, có IP public và quyền SSH (root hoặc user có `sudo`).
- [ ] **Tên miền** `leadscan.net`, có quyền sửa DNS.
- [ ] **Resend** (gửi email): tài khoản + API key, tên miền gửi đã xác minh (xem Phần 9).
- [ ] **Thông tin thanh toán**: tài khoản thu (BIDV `8600642866`) và tên chủ tài khoản.
- [ ] Code mới nhất đã ở trên GitHub nhánh `main`.

---

## Phần 1 — Đẩy code từ máy bạn lên GitHub

Chạy trong thư mục dự án trên máy bạn:

```bash
git status
```

```bash
git add -A && git commit -m "mô tả thay đổi" && git push origin main
```

> `.env` đã nằm trong `.gitignore` nên không bị đẩy lên. Không bao giờ commit mật khẩu, API key, khoá RSA.

---

## Phần 2 — Trỏ DNS về VPS

Vào trang quản lý DNS của tên miền, tạo bản ghi:

| Loại | Tên | Giá trị |
|---|---|---|
| A | `@` | IP của VPS |

Làm sớm vì DNS có thể mất vài phút đến vài giờ mới cập nhật. Kiểm tra từ máy bạn:

```bash
nslookup leadscan.net
```

---

## Phần 3 — Vào VPS và chuẩn bị máy

### 3.1. SSH vào VPS

```bash
ssh root@IP_VPS
```

### 3.2. (Khuyên dùng) Tạo user riêng, không chạy bằng root

Bỏ qua nếu nhà cung cấp đã cho sẵn user thường có `sudo` (vd `ubuntu`).

```bash
adduser deploy && usermod -aG sudo deploy
```

```bash
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Thoát ra và SSH lại bằng user mới:

```bash
ssh deploy@IP_VPS
```

Từ đây trở đi mọi lệnh chạy bằng user này.

### 3.3. Cập nhật hệ thống

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.4. Cài Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Cho user hiện tại dùng Docker không cần `sudo`:

```bash
sudo usermod -aG docker $USER && newgrp docker
```

Kiểm tra:

```bash
docker --version && docker compose version
```

### 3.5. Cài Nginx, certbot, git

```bash
sudo apt install -y nginx certbot python3-certbot-nginx git
```

### 3.6. Firewall: chỉ mở SSH, 80, 443

```bash
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
```

```bash
sudo ufw status
```

### 3.7. Swap (bắt buộc nếu RAM ≤ 2 GB, nên có với 4 GB)

Bước build Next.js tốn RAM; thiếu RAM thì build bị kill giữa chừng.

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3.8. Múi giờ (để log và backup đúng giờ Việt Nam)

```bash
sudo timedatectl set-timezone Asia/Ho_Chi_Minh
```

---

## Phần 4 — Lấy code về VPS

Repo là private nên VPS cần một **deploy key** (khoá SSH chỉ đọc, chỉ dùng cho repo này).

### 4.1. Tạo khoá trên VPS

```bash
ssh-keygen -t ed25519 -C "leadscan-vps" -f ~/.ssh/id_ed25519 -N ""
```

```bash
cat ~/.ssh/id_ed25519.pub
```

### 4.2. Thêm vào GitHub

GitHub → repo **DoanThaiA/leadscan** → **Settings** → **Deploy keys** → **Add deploy key**:
- Title: `VPS leadscan`
- Key: dán dòng vừa in ra (bắt đầu bằng `ssh-ed25519`)
- **Không** tick *Allow write access*

### 4.3. Clone

```bash
ssh -T git@github.com
```

(Gõ `yes` nếu được hỏi; thấy "successfully authenticated" là được.)

```bash
git clone git@github.com:DoanThaiA/leadscan.git ~/leadscan && cd ~/leadscan
```

---

## Phần 5 — Tạo file cấu hình `.env`

```bash
cd ~/leadscan && cp .env.example .env
```

Sinh mật khẩu DB:

```bash
openssl rand -hex 32
```

Mở file để sửa:

```bash
nano .env
```

(Lưu: `Ctrl+O` → Enter. Thoát: `Ctrl+X`.)

### Biến bắt buộc

| Biến | Điền gì |
|---|---|
| `POSTGRES_PASSWORD` | Chuỗi vừa sinh bằng `openssl`. **Đặt 1 lần, không đổi về sau** (DB đã khởi tạo bằng mật khẩu này) |
| `SITE_URL` | `https://leadscan.net` |
| `LEADSCAN_ALLOWED_HOSTS` | `["leadscan.net"]` |
| `LEADSCAN_COOKIE_SECURE` | `true` |
| `LEADSCAN_MAIL_MAILER` | `resend` |
| `LEADSCAN_RESEND_API_KEY` | API key Resend (`re_...`) |
| `LEADSCAN_NOTIFY_FROM` | Địa chỉ gửi, vd `no-reply@leadscan.net` — tên miền phải đã xác minh trên Resend |
| `LEADSCAN_MAIL_FROM_NAME` | Tên hiển thị người gửi, vd `LeadScan B2B` |
| `LEADSCAN_NOTIFY_EMAIL` | Email nhận báo khi có đăng ký mới (để trống = không gửi) |
| `LEADSCAN_ADMIN_URL` | `https://leadscan.net/admin` |
| `LEADSCAN_MEMBER_URL` | `https://leadscan.net/thanh-vien` |
| `LEADSCAN_INVOICE_EMAIL` | Email kế toán nhận yêu cầu xuất hoá đơn |

### Thanh toán

| Biến | Điền gì |
|---|---|
| `LEADSCAN_PAYMENT_PROVIDER` | `infocms` — **không để `mock` trên production** (mock có nút giả lập đã trả tiền) |
| `LEADSCAN_PAYMENT_BANK_BIN` | `970418` (BIDV) |
| `LEADSCAN_PAYMENT_BANK_NAME` | `BIDV` |
| `LEADSCAN_PAYMENT_ACCOUNT_NO` | `8600642866` |
| `LEADSCAN_PAYMENT_ACCOUNT_NAME` | Tên chủ tài khoản, VIẾT HOA KHÔNG DẤU |

> Hiện chưa tích hợp xong InfoCMS (QuickQR, chữ ký RSA). Trang thanh toán hiện QR tĩnh tới tài khoản trên, khách vẫn chuyển được tiền, nhưng **admin phải xác nhận tay** ở mục *Thanh toán* sau khi đối soát sao kê.

### So khớp cơ hội (Cohere)

| Biến | Điền gì |
|---|---|
| `COHERE_API_KEY` | Khoá API lấy ở https://dashboard.cohere.com/api-keys. Chỉ cần biến này — model (`embed-v5.0-pro` / `embed-v5.0-fast`, 1024 chiều) và endpoint đã cài sẵn |

> **Khoá Trial (miễn phí):** dùng được các model trên, không mất phí, nhưng tối đa **1.000 lần gọi/tháng** và **2.000 văn bản/phút**; Cohere **không cho dùng khoá Trial cho mục đích thương mại/production**. Hệ thống đếm lượt gọi (trang Tổng quan admin và lệnh `diagnose` hiện số đã dùng). Hết lượt → tới tháng sau so khớp chỉ dùng tiêu chí + từ khoá, không lỗi. Khi chuyển sang khoá Production, đặt `LEADSCAN_COHERE_MONTHLY_LIMIT=0`.
> Mỗi phiếu tìm hoặc phiếu cơ hội mới tốn khoảng 1 lượt; nhập file/`rematch` gộp 96 phiếu vào 1 lượt.
>
> Khi khách gửi phiếu tìm cơ hội, **worker** (Celery) nhúng mô tả bằng Cohere, lấy ứng viên gần nhất bằng pgvector rồi chấm điểm hybrid. Worker dừng thì phiếu sẽ đứng ở trạng thái "đang tìm".
> Lần đầu thêm khoá (hoặc sau khi đổi model): `docker compose exec api python -m app.cli rematch` để nhúng và so khớp lại toàn bộ.

### Biến tuỳ chọn

| Biến | Mặc định | Khi nào đổi |
|---|---|---|
| `API_PORT` / `WEB_PORT` | `8012` / `3012` | VPS đã có ứng dụng khác dùng cổng này (nhớ sửa `upstream` trong `deploy/nginx.conf`) |
| `LEADSCAN_MEMBERSHIP_FEE`, `..._POINTS`, `..._DAYS` | 10tr / 10tr điểm / 365 ngày | Đổi giá gói thành viên |
| `LEADSCAN_TOPUP_PACKS`, `LEADSCAN_TOPUP_MIN` | 5/10/20/50tr, tối thiểu 1tr | Đổi gói nạp |
| `LEADSCAN_ORDER_EXPIRE_HOURS` | 24 | Thời hạn đơn thanh toán |
| `LEADSCAN_COHERE_MONTHLY_LIMIT` | 1000 | Hạn mức lượt gọi Cohere/tháng (khoá Trial). Khoá Production: đặt `0` |
| `LEADSCAN_MATCH_MIN_FIT` | 35 | Điểm "khớp yêu cầu" tối thiểu (0–100) để cơ hội được xem là phù hợp |
| `LEADSCAN_COHERE_COS_LOW` / `..._HIGH` | 0.20 / 0.60 | Cosine Cohere quy ra 0 / 100 điểm ngữ nghĩa — chỉnh theo dữ liệu thật |
| `LEADSCAN_MATCH_CANDIDATES` | 500 | Số phiếu gần nhất (pgvector) đưa vào chấm điểm mỗi lần so khớp |

Bảo vệ file (chỉ user của bạn đọc được):

```bash
chmod 600 .env
```

---

## Phần 6 — Build và chạy

```bash
cd ~/leadscan && docker compose up -d --build
```

Lần đầu mất khoảng 5–10 phút (tải image, cài thư viện, build Next.js).

Kiểm tra trạng thái:

```bash
docker compose ps
```

Kết quả đúng:
- `db`, `redis`, `api`: `running (healthy)`
- `web`, `worker`, `beat`: `running`
- `migrate`: `exited (0)` — bình thường, nó chạy xong migration rồi thoát

Kiểm tra API và web từ chính VPS:

```bash
curl -s http://127.0.0.1:8012/api/health
```

```bash
curl -sI http://127.0.0.1:3012 | head -1
```

Lỗi thì xem log:

```bash
docker compose logs --tail=100 migrate api web
```

---

## Phần 7 — Nginx và HTTPS

### 7.1. Cài cấu hình Nginx

Nếu dùng tên miền khác `leadscan.net`, sửa `server_name` trong `deploy/nginx.conf` trước.

```bash
sudo cp ~/leadscan/deploy/nginx.conf /etc/nginx/sites-available/leadscan.conf
```

```bash
sudo ln -s /etc/nginx/sites-available/leadscan.conf /etc/nginx/sites-enabled/leadscan.conf
```

> Đặt tên file có đuôi **`.conf`**: nhiều VPS cấu hình `nginx.conf` chỉ nạp `sites-enabled/*.conf`
> (kiểm tra bằng `grep -n include /etc/nginx/nginx.conf`). Thiếu đuôi `.conf` thì Nginx bỏ qua file,
> certbot không tìm thấy block của tên miền và sẽ ghi chứng chỉ nhầm vào block mặc định.

VPS mới chưa có site nào khác thì tắt trang mặc định của Nginx:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Kiểm tra cú pháp và nạp lại:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Lúc này `http://leadscan.net` (chưa HTTPS) đã vào được trang chủ.

### 7.2. Bật HTTPS

DNS phải trỏ đúng về VPS trước (Phần 2).

```bash
sudo certbot --nginx -d leadscan.net
```

Certbot hỏi email (để báo khi chứng chỉ sắp hết hạn) và đồng ý điều khoản. Nó tự thêm chứng chỉ vào cấu hình Nginx, tự chuyển hướng HTTP → HTTPS và tự gia hạn.

Kiểm tra gia hạn tự động:

```bash
sudo certbot renew --dry-run
```

---

## Phần 8 — Tạo tài khoản quản trị đầu tiên

```bash
cd ~/leadscan && docker compose exec api python -m app.cli create-admin --email ban@congty.vn --name "Tên bạn"
```

Lệnh hỏi mật khẩu (tối thiểu 10 ký tự). Chạy lại cùng email = đặt lại mật khẩu.

---

## Phần 9 — Xác minh tên miền gửi email trên Resend

Không làm bước này thì email (đặt lại mật khẩu, hoá đơn, báo đăng ký) không gửi được.

1. Resend → **Domains** → **Add domain** → nhập tên miền của `LEADSCAN_NOTIFY_FROM` (vd `leadscan.net`).
2. Resend đưa ra vài bản ghi DNS (MX, TXT cho SPF, TXT cho DKIM). Thêm đúng từng bản ghi vào trang quản lý DNS.
3. Chờ Resend báo **Verified**.
4. **API Keys** → tạo key → điền vào `LEADSCAN_RESEND_API_KEY` trong `.env`, rồi:

```bash
cd ~/leadscan && docker compose up -d
```

---

## Phần 10 — Kiểm tra toàn bộ

```bash
cd ~/leadscan && docker compose exec api python -m app.cli diagnose
```

Mọi dòng phải là `[ OK ]` (DB, Redis, email).

Mở trình duyệt và thử:

- [ ] `https://leadscan.net` — trang chủ có ổ khoá HTTPS
- [ ] Gửi 1 đăng ký thử trên trang chủ → nhận email thông báo (nếu đặt `LEADSCAN_NOTIFY_EMAIL`)
- [ ] `https://leadscan.net/admin` — đăng nhập, thấy đăng ký vừa gửi
- [ ] `https://leadscan.net/thanh-vien` — đăng nhập bằng tài khoản vừa đăng ký
- [ ] Tạo đơn nạp tiền → trang thanh toán hiện QR BIDV đúng số tài khoản, số tiền, nội dung
- [ ] Quên mật khẩu → nhận được email đặt lại

Kiểm tra cổng nội bộ không lộ ra ngoài — chạy **từ máy bạn**, phải bị từ chối / hết thời gian:

```bash
curl -m 5 http://IP_VPS:8012/api/health
```

---

## Phần 11 — Sao lưu tự động

Tạo thư mục backup:

```bash
mkdir -p ~/backups
```

Mở crontab:

```bash
crontab -e
```

Thêm dòng sau (backup 2 giờ sáng mỗi ngày, giữ 14 ngày; đổi `/home/deploy` nếu user khác):

```
0 2 * * * cd /home/deploy/leadscan && docker compose exec -T db pg_dump -U leadscan leadscan | gzip > /home/deploy/backups/leadscan_$(date +\%F).sql.gz && find /home/deploy/backups -name '*.sql.gz' -mtime +14 -delete
```

Chạy thử backup ngay:

```bash
cd ~/leadscan && docker compose exec -T db pg_dump -U leadscan leadscan | gzip > ~/backups/leadscan_test.sql.gz && ls -lh ~/backups
```

> Backup chỉ nằm trên VPS thì mất VPS là mất luôn. Định kỳ tải về máy bạn hoặc đẩy sang nơi khác:
> ```bash
> scp deploy@IP_VPS:~/backups/leadscan_YYYY-MM-DD.sql.gz .
> ```

Khôi phục từ một bản backup (**ghi đè dữ liệu hiện tại**):

```bash
cd ~/leadscan && gunzip -c ~/backups/leadscan_YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U leadscan leadscan
```

---

## Phần 12 — Cập nhật phiên bản mới (lặp lại mỗi lần)

**1. Máy bạn:** đẩy code lên GitHub

```bash
git add -A && git commit -m "mô tả thay đổi" && git push origin main
```

**2. VPS:** (nên backup trước nếu thay đổi lớn hoặc có migration)

```bash
cd ~/leadscan && docker compose exec -T db pg_dump -U leadscan leadscan | gzip > ~/backups/truoc_cap_nhat_$(date +\%F_\%H\%M).sql.gz
```

```bash
cd ~/leadscan && git pull && docker compose up -d --build
```

Hoặc gộp 1 lệnh chạy từ máy bạn:

```bash
ssh deploy@IP_VPS "cd ~/leadscan && git pull && docker compose up -d --build"
```

`docker compose up -d --build` chỉ build lại phần thay đổi, tự chạy migration trước khi API khởi động lại, web gián đoạn vài giây.

**3. Nếu bản cập nhật ghi cần so khớp lại** (đổi thuật toán / model embedding): `docker compose exec api python -m app.cli rematch`.

**4. Nếu `.env.example` có biến mới:** thêm biến đó vào `.env` trên VPS rồi chạy lại `docker compose up -d`.

**5. Nếu `deploy/nginx.conf` thay đổi:** copy lại (giữ phần SSL certbot đã thêm — nên sửa tay file trong `/etc/nginx/sites-available/leadscan.conf` cho khớp thay vì ghi đè), rồi `sudo nginx -t && sudo systemctl reload nginx`.

Dọn image cũ cho đỡ đầy ổ (thỉnh thoảng):

```bash
docker image prune -f
```

> **Không sửa code trực tiếp trên VPS** — lần `git pull` sau sẽ xung đột. Mọi thay đổi sửa ở máy bạn rồi push.

---

## Phần 13 — Lệnh vận hành hay dùng

| Việc | Lệnh (chạy trong `~/leadscan`) |
|---|---|
| Xem trạng thái | `docker compose ps` |
| Xem log trực tiếp | `docker compose logs -f api worker web` |
| Khởi động lại 1 dịch vụ | `docker compose restart api` |
| Dừng toàn bộ | `docker compose down` (dữ liệu DB vẫn giữ trong volume) |
| Chạy lại toàn bộ | `docker compose up -d` |
| Tạo / đặt lại mật khẩu admin | `docker compose exec api python -m app.cli create-admin --email ...` |
| Chẩn đoán DB, Redis, email | `docker compose exec api python -m app.cli diagnose` |
| So khớp lại toàn bộ cơ hội ↔ phiếu tìm | `docker compose exec api python -m app.cli rematch` (thêm `--reembed` để gọi lại Cohere cho tất cả) |
| Vào DB bằng psql | `docker compose exec db psql -U leadscan leadscan` |
| Log Nginx | `sudo tail -f /var/log/nginx/error.log` |
| Dung lượng ổ | `df -h` và `docker system df` |

> **Không bao giờ chạy `docker compose down -v`** — `-v` xoá luôn volume, mất toàn bộ dữ liệu DB.

---

## Phần 14 — Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Build `web` bị dừng, log có `Killed` | Thiếu RAM | Tạo swap (3.7) rồi build lại |
| `migrate` exit khác 0, `api` không lên | Sai `POSTGRES_PASSWORD` hoặc lỗi migration | `docker compose logs migrate`. Nếu đã đổi mật khẩu sau lần chạy đầu: đặt lại mật khẩu cũ |
| `docker compose up` báo `Đặt POSTGRES_PASSWORD trong .env` | Chưa điền biến | Điền `POSTGRES_PASSWORD` trong `.env` |
| `port is already allocated` | Cổng 8012/3012 đã bị chiếm | Đổi `API_PORT`/`WEB_PORT` trong `.env` và `upstream` trong Nginx |
| `502 Bad Gateway` | Container `api`/`web` chưa chạy hoặc đang khởi động | `docker compose ps`, xem log; chờ 30 giây sau deploy |
| Certbot báo lỗi xác minh | DNS chưa trỏ về VPS, hoặc cổng 80 bị chặn | `nslookup` tên miền; `sudo ufw status` |
| Đăng nhập admin xong bị đá ra ngay | Truy cập qua HTTP trong khi `COOKIE_SECURE=true` | Truy cập bằng HTTPS (sau Phần 7.2) |
| Gửi form báo lỗi tên miền không hợp lệ | Tên miền chưa có trong `LEADSCAN_ALLOWED_HOSTS` | Thêm vào, `docker compose up -d` |
| Không nhận được email | Resend chưa xác minh tên miền / sai API key | `diagnose`; kiểm tra Phần 9; xem log `worker` |
| `git pull` báo `Permission denied (publickey)` | Deploy key chưa thêm hoặc sai | Làm lại Phần 4.2, thử `ssh -T git@github.com` |
