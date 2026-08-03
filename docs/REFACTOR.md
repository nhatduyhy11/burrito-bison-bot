# Refactor Review

## Kết luận

Structure hiện tại ổn và phù hợp với quy mô dự án, khoảng **7/10**. Dependency
direction rõ, có ADR và test kiến trúc. Chưa cần thay kiến trúc tổng thể; nên ưu
tiên refactor bên trong từng feature.

Function lớn nhất, và nhiều khả năng là function cần tìm, là
`run_automap_flow` trong `tools/hauntedroom/flows/automap.py`.

Tại thời điểm review, toàn bộ **39 test đều pass**.

## Các function đang quá lớn

| Mức ưu tiên | Function | Vị trí | Kích thước | Nhận xét |
| --- | --- | --- | ---: | --- |
| Rất cao | `run_automap_flow` | `tools/hauntedroom/flows/automap.py:245` | 258 dòng | Chứa 8 nested function, load template, giữ state, scheduling và toàn bộ handler |
| Cao | `run_actions` | `tools/hauntedroom/actions/runner.py:86` | 191 dòng | Trộn action dispatch, retry policy, timeout, logging và execution |
| Cao | `load_actions` | `tools/hauntedroom/actions/loader.py:24` | 132 dòng | Parse, validate, resolve path và mutate raw dictionary |
| Trung bình | `run_research_flow` | `tools/hauntedroom/flows/research.py:23` | 120 dòng | State machine được thể hiện bằng nhiều nested loop |
| Trung bình | `run_standby_controller` | `tools/hauntedroom_runner.py:32` | 99 dòng | Command routing và task lifecycle dính vào nhau |
| Trung bình | `clear_blockers` | `tools/hauntedroom/control_events/blockers.py:11` | 78 dòng, 11 tham số | Signature khó dùng và khó test |
| Thấp | `wait_for_template` | `tools/hauntedroom/actions/runner.py:27` | 57 dòng, 10 tham số | Logic chưa quá tệ nhưng parameter list quá dài |

## Vấn đề lớn nhất: `run_automap_flow`

`run_automap_flow` có tuple `handlers`, nhìn bên ngoài giống kiến trúc handler
modular. Tuy nhiên, toàn bộ handler là nested function và capture chung:

- `page`
- `stop_event`
- templates
- `last_map_end_check`
- `map_completed`
- `boss_actions_triggered`
- các path và config

Abstraction handler hiện tại giúp scheduling dễ đọc, nhưng chưa thật sự tách
responsibility hoặc tăng khả năng tái sử dụng. Thêm situation mới vẫn tiếp tục
làm function này lớn hơn.

Hướng refactor phù hợp là tạo `AutomapContext` dataclass chứa page, templates,
config và mutable state; sau đó chuyển từng handler thành function hoặc object
độc lập ở module level. Chưa cần framework hoặc registry phức tạp.

## Phần kiến trúc đang làm tốt

- Phân chia `core / actions / control_events / flows` tự nhiên.
- `hauntedroom_runner.py` đóng vai trò composition root đúng chỗ.
- `core` không import ngược lên feature.
- `actions` và `flows` không phụ thuộc lẫn nhau.
- [`ADR_bot.md`](ADR_bot.md) giải thích rõ ý nghĩa của `core`, tránh hiểu nhầm đây là Clean
  Architecture domain layer.
- `tests/test_hauntedroom_architecture.py` bảo vệ dependency rules.
- Test coverage hiện có tập trung khá tốt vào behavior của runner, vision,
  automap và research.

## Các điểm kiến trúc nên cải thiện

### 1. Raw `dict` là contract giữa loader và runner

`load_actions` thêm các key nội bộ như `_template_path`, `_blocker_paths`, sau đó
runner mặc định chúng tồn tại.

Hệ quả:

- Type checker gần như không giúp được.
- Loader mutate dữ liệu vừa parse.
- Lỗi schema có thể xuất hiện muộn khi execute.
- Thêm action type yêu cầu sửa cả nhánh validate và nhánh execute lớn.

Nên chuyển sang dataclass hoặc discriminated union, ví dụ:

