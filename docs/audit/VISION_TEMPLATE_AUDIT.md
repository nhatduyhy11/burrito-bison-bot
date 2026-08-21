# Review các flow phụ thuộc chữ trong hình

Ngày rà soát: 2026-08-15

## Phạm vi

Runner hiện tại không dùng OCR. Các flow được gọi là "bắt chữ" thực chất dùng
OpenCV template matching với những ảnh crop có chứa chữ tiếng Việt.

Trong runner Haunted Room hiện tại có 21 file template phụ thuộc ngôn ngữ. Chúng
tham gia `Shift+1`, auto-map của `Shift+2`/`Shift+3`/`Shift+4`, train selection
của `Shift+4` và research `Shift+9`. Những template này có nguy cơ không match
trên phiên bản server Trung Quốc dù bố cục game không đổi.

Hai flow mới `Shift+5` và `Shift+6` không dùng template chữ: chúng dùng vùng
tọa độ cố định và ngưỡng màu HSV trên viewport `640x720`. Vì vậy đổi ngôn ngữ
không trực tiếp làm hỏng match, nhưng đổi layout, scale hoặc palette vẫn có thể
làm detector fail.

## Template phụ thuộc ngôn ngữ đang hoạt động

| Flow | Template/chữ đang bắt | Ảnh hưởng trên bản Trung Quốc | Mức độ |
|---|---|---|---|
| Shift+1/Shift+2/Shift+3/Shift+4 — blocker | `overlay_close.png`: "Nhấn khu vực trống để đóng" | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| Shift+1/Shift+2/Shift+3/Shift+4 — blocker | `overlay_close_2.png`: cùng nội dung trên | Không đóng được overlay; action hoặc map-completion cleanup có thể timeout | Cao |
| Shift+1/Shift+2/Shift+3/Shift+4 — newbie | `overlay_newbie.png`: crop chữ "Bồi..." | Popup tutorial có thể không được xử lý | Cao |
| Shift+1/Shift+3/Shift+4 — bắt đầu | `start_battle.png`: "Khiêu chiến" | Không vào trận thường/train được | Rất cao |
| Shift+1 — thoát | `exit_confirm.png`: "Thoát" | Kẹt ở hộp xác nhận thoát | Cao |
| Shift+1 — quay lại | `exit_back.png`: "Quay" | Không quay về home | Cao |
| Shift+2/Shift+3/Shift+4 — kết thúc map | `map_end.png`: "Quay lại" | Không nhận ra map đã kết thúc; auto-map tiếp tục polling | Rất cao |
| Shift+2/Shift+3/Shift+4 — reward | `reward_list_title.png`: phần chữ "mừng" | Có thể không đóng được màn danh sách thưởng | Cao |
| Shift+2/Shift+3/Shift+4 — daily first win | `daily_first_win.png`: "Không nhắc lại hôm nay" | Không vào isolated flow để tick/confirm prompt; cleanup reward có thể không hoàn tất | Cao |
| Shift+9 — research | `research_active.png`: chữ "Kích..." | Có thể cho rằng research active đã biến mất và dừng flow sớm | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `00_mage_king.png`: "Vua Pháp Sư" | Không ưu tiên đúng hero | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `01_dark_lubu.png`: "Hắc Lữ Bố" | Không ưu tiên đúng hero | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `02_hanuman.png`: "Hanuman" | Có thể vẫn match nếu server giữ tên Latin, nhưng không nên phụ thuộc vào điều này | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `03_soul_spear.png`: "Cây Giáo Hút Hồn" | Không ưu tiên đúng item | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `04_thunder_trident.png`: "Đinh Ba Sấm Sét" | Không ưu tiên đúng item | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `09_pinocchio.png`: "Pinocchio" | Có thể vẫn match nếu giữ tên Latin; nếu không sẽ mất priority 09 | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `10_prayer_box.png`: "Hộp Cầu Nguyện" | Không ưu tiên đúng item | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `11_death.png`: "Tăng sao Tử Thần" | Không ưu tiên đúng hero/card tăng sao | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `11_underworld.png`: "U Minh Thần" | Không ưu tiên đúng hero | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `12_soul_reaper.png`: "Liềm Đoạt Hồn" | Không ưu tiên đúng item | Trung bình |
| Hero selection (`Shift+2`/`Shift+3`/`Shift+4`) | `99_mage_king.png`: "Vua Pháp Sư" variant | Không nhận diện option cần loại khỏi fallback | Trung bình |

