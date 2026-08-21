# Haunted Room Runner

Bot tự động hóa Haunted Room bằng Playwright và OpenCV. Runner điều khiển trang
game trong một browser profile riêng, nhận diện màn hình/template từ screenshot
và gửi click qua Playwright; không điều khiển chuột ở cấp hệ điều hành.

Mã Burrito Bison cũ được giữ độc lập tại [`ref_cv/`](../ref_cv/README.md) để tham
khảo. Code và test ở root hiện chỉ dành cho Haunted Room.

## Quick start

Yêu cầu:

- Python `>=3.9`.
- [`uv`](https://docs.astral.sh/uv/) có trong `PATH`.
- Google Chrome đã được cài. Có thể dùng Edge hoặc Chromium qua tùy chọn CLI.
- Chạy mọi lệnh từ thư mục gốc của repo.

Cài dependency và mở runner:

```shell
uv sync
uv run python tools/hauntedroom_runner.py
```

Runner mở game tại `https://hauntedroomvnh5.joynetgame.com/` với viewport mặc
định `640x720` và profile `.tmp/hauntedroom-profile`. Profile giữ cookie,
localStorage và phiên đăng nhập giữa các lần chạy. Không mở đồng thời hai runner
dùng chung profile này.

## Cách vận hành

Với cấu hình mặc định `ACTION_LOOP_COUNT = 0`, runner vào standby và nhận hotkey
khi tab game đang focus:

| Hotkey | Khi runner idle |
| --- | --- |
| `Shift+1` | Chụp một frame, nhận diện màn hình hiện tại và chạy flow phù hợp. |
| `Shift+T` | Chạy train mode rồi auto-battle. |
| `Shift+5` | Lazy-load `--actions` rồi chạy action JSON lặp vô hạn cho đến khi dừng. |
| `Shift+9` | Chạy macro đặc biệt `spawn_exit_lvup`: vào room, bắt đầu battle, thoát room rồi lặp lại liên tục. |
| `Shift+8` | Lưu screenshot vào `tests/fixtures/hauntedroom-captures/`; không đổi trạng thái flow. |
| `Shift+0` | Dừng mềm flow hiện tại và quay lại standby. |
| `Ctrl+C` | Đóng runner và browser. |

`Shift+1` dispatch theo kết quả detect:

| Màn hình | Flow được chạy |
| --- | --- |
| `home` | Start-auto loop: vào trận, chạy auto-map và lặp map. |
| `automap` | Chạy đúng một lượt auto-map. |
| `research` | Research. |
| `artifact` | Artifact. |
| `exp_hero` | EXP available. |
| `hero_avail` | Hero breakthrough available. |
| `train`, `unknown` | Chỉ ghi log, không khởi chạy flow. |

Khi auto-map hoặc start-auto đang chạy, các phím số được dùng làm control:

| Hotkey mặc định | Control |
| --- | --- |
| `Shift+1` | Pause/resume ngay tại checkpoint của flow. |
| `Shift+2` | Pause một lần khi gặp boss kế tiếp. |
| `Shift+3` | Pause một lần khi gặp final boss. |
| `Shift+8` | Chụp screenshot và tiếp tục flow. |
| `Shift+0` | Dừng flow, kể cả khi flow đang pause. |

Các Shift+digit khác bị bỏ qua trong lúc auto-map/start-auto giữ quyền điều
khiển. Hotkey dựa trên vị trí phím vật lý (`Digit0` đến `Digit9`, `KeyT`) và chỉ
hoạt động trong trang browser đang focus.

## Tùy chọn CLI

Ví dụ thường dùng:

```shell
# Hot-reload code/template/action giữa các lần khởi chạy flow
uv run python tools/hauntedroom_runner.py --dev-reload

# Dùng action JSON khác
uv run python tools/hauntedroom_runner.py --actions tools/json_macro/macro_simple.json

# Dùng Edge hoặc Chromium do Playwright quản lý
uv run python tools/hauntedroom_runner.py --browser msedge
uv run python tools/hauntedroom_runner.py --browser chromium

# Bật log/debug behavior của flow auto-map
uv run python tools/hauntedroom_runner.py --debug
```

Các option hiện có:

- `--actions`: action JSON được load khi bấm `Shift+5`, mặc định
  `tools/json_macro/macro.env.json`. File local này bị Git ignore; khởi tạo từ
  `macro_simple.json` và chỉnh tự do theo máy/phiên chạy.

Các macro tham khảo được track trong `tools/json_macro/`:

- `macro_simple.json`: click `(440, 500)` rồi đợi một giây.
- `macro_record.json`: chuỗi click/wait dài được ghi lại trước đây.
- `hauntedroom_actions.sample.json`: ví dụ phức tạp dùng template matching và
  blocker clearing.
- `--profile`: browser profile, mặc định `.tmp/hauntedroom-profile`.
- `--url`: URL game.
- `--browser {chrome,msedge,chromium}`: Chrome là mặc định; `chromium` cần
  browser binary do Playwright quản lý (`uv run playwright install chromium`).
- `--width`, `--height`: viewport, mặc định `640x720`.
- `--headless`: chạy không hiện cửa sổ browser.
- `--dev-reload`: reload flow, vision, template và action liên quan mỗi lần
  `Shift+1` dispatch; các direct flow cũng reload module tương ứng.
- `--debug`: truyền debug mode vào train/auto-map/start-auto.

Xem help trực tiếp để tránh lệch với CLI:

```shell
uv run python tools/hauntedroom_runner.py --help
```

Vòng lặp phát triển khuyến nghị là chạy với `--dev-reload`, sau đó
`Shift+0` → sửa code/template/action JSON → dùng hotkey để chạy lại. Browser và
session được giữ nguyên. Nếu reload lỗi syntax/import/JSON, runner vẫn ở idle để
có thể sửa rồi thử lại.

## Runtime settings

Các switch không nằm trong CLI được khai báo tại
`tools/hauntedroom/settings.py`:

- `START_AUTO_HOTKEYS`: remap năm control của auto-map/start-auto. Giữ nguyên
  tên action, dùng năm digit khác nhau từ `0` đến `9`.
- `CAPTURE_HERO_FALLBACK_SCREENSHOTS`: lưu ảnh chẩn đoán vào
  `.tmp/hauntedroom-fallbacks/` khi hero selection phải fallback.
- `ENABLE_SCRIPT_INJECTION`: bật JavaScript/CSS guard cho profile popup và H5
  SDK iframe. Mặc định hiện là `False`; thay đổi setting này cần restart runner.

Ví dụ remap control:

```python
START_AUTO_HOTKEYS = {
    "pause_resume": "1",
    "pause_at_boss": "2",
    "pause_at_final_boss": "3",
    "stop": "0",
    "screenshot": "8",
}
```

Khi dùng `--dev-reload`, settings của auto-map được đọc lại trước khi bắt đầu
auto-map/start-auto mới.

## Action JSON

File action là một JSON array. Đường dẫn template được resolve tương đối từ vị
trí file JSON. Bốn action type được hỗ trợ:

- `click`: click tọa độ `x`, `y`.
- `click_template`: poll screenshot đến khi template match rồi click.
- `clear_blockers`: click lần lượt các blocker cho đến khi màn hình đích xuất
  hiện và không còn blocker.
- `wait`: chờ theo `ms`.

Ví dụ tối thiểu:

```json
[
  {
    "type": "clear_blockers",
    "templates_dir": "rooms/blocker",
    "until_template": "rooms/start_home.png"
  },
  {
    "type": "click_template",
    "template": "rooms/start_home.png",
    "note": "Start HOME"
  },
  {
    "type": "click",
    "x": 366,
    "y": 536,
    "button": "left"
  },
  {
    "type": "wait",
    "ms": 1000
  }
]
```

`click_template` hỗ trợ `threshold`, `timeout_ms`, `poll_ms`, `delay_ms`,
`click_count`, `repeat_delay_ms`, `recheck_before_repeat`, `button`, `note`,
`skip_if_template`, `click_position`, `scales`, `skip_template_scales` và
`region: [left, top, right, bottom]`.

`clear_blockers` hỗ trợ `priority`, `click_positions`, `threshold`,
`timeout_ms`, `poll_ms`, `delay_ms`, `note` và `until_template_scales`. Các vị
trí click hợp lệ là `center`, `top_middle`, `mid_left`, `bottom_left`.

Action JSON chủ yếu phục vụ đoạn vào/ra room. Auto-map, train, research,
artifact, EXP và hero breakthrough là flow Python riêng. Mỗi timeout sẽ lưu ảnh
vào `.tmp/hauntedroom-timeouts/`; timeout hai lần liên tiếp làm action runner
dừng, còn một loop thành công sẽ reset bộ đếm.

## Testing

Chạy toàn bộ test suite:

```shell
uv run python -m unittest discover -s tests -v
```

Fixture nằm trong `tests/fixtures/`. Xem [TESTING.md](TESTING.md) để chạy từng
nhóm test và biết quy ước quản lý screenshot.

## Cấu trúc chính

- `tools/hauntedroom_runner.py`: entrypoint, browser bootstrap và shutdown.
- `tools/hauntedroom/core/`: CLI, runtime, vision, template matching và mouse.
- `tools/hauntedroom/actions/`: model, loader và runner cho action JSON.
- `tools/hauntedroom/runner/`: standby controller, command registry, navigation
  và dev reload.
- `tools/hauntedroom/flows/`: các business flow.
- `tools/hauntedroom/flows/automap_support/`: phase/action/vision của auto-map.
- `tools/rooms/`: template PNG production.
- `tests/`: test và fixture regression.

## Tài liệu liên quan

- [Auto-map internals](AUTOMAP_FLOWS.md)
- [Map-completion bridge](MAP_COMPLETION_BRIDGE.md)
- [Hero level-up selection](../tools/rooms/automap/hero_levelup/README.md)
- [Testing](TESTING.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Capture audit](CAPTURE_AUDIT.md)
- [Kiến trúc hiện tại](ARCHITECTURE.md)
- [ADR-001: Haunted Room package boundaries](adr/ADR-001-hauntedroom-package-boundaries.md)
- [Framework extraction backlog](planning/FRAMEWORK_EXTRACTION_HANDOVER.md)
- [Vision template audit](planning/VISION_TEMPLATE_AUDIT.md)

## Giới hạn và lưu ý

- Template matching phụ thuộc viewport/scale và asset đã capture; giữ viewport
  đúng với môi trường tạo template để có kết quả ổn định.
- Screen auto-switch chỉ chạy flow khi detector nhận ra một màn hình đã map.
  Trường hợp `unknown` được lưu ảnh vào `.tmp/hauntedroom-fallbacks/` để debug.
- Runner chặn service worker trong automation context để tránh worker cũ làm
  kẹt navigation, nhưng vẫn giữ cookie/localStorage trong persistent profile.
- Nếu startup navigation timeout, runner tự thay tab và retry tối đa ba lần.
  Xem [TROUBLESHOOTING.md](TROUBLESHOOTING.md) trước khi xóa profile vì xóa
  `.tmp/hauntedroom-profile` sẽ mất session đăng nhập.
