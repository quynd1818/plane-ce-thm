# Workspace mặc định cho nhân viên SSO

Ngày: 2026-09-18. Phạm vi: Plane THM, nhánh `preview`.

## Quyết định sản phẩm

Cung cấp một workspace chung do quản trị viên chỉ định cho tài khoản đăng nhập qua Keycloak SSO doanh nghiệp chưa có workspace sử dụng được. Đây là nơi tiếp nhận nhân viên, không phải workspace public cho mọi tài khoản Internet. Không thay đổi chính sách tạo workspace hay quyền xem dự án để giải quyết onboarding.

Tên đề xuất: **THM — Không gian chung**. Quản trị viên tạo hoặc chọn workspace có sẵn rồi cấu hình slug thực tế. Code không tự tạo workspace và không suy đoán slug từ tên.

## User story

Là nhân viên đăng nhập qua SSO lần đầu, tôi muốn hoàn thiện profile rồi vào workspace chung được công ty cấp, để bắt đầu sử dụng hệ thống mà không cần tự tạo workspace hoặc chờ lời mời riêng.

Là quản trị viên, tôi muốn tài khoản đã có workspace không bị thêm nơi khác và quyền đã thu hồi không bị khôi phục khi đăng nhập lại.

## Quy tắc nghiệp vụ

1. Chỉ chạy fallback này sau callback Keycloak thành công. Đăng nhập mật khẩu, magic link và các provider khác không tự nhận workspace qua quy tắc này.
2. Xử lý lời mời đã chấp nhận theo luồng hiện có trước khi đánh giá fallback. Nếu luồng này đã cấp membership hoạt động thì không thêm workspace mặc định.
3. Kiểm tra membership trên toàn hệ thống: phải đang hoạt động, chưa bị xóa và thuộc workspace chưa bị xóa. Có ít nhất một membership hợp lệ thì không tự thêm hoặc thay đổi vai trò ở bất kỳ workspace nào.
4. Nếu không có membership hợp lệ, chỉ thêm vào workspace có slug được cấu hình và đang tồn tại. Không phụ thuộc profile đã hoàn thiện hay chưa.
5. Nếu user từng có membership bị xóa hoặc vô hiệu hóa ở chính workspace mặc định, không tự tạo lại hoặc kích hoạt lại. Quản trị viên phải cấp lại quyền chủ động. Membership đã thu hồi ở workspace khác không tự chặn việc tiếp nhận vào workspace mặc định.
6. Lời mời chưa chấp nhận vẫn còn nguyên để user tự quyết định; không tự chấp nhận, xóa hoặc nâng quyền từ lời mời đó. User không có membership vẫn có thể nhận workspace mặc định; lời mời còn lại tiếp tục dùng được ở luồng lời mời hiện có.
7. Giữ cấu hình vai trò hiện có: Guest (`5`, mặc định kỹ thuật) hoặc Member (`15`). Giá trị không hợp lệ hạ về Guest; không tự cấp Admin. Với nhân viên nội bộ cần cộng tác, quản trị viên có thể chọn Member sau khi xác định phạm vi dự án chung.
8. Không tự thêm ProjectMember, không đổi dự án private thành public, không đổi vai trò membership đang tồn tại. Quyền thực tế với dự án tiếp tục theo cơ chế phân quyền của hệ thống, gồm cả chính sách dự án public hiện có.
9. Callback lặp lại không tạo membership trùng. Các callback auto-join đồng thời phải được xử lý an toàn.
10. Tính năng tắt, slug sai, workspace đã xóa hoặc auto-join lỗi: vẫn cho đăng nhập thành công; không tự tạo workspace. Nếu không có workspace/lời mời và tạo workspace bị hạn chế, hiển thị hướng dẫn liên hệ quản trị viên, không kết luận rằng user chắc chắn chưa được mời.
11. Không đánh dấu profile hoàn thiện từ backend auto-join. Frontend đợi danh sách workspace và lời mời tải xong, yêu cầu hoàn thiện profile, rồi chuyển vào workspace đã cấp. Lỗi tải hoặc hoàn tất onboarding có cách thử lại.

## Cấu hình và vận hành

