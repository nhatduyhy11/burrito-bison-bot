# Review các flow phụ thuộc chữ trong hình

## Phạm vi

Runner hiện tại không dùng OCR. Các flow được gọi là "bắt chữ" thực chất dùng
OpenCV template matching với những ảnh crop có chứa chữ tiếng Việt.

Trong runner Haunted Room hiện tại có 15 file template phụ thuộc ngôn ngữ,
tương ứng khoảng 14 điểm nhận diện logic trong 4 flow. Những template này có
nguy cơ không match trên phiên bản server Trung Quốc dù bố cục game không đổi.

## Template phụ thuộc ngôn ngữ đang hoạt động

| Flow | Template/chữ đang bắt | Ảnh hưởng trên bản Trung Quốc | Mức độ |
|---|---|---|---|
| Shift+1 — blocker | `overlay_close.png`: "Nhấn khu vực trống để đóng" | Không đóng được overlay; flow chờ màn tiếp theo rồi timeout | Cao |
| Shift+1 — blocker | `overlay_close_2.png`: cùng nội dung trên | Không đóng được overlay; flow chờ màn tiếp theo rồi timeout | Cao |
| Shift+1 — newbie | `overlay_newbie.png`: crop chữ "Bồi..." | Popup tutorial có thể không được xử lý | Cao |
| Shift+1/Shift+3 — bắt đầu | `start_battle.png`: "Khiêu chiến" | Không vào trận được | Rất cao |
| Shift+1 — thoát | `exit_confirm.png`: "Thoát" | Kẹt ở hộp xác nhận thoát | Cao |
| Shift+1 — quay lại | `exit_back.png`: "Quay" | Không quay về home | Cao |
| Shift+2/Shift+3 — kết thúc map | `map_end.png`: "Quay lại" | Không nhận ra map đã kết thúc; automap tiếp tục polling | Rất cao |
| Shift+2/Shift+3 — reward | `reward_list_title.png`: phần chữ "mừng" | Có thể không đóng được màn danh sách thưởng | Cao |
| Shift+9 — research | `research_active.png`: chữ "Kích..." | Có thể cho rằng research active đã biến mất và dừng flow sớm | Trung bình |
| Hero level-up | `00_mage_king.png`: "Vua Pháp Sư" | Không ưu tiên đúng hero | Trung bình |
| Hero level-up | `01_dark_lubu.png`: "Hắc Lữ Bố" | Không ưu tiên đúng hero | Trung bình |
| Hero level-up | `02_hanuman.png`: "Hanuman" | Có thể vẫn match nếu server giữ tên Latin, nhưng không nên phụ thuộc vào điều này | Trung bình |
| Hero level-up | `03_soul_spear.png`: "Cây Giáo Hút Hồn" | Không ưu tiên đúng item | Trung bình |
| Hero level-up | `04_thunder_trident.png`: "Đinh Ba Sấm Sét" | Không ưu tiên đúng item | Trung bình |
| Hero level-up | `99_mage_king.png`: "Vua Pháp Sư" variant | Không nhận diện option cần loại khỏi fallback | Trung bình |

### Vị trí khai báo và sử dụng

- Flow Shift+1 và prefix của Shift+3 được khai báo trong
  `tools/hauntedroom_actions.sample.json`.
- `map_end.png` và `map_win/reward_list_title.png` được khai báo và sử dụng trong
  `tools/hauntedroom/flows/automap.py`.
- Các template hero được tự động load từ
  `tools/rooms/automap/hero_levelup/` bởi
  `tools/hauntedroom/flows/automap_support/hero_levelup.py`. Xem
  [hero level-up selection](../tools/rooms/automap/hero_levelup/README.md) để
  biết thứ tự priority, threshold và fallback hiện hành.
- Hai trạng thái research được khai báo trong
  `tools/hauntedroom/flows/research.py`.

## Ghi chú riêng cho hero level-up

Đây là khu vực phụ thuộc chữ nhiều nhất, nhưng nếu tên hero/item không match thì
flow hiện tại không bị treo ngay. Code fallback tìm card từ panel màu, ưu tiên
card tím rồi mới chọn card hợp lệ đầu tiên. Vì vậy bản Trung Quốc vẫn có khả
năng chọn được một option, nhưng mất thứ tự ưu tiên chi tiết từ các template
hero/item.

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
- `boss_hp_bar.png`: hình học và gradient của thanh máu.
- `pet_ready.png`, `pet_active.png`, `spell_ready.png`: icon và glow.
- `research_available.png`: icon notification.
- Giá upgrade/build: kiểm tra pixel trắng, vàng và vùng màu, không đọc số/chữ.
- Hero fallback và option layout: dựa trên panel màu.
- `00_hero_ascend.png`: góc card cyan.

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
3. Các blocker và nút exit.
4. `reward_list_title.png`.
5. Các template ưu tiên hero/item.
6. `research_active.png`.

Hai template đầu tiên có khả năng làm toàn bộ vòng lặp Shift+3 ngừng hoạt động
cao nhất.
