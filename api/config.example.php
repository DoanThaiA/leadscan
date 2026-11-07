<?php
/**
 * CẤU HÌNH LEADSCAN → dev.mcv.network
 *
 * Cách dùng:
 *   1. Copy file này thành  config.php  (cùng thư mục) — hoặc tốt hơn, đặt NGOÀI public_html
 *      với tên  leadscan-config.php  (ví dụ cùng cấp với thư mục public_html).
 *   2. Điền thông tin tài khoản dịch vụ của dev.mcv.network.
 *   3. KHÔNG commit file config.php lên git (đã có trong .gitignore).
 */
return [
    // Địa chỉ API của hệ thống quản lý dự án (không có dấu / ở cuối)
    'mcv_base_url' => 'https://dev.mcv.network/api/v1',

    // Tài khoản dịch vụ dùng để tạo dự án (nên là tài khoản riêng, chỉ có quyền tạo dự án)
    'mcv_username' => '',
    'mcv_password' => '',

    // Tiền tố mã dự án (key). Hệ thống sẽ sinh: LS + 4 ký tự ngẫu nhiên, ví dụ LSK7QD
    'key_prefix' => 'LS',

    // Các trường bổ sung bắt buộc khi tạo dự án trên dev.mcv.network (nếu có), ví dụ:
    //   'project_extra' => ['methodology' => 'kanban', 'owner_id' => 3],
    'project_extra' => [],

    // Tên miền được phép gửi form (chống gửi chéo trang). Để trống = chỉ cho phép chính host hiện tại.
    'allowed_hosts' => ['leadscan.net', 'www.leadscan.net', 'leadscanb2b.com', 'www.leadscanb2b.com'],

    // Email nhận thông báo khi có đăng ký mới (để trống = không gửi)
    'notify_email' => '',
    'notify_from'  => 'no-reply@leadscan.net',

    // Giới hạn chống spam: tối đa N lượt gửi / IP / giờ
    'rate_limit_per_hour' => 5,
];
