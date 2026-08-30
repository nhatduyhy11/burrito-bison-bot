# Colorize Audit

Audit date: 2026-08-19

## Kết quả hiện tại

Audit quét toàn bộ `tools/hauntedroom/**/*.py` bằng Python AST:

- 54 file Python.
- 149 call site `print(...)`.
- 26 call site `colorize(...)`.
- 5 màu ANSI: `GREEN`, `YELLOW`, `ORANGE`, `BLUE`, `RED`.
- 1 call site helper nhận màu động: `_print_gear_error(message, color)`.

`colorize()` chỉ thêm ANSI escape code khi stdout là TTY. Khi có biến môi trường
`NO_COLOR`, hoặc stdout không phải TTY, hàm trả về nguyên văn message. Vì vậy log
redirect vào file và output do test capture sẽ không chứa mã màu.

## Bảng màu

| Constant | ANSI | Ý nghĩa đang được dùng |
| --- | --- | --- |
| `GREEN` | `\033[32m` | Thành công, detector/auto-switch đã xác định trạng thái |
| `YELLOW` | `\033[33m` | Boss cần chú ý, đã arm pause, hoặc flow pause tại boss |
| `ORANGE` | `\033[38;5;208m` | Idle, pause thủ công, cảnh báo có thể tiếp tục/recover |
| `BLUE` | `\033[36m` | Thao tác đang chạy hoặc thông tin control |
| `RED` | `\033[31m` | Lỗi, recovery lỗi, hoặc auto-map bị dừng |

Nguồn định nghĩa duy nhất là `tools/hauntedroom/core/terminal.py`. Không có mã
ANSI hard-code nào khác trong package Haunted Room.

## Inventory theo màu

### Green — 7 call site

| Message | Nguồn | Ghi chú |
| --- | --- | --- |
| `Live screenshot saved: ...` | `core/runtime.py:202` | Chỉ `description == "Live"`; timeout/fallback screenshot vẫn plain |
| `>>> [N] win` | `flows/automap.py:441` | Win counter |
| `Pet summon is active at ...; clicking it.` | `automap_support/boss_action.py:95` | Pet summon đã match threshold |
| `Reward popup confirmed; win recorded.` | `map/reward.py` | Popup reward được xác nhận |
| `[autoswitch] screen=...; no flow started.` | `runner/standby.py:245` | Green dù không start flow |
| `[autoswitch] screen=... -> ...` | `runner/standby.py:254` | Auto-switch thành công |
| `[screen_detect] screen=...` | `screen_detect.py:142` | Green cho cả kết quả `unknown` |

### Yellow — 5 call site

| Message | Nguồn | Ghi chú |
| --- | --- | --- |
| `Final-boss pet has a full glowing bar at ...` | `automap_support/boss_action.py:70` | Pet final boss sẵn sàng |
| `Mini-boss HP entered upper search region at ...` | `automap_support/boss_flow.py:52` | Mini-boss được phát hiện; final boss dùng orange |
| `Auto-map flow paused at mini-boss/final boss.` | `automap_support/boss_flow.py:105` | Pause được kích hoạt khi boss xuất hiện |
| `Auto-map flow will pause at the next boss.` | `runner/standby.py:129` | Đã arm one-shot pause |
| `Auto-map flow will pause at the final boss.` | `runner/standby.py:139` | Đã arm final-only pause |

### Orange — 7 call site

| Message | Nguồn | Ghi chú |
| --- | --- | --- |
| `Final boss HP entered upper search region at ...` | `automap_support/boss_flow.py:52` | Final boss được phát hiện; mini-boss cùng event yellow |
| `Map completed without a detected win reward; ...` | `flows/start_auto.py:100` | Recoverable loss/pause policy |
| `Auto-map flow paused. Press Shift+...` | `runner/standby.py:116` | Pause thủ công ngay lập tức |
| `Runner is already idle.` | `runner/standby.py:152` | Stop command khi không có flow |
| `Runner idle.` sau screenshot | `runner/standby.py:161` | Runner không có flow đang chạy |
| `Runner idle.` trong banner | `runner/standby.py:212` | Orange nested trong banner green; nằm cuối banner nên reset không làm mất màu text phía sau |
| `Runner idle.` sau khi flow kết thúc | `runner/standby.py:232` | Trạng thái standby |

Ngoài 7 call site trực tiếp trên, gear recovery chọn `ORANGE` động cho message bắt
đầu bằng `Initial gear placement could not`; các gear error khác vẫn là `RED`.

### Blue — 6 call site

