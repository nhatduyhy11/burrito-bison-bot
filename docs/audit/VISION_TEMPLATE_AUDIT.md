# Review các flow phụ thuộc chữ trong hình

Ngày rà soát: 2026-08-25

## Phạm vi

Runner hiện tại không dùng OCR. Các flow được gọi là "bắt chữ" thực chất dùng
OpenCV template matching với những ảnh crop có chứa chữ tiếng Việt.

Trong fixed Python runner Haunted Room hiện tại còn 19 file template phụ thuộc
ngôn ngữ: 8 template flow/UI thuộc phạm vi audit chính và 11 template hero
selection được ghi nhận thành một nhóm riêng. Ba điểm vào/thoát từng phụ thuộc
chữ đã được thay thế:

- HOME entry xác nhận màn hero-select bằng crop đồ họa không chứa chữ ở góc trái
  banner, sau đó tìm nút vàng bằng HSV.
- Spawn/exit xác nhận popup pause bằng cặp nút đỏ-vàng và click nút đỏ bằng hình
  học + HSV.
- Spawn/exit quay về HOME bằng component vàng hoàn chỉnh ở vùng chặt của popup
  kết quả, không dùng crop chữ và không bắt nhầm nút vàng của game nằm phía dưới.

`start_battle.png` vẫn còn được train flow sử dụng. Các asset chỉ còn được JSON
macro mẫu tham chiếu được gom riêng ở phần cuối; fixed Python flow/auto chính
không còn load chúng. Các template chữ còn lại vẫn có nguy cơ không match trên
phiên bản server Trung Quốc dù bố cục game không đổi.

Hai screen flow EXP-available và hero-breakthrough không dùng template chữ:
chúng dùng vùng tọa độ cố định và ngưỡng màu HSV trên viewport `640x720`. Hiện
chúng được chọn qua screen auto-switch của `Shift+1`, không còn là direct hotkey
riêng. Vì vậy đổi ngôn ngữ không trực tiếp làm hỏng match, nhưng đổi layout,
scale hoặc palette vẫn có thể làm detector fail.

## Template flow/UI phụ thuộc ngôn ngữ đang hoạt động

| Flow | Template/chữ đang bắt | Ảnh hưởng trên bản Trung Quốc | Mức độ |
|---|---|---|---|
| HOME entry / spawn-exit / auto-map — blocker | `overlay_close.png`: "Nhấn khu vực trống để đóng" | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| HOME entry / spawn-exit / auto-map — blocker | `overlay_close_2.png`: cùng nội dung trên | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| HOME entry / spawn-exit / auto-map — newbie | `overlay_newbie.png`: crop chữ "Bồi..." | Popup tutorial có thể không được xử lý | Cao |
| Train (`Shift+T`) — bắt đầu | `start_battle.png`: "Khiêu chiến" | Không vào được train battle | Rất cao |
| Auto-map / start-auto / train handoff — kết thúc map | `map_end.png`: "Quay lại" | Không nhận ra map đã kết thúc; auto-map tiếp tục polling | Rất cao |
| Auto-map / start-auto / train handoff — reward | `reward_list_title.png`: phần chữ "mừng" | Có thể không đóng được màn danh sách thưởng | Cao |
| Auto-map / start-auto / train handoff — daily first win | `daily_first_win.png`: "Không nhắc lại hôm nay" | Không vào isolated flow để tick/confirm prompt; cleanup reward có thể không hoàn tất | Cao |
| Research screen auto-switch (`Shift+1`) | `research_active.png`: chữ "Kích..." | Có thể cho rằng research active đã biến mất và dừng flow sớm | Trung bình |

## Nhóm template hero selection

Nhóm này được tách khỏi audit giải pháp flow/UI. Mỗi hero có nhiều skin và hình
động, nên không có một visual crop ổn định để thay thế tên hiển thị; phụ thuộc
text template hiện là lựa chọn thực tế và được chấp nhận trong phạm vi hiện tại.

Các image đang dùng:

- `00_mage_king.png`
- `01_dark_lubu.png`
- `02_hanuman.png`
- `03_soul_spear.png`
- `04_thunder_trident.png`
- `09_pinocchio.png`
- `10_prayer_box.png`
- `11_death.png`
- `11_underworld.png`
- `12_soul_reaper.png`
- `99_mage_king.png`

Các file nằm trong `tools/rooms/automap/hero_levelup/`, được auto-map load ở
scale `1.0` và train `Shift+T` tái sử dụng ở scale `0.8`.

## Vị trí khai báo và sử dụng

- HOME entry và fixed spawn/exit entry được dựng trong
  `tools/hauntedroom/runner/commands.py`. `build_start_battle_actions()` dùng
  `ClickHeroSelectBattleAction` thay cho `start_battle.png`; detector nằm trong
  `tools/hauntedroom/actions/hero_select_battle.py`. Train flow độc lập trong
  `tools/hauntedroom/flows/train.py` vẫn load `start_battle.png`.
- Fixed spawn/exit dùng `ClickPauseExitAction` và `ClickMapExitBackAction` từ
  `tools/hauntedroom/actions/pause_exit.py`, không load `exit_confirm.png` hoặc
  `exit_back.png`.
