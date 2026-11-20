# Cơ chế battle trong sandbox browser

Sandbox chạy battle bằng bundle của game và thay các điểm gọi cần lobby hoặc server bằng
xử lý local. Các phần dưới mô tả đường chạy khi tự chơi. Cách chạy nằm trong
[README](../README.md#tự-chơi-trận-offline). Cách áp lại thao tác từ capture nằm trong
[hướng dẫn replay](REPLAY.md).

## Thao tác và tick

Khi tự chơi, `TDServerProxy.commitClientRequest` đi qua nhánh `Local` của game.
Nhánh này gọi `TDServer.handleClientRequest` và ghi thao tác vào `_clientOperationRecord`.
Director tự sinh op của robot đồng đội và dừng tick khi có bảng chặn như chọn summon
hoặc vòng quay. Một lần chạy `--headless --play` có thể dừng ở bảng chặn vì thiếu thao tác.

## Tăng tốc và auto

Trong chế độ tự chơi, `unlockMonthCards` giả lập đã mua hai thẻ tháng.
`UnlockLO` kiểm tra điều kiện `PrivilgeMonthCard` qua
`MallModule.checkActVipCardIsBuy(NewMonthCard, 7|8)`.

- 9003 (thẻ 7) mở nút tăng tốc. Nút x2 gửi op `SetSpeed`. Giá trị
  `BATTLE_SPEED_TIME_SCALE` và `frameSync.timeScale` khi bật là 1.6. Trận đội (Đêm Đỏ) gửi
  `BuildRoomProxy.SetSpeedRequest` trước, rồi mới gửi `SetSpeed`. `stubRoomSpeed` trả lời yêu cầu này local.
- 9007 (thẻ 8) mở auto qua `HostingMgr`, tự gửi các thao tác như Upgrade, Select và Lottery.

Hai nút hiện sau khi vào giường. Các kiểm tra còn liên quan đến
`ActivityModule.isOpen(MonthCardDict)`. Với auto, sandbox bỏ điều kiện loại trận
(`NeedAIBtnBattleType`) và level account (9008). `HostingMgr.update` yêu cầu trạng thái
đang trong phòng và socket đã kết nối. Sandbox giả lập hai trạng thái đó trong lúc gọi
`update`. Có thể xem đối tượng frame qua `window.__simBattleFrame` khi chẩn đoán bằng CDP.
Xem [stubs.js](../web/battle/stubs.js).

## Pause và kết thúc trận

- `stubPause` trả lời `SetPause` local. Director dừng tick khi bảng pause mở.
  Nút `继续战斗` tiếp tục trận. Nút `退出战斗` gửi `Abandon`, dẫn tới `QuitRoom` và màn kết quả.
- `stubQuitRoom` trả lời local với `clientReward: null`. Game vẫn mở
  `BattleResultViewAdventure`. Sandbox ghi `StartGameP` và `QuitRoom` kèm op log theo định dạng capture.
- Khi đóng màn kết quả, game gọi đường về lobby. `leaveOnResultClose` đặt
  `window.__simLeave` để sandbox xử lý. Runner mở lại setup nếu khởi chạy bằng `--setup`,
  hoặc kết thúc phiên `--play`. Việc lưu trận diễn ra trước khi xử lý đóng màn.
  Xem [stubs.js](../web/battle/stubs.js) và [runner](../sandbox/__main__.py).

## Camera và Canvas

`battle/setup.js` đặt `Main Camera` của Canvas chỉ render UI, bỏ các group
`battle_ground*` và tắt xoá màu. Một camera ở depth -100 xoá khung hình.
`camera_battle` ở depth -10 vẽ battle trước `Main Camera`. Nếu `Main Camera` giữ
thiết lập cũ, nó xoá hình battle rồi vẽ lại map lệch offset.
Xem [setup.js](../web/battle/setup.js).

`boot.js` gắn `cc.Widget` căn bốn cạnh cho Canvas dựng bằng code. Engine 2.4 cần
Widget này để layout Canvas giống scene tạo trong editor. Thiếu Widget, Canvas có
kích thước 0×0, làm UI lệch và vùng click không khớp nút. Xem [boot.js](../web/boot.js).
