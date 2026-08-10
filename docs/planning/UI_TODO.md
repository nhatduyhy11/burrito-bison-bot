# Desktop UI TODO

Planning notes only. Tài liệu này mô tả hướng phát triển; chưa phải behavior của
runner hiện tại.

## Quyết định đã chốt

- Giữ CLI hiện tại và cơ chế `Shift+[0-9]` cho người dùng CLI.
- Desktop UI không cài, không inject và không lắng nghe hotkey.
- Người dùng điều khiển UI hoàn toàn bằng nút bấm.
- CLI và UI dùng chung browser service, command definitions, flow và OpenCV
  business logic; không tạo hai implementation automation riêng.
- App chạy local và không cần server/cloud bên ngoài.
- Ưu tiên PySide6 cho desktop UI và `qasync` để nối Qt event loop với `asyncio`.
- Browser vẫn do Playwright mở riêng; UI không nhúng game vào WebView ở phase đầu.

## Mục tiêu

- Mở/đóng browser và persistent profile từ app.
- Start, pause, resume và stop flow bằng nút.
- Hiển thị chính xác trạng thái browser và flow.
- Hiển thị live log và lỗi mà không đóng app.
- Chụp và xem screenshot gần nhất.
- Giữ CLI hoạt động như hiện tại, bao gồm hotkey và dev reload.
- Hỗ trợ Windows trước nhưng không đưa Windows-only API vào business core.

## Ngoài phạm vi ban đầu

- Global hotkey hoặc OS-level keyboard hook.
- Browser extension và Native Messaging.
- Nhúng Chrome/game trực tiếp vào cửa sổ app.
- Remote control qua mạng.
- Cloud sync, tài khoản app hoặc telemetry.
- Visual action/template editor đầy đủ.
- Auto-update trong MVP.

## Kiến trúc mục tiêu

```text
CLI entrypoint                         Desktop UI entrypoint
      |                                        |
hotkey adapter                              button adapter
      |                                        |
      +-------------- command API -------------+
                             |
                         BotService
                  browser + flow lifecycle
                             |
                 standby/command controller
                             |
          actions / flows / Playwright / OpenCV
```

`BotService` là boundary dùng chung. UI không gọi trực tiếp module flow và không
tự quản lý Playwright page/task. CLI hotkey adapter và UI button adapter chỉ đổi
input thành command cho service.

## Command và nút UI

| Command hiện tại | Nút UI đề xuất | Hành vi |
|---|---|---|
| `Shift+1` | Enter / Exit Loop | Chạy flow enter-exit room |
| `Shift+2` | Auto Map Current Battle | Chạy auto-map cho trận đã start thủ công |
| `Shift+3` khi idle | Start Auto Loop | Bắt đầu start-room + auto-map loop |
| `Shift+3` khi running | Pause | Pause đúng state hiện tại |
| `Shift+3` khi paused | Resume | Tiếp tục đúng state hiện tại |
| `Shift+7` | Fixed Click Loop | Chạy click loop cố định |
| `Shift+8` | Capture Screenshot | Lưu và preview screenshot |
| `Shift+9` | Research | Chạy research flow |
| `Shift+0` | Stop | Dừng mềm flow hiện tại |

Tên nút là business label; UI không cần hiển thị tổ hợp phím. Các command chưa
cấu hình không cần xuất hiện dưới dạng nút disabled trong MVP.

## State model

UI không suy luận trạng thái từ text log. Service cần phát state có cấu trúc:

- Browser: `closed`, `starting`, `ready`, `closing`, `failed`.
- Flow: `idle`, `starting`, `running`, `paused`, `stopping`, `failed`.
- `current_command`: command đang chạy hoặc `None`.
- `status_message`: mô tả ngắn dành cho người dùng.
- `last_error`: exception đã format hoặc `None`.
- `last_screenshot`: path ảnh gần nhất hoặc `None`.

Quy tắc enable nút:

- Chưa có browser: chỉ enable Start Browser và settings khởi động.
- Browser ready + flow idle: enable các nút start flow và Capture.
- Flow running: enable Stop, Capture; với start-auto thì enable Pause.
- Flow paused: enable Resume, Stop và Capture.
- Browser starting/closing hoặc flow stopping: khóa action gây xung đột.
- Flow lỗi: trở về idle sau khi đã lưu/phát lỗi; browser tiếp tục mở nếu còn dùng
  được.

## UI MVP

- Khu Browser:
  - Start Browser.
  - Close Browser.
  - Hiển thị browser/profile/URL đang dùng.
- Khu Flow:
  - Các nút command trong bảng trên.
  - Nút Pause/Resume theo state.
  - Nút Stop nổi bật và luôn dễ truy cập khi flow active.
- Khu Status:
  - Browser state.
  - Flow state và tên flow hiện tại.
  - Lỗi gần nhất.
- Khu Log:
  - Append theo thời gian.
  - Giới hạn số dòng để tránh tăng RAM vô hạn.
  - Clear và copy log.
- Khu Screenshot:
  - Capture.
  - Preview ảnh gần nhất.
  - Open containing folder.
- Khu Settings tối thiểu:
  - Browser channel.
  - Persistent profile directory.
  - Game URL.
  - Action JSON path.
  - Viewport width/height.
  - Debug và dev reload.

## TODO triển khai

### Phase 1 — Tách application service

- [ ] Tạo `BotService` không phụ thuộc Qt.
- [ ] Tách browser bootstrap/lifecycle khỏi `hauntedroom_runner.py`.
- [ ] Cung cấp API async: `start_browser()`, `close_browser()`,
  `send_command()`, `pause()`, `resume()`, `stop_flow()` và `capture()`.