- God Mode → Authentication → Keycloak: `KEYCLOAK_AUTO_JOIN_WORKSPACE_SLUG` là slug workspace có sẵn; để trống để tắt fallback.
- `KEYCLOAK_AUTO_JOIN_ROLE`: `5` hoặc `15`; giữ nguyên giá trị đang triển khai, không tự nâng Guest thành Member.
- Hệ thống Keycloak đã cấu hình là nguồn xác thực doanh nghiệp. Không suy ra nhân viên chỉ từ đuôi email và không mở đăng ký public.
- Bản code này không thay đổi cấu hình production, không tạo workspace thật, không tự triển khai. Muốn tính năng hoạt động, cấu hình phải trỏ tới workspace thực tế.
- Không cần migration dữ liệu; membership đã cấp trước đây không bị xóa hoặc sửa hàng loạt.

## Tiêu chí nghiệm thu

| ID   | Given / When                                             | Then                                                                       |
| ---- | -------------------------------------------------------- | -------------------------------------------------------------------------- |
| AC01 | SSO thành công, chưa có membership, cấu hình hợp lệ      | Tạo đúng một membership ở workspace mặc định theo role cấu hình            |
| AC02 | Đã có membership hoạt động ở workspace khác              | Không thêm workspace mặc định; vai trò cũ giữ nguyên                       |
| AC03 | Đã là thành viên workspace mặc định, đăng nhập lại       | Không tạo trùng, không thay đổi vai trò                                    |
| AC04 | Membership mặc định bị xóa hoặc vô hiệu hóa              | Không khôi phục, không tạo thay thế                                        |
| AC05 | Chỉ còn membership bị thu hồi ở workspace khác           | Có thể tham gia workspace mặc định nếu đủ điều kiện                        |
| AC06 | Lời mời đã chấp nhận cấp membership vào workspace khác   | Không thêm workspace mặc định sau khi xử lý lời mời                        |
| AC07 | Có lời mời đang chờ, chưa có membership                  | Có thể cấp workspace mặc định; lời mời không bị thay đổi                   |
| AC08 | Slug trống, không tồn tại hoặc workspace đã xóa          | Đăng nhập vẫn thành công; không tạo workspace/membership                   |
| AC09 | Role cấu hình là Admin hoặc giá trị không hợp lệ         | Không cấp Admin, dùng Guest                                                |
| AC10 | Hai callback auto-join đồng thời                         | Chỉ có một membership, không gây lỗi đăng nhập                             |
| AC11 | User chưa hoàn thiện profile nhưng đã được cấp workspace | Hoàn thiện profile trước; không bị kẹt ở thông báo không có lời mời        |
| AC12 | Workspace/lời mời tải chậm hoặc tải lỗi                  | Chờ dữ liệu hoặc cho thử lại; không coi lỗi tải là danh sách rỗng          |
| AC13 | Tài khoản ngoài luồng Keycloak                           | Không được cấp workspace theo fallback này                                 |
| AC14 | Được auto-join workspace                                 | Không được tự thêm membership vào dự án hoặc thay đổi cấu hình quyền dự án |

## Phân công triển khai

- Backend dev: sửa điều kiện fallback trong `keycloak_auto_join.py`; giữ thứ tự xử lý lời mời; bảo đảm idempotency; bổ sung unit và callback contract tests.
- Frontend: mô tả đúng điều kiện trên màn hình cấu hình quản trị và thông báo chưa có workspace. Giữ các sửa onboarding ở commit `49572fb69`.
- Nghiệm thu: chạy các test backend liên quan Keycloak, test frontend onboarding/auth guard, lint và kiểm tra kiểu dữ liệu cho phần UI thay đổi; review diff trước khi commit `preview`.

## Kết quả kiểm chứng triển khai

- Backend: 16 unit tests và 22 callback contract tests đạt, gồm kiểm tra hai luồng auto-join đồng thời chỉ tạo một membership. Bộ test ban đầu 37 case đạt; case concurrency bổ sung được chạy riêng và đạt.
- Frontend: 19 test onboarding/auth guard đạt; admin typecheck và lint các file UI thay đổi đạt.
- Đã review diff theo quy tắc trên. Chưa triển khai hoặc thay cấu hình workspace của môi trường thật.
