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
- Browser vẫn do Playwright mở riêng; UI không nhúng game vào WebView ở Phase 1.
- Chia roadmap sản phẩm thành hai phase rõ ràng:
  - Phase 1 chỉ làm MVP single-session, không làm tab manager hoặc abstraction
    multi-session trước nhu cầu.
  - Phase 2 mới mở rộng UI thành orchestrator nhiều tab/profile chạy song song.

## Mục tiêu

- Mở/đóng browser và persistent profile từ app.
- Start, pause, resume và stop flow bằng nút.
- Hiển thị chính xác trạng thái browser và flow.
- Hiển thị live log và lỗi mà không đóng app.
- Chụp và xem screenshot gần nhất.
- Giữ CLI hoạt động như hiện tại, bao gồm hotkey và dev reload.
- Hỗ trợ Windows trước nhưng không đưa Windows-only API vào business core.

## Lộ trình sản phẩm

### Phase 1 — MVP single-session

- Một cửa sổ chỉ điều khiển một `BotService`, một browser, một persistent profile
  và tối đa một flow tại một thời điểm.
- UI là một workspace duy nhất; không có tab, nút thêm session hoặc
  `SessionManager`.
- Người dùng chọn/cấu hình một profile directory theo settings MVP hiện tại.
- Tập trung hoàn thiện lifecycle, state, logging, recovery và packaging cho một
  instance trước.
- Không xây abstraction multi-session chưa được Phase 1 sử dụng. Tuy vậy,
  `BotService` không nên phụ thuộc vào Qt hoặc dựa vào mutable global state làm
  hai instance tương lai xung đột.

### Phase 2 — Multi-tab orchestrator

- Main window quản lý nhiều runner session; mỗi tab là một session độc lập.
- Mỗi session sở hữu một `BotService`, browser/flow state, log và screenshot
  riêng.
- Mỗi tab chọn đúng một persistent profile và có thể chạy song song với các tab
  dùng profile khác.
- Profile không được xuất hiện ở hai tab. Nếu người dùng chọn profile đã có tab,
  UI chuyển focus sang tab đó thay vì tạo representation thứ hai.
- Chi tiết profile registry, lease và lifecycle nằm trong backlog Phase 2 bên
  dưới; không implement trong MVP.

## Ngoài phạm vi Phase 1

- Global hotkey hoặc OS-level keyboard hook.
- Browser extension và Native Messaging.
- Nhúng Chrome/game trực tiếp vào cửa sổ app.
- Multi-tab, chạy nhiều profile đồng thời và quản lý nhiều `BotService`.
- Remote control qua mạng.
- Cloud sync, tài khoản app hoặc telemetry.
- Visual action/template editor đầy đủ.
- Auto-update trong MVP.

## Kiến trúc mục tiêu Phase 1

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
| `Shift+4` | Train Then Auto Battle | Chạy train, chọn hero năm vòng rồi bàn giao cho auto-map |
| `Shift+5` | Collect Hero EXP | Click các badge EXP available tới khi hết |
| `Shift+6` | Hero Breakthrough | Đột phá hero available và chuyển sang hero kế tiếp |
| `Shift+7` | Fixed Click Loop | Chạy click loop cố định |
| `Shift+8` | Capture Screenshot | Lưu và preview screenshot |
| `Shift+9` | Research | Chạy research flow |
| `Shift+0` | Stop | Dừng mềm flow hiện tại |

Tên nút là business label; UI không cần hiển thị tổ hợp phím. Bảng phản ánh
command table hiện tại; command mới phải dùng cùng resolver/flow implementation
giữa CLI và UI, không tạo implementation riêng.

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

## TODO triển khai Phase 1

### Bước 1 — Tách application service

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

### Bước 2 — State và logging

- [ ] Định nghĩa immutable state/event models.
- [ ] Phát state change khi browser/flow chuyển trạng thái.
- [ ] Thay các `print()` cần hiển thị bằng logger/event sink dùng chung.
- [ ] Giữ console sink để CLI không mất log hiện tại.
- [ ] Thêm UI sink mà không import Qt từ business modules.
- [ ] Chuẩn hóa error event, traceback log và user-facing message.
- [ ] Giới hạn log buffer trong memory.

### Bước 3 — PySide6 shell

- [ ] Thêm dependency PySide6 và `qasync`.
- [ ] Tạo desktop entrypoint riêng; không thay thế CLI entrypoint.
- [ ] Dựng main window theo UI MVP.
- [ ] Bind button với async service command, không block Qt thread.
- [ ] Render state và enable/disable button từ state model.
- [ ] Hiển thị log theo batch để log dày không làm lag UI.
- [ ] Hiển thị screenshot có scale nhưng giữ đúng aspect ratio.
- [ ] Lưu settings local bằng cơ chế cross-platform phù hợp.

### Bước 4 — Shutdown và recovery

- [ ] Khi đóng app: yêu cầu stop flow, chờ task kết thúc, rồi đóng context.
- [ ] Có timeout và fallback khi flow/browser không shutdown sạch.
- [ ] Xử lý persistent profile đang bị process khác khóa.
- [ ] Xử lý browser bị người dùng đóng thủ công.
- [ ] Cho phép restart browser sau lỗi mà không restart app.
- [ ] Ngăn double-click Start tạo hai browser hoặc hai flow task.
- [ ] Không để exception trong Qt callback bị nuốt.

