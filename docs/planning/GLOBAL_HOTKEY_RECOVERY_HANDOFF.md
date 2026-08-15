# Handoff: OS-Global Hotkey Recovery

## Mục tiêu

Thêm một recovery hotkey `Ctrl+Shift+F12` do OS bắt, chạy nền trong cùng Python
process với Playwright. Hotkey này vẫn hoạt động khi browser, iframe hoặc terminal
không có focus. Khi được bấm, nó yêu cầu standby controller cài lại browser
hotkey listener trên mọi page/frame hiện có trong browser context.

```text
Ctrl+Shift+F12 at OS level
  -> callback on keyboard-listener thread
  -> loop.call_soon_threadsafe(...)
  -> enqueue "__repair_hotkey_listener__"
  -> asyncio standby controller
  -> re-install browser listener on every current page/frame
```

Recovery listener không phải process/service riêng. Nó được start và stop cùng
CLI runner; terminal chỉ là nơi host Python process.

## Vấn đề hiện tại

Browser command hotkey hiện được cài bằng `page.expose_binding()`,
`page.add_init_script()` và `frame.evaluate()` trong
`tools/hauntedroom/core/runtime.py`. Cơ chế này phụ thuộc vào JavaScript listener
trong document/frame đang nhận keyboard event.

Nếu focus chuyển sang document/page chưa có listener, hoặc listener bị mất trong
lifecycle của iframe, `Shift+0..9` không thể tự kích hoạt một lần re-inject. Cần
một recovery path độc lập với DOM và browser keyboard events.

Script hiện tại cũng dùng boolean `window.__hauntedRoomHotkeysInstalled`. Nếu cờ
còn tồn tại nhưng handler không còn hoạt động, evaluate lại script sẽ return sớm
và không sửa được listener.

## Quyết định đã chốt

- MVP chỉ thêm **một** OS-global hotkey: `Ctrl+Shift+F12`.
- `Shift+0..9` vẫn là browser-local hotkey và giữ nguyên command behavior.
- Global callback không gọi Playwright và không tạo asyncio task trực tiếp trên
  keyboard-listener thread.
- Callback chỉ dùng `loop.call_soon_threadsafe()` để enqueue một internal command
  vào queue của standby controller.
- Standby controller xử lý internal repair command trên asyncio event loop rồi
  gọi Playwright để re-inject.
- Repair được phép chạy khi runner idle, running hoặc paused. Nó không stop,
  pause, resume hay restart flow hiện tại.
- Binding và init script được đăng ký đúng một lần lúc startup. Mỗi lần repair
  chỉ re-evaluate script trên các document/frame hiện có.
- Lỗi ở một page/frame đã đóng, navigate hoặc detach không làm hỏng toàn bộ
  repair; tiếp tục với các target còn lại và log kết quả tổng hợp.
- Global listener có cùng lifecycle với CLI runner và luôn được stop trong
  `finally`.
- Không đưa global listener vào desktop UI MVP. Handoff này chỉ áp dụng cho CLI
  runner; UI vẫn điều khiển bằng button adapter như `UI_TODO.md` đã chốt.

## Thiết kế browser listener có thể repair

Thay boolean guard bằng state có version và giữ reference tới handler:

```javascript
() => {
    const previous = window.__hauntedRoomHotkeyState;
    if (previous?.handler) {
        window.removeEventListener("keydown", previous.handler, true);
    }

    const handler = (event) => {
        // Keep the current Shift+Digit validation and dispatch behavior.
    };

    window.addEventListener("keydown", handler, true);
    window.__hauntedRoomHotkeyState = { version: 1, handler };
}
```

Script phải idempotent theo nghĩa mỗi document chỉ còn đúng một active handler
sau bất kỳ số lần repair nào. Không dùng boolean để skip toàn bộ re-install.

Ưu tiên chuyển binding/init-script registration từ `Page` sang
`BrowserContext`:

- `context.expose_binding(...)` cung cấp binding cho mọi frame trong mọi page
  thuộc context.
- `context.add_init_script(...)` bảo vệ page/frame được tạo hoặc navigate về sau.
- Sau khi đăng ký, evaluate script trên mọi frame đang tồn tại để cover current
  documents.

Tách hai operation rõ ràng:

1. `install_hotkey_listener(context, command_queue)`: đăng ký binding và init
   script một lần, rồi cài handler vào current frames.
2. `repair_hotkey_listener(context)`: chỉ cài lại handler vào current frames;
   không expose lại binding và không add lại init script.

Binding callback nên dùng `source` để debug page/frame URL khi cần, nhưng không
đưa URL vào business command routing.

## Thiết kế OS-global adapter

Ưu tiên `pynput.keyboard.GlobalHotKeys` cho MVP và thêm `pynput` vào project
dependencies. Bọc thư viện sau một adapter nhỏ để standby/controller không phụ
thuộc trực tiếp vào callback API của `pynput`.

Adapter nhận sẵn event loop và command queue:

```python
def request_repair() -> None:
    loop.call_soon_threadsafe(
        command_queue.put_nowait,
        REPAIR_HOTKEY_LISTENER_COMMAND,
    )
```

`REPAIR_HOTKEY_LISTENER_COMMAND` là internal sentinel, ví dụ
`"__repair_hotkey_listener__"`; không thêm nó vào `FLOW_COMMANDS` và không cho
nó đi qua flow resolver.

