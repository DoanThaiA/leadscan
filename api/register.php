<?php
declare(strict_types=1);

/**
 * POST /api/register.php  (JSON)
 * Nhận form đăng ký thành viên → lưu hồ sơ → tạo 1 dự án trên dev.mcv.network.
 * Nếu dev.mcv.network tạm lỗi, hồ sơ vẫn được lưu và retry.php sẽ gửi lại sau.
 */

require __DIR__ . '/lib.php';

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

function respond(int $status, array $body): never
{
    http_response_code($status);
    echo json_encode($body, JSON_UNESCAPED_UNICODE);
    exit;
}

function fail(int $status, string $message, array $fields = []): never
{
    respond($status, ['ok' => false, 'message' => $message, 'fields' => $fields]);
}

function str(mixed $v, int $max): string
{
    if (!is_string($v)) {
        return '';
    }
    $v = trim(preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', $v) ?? '');
    return mb_substr($v, 0, $max);
}

/** Chỉ giữ giá trị nằm trong danh sách cho phép */
function pick_list(mixed $v, array $allowed): array
{
    if (!is_array($v)) {
        return [];
    }
    return array_values(array_intersect($allowed, array_map('strval', $v)));
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    fail(405, 'Phương thức không được hỗ trợ.');
}

try {
    $cfg = load_config();
} catch (Throwable $e) {
    error_log('[leadscan] ' . $e->getMessage());
    fail(500, 'Hệ thống chưa sẵn sàng. Vui lòng thử lại sau.');
}

/* --- Chống gửi chéo trang --- */
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin !== '') {
    $host    = strtolower((string)parse_url($origin, PHP_URL_HOST));
    $allowed = array_map('strtolower', $cfg['allowed_hosts'] ?? []);
    $self    = strtolower(explode(':', $_SERVER['HTTP_HOST'] ?? '')[0]);
    if ($host !== $self && !in_array($host, $allowed, true)) {
        fail(403, 'Yêu cầu không hợp lệ.');
    }
}

/* --- Đọc dữ liệu --- */
$raw = file_get_contents('php://input', false, null, 0, 65536);
$in  = json_decode($raw ?: '', true);
if (!is_array($in)) {
    fail(400, 'Dữ liệu gửi lên không hợp lệ.');
}

/* --- Honeypot + thời gian điền form (bot thường gửi < 3 giây) --- */
if (str($in['website_url'] ?? '', 50) !== '') {
    respond(200, ['ok' => true, 'code' => 'LS-' . date('Ymd') . '-0000']); // giả vờ thành công
}
$elapsed = (int)($in['elapsed_ms'] ?? 0);
if ($elapsed > 0 && $elapsed < 3000) {
    fail(429, 'Bạn thao tác quá nhanh, vui lòng thử lại.');
}

/* --- Giới hạn tần suất theo IP --- */
$ip    = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
$rlDir = STORAGE_DIR . '/rate';
ensure_dir($rlDir);
$rlFile = $rlDir . '/' . sha1($ip) . '.json';
$rl     = read_json($rlFile) ?? ['hits' => []];
$now    = time();
$rl['hits'] = array_values(array_filter($rl['hits'], static fn($t) => $t > $now - 3600));
if (count($rl['hits']) >= (int)($cfg['rate_limit_per_hour'] ?? 5)) {
    fail(429, 'Bạn đã gửi quá nhiều lần. Vui lòng thử lại sau ít phút.');
}

/* --- Chuẩn hoá & kiểm tra --- */
$REGIONS = ['Miền Bắc', 'Miền Trung', 'Miền Nam', 'Toàn quốc', 'Quốc tế'];
$OPPS    = ['Đăng mua (App đăng mua)', 'Dự án & gói thầu', 'Nhà máy / dự án FDI mới', 'Hội chợ & triển lãm', 'Mạng xã hội & nhóm chat', 'Nguồn chính thống (Trang vàng, Bộ Công Thương, Công báo)'];
$SIZES   = ['Dưới 10 nhân sự', '10–49 nhân sự', '50–199 nhân sự', '200–499 nhân sự', 'Từ 500 nhân sự'];
$TICKETS = ['Dưới 50 phiếu', '50–200 phiếu', '200–1.000 phiếu', 'Trên 1.000 phiếu', 'Chưa xác định'];

$d = [
    'company_name'     => str($in['company_name'] ?? '', 150),
    'tax_code'         => preg_replace('/[^0-9\-]/', '', str($in['tax_code'] ?? '', 20)) ?? '',
    'industry'         => str($in['industry'] ?? '', 100),
    'company_size'     => str($in['company_size'] ?? '', 40),
    'province'         => str($in['province'] ?? '', 80),
    'website'          => str($in['website'] ?? '', 200),
    'contact_name'     => str($in['contact_name'] ?? '', 100),
    'position'         => str($in['position'] ?? '', 100),
    'email'            => strtolower(str($in['email'] ?? '', 150)),
    'phone'            => preg_replace('/[\s.\-()]/', '', str($in['phone'] ?? '', 20)) ?? '',
    'offering'         => str($in['offering'] ?? '', 1000),
    'target_customers' => str($in['target_customers'] ?? '', 1000),
    'target_regions'   => pick_list($in['target_regions'] ?? [], $REGIONS),
    'opp_types'        => pick_list($in['opp_types'] ?? [], $OPPS),
    'expected_tickets' => in_array($in['expected_tickets'] ?? '', $TICKETS, true) ? $in['expected_tickets'] : '',
    'notes'            => str($in['notes'] ?? '', 1000),
];

