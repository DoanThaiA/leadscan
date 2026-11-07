<?php
declare(strict_types=1);

/**
 * Chẩn đoán kết nối LeadScan → dev.mcv.network. CHỈ chạy bằng dòng lệnh (SSH):
 *   php api/diagnose.php
 * Không in mật khẩu / token. Bị chặn truy cập qua web bởi api/.htaccess.
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit;
}

require __DIR__ . '/lib.php';

function line(bool $ok, string $label, string $detail = ''): void
{
    echo ($ok ? '[ OK ] ' : '[LỖI] ') . $label . ($detail !== '' ? " — {$detail}" : '') . PHP_EOL;
}

line(PHP_VERSION_ID >= 80100, 'PHP ' . PHP_VERSION, 'cần 8.1 trở lên');
line(function_exists('curl_init'), 'Extension cURL');

try {
    $cfg = load_config();
    line(true, 'Đọc được file cấu hình');
} catch (Throwable $e) {
    line(false, 'Đọc file cấu hình', $e->getMessage());
    exit(1);
}

$base = rtrim((string)($cfg['mcv_base_url'] ?? ''), '/');
line($base !== '', 'mcv_base_url', $base);
line(($cfg['mcv_username'] ?? '') !== '' && ($cfg['mcv_password'] ?? '') !== '', 'Đã điền tài khoản dịch vụ (username/password)');

$host = (string)parse_url($base, PHP_URL_HOST);
$ip   = $host !== '' ? gethostbyname($host) : '';
line($ip !== '' && $ip !== $host, "Phân giải DNS {$host}", $ip);

// Có kết nối được tới API không (chưa cần đăng nhập)
try {
    [$code] = http_request('GET', $base . '/projects', ['Accept: application/json']);
    line(in_array($code, [200, 401, 403], true), 'Kết nối tới API', "HTTP {$code} (401 là bình thường khi chưa đăng nhập)");
    if ($code === 403) {
        echo "       → 403 có thể do máy chủ dev.mcv.network chặn IP của hosting này (firewall/allowlist).\n";
    }
} catch (Throwable $e) {
    line(false, 'Kết nối tới API', $e->getMessage());
    echo "       → Không tới được dev.mcv.network từ server này (DNS, firewall hoặc chặn IP).\n";
}

// Đăng nhập
try {
    mcv_token($cfg, true);
    line(true, 'Đăng nhập tài khoản dịch vụ');
} catch (Throwable $e) {
    line(false, 'Đăng nhập tài khoản dịch vụ', $e->getMessage());
}

// Quyền của tài khoản dịch vụ (cần tạo được khách hàng, dự án, người liên hệ)
try {
    [$st, $me] = mcv_call($cfg, 'GET', '/auth/me');
    if ($st === 200 && is_array($me)) {
        $perms = array_values(array_filter((array)($me['permissions'] ?? []), static fn($p) => preg_match('/customer|project/i', (string)$p)));
        $admin = !empty($me['is_system_admin']);
        line(true, 'Tài khoản: ' . ($me['username'] ?? $me['email'] ?? '?'), $admin ? 'quản trị hệ thống (đủ quyền)' : 'quyền liên quan: ' . ($perms ? implode(', ', $perms) : '(không có)'));
        if (!$admin) {
            $need = ['customer.create', 'project.create'];
            $missing = array_diff($need, $perms);
            if ($missing) {
                echo '       → Có thể thiếu quyền: ' . implode(', ', $missing) . " (tên quyền có thể khác, đối chiếu danh sách ở trên)\n";
            }
        }
    } else {
        line(false, 'Đọc thông tin tài khoản (/auth/me)', "HTTP {$st}");
    }
} catch (Throwable $e) {
    line(false, 'Đọc quyền tài khoản', $e->getMessage());
}

// Thư mục lưu trữ + hồ sơ tồn đọng
$dir = STORAGE_DIR . '/submissions';
line(is_dir(STORAGE_DIR) && is_writable(STORAGE_DIR), 'Thư mục storage/ ghi được');
$pending = 0;
foreach (glob($dir . '/LS-*.json') ?: [] as $f) {
    $r = read_json($f);
    if ($r && ($r['status'] ?? '') !== 'synced') {
        $pending++;
        echo "       · {$r['code']}: " . ($r['last_error'] ?? '(chưa thử đồng bộ)') . PHP_EOL;
    }
}
echo "Hồ sơ chưa đồng bộ: {$pending}" . PHP_EOL;
