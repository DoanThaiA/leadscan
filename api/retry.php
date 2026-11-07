<?php
declare(strict_types=1);

/**
 * Gửi lại các hồ sơ đăng ký chưa tạo được dự án trên dev.mcv.network.
 * CHỈ chạy bằng dòng lệnh / cron (bị chặn truy cập qua web bởi api/.htaccess).
 *
 * Cron gợi ý trên Hostinger (mỗi 15 phút):
 *   php /home/<user>/domains/leadscan.net/public_html/api/retry.php
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit;
}

require __DIR__ . '/lib.php';

$cfg   = load_config();
$files = glob(STORAGE_DIR . '/submissions/LS-*.json') ?: [];
$done = $failed = 0;

foreach ($files as $f) {
    $rec = read_json($f);
    if (!$rec || ($rec['status'] ?? '') !== 'pending') {
        continue;
    }
    if (($rec['attempts'] ?? 0) >= 20) {
        continue; // quá nhiều lần thất bại — cần xử lý thủ công
    }
    $res = sync_submission($cfg, (string)$rec['code']);
    if (($res['status'] ?? '') === 'synced') {
        $done++;
        echo "OK   {$rec['code']} → " . ($res['project_key'] ?? '?') . PHP_EOL;
    } else {
        $failed++;
        echo "FAIL {$rec['code']}: " . ($res['last_error'] ?? '') . PHP_EOL;
    }
}
echo "Xong: {$done} thành công, {$failed} lỗi." . PHP_EOL;