### Bước 5 — Packaging

- [ ] Chốt PyInstaller hoặc Nuitka sau prototype.
- [ ] Package action JSON, template PNG và metadata bằng path không phụ thuộc cwd.
- [ ] Quyết định dùng Chrome đã cài hay bundle Playwright Chromium.
- [ ] Tách writable data: profile, logs, screenshots và user settings khỏi app
  bundle read-only.
- [ ] Tạo Windows build đầu tiên.
- [ ] Smoke-test đường dẫn có space và non-ASCII.
- [ ] Audit macOS/Linux: browser discovery, filesystem path và window behavior.

## Testing TODO Phase 1

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

## Backlog Phase 2 — Multi-tab orchestrator

### Kiến trúc session

```text
MainWindow / SessionManager
├── Tab A -> BotService A -> Profile 1 -> Browser A
├── Tab B -> BotService B -> Profile 2 -> Browser B
└── Tab C -> chưa chọn profile
```

- [ ] Thêm `SessionManager` ở UI/application layer để tạo, tìm, đóng và shutdown
  các runner session.
- [ ] Mỗi tab sở hữu đúng một `BotService`; không chia sẻ `page`, context,
  flow task hoặc `FlowControl` giữa các tab.
- [ ] Route state event, log, lỗi và screenshot về đúng tab phát sinh chúng.
- [ ] Tab label hiển thị profile và trạng thái ngắn, ví dụ `Profile 1 · Running`.
- [ ] Xác định giới hạn số session/browser chạy đồng thời để tránh CPU/RAM tăng
  không kiểm soát.

### Profile selector và tạo profile

- [ ] Dùng editable dropdown để liệt kê profile có sẵn trong một profiles root
  do app quản lý.
- [ ] Khi người dùng nhập tên chưa tồn tại, hiển thị action rõ ràng như
  `Create profile "name"`.
- [ ] Chỉ tạo directory sau khi người dùng nhấn Enter, xác nhận hoặc Start
  Browser; không tạo theo từng ký tự đang gõ để tránh profile rác do typo.
- [ ] Validate tên profile, canonical path và trùng tên trước khi tạo.
- [ ] Có action `Import existing profile directory...` nếu cần dùng profile nằm
  ngoài profiles root.
- [ ] Khi profile đã thuộc một tab, disable nó ở dropdown tab khác. Nếu profile
  được chọn qua search/import, chuyển sang tab đang sở hữu profile đó.
- [ ] Chỉ cho đổi profile của tab khi browser của tab đang `closed`; khóa selector
  trong các state `starting`, `ready` và `closing`.

### Profile ownership và lease

- [ ] `SessionManager` acquire profile lease atomically trước khi start browser
  để hai thao tác Start gần nhau không mở cùng profile.
- [ ] Giữ lease trong toàn bộ thời gian browser context còn mở, kể cả khi flow
  đang `idle`, `paused` hoặc `failed`.
- [ ] Chỉ release lease sau khi context đã đóng, hoặc sau launch failure đã cleanup
  hoàn tất; không release chỉ vì flow dừng.
- [ ] UI ownership chỉ bảo vệ các tab trong app. Vẫn bắt và hiển thị lỗi khi
  profile bị Chrome, CLI hoặc process bên ngoài khóa.
- [ ] Canonicalize path trước khi so sánh để các path spelling khác nhau không
  vượt qua kiểm tra trùng profile.

### Lifecycle và UX nhiều tab

- [ ] Đóng tab đang chạy phải yêu cầu stop flow, đóng browser và chờ cleanup;
  cần confirmation nếu thao tác làm gián đoạn flow.
- [ ] Đóng app phải shutdown tất cả session với timeout/fallback riêng, không để
  lỗi một tab ngăn cleanup các tab còn lại.
- [ ] Browser crash hoặc launch failure ở một tab không được làm hỏng session
  khác.
- [ ] Log buffer và screenshot history/preview phải có giới hạn theo session.
- [ ] Làm rõ settings nào là global và settings nào thuộc từng session.
- [ ] Cân nhắc cảnh báo tài nguyên khi nhiều game/browser chạy đồng thời và hành
  vi Chromium khi window bị minimize hoặc occluded.

### Testing Phase 2

- [ ] Test hai tab với hai profile chạy độc lập và event không bị route nhầm.
- [ ] Test hai tab Start gần đồng thời với cùng profile: chỉ một tab acquire được
  lease.
- [ ] Test profile browser-ready nhưng flow-idle vẫn không thể được tab khác dùng.
- [ ] Test profile bị process ngoài app khóa và lease nội bộ được cleanup sau lỗi.
- [ ] Test đóng tab ở các state closed/starting/ready/running/paused/closing.
- [ ] Test đóng app khi nhiều session ở các state khác nhau.
- [ ] Test chọn profile đã có tab sẽ focus tab cũ, không tạo tab trùng.
- [ ] Test create/import profile, path canonicalization và tên/path không hợp lệ.

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
