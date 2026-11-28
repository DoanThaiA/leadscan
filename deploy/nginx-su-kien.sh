#!/usr/bin/env bash
# Cập nhật Nginx đang chạy trên VPS cho trang sự kiện (cho tải profile PDF / ảnh chuyển khoản tới 20 MB).
#
#   sudo bash deploy/nginx-su-kien.sh                        # file mặc định /etc/nginx/sites-available/leadscan.conf
#   sudo bash deploy/nginx-su-kien.sh /duong/dan/file.conf   # file cấu hình khác
#
# Chỉ chèn / thay các khối "location" của sự kiện (lấy từ deploy/nginx.conf) ngay trước "location /api/";
# KHÔNG ghi đè cả file nên phần HTTPS do certbot thêm vẫn giữ nguyên. Có sao lưu, `nginx -t` lỗi thì trả lại
# file cũ. Chạy lại nhiều lần vẫn được.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)/nginx.conf"
CONF="${1:-/etc/nginx/sites-available/leadscan.conf}"

if [ ! -f "$CONF" ]; then
  echo "Không thấy $CONF. Tìm file đang chạy bằng:  grep -rl leadscan_api /etc/nginx/" >&2
  exit 1
fi

# Sao lưu ngoài sites-enabled để Nginx không nạp nhầm bản sao
BACKUP="${BACKUP_DIR:-/var/tmp}/$(basename "$CONF").$(date +%Y%m%d-%H%M%S).bak"
cp -p "$CONF" "$BACKUP"

python3 - "$SRC" "$CONF" <<'PY'
import io, re, sys

src = io.open(sys.argv[1], encoding="utf-8").read()
path = sys.argv[2]
conf = io.open(path, encoding="utf-8").read()

# Khối location của sự kiện (kèm dòng chú thích phía trên); các khối này không có ngoặc nhọn lồng nhau
BLOCK = re.compile(r"(?:^[ \t]*#[^\n]*\n)*^[ \t]*location ~ \^/api/(?:events|admin/event-registrations)/[^\n]*\{\n[^{}]*?^[ \t]*\}\n\n?", re.M)

blocks = [m.group(0).rstrip("\n") for m in BLOCK.finditer(src)]
if len(blocks) != 3:
    sys.exit(f"deploy/nginx.conf phải có 3 khối sự kiện, thấy {len(blocks)}.")

conf = BLOCK.sub("", conf)  # bỏ bản cũ (nếu đã chèn trước đó)
anchor = re.compile(r"(?:^[ \t]*#[^\n]*\n)*^[ \t]*location /api/ \{", re.M)
if not anchor.search(conf):
    sys.exit(f"Không thấy 'location /api/' trong {path} — hãy chép tay 3 khối sự kiện từ deploy/nginx.conf.")
insert = "\n\n".join(blocks) + "\n\n"
conf = anchor.sub(lambda m: insert + m.group(0), conf)  # mọi khối server có /api/
io.open(path, "w", encoding="utf-8").write(conf)
PY

if nginx -t; then
  systemctl reload nginx
  echo "Xong: Nginx đã nhận tệp sự kiện tới 20 MB. Bản cấu hình cũ: $BACKUP"
else
  cp -p "$BACKUP" "$CONF"
  echo "nginx -t báo lỗi → đã trả lại cấu hình cũ, chưa thay đổi gì." >&2
  exit 1
fi
