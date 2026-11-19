# CRM Lite hạng Vàng: chạy thử với 3–5 khách

CRM tại `/thanh-vien/crm`: mỗi phiếu đã mua thành 1 lead. Có pipeline, ghi chú (tự che SĐT/email lạ), việc cần làm,
lịch sử, xuất Excel (chỉ dữ liệu doanh nghiệp), 2 nút AI (tóm tắt công ty, soạn tin mời), email nhắc việc 8:00 và báo cáo tuần thứ Hai.

## 1. Trước khi bật

- [ ] Chạy migration trên máy chủ: `alembic upgrade head` (thêm 5 bảng `crm_*`, không sửa bảng cũ).
- [ ] Pháp chế đồng ý gửi **dữ liệu doanh nghiệp** (nội dung phiếu không kèm đầu mối, hồ sơ MST kho A, hồ sơ doanh nghiệp của khách) ra API Claude.
      Chưa đồng ý thì để `LEADSCAN_CRM_AI_ENABLED=false`: CRM vẫn chạy đủ, chỉ ẩn kết quả AI.
- [ ] Nếu bật AI: đặt `COHERE_API_KEY` (chính) và `DEEPSEEK_API_KEY` (dự phòng), `LEADSCAN_CRM_AI_ENABLED=true`. Kiểm tra `LEADSCAN_CRM_AI_BUDGET_USD` (mặc định 22 USD/khách/tháng)
      và giá `LEADSCAN_CRM_AI_PRICE_IN/OUT` khớp model đang dùng.
- [ ] `celery beat` đang chạy (email nhắc việc / báo cáo tuần) và đã cấu hình gửi mail (Resend hoặc SMTP).

## 2. Chọn khách chạy thử

- [ ] Chọn 3–5 khách hạng Vàng có nhiều phiếu đã mua và sale chủ động. Lấy **mã khách** (LS-…) trong trang quản trị.
- [ ] Đặt `LEADSCAN_CRM_PILOT_CODES=LS-…,LS-…` rồi khởi động lại api + worker. Khách Vàng khác thấy thông báo "Sắp có cho bạn".
- [ ] Báo khách: phiếu cũ đã có sẵn trong CRM, thêm đồng nghiệp bằng tài khoản cùng doanh nghiệp, AI chỉ soạn nháp, khách tự gửi.

## 3. Theo dõi trong 2 tuần

| Câu hỏi | Xem ở đâu |
|---|---|
| Khách có dùng không? | `crm_events` (đổi giai đoạn, ghi chú, việc) theo `company_id` |
| AI tốn bao nhiêu, có ai chạm trần? | `SELECT company_id, SUM(cost_usd), COUNT(*) FROM crm_ai_runs WHERE created_at >= date_trunc('month', now()) GROUP BY 1` |
| AI lỗi? | `crm_ai_runs WHERE error <> ''` |
| Ghi chú bị che SĐT/email nhiều không (dấu hiệu sale cố lưu dữ liệu cá nhân)? | tìm `[đã ẩn` trong `crm_notes.content` |
| Email nhắc việc có đi không? | log worker: `CRM: gửi N email nhắc việc` |

Hỏi khách sau 1 tuần: cột pipeline có hợp quy trình của họ không, bản nháp AI có dùng được không, email nhắc 8:00 có phiền không.

## 4. Mở cho mọi khách Vàng

- [ ] Không có lỗi nghiêm trọng, chi phí AI thực tế trong ngân sách.
- [ ] Xoá `LEADSCAN_CRM_PILOT_CODES` (để trống), khởi động lại api + worker.

## Đã kiểm thử (tuần 3)

- Phân quyền trên **mọi** route CRM (test tự liệt kê route): chưa đăng nhập → 401, hạng Thường → 403, doanh nghiệp khác → 404 / không thấy dữ liệu, gửi chéo trang → 403.
- Chạy test CRM và toàn bộ chuỗi migration (lên/xuống) trên PostgreSQL 17 + pgvector.
- Hiệu năng 10.000 lead + 10.000 việc: bảng 0,05s · trang việc 0,10s · tìm kiếm 1,2s · lần mở đầu (đồng bộ) 0,5s · xuất Excel 3s.
- Xuất Excel chống chèn công thức (`=HYPERLINK…` từ dữ liệu phiếu không chạy khi mở file).
- AI: tối đa 6 lượt / doanh nghiệp / phút, chặn bấm dồn vượt trần ngân sách.

Chưa kiểm thử: gọi Claude thật (máy dev chưa có khoá API). Lần đầu bật AI trên máy chủ, bấm thử 1 lần mỗi nút
và xem `crm_ai_runs` có token và chi phí hợp lý.
