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
uv run python -m unittest tests.test_hauntedroom_runner -v
```

Chạy một test cụ thể:

```shell
uv run python -m unittest tests.test_hauntedroom_runner.HauntedRoomAutoMapTest.test_map_end_completes_when_home_ready_without_reward -v
```

## Phạm vi

- `test_hauntedroom_architecture.py`: dependency rule giữa `core`, `actions`,
  `control_events` và `flows`.
- `test_hauntedroom_vision.py`: template matching, multi-scale và vị trí click.
- `test_hauntedroom_runner.py`: action runner, timeout/retry, hotkey, research và
  business flow auto-map `Shift+2`.
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
