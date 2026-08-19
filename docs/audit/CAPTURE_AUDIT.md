# Capture audit

Audit này tách rõ hai khái niệm thường cùng được gọi là “capture”:

- **Capture in-memory**: Playwright trả bytes PNG, `core/vision.py` decode thành
  mảng OpenCV BGR/grayscale. Frame chỉ sống trong RAM và không tạo file.
- **Persisted screenshot**: Playwright ghi PNG xuống disk qua
  `core/runtime.py`.

## Các đường ghi file

| Nguồn | Trigger | API | Thư mục | Tự động |
|---|---|---|---|---|
| Action runner | `ClickTemplateAction` hết timeout | `save_timeout_screenshot` | `.tmp/hauntedroom-timeouts/` | Có |
| Blocker clearer | Hết timeout khi clear blocker/chờ template đích | `save_timeout_screenshot` | `.tmp/hauntedroom-timeouts/` | Có |
| Screen detect / `Shift+1` | Detector trả về `unknown` | `save_fallback_screenshot` | `.tmp/hauntedroom-fallbacks/` | Có |
| Auto-map hero fallback | Đủ 3 card nhưng không match priority, yellow hoặc purple; setting `CAPTURE_HERO_FALLBACK_SCREENSHOTS=True` | `save_fallback_screenshot` | `.tmp/hauntedroom-fallbacks/` | Có |
| Standby/auto-map control | Người dùng bấm hotkey screenshot, mặc định `Shift+8` | `save_live_screenshot` | `tests/fixtures/hauntedroom-captures/` | Không, chỉ theo lệnh người dùng |

`save_screenshot()` là primitive chung tạo timestamp, sanitize label và gọi
`page.screenshot(path=...)`. Không có production code nào khác gọi
`page.screenshot(path=...)` trực tiếp.

Hero fallback dùng API và directory riêng, không tái sử dụng live screenshot.
Vì `.tmp/` nằm trong `.gitignore`, capture tự động không làm bẩn fixture hoặc
working tree.

## Capture in-memory theo flow

| Flow / subsystem | Màu | Capture để làm gì | Có tự ghi file không? |
|---|---|---|---|
| `screen_detect` / `Shift+1` | BGR | Phân loại `home`, special flow, train, automap hoặc unknown | Chỉ khi kết quả là `unknown` |
| Action runner | Grayscale | Poll template, skip-template và action checkpoint | Chỉ khi timeout, theo bảng trên |
| Blocker clearer | Grayscale | Tìm blocker và template đích | Chỉ khi timeout, theo bảng trên |
| Research | Grayscale | Poll badge available và trạng thái active | Không |
| Artifact | Grayscale | Tìm mark ở tab/card/activate và trạng thái popup close | Không |
| EXP available | BGR | Tìm badge EXP vàng sau mỗi click | Không |
| Hero breakthrough | BGR | Tìm nút vàng kèm dấu `!` đỏ và recheck hero kế tiếp | Không |
| Train | BGR | Gate lượt train và chọn card qua từng round | Không |
| Auto-map coordinator | BGR, rồi derive grayscale | Một frame chính mỗi poll cho priority handlers | Chỉ hero fallback có thể ghi file |
| Auto-map level-up/build | BGR | Recheck UI sau click, xác nhận option/menu | Không |
| Auto-map hero picker | BGR | Poll picker, match priority và fallback màu | Có điều kiện hero fallback |
| Auto-map gear | BGR | Detect menu, anchor, drag result và trạng thái đóng menu | Không |
| Auto-map boss pet | BGR | Detect ready bar, popup và summon active | Không |
| Auto-map completion / daily first win | BGR | Reward, checkbox, blocker và home handoff | Không |

`start_auto.py` và `click_loop.py` không tự capture. Start-auto ủy quyền cho action
runner/auto-map; click-loop chỉ click theo tọa độ cố định.

## Policy hiện tại

1. Capture tự động phục vụ debug phải nằm dưới `.tmp/`.
2. `tests/fixtures/` chỉ nhận screenshot do người dùng chủ động bấm hotkey và
   các fixture đã được curate/commit có chủ đích.
3. Detector bình thường chỉ dùng frame trong RAM; không persist từng poll.
4. Khi thêm capture mới, phải chọn rõ một trong ba API: timeout, fallback hoặc
   live/manual; không gọi primitive `save_screenshot()` trực tiếp từ flow.