- Đường dẫn `map_end.png`, `map_win/reward_list_title.png` và nhóm
  `map_win/daily_first_win*.png` được khai báo trong
  `tools/hauntedroom/flows/automap_support/vision/template_config.py`, rồi load qua
  `tools/hauntedroom/flows/automap_support/templates.py`. Map-end/home
  orchestration nằm trong `map/lifecycle.py`; visual query và business handling
  của daily-first-win/reward nằm lần lượt trong `map/first_win.py` và
  `map/reward.py`.
- Map-completion cleanup của auto-map cũng load các PNG trong
  `tools/rooms/blocker/`, nên ba blocker phụ thuộc chữ ở bảng trên ảnh hưởng cả
  auto-map, start-auto và phần auto-map sau train.
- Hai trạng thái research được khai báo trong
  `tools/hauntedroom/flows/research.py`.

## Detector hiện tại không phụ thuộc chữ

Các detector sau tương đối an toàn hơn khi đổi ngôn ngữ:

- `start_home.png`: icon.
- `exit_click.png`: nút pause.
- HOME/start-auto start battle: `hero_select_battle_banner_left.png` là crop
  `43x49` của góc trái banner, không chứa chữ; match grayscale ở scale `1.0`
  trong top region `(210, 10, 430, 90)` với threshold `0.80`. Chỉ sau khi banner
  match mới tìm connected component vàng ở bottom region `(230, 650, 410, 719)`
  và click tâm nút.
- Fixed spawn/exit confirm: không dùng header/template chữ. Detector yêu cầu
  đồng thời component đỏ bên trái và vàng bên phải trong bottom popup, kiểm tra
  kích thước, cùng hàng, chênh chiều cao và gap `20-50px`, rồi click tâm nút đỏ.
  Fixture Trung Quốc hiện trả `(251, 633)`.
- Fixed spawn/exit back: không dùng `exit_back.png`. Detector chỉ tìm component
  vàng hoàn chỉnh trong ROI `(245, 610, 390, 658)`, yêu cầu kích thước
  `100-120x30-40`, area tối thiểu `2500`, fill ratio tối thiểu `0.65` và top-left
  nằm gần `(264, 620)`, rồi click tâm `(319, 637)`. ROI kết thúc ở `y=658`, nên
  nút vàng của game phía dưới chỉ có thể lọt vài pixel và không đạt geometry.
  Nếu `start_home.png` đã sẵn sàng thì action được skip như flow cũ.
- `lv_up.png`, `built.png`, `lv_spin.png`: icon.
- `win_reward.png`: biểu tượng reward.
- `daily_first_win_checkbox.png` và `daily_first_win_checked.png`: hình học ô
  checkbox; riêng label `daily_first_win.png` vẫn phụ thuộc chữ như bảng trên.
- `boss_hp_bar.png`: hình học và gradient của thanh máu.
- `pet_ready.png`, `pet_active.png`, `spell_ready.png`: icon và glow.
- `research_available.png`: icon notification.
- Giá upgrade/build: kiểm tra pixel trắng, vàng và vùng màu, không đọc số/chữ.
- `Shift+T` train entry: availability dựa vào số pixel màu trong vùng dòng chữ,
  challenge button dựa vào connected component màu vàng. Không match glyph cố
  định, nhưng availability vẫn nhạy với vị trí/font vì region nằm trên chữ.
- EXP-available screen flow: tìm lõi badge vàng tại grid 3x3, cho phép offset dọc
  khi scroll; không dùng OCR/template chữ.
- Hero-breakthrough screen flow: yêu cầu đồng thời nút vàng trong popup và dấu
  `!` đỏ ở vùng mark; tab `Đột phá` phía dưới nằm ngoài search region.

## Template chữ chỉ còn trong JSON macro mẫu

Hai asset dưới đây chỉ còn được
`tools/json_macro/hauntedroom_actions.sample.json` tham chiếu. Fixed Python
spawn/exit, start-auto và auto-map chính không load chúng:

- `tools/rooms/exit_confirm.png`: chữ "Thoát"; đã được thay bằng detector cặp
  nút đỏ-vàng và `ClickPauseExitAction`.
- `tools/rooms/exit_back.png`: chữ "Quay"; đã được thay bằng detector component
  vàng theo vị trí/hình học và `ClickMapExitBackAction`.

JSON macro mẫu vẫn giữ hai action template cũ để tương thích với macro tùy chọn;
nhánh này chưa language-agnostic.

## Template chữ unused hoặc legacy

- `tools/rooms/automap/kill.png`: chữ "Xong", không có code reference.
- `tools/rooms/boss/boss_approaching.png`: có dính một phần chữ, nhưng flow hiện
  tại không load template này.
- Trong thư mục legacy `ref_cv`:
  - `tap-to-continue.png` đang được code legacy dùng.
  - `filled-with-goodies.png` đang được code legacy dùng.
  - `unlocked.png` được đăng ký trong vision nhưng chưa được game flow gọi.

Phần `ref_cv` là bot mẫu/legacy và không thuộc runner Haunted Room hiện tại.

## Thứ tự ưu tiên thay thế đề xuất

1. `map_end.png`.
2. `daily_first_win.png`.
3. Các blocker.
4. `start_battle.png` còn lại trong train flow.
5. `reward_list_title.png`.
6. `research_active.png`.

`map_end.png` có khả năng làm toàn bộ vòng lặp start-auto ngừng hoạt động cao
nhất. Ba detector mới không cần asset chữ theo ngôn ngữ, nhưng vẫn cần fixture
mới nếu server khác thay viewport, vị trí banner/nút, scale hoặc palette màu.
