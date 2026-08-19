# Screen auto-switch: leftover issues

Unified flow đã được triển khai bằng `Shift+1`: runner chụp màn hình một lần,
nhận diện screen và dispatch sang flow tương ứng. File này chỉ giữ lại những phần
chưa hoàn tất.

## Dev reload chưa refresh screen classifier và template

Standby gọi `detect_current_screen()` trước khi resolve command và chạy reload policy.
Ngoài ra `_load_screen_templates()` đang cache template bằng `lru_cache`, nên thay đổi
classifier hoặc template screen trong lúc runner đang mở có thể chưa được áp dụng ở
lần bấm `Shift+1` tiếp theo.

Cần làm:

- Khi bật `--dev-reload`, reload `hauntedroom.screen_detect` trước khi capture/classify.
- Clear cache `_load_screen_templates()` để template được đọc lại.
- Giữ nguyên contract chỉ capture/classify một lần cho mỗi lần dispatch.
- Thêm test xác nhận classifier và template cache được refresh trong dev mode, đồng
  thời normal mode không reload.

## Tiêu chí đóng handoff

- Sửa code hoặc template screen được áp dụng ở lần `Shift+1` kế tiếp khi dùng
  `--dev-reload`.
- Các test screen detection và standby controller hiện có vẫn pass.
