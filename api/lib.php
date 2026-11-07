<?php
declare(strict_types=1);

/**
 * Thư viện dùng chung cho register.php và retry.php
 * - nạp cấu hình, lưu hồ sơ đăng ký, gọi API dev.mcv.network
 */

const STORAGE_DIR = __DIR__ . '/../storage';

function load_config(): array
{
    // Ưu tiên file nằm ngoài public_html (an toàn hơn), sau đó mới tới api/config.php
    $candidates = [
        dirname(__DIR__, 2) . '/leadscan-config.php',
        __DIR__ . '/config.php',
    ];
    foreach ($candidates as $f) {
        if (is_file($f)) {
            $cfg = require $f;
            if (is_array($cfg)) {
                return $cfg;
            }
        }
    }
    throw new RuntimeException('Chưa có file cấu hình (api/config.php).');
}

function ensure_dir(string $dir): void
{
    if (!is_dir($dir) && !mkdir($dir, 0750, true) && !is_dir($dir)) {
        throw new RuntimeException('Không tạo được thư mục lưu trữ.');
    }
}

/** Ghi JSON an toàn (khoá file, ghi nguyên tử) */
function write_json(string $path, array $data): void
{
    ensure_dir(dirname($path));
    $tmp = $path . '.' . bin2hex(random_bytes(4)) . '.tmp';
    $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    if ($json === false || file_put_contents($tmp, $json, LOCK_EX) === false || !rename($tmp, $path)) {
        @unlink($tmp);
        throw new RuntimeException('Không ghi được dữ liệu.');
    }
}

function read_json(string $path): ?array
{
    if (!is_file($path)) {
        return null;
    }
    $raw = file_get_contents($path);
    $data = $raw === false ? null : json_decode($raw, true);
    return is_array($data) ? $data : null;
}

/* ------------------------------------------------------------------ */
/* ADAPTER: chuyển hồ sơ đăng ký → dữ liệu tạo dự án trên dev.mcv.network */
/* Nếu API dự án có tên trường khác, chỉ cần sửa hàm này.               */
/* ------------------------------------------------------------------ */

function build_project_payload(array $d, string $code, string $key, array $cfg): array
{
    $line = static fn(string $label, ?string $v): string => ($v !== null && $v !== '') ? "- **{$label}:** {$v}\n" : '';
    $list = static fn(array $a): string => $a ? implode(', ', $a) : '';

    $desc  = "Khách hàng đăng ký thành viên LeadScan B2B — mã đăng ký **{$code}**.\n\n";
    $desc .= "## Doanh nghiệp\n";
    $desc .= $line('Tên doanh nghiệp', $d['company_name']);
    $desc .= $line('Mã số thuế', $d['tax_code']);
    $desc .= $line('Ngành hàng', $d['industry']);
    $desc .= $line('Quy mô', $d['company_size']);
    $desc .= $line('Tỉnh/thành', $d['province']);
    $desc .= $line('Website', $d['website']);
    $desc .= "\n## Người liên hệ\n";
    $desc .= $line('Họ tên', $d['contact_name']);
    $desc .= $line('Chức vụ', $d['position']);
    $desc .= $line('Email', $d['email']);
    $desc .= $line('Điện thoại/Zalo', $d['phone']);
    $desc .= "\n## Chân dung cơ hội mong muốn\n";
    $desc .= $line('Sản phẩm/dịch vụ cung cấp', $d['offering']);
    $desc .= $line('Khách hàng mục tiêu', $d['target_customers']);
    $desc .= $line('Khu vực ưu tiên', $list($d['target_regions']));
    $desc .= $line('Loại cơ hội quan tâm', $list($d['opp_types']));
    $desc .= $line('Dự kiến số phiếu/năm', $d['expected_tickets']);
    $desc .= $line('Ghi chú', $d['notes']);
    $desc .= "\n_Gói đăng ký: Thành viên 10.000.000đ/năm — trừ dần vào giá phiếu cơ hội đã mua._\n";

    $payload = [
        'key'         => $key,
        'name'        => mb_substr('LeadScan · ' . $d['company_name'], 0, 120),
        'description' => $desc,
    ];
    return array_merge($payload, $cfg['project_extra'] ?? []);
}

function new_project_key(array $cfg): string
{
    $alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    $s = '';
    for ($i = 0; $i < 4; $i++) {
        $s .= $alphabet[random_int(0, strlen($alphabet) - 1)];
    }
    return strtoupper((string)($cfg['key_prefix'] ?? 'LS')) . $s;
}

