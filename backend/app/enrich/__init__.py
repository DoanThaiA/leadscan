"""Phân hệ làm giàu dữ liệu doanh nghiệp theo mã số thuế (bảng: app/models_enrich.py).

normalize    chuẩn hoá MST, bỏ dấu tiếng Việt
permissions  vai trò → quyền, lọc trường kho B theo quyền
sources      danh mục nguồn + độ tin cậy
merge        chọn giá trị hiển thị từ bằng chứng, ghi nhật ký thay đổi
importer     đọc file CSV/Excel, tạo lô MST
khob         lối DUY NHẤT để đọc kho B: kiểm quyền + ghi nhật ký truy cập
"""
