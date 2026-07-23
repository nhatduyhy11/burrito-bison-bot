# Haunted Room Runner

Runner Playwright đơn giản để tự động click và chờ trong Haunted Room. Script dùng browser context của Playwright, không điều khiển chuột ở cấp hệ điều hành.

## Yêu cầu

- Có [`uv`](https://docs.astral.sh/uv/) trong `PATH`.
- Đã cài Google Chrome trên Windows hoặc macOS.
- Chạy lệnh từ thư mục gốc của repo.

Playwright được khai báo trong `pyproject.toml` và khóa phiên bản trong `uv.lock`. Cài hoặc đồng bộ toàn bộ dependency bằng:

```shell
uv sync
```

Khi cần thêm Playwright vào một project `uv` mới, lệnh tương đương phù hợp với `pip install playwright` là `uv add playwright`; lệnh này cập nhật cả `pyproject.toml` và `uv.lock`. Browser mặc định là Chrome cài trên máy và được Playwright tự tìm theo hệ điều hành, không dùng đường dẫn hardcoded.

## Lệnh chạy

Chạy action mặc định rồi tự đóng browser khi hoàn tất:

```shell
uv run python tools/hauntedroom_runner.py
```

Giữ browser mở sau khi chạy xong:

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

Xem toàn bộ tùy chọn:

```shell
uv run python tools/hauntedroom_runner.py --help
```

## Action file

File action là một JSON array. Runner chạy tuần tự toàn bộ array rồi lặp lại theo `ACTION_LOOP_COUNT` trong `tools/hauntedroom_common.py`. Khi `ACTION_LOOP_COUNT = 0`, runner chỉ mở trang game, không đọc/chạy action và chờ cho tới khi nhấn `Ctrl+C`.

Hai action hiện được hỗ trợ:

```json
[
  { "type": "click", "x": 330, "y": 570, "button": "left", "note": "Start" },
  { "type": "wait", "ms": 1500, "note": "Wait for screen" }
]
```

- `click`: bắt buộc có `x`, `y`; `button` và `note` là tùy chọn.
- `wait`: bắt buộc có `ms`; `note` là tùy chọn.

File mặc định là `tools/hauntedroom_actions.sample.json`.

## Log và ghi tọa độ

Mỗi vòng lặp có log bắt đầu và hoàn tất:

```text
loop 1/10 start
...
loop 1/10 finish
```

Các thao tác click thủ công trong browser được in ra terminal dưới dạng JSON để có thể chép vào action file. Click do runner tự gửi sẽ không bị ghi lại.

Wait dài có countdown; ngưỡng countdown và số vòng lặp được cấu hình trong `tools/hauntedroom_common.py`.

## Browser profile

Profile mặc định nằm tại `.tmp/hauntedroom-profile`. Cookies, localStorage, IndexedDB và session game được giữ lại giữa các lần chạy.

Chỉ một browser instance được dùng profile này tại cùng thời điểm. Nếu một lần chạy với `--keep-open` vẫn còn hoạt động, lần chạy tiếp theo có thể báo profile đang được sử dụng.

Xóa profile sẽ reset session và có thể làm game quay lại luồng guest/intro.

## Giới hạn hiện tại

- Chỉ hỗ trợ click theo tọa độ và wait.
- Chưa có screenshot action, template matching hoặc image recognition.
- Viewport cần được giữ cố định để tọa độ click không bị lệch.