/* ------------------------------------------------------------------ */
/* Client HTTP cho dev.mcv.network                                      */
/* ------------------------------------------------------------------ */

function http_request(string $method, string $url, array $headers, $body = null): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST  => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 6,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_SSL_VERIFYHOST => 2,
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_FOLLOWLOCATION => false,
    ]);
    if ($body !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
    }
    $resp = curl_exec($ch);
    $err  = curl_error($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    if ($resp === false) {
        throw new RuntimeException('Không kết nối được dev.mcv.network: ' . $err);
    }
    return [$code, json_decode((string)$resp, true), (string)$resp];
}

function mcv_token(array $cfg, bool $force = false): string
{
    $cache = STORAGE_DIR . '/token.json';
    if (!$force) {
        $t = read_json($cache);
        if ($t && ($t['exp'] ?? 0) > time() && !empty($t['token'])) {
            return (string)$t['token'];
        }
    }
    if (($cfg['mcv_username'] ?? '') === '' || ($cfg['mcv_password'] ?? '') === '') {
        throw new RuntimeException('Chưa cấu hình tài khoản dịch vụ dev.mcv.network.');
    }
    [$code, $json] = http_request(
        'POST',
        rtrim($cfg['mcv_base_url'], '/') . '/auth/login',
        ['Content-Type: application/x-www-form-urlencoded', 'Accept: application/json'],
        http_build_query(['username' => $cfg['mcv_username'], 'password' => $cfg['mcv_password']])
    );
    if ($code !== 200 || empty($json['access_token'])) {
        throw new RuntimeException("Đăng nhập dev.mcv.network thất bại (HTTP {$code}).");
    }
    write_json($cache, ['token' => $json['access_token'], 'exp' => time() + 20 * 60]);
    return (string)$json['access_token'];
}

/**
 * Tạo dự án. Trả về mảng dự án từ API.
 * Tự đăng nhập lại khi token hết hạn, tự đổi mã key khi bị trùng.
 */
function mcv_create_project(array $cfg, array $d, string $code): array
{
    $base  = rtrim($cfg['mcv_base_url'], '/');
    $token = mcv_token($cfg);
    $key   = new_project_key($cfg);

    for ($attempt = 0; $attempt < 4; $attempt++) {
        $payload = build_project_payload($d, $code, $key, $cfg);
        [$status, $json, $raw] = http_request('POST', $base . '/projects', [
            'Authorization: Bearer ' . $token,
            'Content-Type: application/json',
            'Accept: application/json',
        ], json_encode($payload, JSON_UNESCAPED_UNICODE));

        if ($status === 401 && $attempt === 0) {
            $token = mcv_token($cfg, true);
            continue;
        }
        if ($status >= 200 && $status < 300 && is_array($json)) {
            return $json;
        }
        $keyClash = in_array($status, [409, 422], true) && stripos($raw, 'key') !== false;
        if ($keyClash && $attempt < 3) {
            $key = new_project_key($cfg);
            continue;
        }
        $detail = is_array($json) && isset($json['detail'])
            ? (is_string($json['detail']) ? $json['detail'] : json_encode($json['detail'], JSON_UNESCAPED_UNICODE))
            : mb_substr($raw, 0, 300);
        throw new RuntimeException("Tạo dự án thất bại (HTTP {$status}): {$detail}");
    }
    throw new RuntimeException('Tạo dự án thất bại sau nhiều lần thử.');
}

/** Đồng bộ 1 hồ sơ sang dev.mcv.network và cập nhật trạng thái */
function sync_submission(array $cfg, string $code): array
{
    $path = STORAGE_DIR . "/submissions/{$code}.json";
    $rec  = read_json($path);
    if (!$rec) {
        throw new RuntimeException("Không thấy hồ sơ {$code}.");
    }
    if (($rec['status'] ?? '') === 'synced') {
        return $rec;
    }
    $rec['attempts'] = (int)($rec['attempts'] ?? 0) + 1;
    try {
        $project = mcv_create_project($cfg, $rec['data'], $code);
        $rec['status']         = 'synced';
        $rec['project_id']     = $project['id'] ?? null;
        $rec['project_key']    = $project['key'] ?? null;
        $rec['synced_at']      = date('c');
        $rec['last_error']     = null;
    } catch (Throwable $e) {
        $rec['status']     = 'pending';
        $rec['last_error'] = $e->getMessage();
        $rec['last_try']   = date('c');
    }
    write_json($path, $rec);
    return $rec;
}
