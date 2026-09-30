# Handoff: Manual listener repair qua terminal

## Vấn đề

Hotkey listener và click logger được cài vào `window` của page bằng page-level
`expose_binding` / `evaluate` một lần lúc startup. Vì vậy:

- Mọi navigation/reload phá hủy listener; click logger (chỉ evaluate một lần)
  chết vĩnh viễn sau navigation đầu tiên.
- Tab mới sinh ra sau startup (popup, switch account) không có binding —
  hotkey chết hẳn trên tab đó.
- Boolean guard `__hauntedRoomHotkeysInstalled` khiến re-install bị skip khi
  document còn sống mà handler đã hỏng.

## Mục tiêu

Người dùng nắm **100% quyền kiểm soát thủ công**: listener không bao giờ tự
cài lại theo bất kỳ cơ chế nào. Khi listener hỏng (sau navigation, tab mới,
hoặc bất kỳ lý do nào), người dùng alt-tab vào terminal bấm phím để re-install
listener lên mọi page/frame hiện có, không phải restart runner.

## Nguyên tắc cốt lõi

Không có cơ chế auto-repair: không init script, không hook vào navigation
event, không watchdog định kỳ. Listener chỉ được cài qua đúng hai đường:
startup install và repair thủ công từ terminal.

## Hướng đã chốt

1. Đăng ký binding lên `BrowserContext` thay vì `Page`, đúng một lần lúc
   startup. Binding là hạ tầng để repair có hiệu lực trên mọi tab hiện có và
   tab sinh ra sau này; nó không phải cơ chế cài listener.
2. Cài listener bằng script idempotent có versioned handler state: mỗi lần
   install giữ reference handler cũ, remove trước khi add, tăng version.
   Install bao nhiêu lần trên cùng document cũng còn đúng một handler, và
   cài sạch sẽ trên document mới chưa có state.
3. Tách hai operation: startup install (đăng ký binding, rồi evaluate lên các
   frame hiện có) và repair (chỉ re-evaluate install script trên mọi
   page/frame hiện có trong context, lỗi một frame không làm hỏng các frame
   còn lại, log tổng kết). Repair phủ cả hotkey listener lẫn click logger.
4. Thêm terminal input adapter: một thread đọc input theo từng phím (char
   mode, không cần Enter), bấm `Shift+R` enqueue sentinel
   `__repair_hotkey_listener__`, `Shift+P` enqueue sentinel
   `__probe_hotkey_listener__` vào command queue. Cross-OS bằng stdlib:
   `msvcrt` trên Windows, `termios` cbreak trên POSIX; không thêm dependency.
5. Standby controller xử lý hai sentinel trước mọi flow/control routing —
   repair và probe chạy được khi runner idle, running hay paused, không đổi
   flow state.
6. Probe là health check end-to-end: dispatch synthetic keydown tương đương
   một hotkey có sẵn và xác nhận command về queue. Kết quả log phải phân biệt
   được "chain JS → binding → queue chết" với "listener sống nhưng tab mất
   focus".
7. Standby không giữ `page` chết: trước khi dùng page cho screenshot hoặc
   flow, resolve lại game page từ `context.pages` nếu page hiện tại đã đóng.

## Phạm vi triển khai

- `core/browser_hook.py`: versioned install scripts, context-level binding,
  repair và probe operation, sentinel constant.
- `runner/terminal_input.py` (mới): terminal input adapter, chỉ là cầu
  thread → `call_soon_threadsafe` → command queue; adapter không gọi
  Playwright trực tiếp.
- `runner/standby.py`: nhánh xử lý sentinel trước routing; re-resolve page.
- Startup wiring trong entrypoint: đăng ký binding trên context, cài listener
  sau khi game page sẵn sàng.
- Terminal mode phải được restore khi runner thoát (POSIX); hành vi Ctrl+C
  giữ nguyên trên cả ba OS.

## Ngoài phạm vi

- Bất kỳ hình thức tự cài lại listener nào (init script, navigation hook,
  polling).
- Mất focus (keydown không đến tab không focus): repair không chữa được case
  này; chỉ giảm thiểu bằng `bring_to_front` khi đóng popup. Recovery bằng
  OS-global hotkey thuộc handoff `GLOBAL_HOTKEY_RECOVERY_HANDOFF.md`, là
  bước nâng cấp sau và dùng lại đúng sentinel/queue của gói này.
- Repair cho browser/context đã crash hoặc đóng.
- Thay đổi command behavior hay business logic của flow.

## Tiêu chí hoàn thành

- Startup: hotkey và click logger hoạt động đúng như hiện tại.
- Sau navigation/reload hoặc mở tab mới: listener chết và **không tự sống
  lại**; chỉ bấm `Shift+R` là hoạt động trở lại trên mọi page/frame hiện có.
- Bấm repair nhiều lần không tạo duplicate handler (một phím chỉ enqueue đúng
  một command).
- `Shift+P` log rõ chain sống hay chết và phân biệt được nguyên nhân.
- Terminal không kẹt mode sau khi runner thoát; Ctrl+C tắt runner sạch trên
  Windows, Linux, macOS.
- Test hiện tại vẫn pass; thêm test cho repair idempotent, sentinel không đi
  qua flow resolver, và listener không tự cài lại sau navigation.
