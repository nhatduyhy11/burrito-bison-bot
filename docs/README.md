# Haunted Room Runner

Mã nguồn Burrito Bison cũ được giữ làm tài liệu tham khảo độc lập tại
[`ref_cv/`](../ref_cv/README.md); runner và test ở root hiện chỉ dành cho Haunted Room.

Runner Playwright dùng OpenCV template matching để tìm và click các nút trong Haunted Room. Script dùng browser context của Playwright, không điều khiển chuột ở cấp hệ điều hành.

Tài liệu liên quan:

- [Auto-map flows: `Shift+2` và `Shift+3`](AUTOMAP_FLOWS.md)
- [Map-completion bridge và các điểm có thể stuck](MAP_COMPLETION_BRIDGE.md)
- [Hero level-up selection assets](../tools/rooms/automap/hero_levelup/README.md)
- [Testing](TESTING.md)
- [Capture audit](CAPTURE_AUDIT.md)
- [ADR cấu trúc `core / actions / flows`](ADR_bot.md)
- [Refactor review](REFACTOR.md)
- [Audit template phụ thuộc ngôn ngữ](planning/VISION_TEMPLATE_AUDIT.md)

## Yêu cầu

- Có [`uv`](https://docs.astral.sh/uv/) trong `PATH`.
- Đã cài Google Chrome trên Windows hoặc macOS.
- Chạy lệnh từ thư mục gốc của repo.

Playwright được khai báo trong `pyproject.toml` và khóa phiên bản trong `uv.lock`. Cài hoặc đồng bộ toàn bộ dependency bằng:

```shell
uv sync
{"type": "click", "x": 366, "y": 536, "button": "left"}
```

Khi cần thêm Playwright vào một project `uv` mới, lệnh tương đương phù hợp với `pip install playwright` là `uv add playwright`; lệnh này cập nhật cả `pyproject.toml` và `uv.lock`. Browser mặc định là Chrome cài trên máy và được Playwright tự tìm theo hệ điều hành, không dùng đường dẫn hardcoded.

## Lệnh chạy

Mở runner với action mặc định. Với `ACTION_LOOP_COUNT = 0`, runner vào chế độ standby:

```shell
uv run python tools/hauntedroom_runner.py
```

Khi đang phát triển auto-map, bật hot-reload để giữ nguyên browser và session:

```shell
uv run python tools/hauntedroom_runner.py --dev-reload
```

Sau khi sửa code flow/action, action JSON hoặc template PNG, bấm `Shift+0` để dừng flow cũ rồi bấm hotkey bắt đầu lại. Dev reload giữ nguyên browser/session, nhưng reload module Python liên quan tới flow mới và reload action JSON trước `Shift+1`, `Shift+3` hoặc `Shift+4`. Nếu reload lỗi syntax/import/JSON, runner vẫn mở và ở trạng thái idle để sửa file rồi thử lại.

Với `ACTION_LOOP_COUNT = 0`, standby đã tự giữ browser mở cho tới khi bấm `Ctrl+C`, vì vậy không cần thêm `--keep-open` vào lệnh hot-reload. `--keep-open` chỉ có tác dụng khi cấu hình `ACTION_LOOP_COUNT` lớn hơn `0`.

Khi cấu hình `ACTION_LOOP_COUNT` lớn hơn `0`, giữ browser mở sau khi chạy xong:

```shell
uv run python tools/hauntedroom_runner.py --keep-open
```

Chạy một file action khác:

```shell
uv run python tools/hauntedroom_runner.py --actions tools/my_actions.json
```

Các tùy chọn thường dùng:

- `--browser chrome`: dùng Google Chrome; đây là mặc định và hoạt động trên Windows/macOS.
- `--browser msedge`: dùng Microsoft Edge đã cài trên máy.
- `--browser chromium`: dùng Chromium do Playwright quản lý; browser binary phải được cài riêng.
- `--headless`: chạy không hiển thị cửa sổ browser.
- `--width` và `--height`: thay đổi viewport; mặc định hiện tại là `640x720`.
- `--profile`: thay đổi thư mục browser profile.
- `--url`: thay đổi URL đích.
- `--dev-reload`: reload module Python liên quan mỗi lần bắt đầu flow (`Shift+1` đến `Shift+7`, và `Shift+9`); với `Shift+1`, `Shift+3` và `Shift+4` cũng reload action JSON. Dùng cho vòng lặp debug `Shift+0` → sửa code/template/action → bắt đầu lại flow.
- `--keep-open`: chỉ giữ browser sau khi action hoàn tất khi `ACTION_LOOP_COUNT > 0`; không cần trong standby mặc định.

Xem toàn bộ tùy chọn:

```shell
uv run python tools/hauntedroom_runner.py --help
```

## Runtime settings

Các switch vận hành cấp cao nằm trong `tools/hauntedroom/settings.py`, không phải
CLI args:

- `CAPTURE_HERO_FALLBACK_SCREENSHOTS`: bật/tắt lưu ảnh tracking khi hero selection
  rơi vào fallback 3 card không có card tím. Khi chạy `--dev-reload`, sửa flag này
  rồi dừng/bắt đầu lại `Shift+2` hoặc `Shift+3` sẽ có hiệu lực.
- `ENABLE_SCRIPT_INJECTION`: bật/tắt inject guard JavaScript/CSS cho profile popup
  và iframe `#hwssH5GameCoreframe`. Flag này chỉ đọc lúc runner startup; đổi giá trị
  cần restart browser runner.

## Action file

File action là một JSON array. Runner chạy tuần tự toàn bộ array rồi lặp lại theo `ACTION_LOOP_COUNT` trong `tools/hauntedroom/core/runtime.py`.

Mental model: `run_actions()` execute một sequence typed action trên browser.
Nếu macro được viết bằng JSON, `load_actions()` là adapter đọc JSON, validate
field, resolve path template và normalize default thành typed action object. Vì
vậy JSON macro đi qua `load_actions()` trước, còn Python code có thể tạo
`ClickAction`, `ClickTemplateAction`, `WaitAction` hoặc `ClearBlockersAction` và
gọi `run_actions()` trực tiếp. Auto-map, train, EXP available, hero breakthrough
và research là flow Python riêng, không phải macro JSON trực tiếp; train chỉ tái
sử dụng typed action/config của `start_battle.png` để vào trận.

Khi `ACTION_LOOP_COUNT = 0`, runner load action rồi vào chế độ standby:

- `Shift+T`: tạm thời chạy train mode rồi auto-battle; sau khi flow ổn định sẽ
  được nhập vào screen auto-switch.
- `Shift+5`: click `(440, 500)` trong browser mỗi 1 giây cho đến khi bấm `Shift+0`.
- `Shift+8`: lưu screenshot live của viewport hiện tại vào `tests/fixtures/hauntedroom-captures/` rồi tiếp tục trạng thái hiện tại. Nếu runner đang idle thì vẫn idle; nếu flow đang chạy thì flow vẫn chạy.
- `Shift+1`: chụp một frame rồi tự chọn flow. `home` chạy start-auto loop;
  `automap` chạy đúng một lượt auto-map; `research`, `artifact`, `exp_hero` và
  `hero_avail` chạy flow tương ứng rồi về idle khi xong. `train` và `unknown` chỉ
  được log, không click và không khởi chạy flow.
- Các entry cũ `Shift+2`, `Shift+3`, `Shift+4`, `Shift+6`, `Shift+7`, `Shift+9`,
  `Shift+G` và `Shift+Y` đã được bỏ. Khi auto-map do `Shift+1` khởi chạy đang
  active, các Shift+digit được cấu hình vẫn là control pause/resume,
  pause-at-boss, screenshot và stop.
- `Shift+0`: dừng mềm flow hiện tại và quay lại standby; browser vẫn mở.
- `Ctrl+C` trong terminal: đóng runner và browser.

Hotkey dùng vị trí phím vật lý (`Digit0` đến `Digit9` và `KeyT`), hoạt động trên Windows/macOS và chỉ điều khiển trang browser đang focus. Các Shift+digit không được map bị ignore. `Shift+8` chỉ chụp screenshot và không đổi trạng thái flow. `Shift+0` vẫn dừng hẳn được flow khi flow đang pause.

Các số điều khiển trong lúc auto-map/start-auto chạy được cấu hình tại
`START_AUTO_HOTKEYS` trong `tools/hauntedroom/settings.py`. Giữ nguyên tên action
và chỉ đổi các chuỗi số; năm action phải dùng năm số khác nhau. Ví dụ:

```python
START_AUTO_HOTKEYS = {
    "pause_resume": "1",
    "pause_at_boss": "2",
    "pause_at_final_boss": "3",
    "stop": "0",
    "screenshot": "8",
}
```

Config này chỉ override hotkey khi auto-map hoặc start-auto đang chạy. Khi runner
idle hoặc đang chạy flow khác, `Shift+0` và `Shift+8` vẫn giữ behavior mặc định. Với
`--dev-reload`, config được đọc lại khi bắt đầu một flow `Shift+2`/`Shift+3` mới; nếu
không dùng dev reload thì cần restart runner.

Code runner được chia theo trách nhiệm:

- `tools/hauntedroom_runner.py`: entrypoint, CLI/browser bootstrap và shutdown.
- `tools/hauntedroom/runner/standby.py`: hotkey queue, control command và lifecycle task; command table được inject từ entrypoint.
- `tools/hauntedroom/runner/commands.py`: factory/dataclass thuần cho hotkey command spec.
- `tools/hauntedroom/runner/default_commands.py`: wiring mặc định tạo `FLOW_COMMANDS`.
- `tools/hauntedroom/runner/navigation.py`: mở URL game và retry lỗi navigation transient khi khởi động.
- `tools/hauntedroom/runner/reload.py`: dev reload policy.
- `tools/hauntedroom/flows/start_auto.py`: composite flow/wrapper `Shift+3`.
- `tools/hauntedroom/flows/train.py`: composite train → hero selection → auto-map của `Shift+4`.
- `tools/hauntedroom/flows/exp_available.py`: detector/click loop EXP của `Shift+5`.
- `tools/hauntedroom/flows/hero_up_available.py`: detector/click loop đột phá hero của `Shift+6`.

Bốn action hiện được hỗ trợ. Flow dùng `clear_blockers` tại các checkpoint có thể xuất hiện popup:

```json
[
  { "type": "clear_blockers", "templates_dir": "rooms/blocker", "until_template": "rooms/start_home.png" },
  { "type": "click_template", "template": "rooms/start_home.png", "note": "Start HOME" },
  { "type": "click_template", "template": "rooms/start_battle.png", "note": "Start Battle" }
]
```

- `click_template`: chụp viewport và dùng OpenCV tìm template liên tục. Khi score đạt threshold, runner chờ `delay_ms` rồi click tâm template.
- `clear_blockers`: match các file PNG trong `templates_dir` theo thứ tự `priority`. Runner click blocker đầu tiên đạt threshold rồi quét lại từ đầu. Khi thấy `until_template` và không còn blocker, runner chuyển sang action kế tiếp mà không click `until_template`.
- `click`: bắt buộc có `x`, `y`; `button` và `note` là tùy chọn.
- `wait`: bắt buộc có `ms`; `note` là tùy chọn.

### Profile popup và game-core iframe guard

Game đôi khi mở một tab mới có URL dạng
`https://cp.hhgame.vn/v2/user/profile/...`. Đây là sự kiện hiếm nên runner không
chạy một polling loop riêng cho nó. Khi khởi động, entrypoint gọi
`install_profile_popup_guard(page)` đúng một lần, trước khi load URL game:

1. `page.add_init_script(...)` đăng ký guard cho mọi document/frame được tạo
   hoặc navigate về sau.
2. Runner đồng thời evaluate guard trên các frame đang tồn tại để bảo vệ cả
   document hiện tại.
3. Guard chỉ nhận URL có protocol `https`, host chính xác `cp.hhgame.vn` và path
   bắt đầu bằng `/v2/user/profile/`.
4. Guard chặn ba đường mở phổ biến: `window.open(...)`, click vào link và submit
   form trỏ tới URL trên. Các URL khác vẫn dùng hành vi browser bình thường.

Nếu website mở tab bằng một cơ chế vượt qua profile guard, mỗi vòng quét của
`clear_blockers` có fallback kiểm tra `page.context.pages`. Khi Playwright thực
sự thấy một tab profile, runner đóng tab đó, đưa tab game gốc về foreground và
tiếp tục logic blocker bình thường.

Sau khi URL game được commit, entrypoint chờ nền 30 giây rồi mới
gọi `install_game_core_frame_guard(page)`. Khoảng chờ không khóa hotkey/controller
và để game hoàn tất startup trước khi CSS được inject. Sau khoảng chờ, guard thêm
một style idempotent vào top document để đặt
`#hwssH5GameCoreframe{visibility:hidden!important}`. Guard không đọc `#document`
bên trong iframe, không dùng `MutationObserver`/`postMessage`, và không thay đổi
`display` hoặc `pointer-events`. Sau khi inject thành công, runner ghi một dòng
`iframe guard: injected CSS after 30000ms; #hwssH5GameCoreframe hidden` ra log.

Đường dẫn `template` được tính tương đối từ file action JSON. Các tùy chọn của `click_template`:

- `threshold`: mặc định `0.9`.
- `timeout_ms`: thời gian tối đa chờ ảnh, mặc định `30000`.
- `poll_ms`: khoảng nghỉ giữa các lần detect, mặc định `600`.
- `delay_ms`: thời gian chờ trước mỗi click, gồm cả click đầu sau detect và các click liên tiếp; mặc định `400`.
- `click_count`: số lần click template tối đa sau khi detect, mặc định `1`.
- `recheck_before_repeat`: khi là `true`, chụp và detect lại template trước mỗi
  click lặp; dừng các click còn lại ngay khi template biến mất.
- `repeat_delay_ms`: thời gian chờ trước mỗi lần detect/click lặp; mặc định dùng
  giá trị `delay_ms`.
- `button`: mặc định `left`.
- `skip_if_template`: template báo action hiện tại đã không còn cần thiết; nếu template này đạt cùng `threshold`, runner bỏ qua click hiện tại và chuyển sang action kế tiếp.

`clear_blockers` hỗ trợ `click_positions` để đổi điểm click theo tên file. Vị trí mặc định là `center`; `top_middle` click chính giữa cạnh trên của vùng match:

```json
{ "click_positions": { "overlay_newbie.png": "top_middle" } }
```

Thứ tự kiểm tra blocker được cấu hình bằng tên file trong `priority`. Các PNG không được liệt kê sẽ được nối vào cuối theo thứ tự tên file:

```json
{
  "priority": [
    "lubu_close.png",
    "overlay_close.png",
    "overlay_close_2.png",
    "overlay_newbie.png"
  ]
}
```

Không có thời gian load cố định trước flow. Template đầu tiên đóng vai trò điều kiện báo game đã load.

Flow cũng chạy `clear_blockers` sau khi click `start_home` và trước khi click `start_battle`, vì blocker có thể xuất hiện trong lúc chuyển giữa hai màn hình này.

File mặc định là `tools/hauntedroom_actions.sample.json`.

## Log và ghi tọa độ

Mỗi vòng lặp có log bắt đầu và hoàn tất:

```text
loop 1/10 start
...
loop 1/10 finish
```

Các thao tác click thủ công trong browser được in ra terminal dưới dạng JSON để có thể chép vào action file. Click do runner tự gửi sẽ không bị ghi lại.

Wait dài có countdown; ngưỡng countdown và số vòng lặp được cấu hình trong `tools/hauntedroom/core/runtime.py`.

## Testing

Project root chạy test bằng `unittest` trong Python standard library, qua môi
trường `uv`; không dùng pytest cho lệnh test chính.

```shell
uv run python -m unittest discover -s tests -v
```

Xem [TESTING.md](TESTING.md) để biết cách chạy từng nhóm test và quản lý fixture.

### Test fixtures

Các screenshot PNG dùng làm testcase nằm trong `tests/fixtures/`. `Shift+8` lưu ảnh
chụp trực tiếp vào `tests/fixtures/hauntedroom-captures/`; ảnh đã chọn từ các lần
timeout nằm ở `tests/fixtures/hauntedroom-timeouts/`. Screenshot timeout mới vẫn
được runner lưu tạm tại `.tmp/hauntedroom-timeouts/`.

## Browser profile

Profile mặc định nằm tại `.tmp/hauntedroom-profile`. Cookies, localStorage, IndexedDB và session game được giữ lại giữa các lần chạy.

Chỉ một browser instance được dùng profile này tại cùng thời điểm. Nếu một lần chạy với `--keep-open` vẫn còn hoạt động, lần chạy tiếp theo có thể báo profile đang được sử dụng.

Runner chặn service worker trong browser context automation vì game không cần thành phần này để bot hoạt động, trong khi worker cũ trong persistent profile có thể cản navigation mới. Cookies, localStorage và dữ liệu đăng nhập vẫn được giữ nguyên.

Khi navigation đầu tiên bị treo, thường gặp hơn nếu chạy lại ngay sau `Ctrl+C`, runner chờ tối đa 15 giây, tạo tab thay thế trong cùng browser context rồi mới bỏ tab đang kẹt và tự thử lại. Thứ tự này giữ persistent context còn sống khi tab cũ bị đóng. Tab mới được cài lại popup guard trước khi tải game; cookie, localStorage và dữ liệu đăng nhập trong persistent profile vẫn được giữ. Runner thử tối đa 3 lần, với khoảng chờ tăng dần 2 giây và 4 giây; chỉ lần cuối thất bại mới trả traceback. Terminal sẽ in `Navigation attempt ... timed out` khi cơ chế này được kích hoạt.

Nếu cả ba lần startup navigation đều timeout và browser đứng ở `about:blank`, xem
[TROUBLESHOOTING.md](TROUBLESHOOTING.md#cả-ba-lần-startup-navigation-đều-timeout)
để chẩn đoán URL, network service và phục hồi cache profile mà không mất session.

Xóa profile sẽ reset session và có thể làm game quay lại luồng guest/intro.

## Giới hạn hiện tại

- Template matching thử hai scale cố định `1.0` và `0.67`, sau đó dùng kết quả có score cao hơn.
- Viewport nên được giữ cố định ở kích thước dùng khi chụp template.
- Khi hết `timeout_ms` lần đầu, runner ghi `timeout count=1/2`, bỏ phần action còn lại của loop hiện tại và thử lại từ đầu ở loop kế tiếp.
- Hai loop timeout liên tiếp sẽ dừng runner. Một loop hoàn tất không timeout sẽ reset bộ đếm về `0`.
- Mỗi lần timeout, runner lưu screenshot cuối vào `.tmp/hauntedroom-timeouts/` và in đường dẫn file trong terminal.

## Template search region

`click_template` accepts an optional `region` field with
`[left, top, right, bottom]` coordinates. Template matching is limited to that
rectangle, while the resulting click still uses absolute viewport coordinates:

```json
{
  "type": "click_template",
  "template": "rooms/misc/research_available.png",
  "region": [120, 390, 520, 600]
}
```
