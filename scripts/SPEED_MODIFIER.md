# SPEED_MODIFIER — Nghiên cứu tốc độ campaign

Ngày: 2026-11-08. Trạng thái: plan nghiên cứu, chưa triển khai hoặc thử runtime.

## Mục tiêu và phạm vi

Xác định khả năng điều chỉnh tốc độ campaign chính trực tiếp trên client, độc lập với nút X2; làm rõ giới hạn tốc độ thực tế, khả năng bị game ghi đè và ảnh hưởng đến việc server chấp nhận kết quả. Không mở rộng sang các chế độ khác.

## Phát hiện từ đọc code

- Campaign (`EBattleTypeHangUpSystem`) dùng `BattleAdvFrame`, kế thừa `TDBattleFrame`; provider tạo `AdvBattleRoom`, chọn đồng bộ `Local` và có `needCheck = true`.
- Nút X2 dùng `BATTLE_SPEED_TIME_SCALE = [1, 1.6]`, với `BATTLE_DEFAULT_TIME_SCALE = 1`. Nhãn x2 được tạo từ index, không phản ánh trực tiếp hệ số thực.
- Luồng UI kiểm tra quyền `BattleSpeed`, thời hạn trải nghiệm hoặc vật phẩm trải nghiệm. Thao tác tốc độ của campaign đi qua operation `SetSpeed`, sau đó cập nhật tốc độ local.
- `BattleMainLoop.setTimeScale()` cập nhật cả frame sync và blackboard. Trong hàm đã đọc không thấy kiểm quyền thẻ hoặc giới hạn trên; điều này chưa chứng minh toàn bộ luồng không có guard khác.
- `FrameSyncCocos` nhân delta với hệ số tốc độ rồi clamp theo thời lượng một tick. Vì vậy hệ số đặt lớn hơn 1.6 không bảo đảm tốc độ thực tăng tuyến tính.
- Blackboard truyền thay đổi tốc độ đến HUD, effect, entity và camera. Chỉ sửa đồng hồ logic có thể khiến phần hiển thị thiếu đồng bộ.
- Luồng cập nhật tốc độ của game có thể ghi đè một giá trị đặt trực tiếp. Đổi engine trực tiếp không tự thực hiện thao tác UI, lưu lựa chọn hoặc tạo operation tốc độ tương ứng.
- Campaign có luồng gửi operation và dữ liệu kết thúc trận như frame kết thúc, thời gian mô phỏng, thống kê bổ sung. Có nhánh hash trạng thái theo tick khi cấu hình tương ứng bật; client cũng có xử lý kết quả do server trả về và thông báo kiểm tra bất thường dẫn đến lùi tiến độ.

Các phát hiện trên đến từ phân tích bundle client đã lưu, chưa đối chiếu bản live. Không có source server; chưa xác nhận những cấu hình kiểm tra nào đang bật hoặc chính sách kiểm quyền tốc độ phía server.

## Hướng nghiên cứu

### 1. Xác nhận đường chạy campaign thực tế

Đối chiếu runtime với các class và luồng đã đọc. Xác định đối tượng sở hữu tốc độ, cơ chế đồng bộ và các điểm có thể đặt lại giá trị trong một trận hoặc khi chuyển ải.

### 2. Đo giới hạn điều chỉnh tại engine

Đánh giá việc đổi tốc độ qua API engine có sẵn trước. Đo thời gian thực so với tiến độ tick, độ đồng bộ animation và tính ổn định ở nhiều mức tốc độ để xác định trần thực tế do frame loop.

### 3. Đánh giá các tầng can thiệp sâu hơn

Nếu API tốc độ không đáp ứng mục tiêu, so sánh điều chỉnh lịch chạy tick với can thiệp nguồn thời gian. Làm rõ phạm vi ảnh hưởng đến battle, UI và hoạt động mạng trước khi chọn kiến trúc. Chưa có bằng chứng tool bên ngoài được nhắc đến dùng kỹ thuật nào.

### 4. Xác minh ranh giới client–server

Quan sát dữ liệu operation, kết thúc trận và phản hồi trong môi trường thử nghiệm được phép. Phân biệt hiệu ứng tăng tốc local, kết quả được server chấp nhận ngay và khả năng kiểm tra sau đó. Không suy luận rằng damage bình thường đồng nghĩa với không có kiểm tra khác.

### 5. Chốt thiết kế modifier

Chỉ quyết định triển khai sau khi rõ giới hạn runtime và luồng xác minh. Modifier cần phạm vi riêng cho campaign, đồng bộ logic với hiển thị và có khả năng khôi phục tốc độ ban đầu; tránh tác động đồng hồ toàn ứng dụng khi chưa cần thiết.

## Kết quả cần có

- Kết luận có bằng chứng về tầng điều chỉnh phù hợp và khoảng tốc độ thực tế.
- Phân biệt rõ guard đã quan sát, hành vi mới suy luận và phần server chưa biết.
- Quyết định tiếp tục hoặc dừng triển khai dựa trên kết quả runtime; không coi việc màn hình chạy nhanh là bằng chứng qua được xác minh.

## Tham khảo phương pháp

Cách xác định và phân tích bundle: [BUNDLE_RESEARCH.md](../docs/client/BUNDLE_RESEARCH.md). Tải + tách module: `scripts/bundle/fetch_bundle.py`.
