# Action JSON

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
trí click hợp lệ là `center`, `top_middle`, `mid_left`, `bottom_left`. Template
nằm trong `FIXED_BLOCKER_CLICKS` (`core.template_matching`, hiện có
`overlay_newbie.png`) bị bỏ qua `click_positions` và luôn được click tại tọa
độ cố định vì màn tương ứng đóng bằng "nhấn khu vực trống".

Action JSON chủ yếu phục vụ đoạn vào/ra room. Auto-map, train, research,
artifact, EXP và hero breakthrough là flow Python riêng. Mỗi timeout sẽ lưu ảnh
vào `.tmp/hauntedroom-timeouts/`; timeout hai lần liên tiếp làm action runner
dừng, còn một loop thành công sẽ reset bộ đếm.

## Cách chạy

Action JSON được load khi bấm `Shift+5` (lazy-load theo mỗi lần chạy) hoặc qua
cờ CLI `--actions`, mặc định `tools/json_macro/macro.env.json`. Xem
[README](README.md#tùy-chọn-cli) để biết cách trỏ tới file JSON khác và danh
sách macro tham khảo trong `tools/json_macro/`.
