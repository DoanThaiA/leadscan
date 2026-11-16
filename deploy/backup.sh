#!/usr/bin/env bash
# Sao lưu CSDL LeadScan hằng ngày, MÃ HOÁ (N05, N08).
#
# Cài một lần trên VPS (chạy 2:30 sáng mỗi ngày):
#   chmod +x ~/leadscan/deploy/backup.sh
#   (crontab -l 2>/dev/null; echo "30 2 * * * cd ~/leadscan && ./deploy/backup.sh >> ~/leadscan-backup.log 2>&1") | crontab -
#
# Cần trong ~/leadscan/.env:
#   BACKUP_PASSPHRASE=<chuỗi dài ngẫu nhiên — cất ở nơi khác VPS; mất = không giải mã được bản sao lưu>
#   BACKUP_DIR=/var/backups/leadscan      (tuỳ chọn)
#   BACKUP_KEEP_DAYS=30                   (tuỳ chọn)
# Nên chép thư mục BACKUP_DIR sang nơi khác (rclone sang R2 / máy khác) — sao lưu cùng máy không chống được mất VPS.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

: "${BACKUP_PASSPHRASE:?Đặt BACKUP_PASSPHRASE trong .env}"
DIR="${BACKUP_DIR:-/var/backups/leadscan}"
KEEP="${BACKUP_KEEP_DAYS:-30}"
mkdir -p "$DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DIR/leadscan-$STAMP.sql.gz.enc"

# pg_dump chạy trong container db; nén rồi mã hoá AES-256 (khoá dẫn xuất PBKDF2 từ passphrase) — file trên đĩa không đọc được nếu thiếu passphrase
docker compose exec -T db pg_dump -U leadscan -d leadscan --no-owner --format=plain \
  | gzip -9 \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE -out "$OUT"
sha256sum "$OUT" > "$OUT.sha256"
echo "$(date -Is) đã sao lưu $(du -h "$OUT" | cut -f1) → $OUT"

# volume bản gốc làm giàu MST (khi không dùng R2) — các file trong đó đã được ứng dụng mã hoá sẵn
if docker volume inspect leadscan_enrichraw >/dev/null 2>&1; then
  docker run --rm -v leadscan_enrichraw:/data:ro -v "$DIR":/backup alpine \
    tar -czf "/backup/enrich-raw-$STAMP.tar.gz" -C /data .
fi

find "$DIR" -name 'leadscan-*.sql.gz.enc*' -mtime +"$KEEP" -delete
find "$DIR" -name 'enrich-raw-*.tar.gz' -mtime +"$KEEP" -delete
