# SPEED_MODIFIER — Nghiên cứu tốc độ campaign

Ngày: 2026-11-08. Trạng thái: đã probe runtime 2 lần (2026-11-09); POC hotkey đã code
(`control_events/battle_speed.py`, `runner/speed_control.py`: Shift+] bật x1.6 khi screen
detect = automap, watcher 5s re-apply / tắt khi hết trận, Shift+[ khôi phục). Chưa chạy
POC trên game thật; chưa xác minh server chấp nhận kết quả trận.

## Runtime probe 2026-11-09

- Game chạy ở top frame `hauntedroomvnh5.joynetgame.com`, Cocos `2.4.15`. Handle trận:
  `cc.director.getScene().getComponentInChildren(__require("BattleMainLoop").BattleMainLoop)`
  → `null` ngoài trận; trong campaign `blackBoard.battleVo.battleType == 3`
  (`EBattleTypeHangUpSystem`). Đầu trận `frameSync._isPause = true` một lúc.
- Tick logic 100ms (10 tick/s), render 60fps; `FrameSyncCocos` tối đa 1 tick / frame
  render → trần lý thuyết ~x6. `BattleDebugShellComp` của dev dùng `setTimeScale(8)`.
- Đo: baseline 9.8 tick/s; sau `setTimeScale(1.6)` cửa sổ 6s chỉ đạt 11.0 tick/s và
  `timeScale` đã về 1 → **game ghi đè trong ~1s**. Trả về 1 thì 10.0 tick/s.
- Nghi phạm ghi đè (chưa xác nhận cái nào bắn): event `TDModuleEventType.LocalSetSpeed`
  (`TDOrganCom`, `TDMythicalBeastCom` dispatch với `BattleModule.Ins.getSpeedByBattleType(type)`
  = speed đã lưu, = 1 nếu chưa bật X2) và `TimeSpeedUpdate` từ operation `SetSpeed`
  (`BattleTDBaseDirector`) → `BattleFrame._setTimeSpeed`.
- Probe lần 2 (wrap `setTimeScale` ở instance, log stack):
  - **Thủ phạm ghi đè đã xác nhận:** operation `SetSpeed` trong luồng operation của trận →
    `BattleJuChangDirector/BattleTDAdvDirector/BattleTDBaseDirector.handleOperation` →
    `TimeSpeedUpdate` → `TDBattleFrame._updateTimeSpeed` → `BattleFrame._setTimeSpeed(1)`.
    Bắn 1 lần ở tick 100 (~10s đầu trận), không thấy lần thứ hai trong 40s quan sát.
  - Phase A (chỉ set local): bị reset về 1 ở tick 100, trung bình 6.3 tick/s (thấp bất
    thường, chưa rõ nguyên nhân).
  - Phase B (`BattleModule.Ins.setSpeedByBattleType(3, 1.6)` + `setTimeScale(1.6)`, sau tick
    100): **16.0 tick/s = đúng x1.6**, giữ 20s không bị ghi đè. Chưa tách được do lưu cache hay
    chỉ vì không còn op `SetSpeed` nào sau tick 100.
  - `setSpeedByBattleType` ghi vào cache bền (`_saveCacheData`) — POC phải trả về giá trị cũ
    khi tắt. Probe đã restore (`stored=1`, `timeScale=1`).
- Câu hỏi còn mở: op `SetSpeed` ở tick 100 có phải do client tự gửi theo speed đã lưu (nếu
  vậy lưu 1.6 trước trận sẽ khiến game gửi `SetSpeed` 1.6 lên server = đi đúng luồng nút X2)
  hay do server áp; server có chấp nhận kết quả trận ở 1.6 khi acc không có quyền
  `BattleSpeed` không.

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