- `ClickAction`
- `ClickTemplateAction`
- `WaitAction`
- `ClearBlockersAction`

### 2. Validation chưa hoàn chỉnh

`load_actions` chỉ kiểm tra action `wait` có `ms`, chưa chặn giá trị âm hoặc sai
kiểu. `click.x`, `click.y` và `button` cũng chỉ thực sự bị kiểm tra khi execute.

Validation nên tạo ra object đã chuẩn hóa để executor không phải tiếp tục gọi
`int()` hoặc dùng default trên raw dictionary.

### 3. Config nằm rải trong constants và parameter dài

`run_automap_flow` có 10 tham số, `clear_blockers` có 11 tham số và
`wait_for_template` có 10 tham số.

Có thể gom thành các config object nhỏ:

- `AutomapConfig`
- `TemplateWaitConfig`
- `BlockerConfig`

### 4. Flow coupling trực tiếp với infrastructure

Các flow gọi thẳng Playwright page, OpenCV và `print`. Với tool local nhỏ thì
đây là trade-off chấp nhận được. Nếu cần simulator, replay screenshot hoặc
integration test tốt hơn, có thể thêm abstraction mỏng như `GameRuntime` cho:

- capture
- click
- wait
- log

Chưa nên dựng Clean Architecture đầy đủ cho quy mô hiện tại.

### 5. Test file quá lớn

Đã xử lý. File monolith `tests/test_hauntedroom_runner.py` được thay bằng các
package theo feature: `actions/`, `automap/`, `control_events/`, `hero_select/`,
`research/` và `runner/`. Nhóm auto-map tiếp tục được chia theo boss, build,
level-up, map-end và orchestration chung.

### 6. Packaging vẫn mang tính script

`pyproject.toml` đặt `package = false`, còn test tự thêm `tools` vào `sys.path`.
Điều này ổn nếu đây chỉ là bot local. Nếu sắp có nhiều entrypoint hoặc CI/deploy,
nên đóng package và khai báo console script.

### 7. `ref_cv/` có thể gây nhiễu tooling

README đã nói đây là code tham khảo độc lập, nhưng project con này có
`pyproject.toml`, test và lock file riêng trong repo chính. Tooling hoặc test
discovery có thể hiểu nhầm scope. Có thể giữ nguyên nếu intentional, hoặc chuyển
sang `archive/` hay repo riêng.

## Các finding cụ thể

### README và code không đồng nhất

README nói default `delay_ms` là `500`, nhưng code đang dùng `400` tại
`tools/hauntedroom/actions/runner.py:23`.

### Run mode bị điều khiển bằng source constant

`ACTION_LOOP_COUNT` nằm trong `tools/hauntedroom/core/runtime.py`, nhưng lại quyết
định chế độ chạy ở entrypoint. Nên chuyển thành CLI/config thay vì phải sửa source
để đổi mode.

### Timeout của blocker cần được làm rõ về semantics

`clear_blockers` reset deadline sau mỗi lần click blocker. Vì vậy `timeout_ms`
hiện giống inactivity timeout hơn là giới hạn tổng thời gian của action. Behavior
này có thể đúng chủ ý, nhưng nên đặt tên hoặc document rõ.

## Thứ tự refactor đề xuất

1. Tách `run_automap_flow` bằng `AutomapContext` và các handler độc lập.
2. Chuyển action dictionary thành typed dataclass và chia `run_actions` thành
   executor theo từng action type.
3. Biến research flow thành state machine nhỏ, hoặc ít nhất tách phase
   `available` và `active`.
4. Tách command routing khỏi task lifecycle trong standby controller.
5. Chia test file theo feature.
6. Sửa drift giữa README và config thực tế.

## Nguyên tắc khi refactor

- Giữ nguyên dependency rule đã ghi trong [`ADR_bot.md`](ADR_bot.md).
- Refactor theo behavior hiện tại và giữ test xanh sau từng bước.
- Không tạo registry hoặc abstraction tổng quát khi mới chỉ có một consumer.
- Ưu tiên typed boundary và state rõ ràng hơn là chỉ chuyển code sang nhiều file.
- Mỗi bước nên đủ nhỏ để review và rollback độc lập.