### Vị trí khai báo và sử dụng

- Flow Shift+1 và prefix của Shift+3 được khai báo trong
  `tools/json_macro/hauntedroom_actions.sample.json`; `Shift+4` tái sử dụng typed
  `start_battle.png` action/config từ cùng file để vào train battle.
- Đường dẫn `map_end.png`, `map_win/reward_list_title.png` và nhóm
  `map_win/daily_first_win*.png` được khai báo trong
  `tools/hauntedroom/flows/automap_support/config.py`, rồi load qua
  `tools/hauntedroom/flows/automap_support/templates.py`. Map-end/home
  orchestration nằm trong `map/lifecycle.py`; visual query và business handling
  của daily-first-win/reward nằm lần lượt trong `map/first_win.py` và
  `map/reward.py`.
- Map-completion cleanup của auto-map cũng load các PNG trong
  `tools/rooms/blocker/`, nên ba blocker phụ thuộc chữ ở bảng trên ảnh hưởng cả
  `Shift+2`, `Shift+3` và phần auto-map sau train của `Shift+4`.
- Các template hero được tự động load từ
  `tools/rooms/automap/hero_levelup/` bởi
  `tools/hauntedroom/flows/automap_support/hero_levelup_vision.py`. Auto-map
  quan sát chúng ở scale `1.0`; `train_select.py` tái sử dụng danh sách asset ở
  scale `0.8` cho `Shift+4`. Xem
  [hero level-up selection](../../tools/rooms/automap/hero_levelup/README.md) để
  biết thứ tự priority, threshold và fallback hiện hành.
- Hai trạng thái research được khai báo trong
  `tools/hauntedroom/flows/research.py`.

## Ghi chú riêng cho hero level-up

Đây là khu vực phụ thuộc chữ nhiều nhất. Trong auto-map, nếu tên hero/item không
match thì action chọn card từ panel màu theo vàng → tím → đỏ. Vì vậy bản Trung
Quốc vẫn có khả năng chọn được một option, nhưng mất thứ tự ưu tiên chi tiết từ
các template hero/item.

Train `Shift+4` tái sử dụng cùng template tên ở scale `0.8`, nhưng fallback của
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
- `Shift+4` train entry: availability dựa vào số pixel màu trong vùng dòng chữ,
  challenge button dựa vào connected component màu vàng. Không match glyph cố
  định, nhưng availability vẫn nhạy với vị trí/font vì region nằm trên chữ.
- `Shift+4` train picker: card geometry, cạnh đỏ/tím và góc vàng selected; chỉ
  phần priority name dùng template chữ.
- `Shift+5` EXP available: tìm lõi badge vàng tại grid 3x3, cho phép offset dọc
  khi scroll; không dùng OCR/template chữ.
- `Shift+6` hero breakthrough: yêu cầu đồng thời nút vàng trong popup và dấu
  `!` đỏ ở vùng mark; tab `Đột phá` phía dưới nằm ngoài search region.

## Template chữ hiện không tham gia runner chính

- `tools/rooms/automap/kill.png`: chữ "Xong", không có code reference.
- `tools/rooms/boss/boss_approaching.png`: có dính một phần chữ, nhưng flow hiện
  tại không load template này.
- Trong thư mục legacy `ref_cv`:
  - `tap-to-continue.png` đang được code legacy dùng.
  - `filled-with-goodies.png` đang được code legacy dùng.
  - `unlocked.png` được đăng ký trong vision nhưng chưa được game flow gọi.

Phần `ref_cv` là bot mẫu/legacy và không thuộc runner Haunted Room hiện tại.

## Thứ tự ưu tiên thay thế đề xuất

1. `start_battle.png`.
2. `map_end.png`.
3. `daily_first_win.png`.
4. Các blocker và nút exit.
5. `reward_list_title.png`.
6. Các template ưu tiên hero/item, đặc biệt vì `Shift+4` có thể timeout khi
   fallback không đủ card tím.
7. `research_active.png`.

Hai template đầu tiên có khả năng làm toàn bộ vòng lặp Shift+3 ngừng hoạt động
cao nhất. `Shift+5`/`Shift+6` không cần asset thay thế theo ngôn ngữ, nhưng cần
fixture mới nếu server khác thay viewport, vị trí grid/popup hoặc palette màu.
