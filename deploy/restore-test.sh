#!/usr/bin/env bash
# Phục hồi thử bản sao lưu mới nhất vào một CSDL tạm rồi kiểm tra (N08: ít nhất mỗi quý một lần). Không đụng CSDL thật.
#   ./deploy/restore-test.sh                 # bản mới nhất trong BACKUP_DIR
#   ./deploy/restore-test.sh <file.enc>      # một bản cụ thể
# Ghi kết quả vào ~/leadscan-restore-test.log để làm bằng chứng nghiệm thu.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
: "${BACKUP_PASSPHRASE:?Đặt BACKUP_PASSPHRASE trong .env}"
DIR="${BACKUP_DIR:-/var/backups/leadscan}"
FILE="${1:-$(ls -1t "$DIR"/leadscan-*.sql.gz.enc | head -1)}"
[ -f "$FILE" ] || { echo "Không thấy bản sao lưu"; exit 1; }
sha256sum -c "$FILE.sha256"

TMPDB="restore_test_$(date +%s)"
docker compose exec -T db psql -U leadscan -d postgres -c "CREATE DATABASE $TMPDB" >/dev/null
trap 'docker compose exec -T db psql -U leadscan -d postgres -c "DROP DATABASE IF EXISTS $TMPDB" >/dev/null' EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE -in "$FILE" \
  | gunzip \
  | docker compose exec -T db psql -q -U leadscan -d "$TMPDB" -v ON_ERROR_STOP=1 >/dev/null

COUNTS="$(docker compose exec -T db psql -At -U leadscan -d "$TMPDB" -c "
  SELECT 'doanh_nghiep=' || (SELECT count(*) FROM kho_a.enrich_companies)
      || ' nguoi=' || (SELECT count(*) FROM kho_b.enrich_persons)
      || ' nhat_ky_kho_b=' || (SELECT count(*) FROM kho_b.enrich_access_logs)
      || ' khach_hang=' || (SELECT count(*) FROM public.companies)")"
echo "$(date -Is) phục hồi thử OK: $(basename "$FILE") → $COUNTS" | tee -a ~/leadscan-restore-test.log
