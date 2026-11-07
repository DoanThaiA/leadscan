<?php
declare(strict_types=1);

/**
 * Thư viện dùng chung cho register.php, retry.php, diagnose.php
 * Luồng đồng bộ mỗi hồ sơ đăng ký sang dev.mcv.network:
 *   1) tạo KHÁCH HÀNG  (POST /customers)
 *   2) tạo DỰ ÁN gắn khách hàng đó  (POST /projects, customer_id)
 *   3) tạo NGƯỜI LIÊN HỆ chính của khách  (POST /customers/{id}/contacts)
 * Mỗi bước được ghi nhớ trong hồ sơ nên retry sẽ chạy tiếp từ bước còn dang dở,
 * không tạo trùng khách hàng/dự án.
 */

date_default_timezone_set('Asia/Ho_Chi_Minh');

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

/* ================================================================== */
/* ADAPTER: map hồ sơ đăng ký → dữ liệu khách hàng / dự án / liên hệ   */
/* Chỉ dùng văn bản thuần (không Markdown) vì ô Mô tả/Ghi chú hiển thị */
/* nguyên văn. Nếu API đổi tên trường, chỉ cần sửa các hàm dưới đây.   */
/* ================================================================== */

/** Ghép "Nhãn: giá trị" từng dòng, bỏ qua mục trống */
function plain_rows(array $rows): string
{
    $out = [];
    foreach ($rows as $label => $value) {
        $v = is_array($value) ? implode(', ', $value) : trim((string)$value);
        if ($v !== '') {
            $out[] = "{$label}: {$v}";
        }
    }
    return implode("\n", $out);
}

function build_customer_payload(array $d, string $code): array
{
    $address = $d['province'];
    if (($d['address'] ?? '') !== '' && mb_stripos($d['address'], $d['province']) === false) {
        $address = $d['address'] . ', ' . $d['province'];   // chưa có tỉnh/thành trong địa chỉ thì ghép thêm
    } elseif (($d['address'] ?? '') !== '') {
        $address = $d['address'];
    }

    $contact = $d['contact_name'] . ($d['position'] !== '' ? ' (' . $d['position'] . ')' : '');
    $note = plain_rows([
        'Nguồn'           => 'Đăng ký thành viên trên LeadScan B2B',
        'Mã đăng ký'      => $code,
        'Thời gian'       => date('d/m/Y H:i'),
        'Ngành hàng'      => $d['industry'],
        'Quy mô nhân sự'  => $d['company_size'],
        'Tỉnh/thành'      => $d['province'],
        'Người liên hệ'   => $contact,
        'Gói đăng ký'     => 'Thành viên 10.000.000đ/năm, trừ dần vào phiếu cơ hội đã mua',
    ]);

    return [
        'code'     => $code,                 // "Mã khách hàng" là trường bắt buộc
        'name'     => $d['company_name'],
        'tax_code' => $d['tax_code'],
        'email'    => $d['email'],
        'phone'    => $d['phone'],
        'address'  => $address,
        'website'  => $d['website'] !== '' ? $d['website'] : null,
        'note'     => $note,
    ];
}

function build_contact_payload(array $d): array
{
    return [
        'full_name'  => $d['contact_name'],
        'position'   => $d['position'] !== '' ? $d['position'] : null,
        'email'      => $d['email'],
        'phone'      => $d['phone'],
        'is_primary' => true,
    ];
}

/** Mô tả dự án = phần "Chân dung cơ hội bạn muốn tìm" của form, văn bản thuần */
function build_project_description(array $d): string
{
    $blocks = ['CHÂN DUNG CƠ HỘI MUỐN TÌM'];

    if ($d['offering'] !== '') {
        $blocks[] = "Sản phẩm/dịch vụ cung cấp:\n" . $d['offering'];
    }
    if ($d['target_customers'] !== '') {
        $blocks[] = "Khách hàng mục tiêu:\n" . $d['target_customers'];
    }
    $prefs = plain_rows([
        'Khu vực ưu tiên'           => $d['target_regions'],
        'Loại cơ hội quan tâm'      => $d['opp_types'],
        'Dự kiến số phiếu mua/năm'  => $d['expected_tickets'],
    ]);
    if ($prefs !== '') {
        $blocks[] = $prefs;
    }
    if ($d['notes'] !== '') {
        $blocks[] = "Ghi chú thêm:\n" . $d['notes'];
    }
    return implode("\n\n", $blocks);
}

