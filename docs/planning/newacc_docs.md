# Tài liệu kỹ thuật: Flow New Account (Newbie Flow)

Tài liệu này mô tả chi tiết luồng xử lý tự động dành cho tài khoản mới (`new_account` hay `newbie` flow) được kích hoạt thông qua hotkey `Shift+1` và so sánh điểm khác biệt của nó với luồng chạy map tự động thông thường (`automap` / `start_auto`).

---

## 1. Tổng quan Luồng Xử lý New Account

Khi người dùng nhấn `Shift+1` ở màn hình ban đầu của tài khoản mới:
1. **Screen Detection**: Runner nhận diện được màn hình hiện tại là `ScreenName.NEW_ACCOUNT` (newbie).
2. **Clear Prompts (Dọn dẹp popup chào mừng)**:
   - Runner liên tục click vào tọa độ dùng chung `NEW_ACCOUNT_ACTION_CLICK` `(320, 630)` với khoảng nghỉ `1,000ms`.
   - Quá trình click lặp lại cho đến khi nhận diện được màn hình chơi game (`ScreenName.AUTOMAP`).
3. **Chạy Map Đầu tiên (First Map Run)**:
   - Runner gọi `automap_flow` với tham số `new_account_lubu_popup_active=True`.
   - Tham số này kích hoạt bộ kiểm tra đặc biệt nhằm tắt popup Lu Bu xuất hiện giữa chừng trong trận chiến đầu tiên (nhận diện template `lubu_close.png` và click để tắt).
   - Screenshot chẩn đoán cho hero fallback được tắt riêng (`capture_hero_fallback_screenshots=False`); flow vẫn capture frame cần thiết để nhận diện các lựa chọn hero sau khi mở picker.
   - Trận chiến đầu tiên được chạy cho tới khi hoàn thành (đạt `MAP_END`) và quay trở về màn hình chính (`home` screen).
4. **Handoff Đặc biệt (Enter-Exit Map)**:
   - Sau khi map đầu tiên kết thúc thành công, thay vì dừng lại ngay lập tức, runner sẽ thực thi thêm **đúng 1 lần luồng vào-ra map (enter-exit map)**.
   - Luồng này chạy qua các hành động sau:
     1. Chờ/xóa các blockers/popups trên màn hình chính.
     2. Click vào icon bản đồ trên màn hình chính (`start_home.png`) 3 lần để mở giao diện chuẩn bị.
     3. Click nút bắt đầu trận đấu thông qua `ClickHeroSelectBattleAction`.
     4. Khi đã vào trận đấu mới, click nút exit góc trên (`exit_click.png`) để mở menu Pause.
     5. Xác nhận thoát trận đấu qua `ClickPauseExitAction` và thoát hẳn về màn hình chọn map qua `ClickMapExitBackAction`.
     6. Chờ/xóa các blockers cho đến khi màn hình chính `start_home.png` hiển thị trở lại.
   - Sau khi hoàn thành xong 1 chu kỳ vào-ra map này, runner chính thức dừng và đưa trạng thái về idle (standby).

---

## 2. So sánh giữa New Account Flow và Normal Auto-Map

| Đặc điểm | Luồng New Account (`new_account`) | Luồng Auto-Map Thường (`start_auto` / `automap`) |
| :--- | :--- | :--- |
| **Màn hình bắt đầu** | Bắt đầu từ màn hình popup của tài khoản mới (`ScreenName.NEW_ACCOUNT`). | Bắt đầu từ màn hình chính (`home` / `start_home.png`) hoặc trực tiếp trong trận đấu (`automap`). |
| **Xử lý popup tài khoản mới** | Có click dọn dẹp các prompt khởi tạo tài khoản mới. | Không xử lý các prompt khởi tạo tài khoản mới. |
| **Tắt popup Lu Bu** | Được bật (`new_account_lubu_popup_active=True`) để tự động tắt popup Lu Bu khi đang chạy map. | Mặc định tắt (chỉ bật khi có yêu cầu). |
| **Số lần lặp trận đấu** | Chạy map đầu tiên xong, thực hiện **chỉ đúng 1 lần** chu kỳ vào-ra map rồi dừng hẳn. | Chạy lặp đi lặp lại vô hạn các map tiếp theo cho đến khi người dùng bấm dừng (`Shift+0` hoặc gặp điều kiện dừng cấu hình). |
| **Mục đích** | Thiết lập ban đầu cho tài khoản mới qua trận đầu tiên, đồng bộ trạng thái game. | Auto cày cuốc map liên tục để thu thập tài nguyên. |

---

## 3. Kiến trúc code & Tái cấu trúc DRY

Để tránh việc lặp lại code (Don't Repeat Yourself - DRY), các hàm xây dựng danh sách hành động (Action list builders) đã được tách rời từ `tools/hauntedroom/runner/commands.py` sang một module dùng chung:
- **File mới**: `tools/hauntedroom/actions/builder.py`
- **Các hàm được chuyển**:
  - [`build_start_battle_actions`](../../tools/hauntedroom/actions/builder.py): Tạo danh sách các hành động để click từ màn hình chính vào trận đấu.
  - [`build_spawn_exit_lvup_actions`](../../tools/hauntedroom/actions/builder.py): Tạo danh sách các hành động từ lúc bắt đầu trận đấu, exit trận đấu và quay về màn hình chính.

Cả `runner/commands.py` (sử dụng cho lệnh `Shift+9`) và `flows/new_account.py` (sử dụng cho luồng newbie tài khoản mới) đều import và sử dụng chung danh sách hành động từ module `builder.py` này.