- [ ] Đưa ownership của `page`, command queue, flow task và `FlowControl` vào
  service/controller rõ ràng.
- [ ] Cho caller chọn input adapter: CLI hotkey hoặc UI button.
- [ ] Đảm bảo đường UI không gọi `start_hotkey_listener()` và không inject
  `HOTKEY_SCRIPT`.
- [ ] Giữ CLI gọi hotkey adapter trước navigation như behavior hiện tại.
- [ ] Không để một lỗi flow tự động đóng browser/service nếu browser vẫn khỏe.

### Phase 2 — State và logging

- [ ] Định nghĩa immutable state/event models.
- [ ] Phát state change khi browser/flow chuyển trạng thái.
- [ ] Thay các `print()` cần hiển thị bằng logger/event sink dùng chung.
- [ ] Giữ console sink để CLI không mất log hiện tại.
- [ ] Thêm UI sink mà không import Qt từ business modules.
- [ ] Chuẩn hóa error event, traceback log và user-facing message.
- [ ] Giới hạn log buffer trong memory.

### Phase 3 — PySide6 shell

- [ ] Thêm dependency PySide6 và `qasync`.
- [ ] Tạo desktop entrypoint riêng; không thay thế CLI entrypoint.
- [ ] Dựng main window theo UI MVP.
- [ ] Bind button với async service command, không block Qt thread.
- [ ] Render state và enable/disable button từ state model.
- [ ] Hiển thị log theo batch để log dày không làm lag UI.
- [ ] Hiển thị screenshot có scale nhưng giữ đúng aspect ratio.
- [ ] Lưu settings local bằng cơ chế cross-platform phù hợp.

### Phase 4 — Shutdown và recovery

- [ ] Khi đóng app: yêu cầu stop flow, chờ task kết thúc, rồi đóng context.
- [ ] Có timeout và fallback khi flow/browser không shutdown sạch.
- [ ] Xử lý persistent profile đang bị process khác khóa.
- [ ] Xử lý browser bị người dùng đóng thủ công.
- [ ] Cho phép restart browser sau lỗi mà không restart app.
- [ ] Ngăn double-click Start tạo hai browser hoặc hai flow task.
- [ ] Không để exception trong Qt callback bị nuốt.

### Phase 5 — Packaging

- [ ] Chốt PyInstaller hoặc Nuitka sau prototype.
- [ ] Package action JSON, template PNG và metadata bằng path không phụ thuộc cwd.
- [ ] Quyết định dùng Chrome đã cài hay bundle Playwright Chromium.
- [ ] Tách writable data: profile, logs, screenshots và user settings khỏi app
  bundle read-only.
- [ ] Tạo Windows build đầu tiên.
- [ ] Smoke-test đường dẫn có space và non-ASCII.
- [ ] Audit macOS/Linux: browser discovery, filesystem path và window behavior.

## Testing TODO

- [ ] Unit test state transition cho start/run/pause/resume/stop/fail.
- [ ] Test UI adapter gửi đúng command mà không cài hotkey.
- [ ] Test CLI adapter vẫn cài và nhận hotkey.
- [ ] Test CLI và UI dùng cùng command resolver/flow implementation.
- [ ] Test double command khi busy không tạo flow thứ hai.
- [ ] Test Capture không làm thay đổi flow state.
- [ ] Test đóng app khi idle, running và paused.
- [ ] Test lỗi flow trả UI về trạng thái có thể tiếp tục sử dụng.
- [ ] Test browser crash/disconnect.
- [ ] Test log buffer có giới hạn.
- [ ] Smoke-test packaged app với persistent profile thật.

## Rủi ro cần theo dõi

- Click vào app làm browser mất focus. Playwright input vẫn hoạt động, nhưng game
  hoặc Chromium có thể throttle khi browser bị minimize/occluded hoàn toàn.
- OpenCV/template matching không được chạy trên Qt UI thread.
- Persistent Chromium profile không thể được hai process dùng đồng thời.
- PySide6 + OpenCV + Playwright tạo bundle lớn.
- Browser channel có thể khác nhau giữa OS; không hardcode executable path.
- Hot reload là công cụ development; cần quyết định ẩn hay giữ trong production
  UI.
- Current flow log chủ yếu là text; refactor logging cần tránh làm thay đổi timing
  của automation.

## Tiêu chí hoàn thành MVP

- App mở được browser bằng persistent profile.
- Người dùng chạy, pause/resume và stop các flow hỗ trợ chỉ bằng nút.
- UI path không inject hotkey script.
- CLI hotkey vẫn hoạt động và không bị thay đổi command behavior.
- UI luôn hiển thị đúng browser/flow state và không freeze khi flow chạy.
- Lỗi flow được hiển thị nhưng app và browser vẫn có thể tiếp tục dùng.
- Capture screenshot hoạt động và preview được trong app.
- Đóng app giải phóng flow task, Playwright context và browser sạch.
- Có Windows build chạy được ngoài source checkout.

## Câu hỏi để chốt sau prototype

- MVP dùng Chrome đã cài hay bundle Chromium?
- Settings nào được phép sửa khi browser/flow đang chạy?
- Có cần thu gọn xuống system tray không?
- Screenshot preview chỉ giữ ảnh gần nhất hay có history?
- Dev reload có xuất hiện trong production build không?
- macOS/Linux là release requirement ngay từ đầu hay sau Windows MVP?