Nếu OS hook không khởi tạo được vì permission hoặc platform support, log warning
rõ ràng rồi tiếp tục chạy browser listener bình thường. Recovery là safety path,
không được làm CLI runner mất khả năng startup.

## Lifecycle dự kiến

```text
launch persistent BrowserContext
  -> navigate game page
  -> create command queue
  -> register context binding/init script
  -> install browser handlers into current frames
  -> start OS-global recovery listener
  -> run standby loop
  -> Ctrl+Shift+F12 may enqueue repair at any time
  -> finally stop OS listener
  -> stop flow/controller tasks
  -> close BrowserContext
```

Nếu startup thất bại sau khi OS listener đã start, cleanup vẫn phải stop listener.
Không để listener thread giữ process sống sau khi browser/context đóng.

## Phạm vi triển khai

1. Thêm dependency global keyboard hook vào `pyproject.toml` và lock file.
2. Refactor hotkey installation trong `core/runtime.py` thành startup install và
   repair operation riêng, dùng `BrowserContext`.
3. Thêm OS-global recovery adapter ở runner/input layer; không đặt keyboard hook
   trong flow hoặc vision modules.
4. Start adapter sau khi command queue và asyncio loop đã tồn tại.
5. Xử lý internal repair command trước control/flow command routing trong
   `runner/standby.py`.
6. Stop adapter trong `finally`, kể cả khi flow, Playwright hoặc startup lỗi.
7. Thêm dòng `Ctrl+Shift+F12  Repair browser hotkeys` vào CLI menu/log.
8. Cập nhật `docs/README.md` với behavior, macOS permission và fallback khi OS
   hook không khả dụng.

Tên module cụ thể là quyết định triển khai. Ưu tiên một input-adapter module dưới
`runner/` thay vì đưa `pynput` vào `core/runtime.py` hoặc business flow.

## Concurrency và error handling

- Callback của `pynput` chạy ngoài asyncio event loop; chỉ được gọi
  `loop.call_soon_threadsafe()` từ callback đó.
- Mọi Playwright call phải chạy trong standby controller/event loop.
- Repair command không bị rule "runner busy" chặn.
- Nhiều lần bấm recovery liên tiếp không tạo duplicate DOM handlers. Có thể xử
  lý tuần tự qua queue; không cần chạy nhiều repair task song song.
- Khi iterate `context.pages` và `page.frames`, target có thể đóng/detach giữa
  lúc lấy snapshot và evaluate. Catch Playwright error theo từng frame.
- Log tối thiểu: số frame repair thành công, số frame bỏ qua/thất bại và lỗi OS
  hook startup nếu có.

## Testing cần có

- OS callback dùng `loop.call_soon_threadsafe()` để enqueue đúng internal command;
  test bằng fake listener, không đăng ký hotkey thật trong unit test.
- Internal repair command được xử lý khi idle, running và paused mà không đổi
  `flow_task`, `stop_event` hoặc `current_command`.
- Repair iterate mọi current page/frame và tiếp tục khi một frame evaluate lỗi.
- Startup chỉ expose binding và add init script một lần.
- Repeated repair không để duplicate `keydown` handlers.
- Internal command không đi qua `FLOW_COMMANDS` hoặc flow resolver.
- Global listener được stop trong normal shutdown và exception cleanup.
- OS-hook startup failure chỉ log warning; browser hotkeys và runner vẫn chạy.
- Existing tests cho `Shift+0..9`, pause/resume, screenshot và busy-flow behavior
  vẫn pass.

## Manual verification

1. Start CLI runner và xác nhận `Shift+8` vẫn chụp screenshot trong browser.
2. Focus terminal hoặc app khác, bấm `Ctrl+Shift+F12`, xác nhận log repair xuất
   hiện mà flow state không đổi.
3. Tạo/navigate iframe hoặc mở popup trong cùng browser context, bấm recovery và
   xác nhận listener được cài trên current frames.
4. Bấm recovery nhiều lần rồi bấm một browser hotkey; command chỉ được enqueue
   đúng một lần.
5. Thử recovery khi flow đang running và paused; flow tiếp tục đúng state.
6. Đóng runner bằng `Ctrl+C`; xác nhận global shortcut không còn bị process bắt.
7. Trên macOS, kiểm tra cả trường hợp chưa cấp và đã cấp Input
   Monitoring/Accessibility cho Terminal hoặc app host.

## Ngoài phạm vi

- Chuyển toàn bộ `Shift+0..9` thành OS-global hotkey.
- Điều khiển bot khi browser context đã crash hoặc bị đóng.
- Restart browser/context bằng recovery key.
- Chạy recovery listener như daemon/service độc lập.
- Thêm global hotkey vào desktop UI Phase 1.
- Xây abstraction multi-session hoặc route recovery tới nhiều browser contexts.
- Thay đổi command behavior hoặc business logic của các flow.

## Tiêu chí hoàn thành

Trong lúc CLI runner và BrowserContext còn sống, người dùng có thể bấm
`Ctrl+Shift+F12` mà không cần focus browser hoặc terminal để yêu cầu re-install
browser hotkey listener trên mọi current page/frame. Recovery không làm thay đổi
flow state, không tạo duplicate handler, không gọi Playwright từ keyboard thread
và global listener được dọn sạch khi runner kết thúc.