$errors = [];
$need = static function (string $f, string $msg) use (&$errors, $d): void {
    if ($d[$f] === '') {
        $errors[$f] = $msg;
    }
};
$need('company_name', 'Vui lòng nhập tên doanh nghiệp.');
$need('industry', 'Vui lòng nhập ngành hàng.');
$need('province', 'Vui lòng nhập tỉnh/thành.');
$need('contact_name', 'Vui lòng nhập họ tên người liên hệ.');
$need('offering', 'Vui lòng mô tả sản phẩm/dịch vụ của bạn.');
$need('target_customers', 'Vui lòng mô tả khách hàng mục tiêu.');
if (!in_array($d['company_size'], $SIZES, true)) {
    $errors['company_size'] = 'Vui lòng chọn quy mô.';
}
if (!preg_match('/^\d{10}(-?\d{3})?$/', $d['tax_code'])) {
    $errors['tax_code'] = 'Mã số thuế gồm 10 hoặc 13 chữ số.';
}
if (!filter_var($d['email'], FILTER_VALIDATE_EMAIL)) {
    $errors['email'] = 'Email chưa đúng định dạng.';
}
if (!preg_match('/^(0|\+84)\d{9,10}$/', $d['phone'])) {
    $errors['phone'] = 'Số điện thoại chưa đúng định dạng.';
}
if ($d['website'] !== '') {
    $w = preg_match('#^https?://#i', $d['website']) ? $d['website'] : 'https://' . $d['website'];
    if (!filter_var($w, FILTER_VALIDATE_URL)) {
        $errors['website'] = 'Website chưa đúng định dạng.';
    } else {
        $d['website'] = $w;
    }
}
if (empty($in['agree'])) {
    $errors['agree'] = 'Bạn cần đồng ý điều khoản để tiếp tục.';
}
if ($errors) {
    fail(422, 'Vui lòng kiểm tra lại thông tin.', $errors);
}

/* --- Chống đăng ký trùng mã số thuế --- */
$indexFile = STORAGE_DIR . '/tax_index.json';
$lockFile  = STORAGE_DIR . '/.lock';
ensure_dir(STORAGE_DIR);
$lock = fopen($lockFile, 'c');
if ($lock === false || !flock($lock, LOCK_EX)) {
    fail(500, 'Hệ thống bận, vui lòng thử lại.');
}
try {
    $index = read_json($indexFile) ?? [];
    $taxKey = preg_replace('/\D/', '', $d['tax_code']);
    if (isset($index[$taxKey])) {
        fail(409, 'Mã số thuế này đã được đăng ký. Nếu cần hỗ trợ, vui lòng liên hệ LeadScan.', ['tax_code' => 'Mã số thuế đã được đăng ký.']);
    }

    $code = sprintf('LS-%s-%s', date('Ymd'), strtoupper(bin2hex(random_bytes(2))));
    write_json(STORAGE_DIR . "/submissions/{$code}.json", [
        'code'       => $code,
        'status'     => 'pending',
        'created_at' => date('c'),
        'ip'         => $ip,
        'data'       => $d,
        'attempts'   => 0,
    ]);
    $index[$taxKey] = $code;
    write_json($indexFile, $index);

    $rl['hits'][] = $now;
    write_json($rlFile, $rl);
} finally {
    flock($lock, LOCK_UN);
    fclose($lock);
}

/* --- Tạo dự án trên dev.mcv.network (lỗi không làm mất hồ sơ) --- */
$rec = sync_submission($cfg, $code);
if (($rec['status'] ?? '') !== 'synced') {
    error_log("[leadscan] {$code} chưa đồng bộ: " . ($rec['last_error'] ?? ''));
}

/* --- Báo email cho quản trị (tuỳ chọn) --- */
if (!empty($cfg['notify_email'])) {
    $subject = '=?UTF-8?B?' . base64_encode("[LeadScan] Đăng ký mới: {$d['company_name']} ({$code})") . '?=';
    $body = "Mã đăng ký: {$code}\nDoanh nghiệp: {$d['company_name']}\nMST: {$d['tax_code']}\n"
          . "Liên hệ: {$d['contact_name']} - {$d['phone']} - {$d['email']}\n"
          . 'Dự án: ' . (($rec['status'] ?? '') === 'synced' ? ($rec['project_key'] ?? 'đã tạo') : 'CHƯA tạo được (sẽ tự thử lại)') . "\n";
    $headers = 'From: ' . ($cfg['notify_from'] ?? 'no-reply@leadscan.net') . "\r\nContent-Type: text/plain; charset=UTF-8";
    @mail((string)$cfg['notify_email'], $subject, $body, $headers);
}

respond(200, ['ok' => true, 'code' => $code]);