| Message | Nguồn | Ghi chú |
| --- | --- | --- |
| Banner `Haunted Room runner ready` | `runner/standby.py:200` | Toàn banner blue, riêng dòng idle cuối được bọc orange |
| `Initial gear is available; opening menu at ...` | `automap_support/gear_action.py:107` | Thao tác mở gear menu |
| `Dragging initial gear from ...` | `automap_support/gear_action.py:145` | Thao tác drag gear |
| `Level spin interrupt at ...; clicking ...` | `automap_support/upgrade_action.py:51` | Thao tác interrupt/click |
| `Auto-map flow resumed.` | `runner/standby.py:110` | Resume thủ công |
| `Auto-map controls:` và từng hotkey trên một dòng riêng | `runner/standby.py` | Hướng dẫn control cho flow vừa start |

### Red — 1 call site trực tiếp và 1 helper động

| Message | Nguồn | Ghi chú |
| --- | --- | --- |
| `Auto-map flow stopped; runner is idle.` | `flows/automap.py:458` | Stop được xem là trạng thái lỗi/cảnh báo mạnh, dù có chữ `idle` |
| `_print_gear_error(message, color=RED)` | `automap_support/gear_action.py:27` | Default cho lỗi mở/đóng menu, capture, anchor và deployment |

Gear helper dùng `RED` cho các nhóm message sau:

- Không mở được gear menu hoặc retry mở menu.
- Không tìm thấy door HP anchor.
- Không capture/verify/đóng được gear menu trong recovery.
- Gear menu vẫn mở sau toàn bộ recovery attempts.
- Exception trong initial gear deployment.

Ngoại lệ duy nhất hiện tại là `Initial gear placement could not be verified ...`,
được đổi sang `ORANGE` vì flow vẫn recovery và tiếp tục.

## Log plain đáng chú ý

Phần lớn 149 `print(...)` vẫn là plain text. Đây không nhất thiết là lỗi: progress,
tọa độ debug, countdown và separator không cần màu. Tuy nhiên các message sau có
semantic gần với nhóm đã có màu và nên được quyết định rõ nếu chuẩn hóa tiếp:

| Message/nhóm | Hiện tại | Điểm cần quyết định |
| --- | --- | --- |
| `Initial gear placed; ...` | Plain | Success tương tự reward/pet active đang green |
| `Boss spell is ready; ...` | Plain | Ready/action tương tự pet ready yellow hoặc active action blue |
| `Stopping current flow...` | Plain | Có thể giữ neutral vì đây mới là command, chưa phải outcome |
| `Flow failed; runner is idle: ...` | Plain | Failure nhưng không red |
| `Dev reload failed; runner remains idle: ...` | Plain | Failure nhưng không red |
| `[autoswitch] ...; no flow started.` | Green | Kết quả detect thành công nhưng outcome không start flow |
| `[screen_detect] screen=unknown` | Green | Detector chạy xong nhưng không nhận diện được screen |
| Screenshot save failure | Plain | Failure nhưng không red; success của live screenshot lại green |
| Mini-boss HP vào search region | Yellow | Final boss cùng event dùng orange |
| `Auto-map flow stopped; runner is idle.` | Red | Chữ `idle` có thể gây nhầm với các message idle orange, nhưng stop outcome có thể chủ ý là red |

Audit không đổi các message trên. Cần policy cụ thể trước khi recolor để tránh biến
mọi log thành màu và làm mất tín hiệu quan trọng.

## Policy đề xuất khi thêm log mới

1. `GREEN`: outcome thành công đã được xác nhận.
2. `YELLOW`: trạng thái sắp cần user/flow chú ý, đặc biệt boss và armed pause.
3. `ORANGE`: trạng thái recoverable, idle, hoặc pause thủ công.
4. `BLUE`: action đang thực hiện, resume, hoặc hướng dẫn control.
5. `RED`: failure không recover được, flow stop do lỗi, hoặc recovery lỗi.
6. Plain: debug telemetry, countdown, separator và routine progress không cần nhấn mạnh.
7. Không hard-code ANSI; luôn import constant và `colorize` từ `core.terminal`.
8. Message có nhiều nhánh semantic phải chọn màu theo outcome, không chỉ theo prefix,
   trừ khi prefix chính là contract ổn định như gear verification hiện tại.

## Lệnh tái audit

Liệt kê call site có màu:

```powershell
rg -n -C 3 "colorize\(" tools/hauntedroom -g "*.py"
```

Kiểm tra ANSI hard-code ngoài module terminal:

```powershell
rg -n -F -e '\033[' -e '\x1b[' tools/hauntedroom -g "*.py"
```

Chạy regression suite liên quan trực tiếp:

```powershell
python -m pytest tests/automap/test_boss_action.py tests/automap/test_boss_flow.py tests/automap/test_gear.py tests/runner/test_standby_hotkeys.py tests/runner/test_standby_orchestration.py tests/test_capture_paths.py -q
```
