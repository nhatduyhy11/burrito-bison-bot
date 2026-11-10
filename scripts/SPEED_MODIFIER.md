# Can thiệp tốc độ battle

POC đã xác nhận hoạt động: có thể tăng tốc campaign trực tiếp trên client và server
chấp nhận kết quả trận, không verify speed modifier trong luồng này.

Bot ưu tiên nhận diện màn hình bằng OpenCV và thao tác qua UI. Đọc bundle phục vụ
research; speed modifier là ngoại lệ can thiệp runtime, nên giữ phụ thuộc vào
internal API ở mức tối thiểu và cô lập trong module speed.

## Điểm can thiệp và phạm vi

Lấy đối tượng điều khiển battle hiện tại trong game frame:

```js
const mainLoop = cc.director.getScene().getComponentInChildren(
  __require("BattleMainLoop").BattleMainLoop
);
```

Đổi tốc độ battle hiện tại không cần biết `battleType`:

```js
mainLoop.setTimeScale(scale);
```

- `BattleMainLoop.setTimeScale()` cập nhật frame sync và blackboard, đồng bộ tốc độ
  logic với HUD, effect, entity và camera.
- Đây là speed của instance battle hiện tại, không phải thiết lập global cho mọi
  battle. Mode khác cần dùng cùng cơ chế time scale để API này có hiệu lực;
  POC mới xác nhận ở campaign.
- Không cần `battleType` hay ghi cache speed theo loại trận. Modifier chỉ giữ
  speed gốc của instance + UUID trận để restore đúng trận, không lưu qua trận sau.
- Nút X2 của game thực tế dùng hệ số `1.6` (`BATTLE_SPEED_TIME_SCALE = [1, 1.6]`).
  Quyền `BattleSpeed` được kiểm tra ở luồng UI; có thể can thiệp trực tiếp qua API trên.

## Reset khi settle

Khi mới vào battle, người chơi cần chọn giường/base để settle. Game chủ động reset
speed một lần tại bước này; đây là behavior bình thường của game.

Luồng reset: operation `SetSpeed` → `TimeSpeedUpdate` →
`TDBattleFrame._updateTimeSpeed` → `BattleFrame._setTimeSpeed`.
Nếu modifier đã bật trước khi settle, cần apply lại sau lần reset này.

## Khoảng tốc độ thực tế

- `1.6–2.2` có vẻ là khoảng vận hành an toàn với bot hiện tại. `2.2` cũng là trần
  thực tế của đa số interval trong bot; đây không phải giới hạn cứng của game.
- Mạng chậm có thể khiến asset load không kịp khi tăng tốc.
- Logic gốc chạy 10 tick/s; ở `1.6` đạt 16 tick/s. `FrameSyncCocos` nhân delta theo
  speed nhưng chỉ xử lý tối đa một tick mỗi frame render. Với render 60fps, trần
  lý thuyết khoảng `6×`; tăng hệ số không bảo đảm tốc độ thực tăng tuyến tính.

## Tích hợp runner

- `Shift+]` bật tùy chọn `2.2×`, có thể bật trước hoặc trong flow. `Shift+[` tắt.
- Chỉ flow có `enters_battle=True` mới chạy modifier: auto-map/start-auto, train,
  train ad/exit, spawn/exit và new-account vào auto-map. Flow research, nâng tướng,
  artifact… không kích hoạt modifier. Mode mới có vào trận cần khai báo cờ này.
- Watcher mỗi giây apply lên battle hiện tại, tiếp tục chờ giữa các trận và apply
  lại sau reset khi settle. Không phụ thuộc ID loại battle hay screen `automap`.
- Apply lặp không nhân dồn tốc độ: chỉ gọi `setTimeScale(scale)` khi giá trị hiện tại
  khác `scale`. Mỗi trận chỉ lưu speed gốc một lần; chỉ tạo một watcher cho flow.
- Runner idle, `Shift+0` hoặc đóng runner sẽ dừng watcher và restore nếu vẫn là trận
  đã sửa. Tùy chọn bật được giữ qua idle cho flow battle tiếp theo; `Shift+[` bỏ nó.

Code: [battle_speed.py](../tools/hauntedroom/control_events/battle_speed.py),
[speed_control.py](../tools/hauntedroom/runner/speed_control.py).
Việc bỏ cache và mở sang mode khác chưa được kiểm chứng lại trên game thật;
POC đã xác nhận trước đó ở campaign.

Cách đọc bundle: [BUNDLE_RESEARCH.md](../docs/client/BUNDLE_RESEARCH.md).
