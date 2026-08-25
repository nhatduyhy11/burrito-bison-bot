# Review các flow phụ thuộc chữ trong hình

Ngày rà soát: 2026-08-25

## Phạm vi

Runner hiện tại không dùng OCR. Các flow được gọi là "bắt chữ" thực chất dùng
OpenCV template matching với những ảnh crop có chứa chữ tiếng Việt.

Trong fixed Python runner Haunted Room hiện tại còn 20 file template phụ thuộc
ngôn ngữ. Hai điểm vào/thoát từng phụ thuộc chữ đã được thay thế:

- HOME entry xác nhận màn hero-select bằng crop đồ họa không chứa chữ ở góc trái
  banner, sau đó tìm nút vàng bằng HSV.
- Spawn/exit xác nhận popup pause bằng cặp nút đỏ-vàng và click nút đỏ bằng hình
  học + HSV.

`start_battle.png` vẫn còn được train flow sử dụng. `exit_confirm.png` chỉ còn
trong JSON macro mẫu, không còn tham gia fixed spawn/exit flow. Các template chữ
còn lại vẫn có nguy cơ không match trên phiên bản server Trung Quốc dù bố cục
game không đổi.

Hai screen flow EXP-available và hero-breakthrough không dùng template chữ:
chúng dùng vùng tọa độ cố định và ngưỡng màu HSV trên viewport `640x720`. Hiện
chúng được chọn qua screen auto-switch của `Shift+1`, không còn là direct hotkey
riêng. Vì vậy đổi ngôn ngữ không trực tiếp làm hỏng match, nhưng đổi layout,
scale hoặc palette vẫn có thể làm detector fail.

## Template phụ thuộc ngôn ngữ đang hoạt động

| Flow | Template/chữ đang bắt | Ảnh hưởng trên bản Trung Quốc | Mức độ |
|---|---|---|---|
| HOME entry / spawn-exit / auto-map — blocker | `overlay_close.png`: "Nhấn khu vực trống để đóng" | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| HOME entry / spawn-exit / auto-map — blocker | `overlay_close_2.png`: cùng nội dung trên | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| HOME entry / spawn-exit / auto-map — newbie | `overlay_newbie.png`: crop chữ "Bồi..." | Popup tutorial có thể không được xử lý | Cao |
| Train (`Shift+T`) — bắt đầu | `start_battle.png`: "Khiêu chiến" | Không vào được train battle | Rất cao |
| Spawn/exit (`Shift+9`) — quay lại | `exit_back.png`: "Quay" | Không quay về home | Cao |
| Auto-map / start-auto / train handoff — kết thúc map | `map_end.png`: "Quay lại" | Không nhận ra map đã kết thúc; auto-map tiếp tục polling | Rất cao |
| Auto-map / start-auto / train handoff — reward | `reward_list_title.png`: phần chữ "mừng" | Có thể không đóng được màn danh sách thưởng | Cao |
| Auto-map / start-auto / train handoff — daily first win | `daily_first_win.png`: "Không nhắc lại hôm nay" | Không vào isolated flow để tick/confirm prompt; cleanup reward có thể không hoàn tất | Cao |
| Research screen auto-switch (`Shift+1`) | `research_active.png`: chữ "Kích..." | Có thể cho rằng research active đã biến mất và dừng flow sớm | Trung bình |
| Hero selection (auto-map / train) | `00_mage_king.png`: "Vua Pháp Sư" | Không ưu tiên đúng hero | Trung bình |
| Hero selection (auto-map / train) | `01_dark_lubu.png`: "Hắc Lữ Bố" | Không ưu tiên đúng hero | Trung bình |
| Hero selection (auto-map / train) | `02_hanuman.png`: "Hanuman" | Có thể vẫn match nếu server giữ tên Latin, nhưng không nên phụ thuộc vào điều này | Trung bình |
| Hero selection (auto-map / train) | `03_soul_spear.png`: "Cây Giáo Hút Hồn" | Không ưu tiên đúng item | Trung bình |
| Hero selection (auto-map / train) | `04_thunder_trident.png`: "Đinh Ba Sấm Sét" | Không ưu tiên đúng item | Trung bình |
| Hero selection (auto-map / train) | `09_pinocchio.png`: "Pinocchio" | Có thể vẫn match nếu giữ tên Latin; nếu không sẽ mất priority 09 | Trung bình |
| Hero selection (auto-map / train) | `10_prayer_box.png`: "Hộp Cầu Nguyện" | Không ưu tiên đúng item | Trung bình |
| Hero selection (auto-map / train) | `11_death.png`: "Tăng sao Tử Thần" | Không ưu tiên đúng hero/card tăng sao | Trung bình |
| Hero selection (auto-map / train) | `11_underworld.png`: "U Minh Thần" | Không ưu tiên đúng hero | Trung bình |
| Hero selection (auto-map / train) | `12_soul_reaper.png`: "Liềm Đoạt Hồn" | Không ưu tiên đúng item | Trung bình |
| Hero selection (auto-map / train) | `99_mage_king.png`: "Vua Pháp Sư" variant | Không nhận diện option cần loại khỏi fallback | Trung bình |

### Vị trí khai báo và sử dụng

