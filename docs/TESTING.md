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

Snapshot ngày 2026-08-19:

```text
217 passed, 4 skipped, 36 subtests passed in 14.16s
```

Snapshot trên được lấy bằng đúng lệnh full-suite ở root. Số `subtests` được
pytest báo riêng, không cộng vào con số `217 passed`.

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
uv run python -m unittest tests.automap.test_boss_flow -v
uv run python -m unittest tests.hero_select.test_hero_vision -v
uv run python -m unittest tests.hero_select.test_hero_choice_policy -v
uv run python -m unittest tests.hero_select.test_hero_action -v
uv run python -m unittest tests.hero_select.test_hero_flow_adapter -v
uv run python -m unittest tests.hero_select.test_hero_integration -v
uv run python -m unittest tests.runner.test_standby_hotkeys tests.runner.test_standby_orchestration -v
uv run python -m unittest tests.runner.test_train_flow -v
uv run python -m unittest tests.research.test_research_flow -v
uv run python -m unittest tests.special_flow.test_artifact_flow -v
uv run python -m unittest tests.special_flow.test_exp_available_flow -v
uv run python -m unittest tests.special_flow.test_hero_up_available_flow -v
uv run python -m unittest tests.test_screen_detect -v
```

Chạy một test cụ thể:

```shell
uv run python -m unittest tests.automap.test_map_reward.MapRewardTest.test_map_end_clicks_followup_twice_before_checking_home -v
```

## Phạm vi

- `test_hauntedroom_architecture.py`: dependency rule giữa `core`, `actions`,
  `control_events` và `flows`.
- `test_hauntedroom_vision.py`: template matching, multi-scale và vị trí click.
- `test_hauntedroom_mouse.py`: click/wait, smooth drag và bảo đảm nhả chuột khi
  thao tác lỗi.
- `test_screen_detect.py`: nhận diện screen từ anchor top/arrow, chống match chéo
  và fallback `unknown`, gồm cả việc lưu screenshot chẩn đoán.
- `test_capture_paths.py`: đường dẫn lưu fallback screenshot dưới `.tmp/`.
- `actions/`: action runner, timeout/retry và template wait/skip.
- `automap/`: boss HP/progress/control/action, gear, build, level-up, reward,
  daily-first-win, map completion và orchestration one-map.
- `control_events/`: blocker ngoài normal flow, gồm profile new-tab guard và
  game-core iframe CSS guard có startup delay.
- `hero_select/test_hero_vision.py`: nhận diện layout/card color, ascend và các
  regression ảnh từng fallback sai.
- `hero_select/test_hero_choice_policy.py`: ascend/template priority, priority
  `99` và thứ tự fallback yellow/purple/red.
- `hero_select/test_hero_action.py`: hành vi mở/poll/chọn option, settle timing và
  điều kiện capture tracking.
- `hero_select/test_hero_flow_adapter.py`: contract mỏng giữa `AutomapFlow`, hero
  action và map state.
- `hero_select/test_hero_integration.py`: regression xuyên suốt bằng fixture thật
  từ `AutomapFlow` qua vision/choice đến click và capture policy.
  Asset và selection contract được mô tả tại
  [`tools/rooms/automap/hero_levelup/README.md`](../tools/rooms/automap/hero_levelup/README.md).
- `research/`: polling và interaction của flow research.
- `special_flow/`: detector ảnh, interaction, stop event và dev-reload wiring
  của artifact, EXP available và hero breakthrough.
- `runner/`: standby controller, command specs, hotkey, live capture, dev reload và
  startup navigation retry; gồm screen auto-switch của `Shift+1` và direct flow
  `Shift+T`/`Shift+5`.
- `runner/test_navigation.py`: bỏ page bị kẹt và retry trên page mới khi lần
  navigation đầu timeout, giới hạn số lần thử và validation cấu hình attempts.
- `runner/test_start_automap_loop.py`: regression cho composite flow
  `tools/hauntedroom/flows/start_auto.py`.
- `runner/test_train_flow.py`: nhận diện lượt train, challenge, chọn đủ năm hero
  rồi handoff sang auto-map.
- `tests/fixtures/`: screenshot cố định cho các test nhận diện ảnh.

Business rule cần bảo vệ khi thay đổi auto-map được mô tả trong
[`AUTOMAP_FLOWS.md`](AUTOMAP_FLOWS.md).

## Fixture ảnh

- Fixture đã chọn và ổn định nằm trong `tests/fixtures/`.
- Fixture của các special flow nằm trong `tests/fixtures/special_flow/`, gồm
  artifact, EXP available và hero breakthrough; có cả trường hợp
  available/unavailable, artwork gây nhiễu và grid EXP đã scroll.
- `Shift+8` chụp viewport live vào
  `tests/fixtures/hauntedroom-captures/` mà không dừng flow hiện tại.
- `newbie_block_screen.png` và `newbie_block_screen_en.png` khóa regression
  blocker màn hướng dẫn trên giao diện tiếng Việt và tiếng Anh; cả hai phải dùng
  cùng template đồ họa `overlay_newbie.png` và click `(405, 506)`.
- Screenshot timeout mới được lưu tạm trong `.tmp/hauntedroom-timeouts/`.
- Screenshot fallback của screen detector và hero selection được lưu trong
  `.tmp/hauntedroom-fallbacks/`.
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
