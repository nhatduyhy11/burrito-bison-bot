# Haunted Room Runner

Mã nguồn Burrito Bison cũ được giữ làm tài liệu tham khảo độc lập tại
[`ref_cv/`](../ref_cv/README.md); runner và test ở root hiện chỉ dành cho Haunted Room.

Runner Playwright dùng OpenCV template matching để tìm và click các nút trong Haunted Room. Script dùng browser context của Playwright, không điều khiển chuột ở cấp hệ điều hành.

Tài liệu liên quan:

- [Auto-map flows: `Shift+2` và `Shift+3`](AUTOMAP_FLOWS.md)
- [Hero level-up selection assets](../tools/rooms/automap/hero_levelup/README.md)
- [Testing](TESTING.md)
- [ADR cấu trúc `core / actions / flows`](ADR_bot.md)
- [Refactor review](REFACTOR.md)

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

Sau khi sửa code flow/action, action JSON hoặc template PNG, bấm `Shift+0` để dừng flow cũ rồi bấm hotkey bắt đầu lại. Dev reload giữ nguyên browser/session, nhưng reload module Python liên quan tới flow mới và reload action JSON trước `Shift+1` hoặc `Shift+3`. Nếu reload lỗi syntax/import/JSON, runner vẫn mở và ở trạng thái idle để sửa file rồi thử lại.

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
- `--dev-reload`: reload module Python liên quan mỗi lần bắt đầu flow (`Shift+1`, `Shift+2`, `Shift+3`, `Shift+7`, `Shift+9`); với `Shift+1` và `Shift+3` cũng reload action JSON. Dùng cho vòng lặp debug `Shift+0` → sửa code/template/action → bắt đầu lại flow.
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
- `CLICK_EXIT_ON_BOSS`: khi bật, auto-map click `rooms/exit_click.png` đúng một lần
  khi boss HP đi vào upper search region, nhờ đó game pause và flow dừng trước
  `exit_confirm`. Khi tắt, mini-boss chỉ được detect/no-op; final boss vẫn có thể
  deploy pet theo logic riêng rồi tiếp tục flow. Flag này hot-reload theo `Shift+2`
  hoặc `Shift+3` khi chạy `--dev-reload`.

## Action file

File action là một JSON array. Runner chạy tuần tự toàn bộ array rồi lặp lại theo `ACTION_LOOP_COUNT` trong `tools/hauntedroom/core/runtime.py`.

Khi `ACTION_LOOP_COUNT = 0`, runner load action rồi vào chế độ standby:

- `Shift+1`: chạy flow enter-exit room liên tục.
- `Shift+2`: chạy business-core auto-map sau khi đã vào map và bấm `start_battle` thủ công. Xem [tài liệu auto-map](AUTOMAP_FLOWS.md) để biết priority, điều kiện và hành vi của từng phase.
- `Shift+3`: khi idle, bắt đầu loop start room → auto-map → chờ 2 giây → start map tiếp theo. Khi loop đang chạy, bấm lại để pause; bấm lần nữa để resume đúng state hiện tại. Đoạn start tái sử dụng action của `Shift+1` tới hết `start_battle.png` và bỏ qua đoạn exit. Detector map thua hiện là placeholder luôn trả về `False`; xem [tài liệu auto-map](AUTOMAP_FLOWS.md).
- `Shift+7`: click `(440, 500)` trong browser mỗi 1 giây cho đến khi bấm `Shift+0`.
- `Shift+8`: lưu screenshot live của viewport hiện tại vào `tests/fixtures/hauntedroom-captures/` rồi tiếp tục trạng thái hiện tại. Nếu runner đang idle thì vẫn idle; nếu flow đang chạy thì flow vẫn chạy.
- `Shift+9`: dùng threshold riêng `0.6` và chỉ match scale `1.0`. Runner thử tìm badge `rooms/misc/research_available.png` tối đa 4 lần, cách nhau 600 ms; nếu thấy thì chờ 600 ms và click góc dưới-trái để mở mục nghiên cứu. Sau đó runner click center `research_active.png`. Khi active miss 4 lần, flow quay lại tìm available; chỉ về idle khi available cũng miss đủ 4 lần.
- `Shift+0`: dừng mềm flow hiện tại và quay lại standby; browser vẫn mở.
- `Shift+4` đến `Shift+6`: được dành sẵn cho các flow bổ sung và hiện chỉ in thông báo chưa cấu hình.
- `Ctrl+C` trong terminal: đóng runner và browser.

Hotkey dùng vị trí phím vật lý (`Digit0` đến `Digit9`), hoạt động trên Windows/macOS và chỉ điều khiển trang browser đang focus. Khi một flow đang chạy, runner không nhận flow khác cho tới khi flow đó hoàn tất hoặc được dừng bằng `Shift+0`; riêng `Shift+3` toggle pause/resume cho chính start-auto loop và `Shift+8` chỉ chụp screenshot nên không bị chặn. `Shift+0` vẫn dừng hẳn được flow `Shift+3` khi flow đang pause.

Code runner được chia theo trách nhiệm:

- `tools/hauntedroom_runner.py`: entrypoint, CLI/browser bootstrap và shutdown.
- `tools/hauntedroom/runner/standby.py`: hotkey queue, control command và lifecycle task.
- `tools/hauntedroom/runner/commands.py`: map hotkey sang flow resolver/start function.
- `tools/hauntedroom/runner/reload.py`: dev reload policy.
- `tools/hauntedroom/flows/start_auto.py`: composite flow/wrapper `Shift+3`.

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

Xóa profile sẽ reset session và có thể làm game quay lại luồng guest/intro.

## Giới hạn hiện tại

- Template matching thử hai scale cố định `1.0` và `0.67`, sau đó dùng kết quả có score cao hơn.
- Viewport nên được giữ cố định ở kích thước dùng khi chụp template.
- Khi hết `timeout_ms` lần đầu, runner ghi `timeout count=1/2`, bỏ phần action còn lại của loop hiện tại và thử lại từ đầu ở loop kế tiếp.
- Hai loop timeout liên tiếp sẽ dừng runner. Một loop hoàn tất không timeout sẽ reset bộ đếm về `0`.
- Mỗi lần timeout, runner lưu screenshot cuối vào `.tmp/hauntedroom-timeouts/` và in đường dẫn file trong terminal.