- HOME entry và fixed spawn/exit entry được dựng trong
  `tools/hauntedroom/runner/commands.py`. `build_start_battle_actions()` dùng
  `ClickHeroSelectBattleAction` thay cho `start_battle.png`; detector nằm trong
  `tools/hauntedroom/actions/hero_select_battle.py`. Train flow độc lập trong
  `tools/hauntedroom/flows/train.py` vẫn load `start_battle.png`.
- Fixed spawn/exit dùng `ClickPauseExitAction` từ
  `tools/hauntedroom/actions/pause_exit.py`, không load `exit_confirm.png`.
  `tools/json_macro/hauntedroom_actions.sample.json` vẫn giữ action chữ cũ cho
  JSON macro tùy chọn và chưa language-agnostic.
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
- Các template hero được tự động load từ
  `tools/rooms/automap/hero_levelup/` bởi
  `tools/hauntedroom/flows/automap_support/vision/hero_levelup.py`. Auto-map
  quan sát chúng ở scale `1.0`; `train_select.py` tái sử dụng danh sách asset ở
  scale `0.8` cho train `Shift+T`. Xem
  [hero level-up selection](../../tools/rooms/automap/hero_levelup/README.md) để
  biết thứ tự priority, threshold và fallback hiện hành.
- Hai trạng thái research được khai báo trong
  `tools/hauntedroom/flows/research.py`.

## Ghi chú riêng cho hero level-up

Đây là khu vực phụ thuộc chữ nhiều nhất. Trong auto-map, nếu tên hero/item không
match thì action chọn card từ panel màu theo vàng → tím → đỏ. Vì vậy bản Trung
Quốc vẫn có khả năng chọn được một option, nhưng mất thứ tự ưu tiên chi tiết từ
các template hero/item.

Train `Shift+T` tái sử dụng cùng template tên ở scale `0.8`, nhưng fallback của
train chỉ chọn card tím chưa chọn. Nếu template chữ đều miss và một round không
có đủ hai card tím phù hợp, train selection có thể chờ tới timeout thay vì chọn
card đỏ không nhận diện được. Do đó rủi ro đổi ngôn ngữ của nhóm template này
không chỉ là sai priority mà còn có thể chặn riêng flow train.

`00_hero_ascend.png` không bắt chữ. Template này bắt góc cyan ổn định của card
nên có khả năng dùng xuyên ngôn ngữ.

Do hình hero có animation nhẹ, không nên thay các template tên bằng một template
toàn bộ ảnh hero tĩnh. Các hướng nên xem xét:

- Crop vùng ít chuyển động như icon kỹ năng/vũ khí, khung card hoặc chi tiết
  trang phục ổn định.
- Xác nhận cùng một kết quả qua 3–5 frame liên tiếp.
- Với hero có animation mạnh, giữ nhiều keyframe template cho mỗi hero.
- Kết hợp tín hiệu hình ảnh với vị trí card và hình học của panel thay vì chỉ
  dùng một template toàn cảnh.

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
- `lv_up.png`, `built.png`, `lv_spin.png`: icon.
- `win_reward.png`: biểu tượng reward.
- `daily_first_win_checkbox.png` và `daily_first_win_checked.png`: hình học ô
  checkbox; riêng label `daily_first_win.png` vẫn phụ thuộc chữ như bảng trên.
- `boss_hp_bar.png`: hình học và gradient của thanh máu.
- `pet_ready.png`, `pet_active.png`, `spell_ready.png`: icon và glow.
- `research_available.png`: icon notification.
- Giá upgrade/build: kiểm tra pixel trắng, vàng và vùng màu, không đọc số/chữ.
- Hero fallback và option layout: dựa trên panel màu.
- `00_hero_ascend.png`: góc card cyan.
- `Shift+T` train entry: availability dựa vào số pixel màu trong vùng dòng chữ,
  challenge button dựa vào connected component màu vàng. Không match glyph cố
  định, nhưng availability vẫn nhạy với vị trí/font vì region nằm trên chữ.
- `Shift+T` train picker: card geometry, cạnh đỏ/tím và góc vàng selected; chỉ
  phần priority name dùng template chữ.
- EXP-available screen flow: tìm lõi badge vàng tại grid 3x3, cho phép offset dọc
  khi scroll; không dùng OCR/template chữ.
- Hero-breakthrough screen flow: yêu cầu đồng thời nút vàng trong popup và dấu
  `!` đỏ ở vùng mark; tab `Đột phá` phía dưới nằm ngoài search region.

## Template chữ hiện không tham gia runner chính

- `tools/rooms/exit_confirm.png`: chữ "Thoát"; fixed spawn/exit flow đã thay bằng
  detector cặp nút đỏ-vàng. File hiện chỉ còn được tham chiếu bởi JSON macro mẫu.
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
3. Các blocker và `exit_back.png`.
4. `start_battle.png` còn lại trong train flow.
5. `reward_list_title.png`.
6. Các template ưu tiên hero/item, đặc biệt vì train có thể timeout khi
   fallback không đủ card tím.
7. `research_active.png`.

`map_end.png` có khả năng làm toàn bộ vòng lặp start-auto ngừng hoạt động cao
nhất. Hai detector mới không cần asset chữ theo ngôn ngữ, nhưng vẫn cần fixture
mới nếu server khác thay viewport, vị trí banner/nút, scale hoặc palette màu.