function build_project_payload(array $d, string $key, int $customerId, array $cfg): array
{
    $payload = [
        'key'                 => $key,
        'name'                => mb_substr('LeadScan - ' . $d['company_name'], 0, 120),
        'description'         => build_project_description($d),
        'customer_id'         => $customerId,
        'product_owner_id'    => null,
        'scrum_master_id'     => null,
        'status'              => 'planning',
        'start_date'          => null,
        'end_date'            => null,
        'sprint_duration_days'=> 14,
        'budget_hours'        => null,
    ];
    // Cho phép ghi đè/ bổ sung từ config, ví dụ product_owner_id
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

/* ================================================================== */
/* Client HTTP cho dev.mcv.network                                      */
/* ================================================================== */

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

/** Rút gọn thông báo lỗi từ API (FastAPI trả về trường "detail") */
function mcv_error_text($json, string $raw): string
{
    if (is_array($json) && isset($json['detail'])) {
        return is_string($json['detail'])
            ? $json['detail']
            : (string)json_encode($json['detail'], JSON_UNESCAPED_UNICODE);
    }
    return mb_substr($raw, 0, 300);
}

/**
 * Gọi API có xác thực. Trả về [http_status, json, raw].
 * Tự đăng nhập lại 1 lần nếu token hết hạn (401).
 */
function mcv_call(array $cfg, string $method, string $path, ?array $payload = null): array
{
    $url = rtrim($cfg['mcv_base_url'], '/') . $path;
    for ($try = 0; $try < 2; $try++) {
        $token = mcv_token($cfg, $try > 0);
        $res = http_request($method, $url, [
            'Authorization: Bearer ' . $token,
            'Content-Type: application/json',
            'Accept: application/json',
        ], $payload === null ? null : json_encode($payload, JSON_UNESCAPED_UNICODE));
        if ($res[0] !== 401) {
            return $res;
        }
    }
    return $res;
}

function mcv_ok(int $status): bool
{
    return $status >= 200 && $status < 300;
}

function mcv_create_customer(array $cfg, array $d, string $code): array
{
    [$status, $json, $raw] = mcv_call($cfg, 'POST', '/customers', build_customer_payload($d, $code));
    if (!mcv_ok($status) || !is_array($json) || empty($json['id'])) {
        throw new RuntimeException("Tạo khách hàng thất bại (HTTP {$status}): " . mcv_error_text($json, $raw));
    }
    return $json;
}

function mcv_create_project(array $cfg, array $d, int $customerId): array
{
    $key = new_project_key($cfg);
    for ($attempt = 0; $attempt < 4; $attempt++) {
        [$status, $json, $raw] = mcv_call($cfg, 'POST', '/projects', build_project_payload($d, $key, $customerId, $cfg));
        if (mcv_ok($status) && is_array($json) && !empty($json['id'])) {
            return $json;
        }
        // Trùng mã dự án → sinh mã khác rồi thử lại
        if (in_array($status, [409, 422], true) && stripos($raw, 'key') !== false && $attempt < 3) {
            $key = new_project_key($cfg);
            continue;
        }
        throw new RuntimeException("Tạo dự án thất bại (HTTP {$status}): " . mcv_error_text($json, $raw));
    }
    throw new RuntimeException('Tạo dự án thất bại sau nhiều lần thử.');
}

function mcv_create_contact(array $cfg, array $d, int $customerId): array
{
    [$status, $json, $raw] = mcv_call($cfg, 'POST', "/customers/{$customerId}/contacts", build_contact_payload($d));
    if (!mcv_ok($status) || !is_array($json)) {
        throw new RuntimeException("Tạo người liên hệ thất bại (HTTP {$status}): " . mcv_error_text($json, $raw));
    }
    return $json;
}

/**
 * Đồng bộ 1 hồ sơ sang dev.mcv.network: khách hàng → dự án → người liên hệ.
 * Lưu tiến độ sau từng bước; status = 'synced' khi cả 3 bước xong.
 */
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
    $d = $rec['data'];
    $d['address'] = $d['address'] ?? '';
    $rec['attempts'] = (int)($rec['attempts'] ?? 0) + 1;

    try {
        if (empty($rec['customer_id'])) {
            $c = mcv_create_customer($cfg, $d, $code);
            $rec['customer_id'] = (int)$c['id'];
            write_json($path, $rec);
        }
        if (empty($rec['project_id'])) {
            $p = mcv_create_project($cfg, $d, (int)$rec['customer_id']);
            $rec['project_id']  = (int)$p['id'];
            $rec['project_key'] = $p['key'] ?? null;
            write_json($path, $rec);
        }
        if (empty($rec['contact_done'])) {
            mcv_create_contact($cfg, $d, (int)$rec['customer_id']);
            $rec['contact_done'] = true;
        }
        $rec['status']     = 'synced';
        $rec['synced_at']  = date('c');
        $rec['last_error'] = null;
    } catch (Throwable $e) {
        $rec['status']     = 'pending';
        $rec['last_error'] = $e->getMessage();
        $rec['last_try']   = date('c');
    }
    write_json($path, $rec);
    return $rec;
}
