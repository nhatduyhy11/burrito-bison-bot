# Testing

Test suite ở root bảo vệ runner Haunted Room, gồm dependency rule, vision/template
matching và hành vi của các flow. Project tham khảo trong `ref_cv/` có test suite
độc lập và không thuộc các lệnh bên dưới.

## Chuẩn bị

Chạy từ thư mục gốc của repo:

```shell
uv sync
```

Test chủ yếu viết bằng `unittest` trong Python standard library nhưng được chạy
qua `pytest` để có output gọn và hỗ trợ subtests tốt hơn. Các dependency OpenCV
và NumPy được lấy từ môi trường do `uv` quản lý.

## Chạy test

Chạy toàn bộ suite chính:

```shell
uv run --with pytest pytest tests -q
```

Snapshot ngày 2026-08-15:

```text
1 collection error
```

Full suite hiện dừng khi `tests/automap/test_level_up.py` còn import
`LV_SPIN_CLICK_OFFSET_X` và `UPGRADE_CONFIRM_CLICK` từ
`hauntedroom.flows.automap` thay vì module owner
`hauntedroom.flows.automap_support.upgrade_action`. Hai module special-flow vẫn
chạy độc lập và có tổng cộng 16 test pass.

Lệnh `unittest discover` vẫn dùng được khi cần debug theo standard library:

```shell
uv run python -m unittest discover -s tests -v
```

Chạy một module:

```shell
uv run python -m unittest tests.test_hauntedroom_architecture -v
uv run python -m unittest tests.test_hauntedroom_vision -v
uv run python -m unittest tests.actions.test_runner -v
uv run python -m unittest tests.automap.test_boss -v
uv run python -m unittest tests.hero_select.test_hero_select -v
uv run python -m unittest tests.hero_select.test_hero_fallback -v
uv run python -m unittest tests.research.test_research_flow -v
uv run python -m unittest tests.special_flow.test_exp_available_flow -v
uv run python -m unittest tests.special_flow.test_hero_up_available_flow -v
```

Chạy một test cụ thể:

```shell
uv run python -m unittest tests.automap.test_map_end.MapEndTest.test_map_end_clicks_followup_once_before_checking_home -v
```

## Phạm vi

- `test_hauntedroom_architecture.py`: dependency rule giữa `core`, `actions`,
  `control_events` và `flows`.
- `test_hauntedroom_vision.py`: template matching, multi-scale và vị trí click.
- `test_screen_detect.py`: nhận diện screen từ anchor top/arrow, chống match chéo
  và fallback `unknown`.
- `actions/`: action runner, timeout/retry và template wait/skip.
- `automap/`: boss, build, level-up, map-end và orchestration của `Shift+2`.
- `control_events/`: blocker ngoài normal flow, gồm profile new-tab guard và
  game-core iframe CSS guard có startup delay.
- `hero_select/test_hero_select.py`: template priority, ascend và interaction
  mở/chọn option của popup hero level-up.
- `hero_select/test_hero_fallback.py`: nhận diện layout 1/2/3 card, màu tím,
  priority `99`, regression ảnh từng fallback sai và điều kiện capture tracking.
  Asset và selection contract được mô tả tại
  [`tools/rooms/automap/hero_levelup/README.md`](../tools/rooms/automap/hero_levelup/README.md).
- `research/`: polling và interaction của flow research.
- `special_flow/`: detector ảnh, click loop, stop event, command registration và
  dev-reload wiring của `Shift+5` EXP available và `Shift+6` hero breakthrough.
- `runner/`: standby controller, command specs, hotkey, live capture, dev reload và
  startup navigation retry.
- `runner/test_navigation.py`: bỏ page bị kẹt và retry trên page mới khi lần
  navigation đầu timeout, giới hạn số lần thử và validation cấu hình attempts.
- `runner/test_start_automap_loop.py`: regression cho composite flow
  `tools/hauntedroom/flows/start_auto.py`.
- `tests/fixtures/`: screenshot cố định cho các test nhận diện ảnh.

Business rule cần bảo vệ khi thay đổi auto-map được mô tả trong
[`AUTOMAP_FLOWS.md`](AUTOMAP_FLOWS.md).

## Fixture ảnh

- Fixture đã chọn và ổn định nằm trong `tests/fixtures/`.
- Fixture của hai flow mới nằm trong `tests/fixtures/special_flow/`, gồm cả
  trường hợp available/unavailable, artwork vàng/cam gây nhiễu và grid EXP đã
  scroll.
- `Shift+8` chụp viewport live vào
  `tests/fixtures/hauntedroom-captures/` mà không dừng flow hiện tại.
- Screenshot timeout mới được lưu tạm trong `.tmp/hauntedroom-timeouts/`.
- Chỉ commit ảnh cần thiết để tái hiện một behavior; tránh đưa toàn bộ ảnh debug
  vào suite.

Khi sửa template hoặc detector, nên thêm fixture cho cả trường hợp match và
không match, rồi chạy toàn bộ suite để phát hiện ảnh hưởng chéo giữa các detector.

## Kiểm tra match thủ công

Không đưa ảnh preview vào test suite. Khi cần xem nhanh template match và điểm
click, chạy script thủ công; mặc định script chỉ in JSON, chỉ ghi ảnh vào `.tmp/`
khi thêm `--annotate`.

```shell
uv run python tools/debug_template_match.py \
  tests/fixtures/start_home_clean.png \
  tools/rooms/start_home.png \
  --click-position mid_left \
  --scales 1.0 \
  --annotate
```

Ảnh preview có viền đỏ cho vùng match và chấm xanh cho điểm click, nằm trong
`.tmp/template-match/` và không cần cleanup trước khi commit.
