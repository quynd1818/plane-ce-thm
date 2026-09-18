# Nested pages và export tài liệu

Phạm vi: Pages của dự án; hoãn custom roles/RBAC chi tiết.

## Hành vi

- Danh sách Pages hiển thị cây nhiều cấp, cho thu gọn/mở rộng. Search và bộ lọc vẫn hoạt động; page con khớp bộ lọc được hiển thị ngay cả khi page cha không nằm trong kết quả.
- Editor có breadcrumb, nút **Add subpage** và trường **Parent page**. Chọn **No parent (top level)** để chuyển về gốc.
- Page cha phải nằm trong cùng dự án, còn hiệu lực, không archived/locked và người thao tác có quyền đọc. Không thể chọn chính page hiện tại hoặc hậu duệ làm cha. API kiểm tra cả khi client gọi trực tiếp; thao tác đồng thời được tuần tự hóa theo workspace để không tạo chu trình, kể cả page liên kết nhiều dự án.
- Cấu trúc cây dùng để tổ chức; quyền public/private vẫn theo từng page, không kế thừa tự động. Khi tạo page con, UI mặc định chọn cùng access với page cha; người tạo có thể lựa chọn lại. Di chuyển page không đổi quyền. Người không đọc được page cha không thấy tên page cha qua breadcrumb.
- Archive cha tiếp tục archive các hậu duệ; xóa cha đã archive đưa các con trực tiếp về cấp gốc theo hành vi hiện có.
- **Export** giữ PDF và Markdown, thêm **Word (.docx)**. Xuất nội dung của page đang mở, gồm thay đổi đang có trong editor; không xuất hàng loạt toàn bộ cây.
- PDF giữ lựa chọn khổ giấy hiện có. Word xuất A4, tiếng Việt, heading, đoạn văn, bold/italic/underline, danh sách, bảng, hyperlink và ảnh nhúng. Tiêu đề được escape, tên file giữ dấu tiếng Việt và loại ký tự không hợp lệ.
- Word được sinh ở trình duyệt và chỉ tải module khi chọn export Word. File là OOXML `.docx` thật. Ảnh không lấy được/không hỗ trợ được thay bằng mô tả và thông báo số ảnh thiếu; ảnh không giải mã được khiến export báo lỗi. Có tùy chọn **No images** để xuất phần nội dung văn bản.
- Các thành phần editor đặc thù được chuẩn hóa theo luồng PDF hiện có. Đây không phải bản chụp giữ nguyên mọi pixel của editor; tài liệu vẫn chỉnh sửa được trong Word.

## Kiểm chứng

- API: tạo, đọc/list page con, chuyển về gốc; chặn cycle, parent private khác chủ/khác dự án/revoked/archived/locked; guest/private không lộ nội dung; archive/delete; hai lệnh reparent đồng thời.
- Frontend: cây, thu gọn, xử lý parent không hiển thị, loại descendant khỏi lựa chọn, nút tạo con, lưu/rollback parent gồm `null`.
- DOCX: kiểm tra ZIP/OOXML, tiếng Việt, định dạng, numbering, tables, hyperlinks, media; title không chèn HTML và filename hợp lệ.
- Build web, TypeScript và lint các file thay đổi.

Không cần migration: sử dụng trường `Page.parent` đã có. Cần triển khai cả API và web để sử dụng cây page; thay đổi này không sửa dữ liệu production hoặc cấu hình RBAC.
