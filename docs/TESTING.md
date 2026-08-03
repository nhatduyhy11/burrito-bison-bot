# Testing

Test suite ở root bảo vệ runner Haunted Room, gồm dependency rule, vision/template
matching và hành vi của các flow. Project tham khảo trong `ref_cv/` có test suite
độc lập và không thuộc các lệnh bên dưới.

## Chuẩn bị

Chạy từ thư mục gốc của repo:

```shell
uv sync
```

Test dùng `unittest` trong Python standard library; các dependency OpenCV và NumPy
được lấy từ môi trường do `uv` quản lý.

## Chạy test

Chạy toàn bộ suite:

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
uv run python -m unittest tests.research.test_research_flow -v
```

Chạy một test cụ thể:

```shell
uv run python -m unittest tests.automap.test_map_end.MapEndTest.test_map_end_clicks_followup_once_before_checking_home -v
```

## Phạm vi

- `test_hauntedroom_architecture.py`: dependency rule giữa `core`, `actions`,
  `control_events` và `flows`.
- `test_hauntedroom_vision.py`: template matching, multi-scale và vị trí click.
- `actions/`: action runner, timeout/retry và template wait/skip.
- `automap/`: boss, build, level-up, map-end và orchestration của `Shift+2`.
- `control_events/`: blocker ngoài normal flow, hiện gồm profile new-tab guard.
- `hero_select/test_hero_select.py`: nhận diện, priority, fallback và interaction
  của popup chọn hero.
- `research/`: polling và interaction của flow research.
- `runner/`: standby controller, hotkey, live capture và dev reload.
- `tests/fixtures/`: screenshot cố định cho các test nhận diện ảnh.

Business rule cần bảo vệ khi thay đổi auto-map được mô tả trong
[`SHIFT2_AUTOMAP_FLOW.md`](SHIFT2_AUTOMAP_FLOW.md).

## Fixture ảnh

- Fixture đã chọn và ổn định nằm trong `tests/fixtures/`.
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
